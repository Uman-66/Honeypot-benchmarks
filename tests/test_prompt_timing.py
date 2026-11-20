"""Tests for the prompt-detect timing mode added to harness/run_ssh.py."""

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


PROMPT_CHUNK = b"echo x\r\nx\r\nroot@srv-ubuntu:/tmp# "


def test_prompt_mode_stops_at_the_prompt_without_the_quiet_period():
    chan = FakeChannel([PROMPT_CHUNK])

    started = time.monotonic()
    read = run_ssh._read_command_output(chan, timeout=5.0, timing="prompt")
    elapsed = time.monotonic() - started

    assert read["timed_out"] is False
    assert read["prompt"] is not None
    assert read["t_prompt"] is not None
    assert read["t_first_byte"] is not None
    # The whole point of the mode: no QUIET_PERIOD wait.
    assert elapsed < run_ssh.QUIET_PERIOD
    assert read["t_prompt"] <= elapsed + 0.05


def test_quiet_mode_keeps_the_published_behaviour_and_waits():
    chan = FakeChannel([PROMPT_CHUNK] + [b""] * 200)

    started = time.monotonic()
    read = run_ssh._read_command_output(chan, timeout=5.0, timing="quiet")
    elapsed = time.monotonic() - started

    assert read["timed_out"] is False
    assert read["prompt"] is not None
    # This is the reviewer's point (a): the floor is the harness, not the server.
    assert elapsed >= run_ssh.QUIET_PERIOD - 0.01
    assert read["t_prompt"] is not None and read["t_prompt"] < run_ssh.QUIET_PERIOD


def test_timeout_is_the_fallback_when_no_prompt_arrives():
    chan = FakeChannel([b"partial output\r\n"] * 1000)
    read = run_ssh._read_command_output(chan, timeout=0.05, timing="prompt")
    assert read["timed_out"] is True
    assert read["prompt"] is None
    assert read["t_prompt"] is None
    assert read["t_first_byte"] is not None


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
