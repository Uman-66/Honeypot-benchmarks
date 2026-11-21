"""
tests/test_stage4_safety.py
Console-safety, per-mode slot layout and safety-stop tests for Stage 4.

No Docker and no API calls: every stop is exercised through the pure predicate
or through a synthetic proxy log / closed local port.
"""
import io
import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

import run_stage4 as s4


# ── Console encoding safety ───────────────────────────────────────────────────

class _Cp1252Stream(io.TextIOWrapper):
    """A stdout look-alike that raises UnicodeEncodeError on '≈' / '—'."""

    def __init__(self):
        self._buf = io.BytesIO()
        super().__init__(self._buf, encoding="cp1252", errors="strict", newline="")


def test_safe_print_survives_cp1252_stdout(monkeypatch):
    stream = _Cp1252Stream()
    monkeypatch.setattr(sys, "stdout", stream)
    # Would raise UnicodeEncodeError through plain print()
    s4._safe_print("ETA\u2248 1:02:03  \u2014 done", flush=True)
    stream.flush()
    text = stream.buffer.getvalue().decode("cp1252")
    assert "ETA" in text and "done" in text
    assert "?" in text  # unrepresentable characters replaced, not fatal


def test_safe_print_never_raises_on_broken_stream(monkeypatch):
    class _Broken:
        encoding = "ascii"

        def write(self, _):
            raise UnicodeEncodeError("ascii", "", 0, 1, "boom")

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", _Broken())
    s4._safe_print("\u2248", flush=True)  # must not raise


def test_module_prints_are_ascii_only():
    """No print/_safe_print/log call may carry a non-ASCII character."""
    bad = []
    for name in ("run_stage4.py", "analyze_stage4.py"):
        path = ROOT / "harness" / name
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if not (stripped.startswith("print(") or stripped.startswith("_safe_print(")
                    or stripped.startswith("log.")):
                continue
            if any(ord(ch) > 127 for ch in line):
                bad.append(f"{name}:{i}: {line.strip()[:80]}")
    assert not bad, "non-ASCII in console output: " + "; ".join(bad)


def test_reconfigure_stdio_is_safe():
    s4._reconfigure_stdio()  # must not raise, even under pytest capture


# ── Per-mode slot layout (quiet rows must not share the prompt file) ─────────

def test_quiet_rows_get_their_own_directory(tmp_path):
    prompt_dir = s4._mode_output_dir(tmp_path, "vellmes", "prompt")
    quiet_dir = s4._mode_output_dir(tmp_path, "vellmes", "quiet")
    http_dir = s4._mode_output_dir(tmp_path, "galah", "http")
    assert prompt_dir.name == "raw"
    assert quiet_dir.name == s4.QUIET_SUBDIR
    assert http_dir.name == "raw_http"
    assert s4._mode_jsonl_path(prompt_dir, "vellmes", 1) != \
        s4._mode_jsonl_path(quiet_dir, "vellmes", 1)


def test_completeness_is_per_mode(tmp_path):
    prompt_dir = s4._mode_output_dir(tmp_path, "advshellm", "prompt")
    quiet_dir = s4._mode_output_dir(tmp_path, "advshellm", "quiet")
    prompt_dir.mkdir(parents=True)
    quiet_dir.mkdir(parents=True)
    (prompt_dir / "advshellm_run01.jsonl").write_text(
        "\n".join(['{"x":1}'] * 37), encoding="utf-8")

    assert s4._is_complete_ssh(prompt_dir, "advshellm", 1, "prompt") is True
    assert s4._is_complete_ssh(quiet_dir, "advshellm", 1, "quiet") is False


def test_status_keys_are_per_mode():
    assert s4._slot_key("vellmes", 1, "prompt") == "vellmes:run01:prompt"
    assert s4._slot_key("vellmes", 1, "quiet") == "vellmes:run01:quiet"
    assert s4._slot_key("vellmes", 1, "prompt") != s4._slot_key("vellmes", 1, "quiet")


# ── Safety stop 1: proxy unreachable ─────────────────────────────────────────

def _closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_proxy_unreachable_detected():
    assert s4._proxy_reachable(_closed_port()) is False


# ── Safety stop 2: Fireworks error rate > 20% over last 50 ───────────────────

