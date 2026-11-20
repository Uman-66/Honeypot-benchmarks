"""Tests for the prompt-detect timing mode in harness/run_ssh.py.

Includes the regression that motivated the drain + settle rule: a prompt left
over from the previous command used to end the next read before the command had
run, producing a ~0 ms latency that measured nothing.
"""

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

import run_ssh  # noqa: E402


class FakeChannel:
    """Minimal stand-in for a paramiko Channel with queued recv() chunks."""

    def __init__(self, chunks):
        self.chunks = list(chunks)

    def settimeout(self, _value):
        return None

    def recv(self, _size):
        if self.chunks:
            return self.chunks.pop(0)
        return b""

    def recv_ready(self):
        return bool(self.chunks)


PROMPT = "root@srv-ubuntu:/tmp# "
PROMPT_CHUNK = b"echo x\r\nx\r\n" + PROMPT.encode()
STALE_PROMPT = PROMPT.encode()


# ── The regression ────────────────────────────────────────────────────────────

def test_stale_prompt_alone_is_flagged_as_a_prompt_without_output():
    """Reproduces the bug at the unit level.

    A buffer holding nothing but a prompt is what a stale prompt looks like: the
    read ends with zero bytes of command output. `prompt_without_echo` marks it,
    and `_drain_pending` is what stops it from ever reaching this function.
    """
    chan = FakeChannel([STALE_PROMPT])
    read = run_ssh._read_command_output(chan, timeout=2.0, timing="prompt")

    assert read["raw_output"] == PROMPT
    assert read["prompt"] is not None
    assert read["prompt_without_echo"] is True
    assert run_ssh._prompt_preceded_by_content(read["raw_output"], read["prompt"]) is False


def test_draining_removes_the_stale_prompt_before_the_command_is_sent():
    chan = FakeChannel([STALE_PROMPT])
    drained = run_ssh._drain_pending(chan)

    assert drained == len(STALE_PROMPT)
    assert chan.chunks == []
    # The response only becomes available after the command is sent.
    chan.chunks.append(PROMPT_CHUNK)

    read = run_ssh._read_command_output(chan, timeout=2.0, timing="prompt")
    assert read["raw_output"].startswith("echo x")
    assert read["prompt_without_echo"] is False
    assert run_ssh._prompt_preceded_by_content(read["raw_output"], read["prompt"]) is True


def test_prompt_must_follow_the_echo_or_some_output():
    assert run_ssh._prompt_preceded_by_content("true\r\n" + PROMPT, PROMPT) is True
    assert run_ssh._prompt_preceded_by_content(PROMPT, PROMPT) is False
    assert run_ssh._prompt_preceded_by_content("   \r\n" + PROMPT, PROMPT) is False
    # Trailing whitespace after the prompt is still the prompt.
    assert run_ssh._prompt_preceded_by_content(
        "output\r\n" + PROMPT + "  ", PROMPT
    ) is True


def test_a_late_prompt_that_is_not_final_does_not_end_the_read():
    """Output arriving after a provisional prompt keeps the read alive."""
    chan = FakeChannel([
        b"root@srv-ubuntu:/tmp# ",
        b"real output\r\n",
        b"root@srv-ubuntu:/tmp# ",
    ])
    read = run_ssh._read_command_output(chan, timeout=2.0, timing="prompt")

    assert "real output" in read["raw_output"]
    assert read["raw_output"].rstrip().endswith("#")
    assert read["prompt_without_echo"] is False


# ── Timing ────────────────────────────────────────────────────────────────────

def test_prompt_mode_honours_the_settle_window_not_the_quiet_period():
    chan = FakeChannel([PROMPT_CHUNK])
    started = time.perf_counter()
    read = run_ssh._read_command_output(chan, timeout=5.0, timing="prompt")
    elapsed = time.perf_counter() - started

    assert read["timed_out"] is False
    assert read["prompt"] is not None
    # Waits for the settle window ...
    assert elapsed >= run_ssh.PROMPT_SETTLE * 0.9
    # ... and nowhere near the 0.5 s quiet period.
    assert elapsed < run_ssh.QUIET_PERIOD
    assert read["t_prompt"] is not None


def test_quiet_mode_keeps_the_published_behaviour_and_waits():
    chan = FakeChannel([PROMPT_CHUNK] + [b""] * 400)
    started = time.monotonic()
    read = run_ssh._read_command_output(chan, timeout=5.0, timing="quiet")
    elapsed = time.monotonic() - started

    assert read["timed_out"] is False
    assert read["prompt"] is not None
    # Reviewer point (a): the floor is the harness, not the server.
    assert elapsed >= run_ssh.QUIET_PERIOD - 0.01
    assert read["t_prompt"] is not None


def test_timeout_is_the_fallback_when_no_prompt_arrives():
    chan = FakeChannel([b"partial output\r\n"] * 2000)
    read = run_ssh._read_command_output(chan, timeout=0.05, timing="prompt")
    assert read["timed_out"] is True
    assert read["prompt"] is None
    assert read["t_prompt"] is None
    assert read["t_first_byte"] is not None


# ── CLI ───────────────────────────────────────────────────────────────────────

def test_timing_flag_defaults_to_the_published_mode():
    args = run_ssh.parse_args([])
    assert args.timing == "quiet"
    assert args.timing_explicit is False
    assert args.mask_credentials is True


def test_timing_flag_is_recorded_as_explicit():
    args = run_ssh.parse_args(["--timing", "prompt"])
    assert args.timing == "prompt"
    assert args.timing_explicit is True

    args = run_ssh.parse_args(["--timing=quiet"])
    assert args.timing == "quiet"
    assert args.timing_explicit is True


def test_invalid_timing_mode_is_rejected():
    with pytest.raises(SystemExit):
        run_ssh.parse_args(["--timing", "fast"])


def test_credential_masking_can_be_disabled_from_the_cli():
    args = run_ssh.parse_args(["--no-mask-credentials"])
    assert args.mask_credentials is False
