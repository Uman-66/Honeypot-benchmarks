"""Unit tests for harness/run_lifetime_control.py (no Docker, no API)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

spec = importlib.util.spec_from_file_location(
    "run_lifetime_control", ROOT / "harness" / "run_lifetime_control.py")
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)


def _rows(n_timeout=0, lat=2.0, big=False, leak=False):
    rows = []
    for i in range(36):
        rows.append({
            "cmd_id": f"cmd{i:02d}",
            "latency_s": lat,
            "timed_out": i < n_timeout,
            "cleaned_output": ("guest@ubuntu:~$ ls\r\n" if leak else "x" * (20001 if big else 10)),
        })
    rows.append({"cmd_id": "exit", "latency_s": 1.0, "timed_out": False,
                 "cleaned_output": ""})
    return rows


def test_parse_inspect_state():
    out = "sha256:abc123 2026-11-22T07:44:20.123456789Z\n"
    assert lc.parse_inspect_id(out) == "sha256:abc123"
    assert lc.parse_started_at(out) == "2026-11-22T07:44:20.123456789Z"


def test_parse_inspect_empty():
    assert lc.parse_inspect_id("") == ""
    assert lc.parse_started_at("") == ""


def test_parse_stats_mem():
    assert lc.parse_stats_mem("12.34MiB / 1GiB\n") == "12.34MiB / 1GiB"
    assert lc.parse_stats_mem("") == ""


def test_row_metrics_basic():
    m = lc.row_metrics(_rows(n_timeout=3))
    assert m["n_commands"] == 36          # 'exit' excluded
    assert m["timeouts"] == 3
    assert m["median_latency_s"] == 2.0
    assert m["oversized"] == 0
    assert m["leakage"] == 0


def test_row_metrics_oversized_and_leakage():
    assert lc.row_metrics(_rows(big=True))["oversized"] == 36
    assert lc.row_metrics(_rows(leak=True))["leakage"] == 36
    assert lc.row_metrics(_rows(leak=True))["oversized"] == 0


def test_row_metrics_ignores_timeouts_for_latency():
    rows = _rows()
    rows[0]["timed_out"] = True
    rows[0]["latency_s"] = 120.0
    m = lc.row_metrics(rows)
    assert m["timeouts"] == 1
    assert m["median_latency_s"] == 2.0   # censored row excluded


def test_row_metrics_empty():
    m = lc.row_metrics([])
    assert m["n_commands"] == 0
    assert m["median_latency_s"] is None


def test_guard_message():
    assert lc.guard_message(45, 45) is None
    assert lc.guard_message(46, 45) == "slot_call_anomaly: beelzebub 46 calls"


def test_container_unchanged():
    a = {"id": "sha256:abc", "started_at": "T1"}
    assert lc.container_unchanged(a, dict(a))
    assert not lc.container_unchanged(a, {"id": "sha256:def", "started_at": "T1"})
    assert not lc.container_unchanged(a, {"id": "sha256:abc", "started_at": "T2"})
    assert not lc.container_unchanged({"id": "", "started_at": ""}, a)


def test_percentile():
    assert lc.s4_percentile([1.0, 2.0, 3.0], 50) == 2.0
    assert lc.s4_percentile([1.0, 2.0, 3.0], 100) == 3.0


def test_dry_run_does_not_touch_docker(tmp_path, capsys):
    rc = lc.run(["--runs", "3", "--out", str(tmp_path / "x"), "--dry-run"])
    assert rc == 0
    assert "3 sessions" in capsys.readouterr().out
    assert not (tmp_path / "x").exists()