def _proxy_log(tmp_path, rows):
    p = tmp_path / "api_proxy_log.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def test_error_rate_above_threshold_stops(tmp_path):
    rows = [{"status": 500}] * 11 + [{"status": 200}] * 39   # 22%
    p = _proxy_log(tmp_path, rows)
    rate = s4._recent_http_error_rate(p)
    assert rate > s4.SAFETY_HTTP_ERR_RATE
    assert "high_fireworks_error_rate" in s4._error_rate_stop_message(rate)


def test_error_rate_at_threshold_does_not_stop(tmp_path):
    rows = [{"status": 500}] * 10 + [{"status": 200}] * 40   # exactly 20%
    p = _proxy_log(tmp_path, rows)
    rate = s4._recent_http_error_rate(p)
    assert s4._error_rate_stop_message(rate) is None


# ── Safety stop 3: 3 consecutive LLM slots above 50% timeouts ────────────────

def test_three_consecutive_timeout_slots_stop():
    status: dict = {}
    assert s4._consec_timeout_stop(status, "deceive", 36, 20) is None
    assert s4._consec_timeout_stop(status, "deceive", 36, 30) is None
    msg = s4._consec_timeout_stop(status, "deceive", 36, 25)
    assert msg is not None and "consec_timeout_stop" in msg
    assert status["_consec_timeout_deceive"] == 3


def test_consec_timeout_counter_resets_on_good_slot():
    status: dict = {"_consec_timeout_vellmes": 2}
    assert s4._consec_timeout_stop(status, "vellmes", 36, 2) is None
    assert status["_consec_timeout_vellmes"] == 0


def test_consec_timeout_ignores_non_llm_targets():
    status: dict = {}
    for _ in range(5):
        assert s4._consec_timeout_stop(status, "cowrie", 36, 36) is None


# ── Safety stop 4: free disk below 5 GB ──────────────────────────────────────

def test_disk_stop_below_threshold():
    msg = s4._disk_stop_message(4.99)
    assert msg is not None and "disk_too_low" in msg


def test_disk_ok_above_threshold():
    assert s4._disk_stop_message(5.0) is None
    assert s4._disk_stop_message(80.0) is None


# ── Safety stop 5: cost cap ──────────────────────────────────────────────────

def test_cost_cap_stop():
    msg = s4._cost_stop_message(8.01, 8.0, 1200)
    assert msg is not None and "cost_cap_exceeded" in msg


def test_cost_cap_not_reached():
    assert s4._cost_stop_message(0.31, 8.0, 216) is None


def test_cost_cap_from_synthetic_proxy_log(tmp_path):
    rows = [{"status": 200, "prompt_tokens": 1_000_000,
             "completion_tokens": 1_000_000}] * 13   # 13 * $0.65 = $8.45
    p = _proxy_log(tmp_path, rows)
    cost, n = s4._estimate_cost_from_proxy_log(p)
    assert n == 13 and cost > 8.0
    assert s4._cost_stop_message(cost, 8.0, n) is not None


# ── Safety stop 6: unexpected model string ───────────────────────────────────

def test_unexpected_model_stop(tmp_path):
    bad = "accounts/fireworks/models/" + "not" + "-" + "glm"
    p = _proxy_log(tmp_path, [{"status": 200, "model_reported": bad}])
    seen = s4._unexpected_model_seen(p)
    assert seen == bad
    msg = s4._model_stop_message(seen)
    assert msg is not None and "unexpected_model" in msg


def test_expected_model_does_not_stop(tmp_path):
    p = _proxy_log(tmp_path, [{"status": 200, "model_reported": s4.EXPECTED_MODEL}])
    assert s4._model_stop_message(s4._unexpected_model_seen(p)) is None


# ── Stop reason is written to status.json ────────────────────────────────────

def test_stop_message_persists_reason(tmp_path):
    status_path = tmp_path / "status.json"
    status = {"cowrie:run01:prompt": "complete"}
    msg = s4._cost_stop_message(1.0, 0.5, 3)
    status["safety_stop"] = msg
    s4._write_json_atomic(status_path, status)
    reloaded = json.loads(status_path.read_text(encoding="utf-8"))
    assert reloaded["safety_stop"] == msg
    assert reloaded["cowrie:run01:prompt"] == "complete"
