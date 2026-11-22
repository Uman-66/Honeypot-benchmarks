"""
tests/test_stage4_fixes.py
Regressions for the two Stage 4 driver bugs (run multiplier, cached-token cost)
and for the per-slot call-count sanity guard.

No Docker and no API calls: the runners are driven through their own main()
with the network layer monkeypatched, and the cost/guard helpers are fed
synthetic proxy logs.
"""
import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

import run_stage4 as s4
import run_ssh
import run_http

TARGETS_YAML = str(ROOT / "harness" / "targets.yaml")
COMMANDS_YAML = str(ROOT / "harness" / "commands.yaml")
REQUESTS_YAML = str(ROOT / "harness" / "http_requests.yaml")


def _write_log(tmp_path, rows):
    p = tmp_path / "api_proxy_log.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


# ── Bug 1: one slot must execute the command list exactly once ───────────────

def test_ssh_slot_passes_runs_one_with_run_index(monkeypatch, tmp_path):
    """Run 5 must invoke run_ssh.main once with --runs 1 --run-index 5."""
    calls = []

    def fake_main(argv):
        calls.append(list(argv))
        out = Path(argv[argv.index("--out") + 1])
        idx = int(argv[argv.index("--run-index") + 1])
        out.mkdir(parents=True, exist_ok=True)
        rows = [{"cmd_id": f"c{i}"} for i in range(36)] + [{"cmd_id": "exit"}]
        (out / f"vellmes_run{idx:02d}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return 0

    monkeypatch.setattr(s4.run_ssh, "main", fake_main)
    result = s4._run_ssh_slot(
        {"name": "vellmes"}, 5, tmp_path, "prompt", 2026, 1, "abc1234",
        120.0, TARGETS_YAML, COMMANDS_YAML, logging.getLogger("test"))

    assert len(calls) == 1, "one slot must call the runner exactly once"
    argv = calls[0]
    assert argv[argv.index("--runs") + 1] == "1"
    assert argv[argv.index("--run-index") + 1] == "5"
    path = tmp_path / "vellmes_run05.jsonl"
    assert path.exists()
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 37, "36 commands + exit"
    assert all(row["s4_run"] == 5 for row in lines)
    assert result["n_commands"] == 36 and result["rc"] == 0


def test_http_slot_passes_runs_one_with_run_index(monkeypatch, tmp_path):
    calls = []

    def fake_main(argv):
        calls.append(list(argv))
        out = Path(argv[argv.index("--out") + 1])
        idx = int(argv[argv.index("--run-index") + 1])
        out.mkdir(parents=True, exist_ok=True)
        rows = [{"id": f"r{i}"} for i in range(20)]
        (out / f"galah_run{idx:02d}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return 0

    monkeypatch.setattr(s4.run_http, "main", fake_main)
    result = s4._run_http_slot(
        {"name": "galah"}, 5, tmp_path, 2026, 1, "abc1234", 30.0,
        TARGETS_YAML, REQUESTS_YAML, logging.getLogger("test"))

    assert len(calls) == 1
    argv = calls[0]
    assert argv[argv.index("--runs") + 1] == "1"
    assert argv[argv.index("--run-index") + 1] == "5"
    path = tmp_path / "galah_run05.jsonl"
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 20
    assert result["n_commands"] == 20


def _fake_run_once(target, commands, run_index, timeout, **_kw):
    results = [
        {"cmd_id": c["id"], "run": run_index, "text": c["text"],
         "timed_out": False, "cleaned_output": ""}
        for c in commands
    ]
    return results, {"run": run_index}, {"auth_method_used": "none"}


def _run_ssh_on_fixture(tmp_path, extra_argv):
    out = tmp_path / "raw"
    argv = [
        "--targets", TARGETS_YAML,
        "--commands", COMMANDS_YAML,
        "--target", "cowrie",
        "--out", str(out),
        "--csv-dir", str(tmp_path),
    ] + extra_argv
    assert run_ssh.main(argv) == 0
    return out


def test_run_ssh_run_index_names_and_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(run_ssh, "_run_once", _fake_run_once)
    out = _run_ssh_on_fixture(tmp_path, ["--runs", "1", "--run-index", "5"])
    path = out / "cowrie_run05.jsonl"
    assert path.exists()
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 37
    assert {r["run"] for r in rows} == {5}
    csv_rows = (tmp_path / "ssh_commands_long.csv").read_text(encoding="utf-8")
    assert ",5," in csv_rows


def test_run_ssh_without_run_index_is_unchanged(tmp_path, monkeypatch):
    """Default path still writes run01..runNN and labels rows 1..N."""
    monkeypatch.setattr(run_ssh, "_run_once", _fake_run_once)
    out = _run_ssh_on_fixture(tmp_path, ["--runs", "2"])
    for idx in (1, 2):
        path = out / f"cowrie_run{idx:02d}.jsonl"
        assert path.exists()
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
        assert {r["run"] for r in rows} == {idx}
    assert run_ssh.parse_args(["--runs", "2"]).run_index is None
    assert run_ssh._run_labels(run_ssh.parse_args(["--runs", "2"])) == [1, 2]


def test_run_index_1_and_plain_run_1_produce_identical_files(tmp_path, monkeypatch):
    """--run-index only relabels; a run-1 file must be byte-identical."""
    monkeypatch.setattr(run_ssh, "_run_once", _fake_run_once)
    plain = _run_ssh_on_fixture(tmp_path / "plain", ["--runs", "1"])
    labelled = _run_ssh_on_fixture(tmp_path / "labelled",
                                  ["--runs", "1", "--run-index", "1"])
    assert (plain / "cowrie_run01.jsonl").read_bytes() == \
        (labelled / "cowrie_run01.jsonl").read_bytes()


def test_run_http_run_index_names_and_rows(tmp_path, monkeypatch):
    def fake_request(host, port, req, timeout):
        return {"id": req["id"], "status": 200}

    monkeypatch.setattr(run_http, "_do_request", fake_request)
    out = tmp_path / "raw_http"
    argv = [
        "--targets", TARGETS_YAML,
        "--requests", REQUESTS_YAML,
        "--target", "groundtruth_http",
        "--out", str(out),
        "--csv-dir", str(tmp_path),
        "--runs", "1", "--run-index", "5",
    ]
    assert run_http.main(argv) == 0
    path = out / "groundtruth_http_run05.jsonl"
    assert path.exists()
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 20
    assert {r["run"] for r in rows} == {5}


def test_run_index_requires_runs_one():
    with pytest.raises(SystemExit):
        run_ssh.parse_args(["--runs", "3", "--run-index", "5"])
    with pytest.raises(SystemExit):
        run_http._parse_args(["--runs", "3", "--run-index", "5"])


# ── Bug 2: cached prompt tokens are billed at the cache rate ─────────────────

def test_cost_bills_cached_prompt_tokens_at_cache_rate(tmp_path):
    p = _write_log(tmp_path, [{
        "status": 200, "prompt_tokens": 1_000_000, "completion_tokens": 0,
        "usage": {"prompt_tokens_details": {"cached_tokens": 1_000_000}},
    }])
    cost, n = s4._estimate_cost_from_proxy_log(p)
    assert n == 1
    assert cost == pytest.approx(0.03, abs=1e-9)


def test_cost_without_cached_breakdown_bills_full_prompt(tmp_path):
    """Conservative: no usage/cached_tokens -> whole prompt at $0.15/M."""
    p = _write_log(tmp_path, [
        {"status": 200, "prompt_tokens": 1_000_000, "completion_tokens": 0},
        {"status": 200, "prompt_tokens": 1_000_000, "completion_tokens": 0,
         "usage": {"prompt_tokens_details": {}}},
    ])
    cost, n = s4._estimate_cost_from_proxy_log(p)
    assert n == 2
    assert cost == pytest.approx(0.30, abs=1e-9)


def test_cost_reproduces_first_stage4_batch(tmp_path):
    """48,801,496 prompt (46,645,388 cached) + 2,043,147 completion ~= $2.75."""
    prompt, cached, completion = 48_801_496, 46_645_388, 2_043_147
    uncached = prompt - cached
    p = _write_log(tmp_path, [
        {"status": 200, "prompt_tokens": uncached, "completion_tokens": 0},
        {"status": 200, "prompt_tokens": cached, "completion_tokens": 0,
         "usage": {"prompt_tokens_details": {"cached_tokens": cached}}},
        {"status": 200, "prompt_tokens": 0, "completion_tokens": completion},
    ])
    cost, n = s4._estimate_cost_from_proxy_log(p)
    assert n == 3
    assert cost == pytest.approx(2.7444, abs=0.01)
    assert cost < 3.0, "list-price billing would report ~$8.34"


def test_default_cost_cap_is_six_dollars():
    assert s4.SAFETY_COST_CAP_DEFAULT == 6.0
    assert s4.parse_args([]).cost_cap == 6.0


# ── Per-slot call sanity guard ───────────────────────────────────────────────

def test_slot_call_anomaly_predicate():
    assert s4._slot_call_anomaly_message("vellmes", 38) is None
    assert s4._slot_call_anomaly_message("vellmes", 76) is None   # prompt+quiet
    msg = s4._slot_call_anomaly_message("vellmes", 114)
    assert msg == "slot_call_anomaly: vellmes 114 calls"
    assert s4._slot_call_anomaly_message("galah", 45) is None
    assert s4._slot_call_anomaly_message("galah", 46) == \
        "slot_call_anomaly: galah 46 calls"
    # Targets that never call the model are not guarded.
    assert s4._slot_call_anomaly_message("cowrie", 1000) is None
    assert s4._slot_call_anomaly_message("groundtruth_ssh", 1000) is None


def test_slot_call_count_uses_only_the_current_slot(tmp_path):
    rows = [{"event": "slot_start", "run": 1, "target": "vellmes"}]
    rows += [{"status": 200, "prompt_tokens": 10}] * 38
    rows += [{"event": "slot_start", "run": 2, "target": "vellmes"}]
    rows += [{"status": 200, "prompt_tokens": 10}] * 3
    p = _write_log(tmp_path, rows)
    assert s4._proxy_request_count(p) == 41
    # calls made in the second slot only
    assert s4._proxy_request_count(p) - 38 == 3


def test_guard_would_have_caught_run_two(tmp_path):
    """Run 2 replayed the list twice: 152 calls in one prompt+quiet slot."""
    p = _write_log(tmp_path, [{"event": "slot_start"}] + [{"status": 200}] * 152)
    n = s4._proxy_request_count(p)
    msg = s4._slot_call_anomaly_message("beelzebub", n)
    assert msg is not None and "152" in msg
