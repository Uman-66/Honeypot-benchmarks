#!/usr/bin/env python3
"""
harness/calibrate_floor.py
Measure the harness's own latency floor against the two non-LLM targets.

Reviewer point (a): the published 0.56 s groundtruth_ssh / Cowrie median is
mostly the harness waiting, not the servers answering.  ``run_ssh.py`` stops a
command only after ``QUIET_PERIOD`` (0.5 s) of silence following a prompt, so a
command that finishes in 3 ms is still recorded as ~0.5 s plus the network
round trip and the up-to-0.1 s poll granularity.

This script measures that floor directly.  It sends *trivial* commands (``true``
and ``echo x``) to ``groundtruth_ssh`` and ``cowrie`` only, and reports the
wall-clock distribution under:

    quiet   — the published-batch rule (QUIET_PERIOD of silence after a prompt)
    prompt  — the opt-in ``run_ssh.py --timing prompt`` rule (stop at the prompt)

No LLM is contacted: the target allowlist below contains only the two local
non-API services, so this script cannot spend API credits even by mistake.

Usage:
    python harness/calibrate_floor.py                 # 30 commands per mode/target
    python harness/calibrate_floor.py --n 50 --target cowrie
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

from run_ssh import (  # noqa: E402
    AUTH_TIMEOUT,
    BANNER_TIMEOUT,
    _read_command_output,
    _read_until_prompt,
)

#: Hard allowlist: these are the only targets this script will ever connect to.
ALLOWED_TARGETS = ("groundtruth_ssh", "cowrie")

#: Trivial commands. Neither touches the API-backed path on any target.
TRIVIAL_COMMANDS = ("true", "echo x")

TARGETS_YAML = HARNESS_DIR / "targets.yaml"
DEFAULT_OUT = Path("results/exp")


def _pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = p / 100 * (len(ordered) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def _load_targets(names: list[str]) -> list[dict[str, Any]]:
    with open(TARGETS_YAML, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    by_name = {t["name"]: t for t in data.get("targets", [])}
    selected = []
    for name in names:
        if name not in ALLOWED_TARGETS:
            raise SystemExit(
                f"ERROR: {name!r} is not in the allowlist {ALLOWED_TARGETS}. "
                "This script measures the harness floor and must not call an LLM."
            )
        if name not in by_name:
            raise SystemExit(f"ERROR: target {name!r} missing from {TARGETS_YAML}")
        selected.append(by_name[name])
    return selected


def _open_shell(target: dict[str, Any], timeout: float):
    """Connect, authenticate, open an interactive PTY and read the banner."""
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


def _measure(
    target: dict[str, Any],
    count: int,
    timing: str,
    timeout: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sock = transport = chan = None
    try:
        sock, transport, chan = _open_shell(target, timeout)
        for index in range(count):
            command = TRIVIAL_COMMANDS[index % len(TRIVIAL_COMMANDS)]
            started = time.monotonic()
            chan.sendall((command + "\n").encode("utf-8"))
            read = _read_command_output(chan, timeout, timing, started=started)
            elapsed = time.monotonic() - started
            rows.append({
                "target": target["name"],
                "index": index + 1,
                "command": command,
                "timing": timing,
                "latency_s": round(elapsed, 4),
                "t_first_byte": read["t_first_byte"],
                "t_prompt": read["t_prompt"],
                "timed_out": read["timed_out"],
                "prompt_found": read["prompt"] is not None,
                "bytes": len(read["raw_output"]),
            })
    finally:
        for closer in (chan, transport, sock):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [r["latency_s"] for r in rows if not r["timed_out"]]
    first_bytes = [r["t_first_byte"] for r in rows if r["t_first_byte"] is not None]
    prompts = [r["t_prompt"] for r in rows if r["t_prompt"] is not None]
    return {
        "n": len(rows),
        "n_timeouts": sum(1 for r in rows if r["timed_out"]),
        "n_prompt_found": sum(1 for r in rows if r["prompt_found"]),
        "median_s": round(statistics.median(latencies), 4) if latencies else None,
        "p95_s": round(_pct(latencies, 95), 4) if latencies else None,
        "min_s": round(min(latencies), 4) if latencies else None,
        "max_s": round(max(latencies), 4) if latencies else None,
        "median_first_byte_s": (
            round(statistics.median(first_bytes), 4) if first_bytes else None
        ),
        "median_prompt_s": (
            round(statistics.median(prompts), 4) if prompts else None
        ),
    }


def _write_outputs(out_dir: Path, rows: list[dict[str, Any]],
                   summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "floor_raw.csv"
    fields = ["target", "index", "command", "timing", "latency_s",
              "t_first_byte", "t_prompt", "timed_out", "prompt_found", "bytes"]
    with open(raw_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    json_path = out_dir / "floor.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    lines = [
        "# Harness latency floor (results/exp/floor.md)",
        "",
        "Sent only trivial commands (`true` / `echo x`) to the two non-API targets.",
        "No LLM was contacted.",
        "",
        f"Commands per target and mode: {summary['n_per_cell']}",
        "",
        "| Target | Timing | n | Median (s) | p95 (s) | min | max | Median first byte (s) | Median prompt (s) | Timeouts |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in summary["cells"]:
        lines.append(
            f"| {cell['target']} | {cell['timing']} | {cell['n']} | "
            f"{cell['median_s']} | {cell['p95_s']} | {cell['min_s']} | "
            f"{cell['max_s']} | {cell['median_first_byte_s']} | "
            f"{cell['median_prompt_s']} | {cell['n_timeouts']} |"
        )
    lines += [
        "",
        "**Reading the table.** `quiet` is the published-batch rule and cannot go",
        "below `QUIET_PERIOD` (0.5 s); its median minus the server's own",
        "`median_prompt_s` is the harness floor. `prompt` is the opt-in rule added in",
        "Stage 2 and tracks the server.",
        "",
    ]
    with open(out_dir / "floor.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the harness latency floor on non-API targets",
    )
    parser.add_argument("--target", default=",".join(ALLOWED_TARGETS),
                        help="Comma-separated names (allowlist: groundtruth_ssh, cowrie)")
    parser.add_argument("--n", type=int, default=30,
                        help="Trivial commands per target per timing mode (default: 30)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Per-command timeout in seconds (default: 30)")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help=f"Output directory (default: {DEFAULT_OUT})")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.target.split(",") if n.strip()]
    targets = _load_targets(names)

    all_rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []

    for target in targets:
        for timing in ("quiet", "prompt"):
            print(f"[floor] {target['name']} / {timing}: {args.n} commands ...",
                  end=" ", flush=True)
            rows = _measure(target, args.n, timing, args.timeout)
            all_rows.extend(rows)
            cell = _summary(rows)
            cell["target"] = target["name"]
            cell["timing"] = timing
            cells.append(cell)
            print(f"median {cell['median_s']}s p95 {cell['p95_s']}s "
                  f"(timeouts {cell['n_timeouts']})")

    summary = {"n_per_cell": args.n, "cells": cells}
    _write_outputs(Path(args.out), all_rows, summary)

    print("\n| Target | Timing | Median (s) | p95 (s) | Median prompt (s) |")
    print("|---|---|---:|---:|---:|")
    for cell in cells:
        print(f"| {cell['target']} | {cell['timing']} | {cell['median_s']} | "
              f"{cell['p95_s']} | {cell['median_prompt_s']} |")
    print(f"\nWritten: {Path(args.out) / 'floor.md'}, floor.json, floor_raw.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
