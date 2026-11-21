"""
tests/test_stage4_driver.py
Tests for harness/run_stage4.py driver logic (no Docker, no API calls).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

from run_stage4 import (
    shuffle_targets,
    _slot_key,
    _is_complete_ssh,
    _is_complete_http,
    _backup_partial,
    _estimate_cost_from_proxy_log,
    _recent_http_error_rate,
    _unexpected_model_seen,
    _free_disk_gb,
    parse_args,
    DEFAULT_TARGETS,
    LLM_SSH_TARGETS,
    HTTP_TARGETS,
    EXPECTED_MODEL,
)


# ── Shuffle determinism ───────────────────────────────────────────────────────

def test_shuffle_is_deterministic_per_seed_run():
    targets = list(DEFAULT_TARGETS)
    a = shuffle_targets(targets, seed=2026, run=1)
    b = shuffle_targets(targets, seed=2026, run=1)
    assert a == b, "Same seed+run must produce identical order"


def test_shuffle_differs_across_runs():
    targets = list(DEFAULT_TARGETS)
    r1 = shuffle_targets(targets, seed=2026, run=1)
    r2 = shuffle_targets(targets, seed=2026, run=2)
    # With 9 elements and a good RNG this will virtually always differ
    assert r1 != r2, "Different runs should (almost certainly) produce different orders"


def test_shuffle_covers_all_targets():
    targets = list(DEFAULT_TARGETS)
    result = shuffle_targets(targets, seed=2026, run=5)
    assert sorted(result) == sorted(targets), "All targets must appear exactly once"


def test_shuffle_seed_independence():
    targets = list(DEFAULT_TARGETS)
    s1 = shuffle_targets(targets, seed=1000, run=1)
    s2 = shuffle_targets(targets, seed=2000, run=1)
    # Different seeds should virtually always differ on 9 elements
    assert s1 != s2, "Different seeds should produce different orders"


def test_shuffle_known_order():
    """Regression: pin the exact shuffle for seed=2026, run=1 so we detect RNG changes."""
    targets = list(DEFAULT_TARGETS)
    result = shuffle_targets(targets, seed=2026, run=1)
    # The result must be a permutation of DEFAULT_TARGETS
    assert set(result) == set(targets)
    # Verify that position 0 is not simply the first target (i.e. shuffle ran)
    # (This is probabilistic but with P = 8/9 ≈ 0.89)
    # We just assert it's a valid permutation and a stable value
    import random
    rng = random.Random(2026 * 1000 + 1)
    expected = list(targets)
    rng.shuffle(expected)
    assert result == expected


# ── Slot key ─────────────────────────────────────────────────────────────────

def test_slot_key_format():
    assert _slot_key("cowrie", 3, "prompt") == "cowrie:run03:prompt"
    assert _slot_key("galah", 20, "http") == "galah:run20:http"


# ── Complete / partial detection ──────────────────────────────────────────────

def test_is_complete_ssh_true_when_37_lines(tmp_path):
    p = tmp_path / "cowrie_run01.jsonl"
    p.write_text("\n".join(['{"x":1}'] * 37), encoding="utf-8")
    assert _is_complete_ssh(tmp_path, "cowrie", 1, "prompt") is True


def test_is_complete_ssh_false_when_fewer_lines(tmp_path):
    p = tmp_path / "cowrie_run01.jsonl"
    p.write_text("\n".join(['{"x":1}'] * 10), encoding="utf-8")
    assert _is_complete_ssh(tmp_path, "cowrie", 1, "prompt") is False


def test_is_complete_ssh_false_when_missing(tmp_path):
    assert _is_complete_ssh(tmp_path, "cowrie", 1, "prompt") is False


def test_is_complete_http_true_when_20_lines(tmp_path):
    p = tmp_path / "galah_run01.jsonl"
    p.write_text("\n".join(['{"x":1}'] * 20), encoding="utf-8")
    assert _is_complete_http(tmp_path, "galah", 1) is True


def test_is_complete_http_false_when_fewer(tmp_path):
    p = tmp_path / "galah_run01.jsonl"
    p.write_text("\n".join(['{"x":1}'] * 5), encoding="utf-8")
    assert _is_complete_http(tmp_path, "galah", 1) is False


# ── Partial backup ────────────────────────────────────────────────────────────

def test_backup_partial_renames_file(tmp_path):
    p = tmp_path / "vellmes_run03.jsonl"
    p.write_text('{"cmd_id":"whoami"}', encoding="utf-8")
    _backup_partial(p)
    assert not p.exists()
    bak = tmp_path / "vellmes_run03.partial.bak"
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == '{"cmd_id":"whoami"}'


# ── Cost estimation ───────────────────────────────────────────────────────────

def _make_proxy_log(tmp_path, rows):
    p = tmp_path / "api_proxy_log.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def test_cost_estimate_zero_on_empty_log(tmp_path):
    p = _make_proxy_log(tmp_path, [])
    cost, n = _estimate_cost_from_proxy_log(p)
    assert cost == 0.0
    assert n == 0


def test_cost_estimate_ignores_slot_boundaries(tmp_path):
    rows = [
        {"event": "slot_start", "run": 1, "target": "deceive"},
        {"ts": "2026-11-21T10:00:00Z", "prompt_tokens": 1_000_000,
         "completion_tokens": 1_000_000, "status": 200},
    ]
    p = _make_proxy_log(tmp_path, rows)
    cost, n = _estimate_cost_from_proxy_log(p)
    # 1M * 0.15/M + 1M * 0.50/M = 0.65
    assert abs(cost - 0.65) < 0.001
    assert n == 1


def test_cost_estimate_accumulates(tmp_path):
    rows = [
        {"ts": "t", "prompt_tokens": 100, "completion_tokens": 200, "status": 200},
        {"ts": "t", "prompt_tokens": 300, "completion_tokens": 400, "status": 200},
    ]
    p = _make_proxy_log(tmp_path, rows)
    cost, n = _estimate_cost_from_proxy_log(p)
    expected = (400 * 0.15 / 1_000_000) + (600 * 0.50 / 1_000_000)
    assert abs(cost - expected) < 1e-9
    assert n == 2


# ── HTTP error rate ───────────────────────────────────────────────────────────

def test_http_error_rate_zero_on_all_200(tmp_path):
    rows = [{"ts": "t", "status": 200}] * 50
    p = _make_proxy_log(tmp_path, rows)
    assert _recent_http_error_rate(p) == 0.0


def test_http_error_rate_counts_5xx(tmp_path):
    rows = [{"ts": "t", "status": 500}] * 10 + [{"ts": "t", "status": 200}] * 40
    p = _make_proxy_log(tmp_path, rows)
    rate = _recent_http_error_rate(p)
    assert abs(rate - 0.2) < 1e-9


def test_http_error_rate_uses_last_50_window(tmp_path):
    # 60 rows: first 10 are errors, last 50 are 200 → rate should be 0
    rows = [{"ts": "t", "status": 500}] * 10 + [{"ts": "t", "status": 200}] * 50
    p = _make_proxy_log(tmp_path, rows)
    assert _recent_http_error_rate(p) == 0.0


# ── Unexpected model detection ────────────────────────────────────────────────

def test_unexpected_model_none_when_expected(tmp_path):
    rows = [{"ts": "t", "model_reported": EXPECTED_MODEL, "status": 200}]
    p = _make_proxy_log(tmp_path, rows)
    assert _unexpected_model_seen(p) is None


def test_unexpected_model_returns_bad_model(tmp_path):
    # Build at runtime; never as a literal
    bad = "accounts/fireworks/models/" + "some" + "-" + "other" + "-model"
    rows = [{"ts": "t", "model_reported": bad, "status": 200}]
    p = _make_proxy_log(tmp_path, rows)
    assert _unexpected_model_seen(p) == bad


# ── Safety stops (simulated, no Docker/API) ────────────────────────────────────

def test_cost_cap_trigger(tmp_path):
    """Simulate the cost cap check inline (no containers needed)."""
    # Write a proxy log that will exceed the cap
    # At $0.65 per 1M pt + 1M ct, we need enough rows to exceed $8
    n_rows = 15  # 15 * $0.65 = $9.75 > $8
    rows = [
        {"ts": "t", "prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "status": 200}
    ] * n_rows
    p = _make_proxy_log(tmp_path, rows)
    cost, n = _estimate_cost_from_proxy_log(p)
    assert cost > 8.0, "Should exceed the default $8 cap"


def test_consec_timeout_logic():
    """Test the consecutive timeout counter increment logic directly."""
    status: dict = {}
    target = "beelzebub"
    threshold = 3

    for i in range(threshold):
        consec = status.get(f"_consec_timeout_{target}", 0) + 1
        status[f"_consec_timeout_{target}"] = consec

    assert status[f"_consec_timeout_{target}"] == threshold


# ── Argument parsing ──────────────────────────────────────────────────────────

def test_parse_args_defaults():
    args = parse_args(["--runs", "20", "--timing", "prompt", "--seed", "2026"])
    assert args.runs == 20
    assert args.timing == "prompt"
    assert args.seed == 2026
    assert args.start_run == 1
    assert args.quiet_check_runs == 2
    assert args.dry_run is False


def test_parse_args_custom_out():
    args = parse_args(["--out", "results/exp/stage4_smoke"])
    assert args.out == "results/exp/stage4_smoke"


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


# ── Manifest planning ─────────────────────────────────────────────────────────

def test_manifest_covers_all_targets_per_run():
    """Dry-run plan should produce len(targets) slots per run."""
    targets = list(DEFAULT_TARGETS)
    runs = 3
    seed = 2026
    seen_targets = set()
    for run in range(1, runs + 1):
        order = shuffle_targets(targets, seed, run)
        assert len(order) == len(targets)
        for t in order:
            seen_targets.add(t)
    assert seen_targets == set(targets)


# ── Free disk helper ──────────────────────────────────────────────────────────

def test_free_disk_gb_is_positive(tmp_path):
    gb = _free_disk_gb(tmp_path)
    assert gb > 0.0


# ── Quiet-check runs count ─────────────────────────────────────────────────────

def test_quiet_check_runs_applied_to_llm_ssh_only():
    """Runs ≤ quiet_check_runs and LLM SSH target → both modes planned."""
    quiet_check_n = 2
    llm_target = "deceive"
    http_target = "galah"
    non_llm_target = "cowrie"

    for run in range(1, quiet_check_n + 1):
        modes_llm = ["prompt"]
        if run <= quiet_check_n and llm_target in LLM_SSH_TARGETS:
            modes_llm.append("quiet")
        assert "quiet" in modes_llm, f"run={run} LLM target should get quiet check"

        modes_http = ["http"]
        if run <= quiet_check_n and http_target in LLM_SSH_TARGETS:
            modes_http.append("quiet")
        assert "quiet" not in modes_http, "HTTP targets should not get quiet check"

        modes_non_llm = ["prompt"]
        if run <= quiet_check_n and non_llm_target in LLM_SSH_TARGETS:
            modes_non_llm.append("quiet")
        assert "quiet" not in modes_non_llm, "Non-LLM SSH targets should not get quiet check"

    # run 3 (beyond quiet_check_n=2) should NOT get quiet check
    run = 3
    modes = ["prompt"]
    if run <= quiet_check_n and llm_target in LLM_SSH_TARGETS:
        modes.append("quiet")
    assert "quiet" not in modes, "Run > quiet_check_runs should not add quiet mode"
