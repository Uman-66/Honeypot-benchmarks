#!/usr/bin/env python3
"""
harness/timing_audit.py
Run the full command list in both timing modes against the non-API targets and
compare the outputs command by command.

Purpose: `--timing prompt` is only safe if it captures exactly the same output as
the published quiet-mode rule. This tool answers that directly: for every command
it reports exact equality, masked similarity, and whether the prompt-mode output
is shorter, empty or different.

Only `groundtruth_ssh` and `cowrie` are permitted - no LLM is contacted, so the
audit cannot spend API credits. Outputs go to `results/exp/timing_audit/`.

Usage:
    python harness/timing_audit.py
    python harness/timing_audit.py --targets cowrie --timeout 30
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

import paramiko  # noqa: E402
import yaml  # noqa: E402

from analyze import _similarity, _strip_ansi, mask_text  # noqa: E402
from run_ssh import (  # noqa: E402
    AUTH_TIMEOUT,
    BANNER_TIMEOUT,
    ENCODING,
    ENCODING_ERRORS,
    EXIT_WAIT,
    RECV_CHUNK,
    TRAP_MARKERS,
    _FORBIDDEN_COMMANDS,
    _clean_output,
    _drain_pending,
    _has_literal_escape,
    _read_command_output,
    _read_until_prompt,
)

ALLOWED_TARGETS = ("groundtruth_ssh", "cowrie")
TARGETS_YAML = HARNESS_DIR / "targets.yaml"
COMMANDS_YAML = HARNESS_DIR / "commands.yaml"
DEFAULT_OUT = Path("results/exp/timing_audit")


# ── Session ───────────────────────────────────────────────────────────────────

def _open_shell(target: dict[str, Any], timeout: float):
    sock = socket.create_connection(
        (target["host"], int(target["port"])), timeout=BANNER_TIMEOUT
    )
    transport = paramiko.Transport(sock)
    transport.banner_timeout = BANNER_TIMEOUT
    transport.auth_timeout = AUTH_TIMEOUT
    transport.start_client(timeout=BANNER_TIMEOUT)
    transport.auth_password(
        target["username"], target.get("password", ""), fallback=False
    )
    chan = transport.open_session()
    chan.get_pty(term="xterm", width=220, height=50)
    chan.invoke_shell()
    _read_until_prompt(chan, timeout=timeout)
    return sock, transport, chan


def _run_exit(chan: paramiko.Channel, started: float, clock) -> dict[str, Any]:
    """Wait for the channel to close after `exit`, mirroring run_ssh."""
    closed = False
    status = None
    buf = ""
    deadline = time.monotonic() + EXIT_WAIT
    while time.monotonic() < deadline:
        try:
            chunk = chan.recv(RECV_CHUNK)
        except Exception:
            closed = True
            break
        if chunk:
            buf += chunk.decode(ENCODING, ENCODING_ERRORS)
        if chan.exit_status_ready():
            status = chan.recv_exit_status()
            closed = True
            break
        if not chunk:
            time.sleep(0.02)
    return {
        "cmd_id": "exit",
        "timed_out": not closed,
        "raw_output": buf,
        "cleaned_output": "",
        "latency_s": round(clock() - started, 6),
        "bytes": len(buf),
        "exit_status": status,
        "exit_closes_session": closed,
    }


def run_session(
    target: dict[str, Any],
    commands: list[dict[str, Any]],
    timing: str,
    timeout: float,
) -> list[dict[str, Any]]:
    clock = time.perf_counter if timing == "prompt" else time.monotonic
    sock = transport = chan = None
    rows: list[dict[str, Any]] = []
    try:
        sock, transport, chan = _open_shell(target, timeout)
        for command in commands:
            cmd_id = command["id"]
            cmd_text = command["text"]
            if any(forbidden in cmd_text for forbidden in _FORBIDDEN_COMMANDS):
                rows.append({
                    "cmd_id": cmd_id, "timing": timing, "timed_out": False,
                    "raw_output": "", "cleaned_output": "", "latency_s": 0.0,
                    "bytes": 0, "error": "FORBIDDEN command skipped",
                })
                continue

            stale = _drain_pending(chan) if timing == "prompt" else 0
            started = clock()
            chan.sendall((cmd_text + "\n").encode(ENCODING))

            if cmd_id == "exit":
                row = _run_exit(chan, started, clock)
                row.update({"timing": timing, "stale_bytes": stale})
                rows.append(row)
                break

            read = _read_command_output(chan, timeout, timing, started=started)
            raw = read["raw_output"]
            rows.append({
                "cmd_id": cmd_id,
                "text": cmd_text,
                "timing": timing,
                "latency_s": round(read["elapsed"], 6),
                "t_first_byte": read["t_first_byte"],
                "t_prompt": read["t_prompt"],
                "timed_out": read["timed_out"],
                "prompt_found": read["prompt"] is not None,
                "prompt_without_echo": read["prompt_without_echo"],
                "stale_bytes": stale,
                "bytes": len(raw),
                "cleaned_output": _clean_output(raw, cmd_text, read["prompt"]),
                "raw_output": raw,
                "literal_escape_text_present": _has_literal_escape(raw),
                "trap_markers_found": [
                    marker for marker in TRAP_MARKERS if marker in raw
                ],
            })
    finally:
        for closer in (chan, transport, sock):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
    return rows


# ── Comparison ────────────────────────────────────────────────────────────────

def _pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = p / 100 * (len(ordered) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def _latency(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "median": None, "p95": None, "max": None}
    return {
        "n": len(values),
        "min": round(min(values), 6),
        "median": round(statistics.median(values), 6),
        "p95": round(_pct(values, 95), 6),
        "max": round(max(values), 6),
    }


def compare(
    quiet: list[dict[str, Any]],
    prompt: list[dict[str, Any]],
    hostnames: set[str],
) -> list[dict[str, Any]]:
    qmap = {row["cmd_id"]: row for row in quiet}
    pmap = {row["cmd_id"]: row for row in prompt}
    rows: list[dict[str, Any]] = []
    for cmd_id in qmap:
        if cmd_id not in pmap:
            continue
        a = qmap[cmd_id].get("cleaned_output") or ""
        b = pmap[cmd_id].get("cleaned_output") or ""
        masked_sim = round(
            _similarity(mask_text(a, hostnames), mask_text(b, hostnames)), 4
        )
        flags = []
        # Only a lost output counts: an empty output in both modes is the command,
        # not the timing rule.
        if not b.strip() and a.strip():
            flags.append("empty-prompt-mode")
        if len(b) < len(a):
            flags.append("shorter")
        elif len(b) > len(a):
            flags.append("longer")
        if a != b:
            flags.append("different")
        if a != b and masked_sim >= 0.999 and len(a) == len(b):
            flags.append("volatile-content-only")
        rows.append({
            "cmd_id": cmd_id,
            "quiet_len": len(a),
            "prompt_len": len(b),
            "exact_equal": a == b,
            "masked_similarity": masked_sim,
            "flags": ",".join(flags) if flags else "ok",
            "quiet_timed_out": qmap[cmd_id].get("timed_out"),
            "prompt_timed_out": pmap[cmd_id].get("timed_out"),
        })
    return rows


def _write(target: str, out_dir: Path, quiet, prompt, rows, latencies) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for timing, data in (("quiet", quiet), ("prompt", prompt)):
        with open(out_dir / f"{target}_{timing}.jsonl", "w", encoding="utf-8") as fh:
            for row in data:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(out_dir / "comparison.csv", "a", newline="", encoding="utf-8") as fh:
        fields = ["target", "cmd_id", "quiet_len", "prompt_len", "exact_equal",
                  "masked_similarity", "flags", "quiet_timed_out", "prompt_timed_out"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if fh.tell() == 0:
            writer.writeheader()
        for row in rows:
            writer.writerow({"target": target, **row})

    with open(out_dir / "latency.json", "w", encoding="utf-8") as fh:
        json.dump(latencies, fh, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare quiet and prompt timing modes on non-API targets",
    )
    parser.add_argument("--target", default=",".join(ALLOWED_TARGETS),
                        help="Comma-separated names (allowlist: groundtruth_ssh, cowrie)")
    parser.add_argument("--commands", default=str(COMMANDS_YAML))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.target.split(",") if n.strip()]
    for name in names:
        if name not in ALLOWED_TARGETS:
            raise SystemExit(
                f"ERROR: {name!r} is not in {ALLOWED_TARGETS}; "
                "this audit must not contact an LLM."
            )

    with open(TARGETS_YAML, encoding="utf-8") as fh:
        targets = {t["name"]: t for t in yaml.safe_load(fh)["targets"]}
    with open(args.commands, encoding="utf-8") as fh:
        commands = yaml.safe_load(fh)["commands"]

    out_dir = Path(args.out)
    if (out_dir / "comparison.csv").exists():
        (out_dir / "comparison.csv").unlink()

    latencies: dict[str, Any] = {}
    for name in names:
        target = targets[name]
        print(f"[audit] {name}: running {len(commands)} commands in quiet mode ...",
              flush=True)
        quiet = run_session(target, commands, "quiet", args.timeout)
        print(f"[audit] {name}: prompt mode ...", flush=True)
        prompt = run_session(target, commands, "prompt", args.timeout)

        hostnames = set()
        for row in quiet + prompt:
            if row.get("cmd_id") == "hostname" and (row.get("cleaned_output") or "").strip():
                hostnames.add(row["cleaned_output"].strip().splitlines()[0].strip())

        rows = compare(quiet, prompt, hostnames)
        lat = {
            "quiet": _latency([r["latency_s"] for r in quiet
                               if not r.get("timed_out") and r["cmd_id"] != "exit"]),
            "prompt": _latency([r["latency_s"] for r in prompt
                                if not r.get("timed_out") and r["cmd_id"] != "exit"]),
            "prompt_first_byte": _latency([r["t_first_byte"] for r in prompt
                                           if r.get("t_first_byte") is not None]),
            "prompt_stale_bytes_max": max(
                [r.get("stale_bytes") or 0 for r in prompt] or [0]
            ),
            "prompt_without_echo_rows": sum(
                1 for r in prompt if r.get("prompt_without_echo")
            ),
        }
        latencies[name] = lat
        _write(name, out_dir, quiet, prompt, rows, {name: lat})

        differing = [
            r for r in rows if r["flags"] not in ("ok", "different,volatile-content-only")
        ]
        volatile = [r for r in rows if "volatile-content-only" in r["flags"]]
        print(f"  quiet  {lat['quiet']}")
        print(f"  prompt {lat['prompt']}")
        print(f"  exact-equality: {sum(1 for r in rows if r['exact_equal'])}/{len(rows)}; "
              f"same-length volatile-only: {len(volatile)}; "
              f"truncation/difference: {len(differing)}")
        for row in differing:
            print(f"  DIFF {row['cmd_id']}: {row['flags']} "
                  f"quiet={row['quiet_len']}B prompt={row['prompt_len']}B "
                  f"sim={row['masked_similarity']}")

    print(f"\nWritten: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
