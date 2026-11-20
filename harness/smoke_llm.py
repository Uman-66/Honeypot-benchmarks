#!/usr/bin/env python3
"""
harness/smoke_llm.py
One tiny LLM smoke run against a single target, plus a comparison against the
API proxy log.

Why not run_ssh.py: that script hardcodes `results/ssh_commands_long.csv` and
`results/errors.log`, which must never be appended to outside the published
batch. This tool calls `run_ssh._run_once` directly and writes only under
`--out` (results/exp/smoke).

Usage:
    python harness/smoke_llm.py --target advshellm --timing quiet
    python harness/smoke_llm.py --target advshellm --timing prompt
    python harness/smoke_llm.py --target advshellm --compare
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

import yaml  # noqa: E402

import run_ssh  # noqa: E402

DEFAULT_OUT = Path("results/exp/smoke")
DEFAULT_COMMANDS = DEFAULT_OUT / "smoke_commands.yaml"
TARGETS_YAML = HARNESS_DIR / "targets.yaml"
PROXY_LOG = DEFAULT_OUT / "api_proxy_log.jsonl"


# ── Running ───────────────────────────────────────────────────────────────────

def _load_target(name: str) -> dict[str, Any]:
    with open(TARGETS_YAML, encoding="utf-8") as fh:
        targets = {t["name"]: t for t in yaml.safe_load(fh)["targets"]}
    if name not in targets:
        raise SystemExit(f"ERROR: target {name!r} is not in {TARGETS_YAML}")
    return targets[name]


def run_once(
    target: dict[str, Any],
    commands: list[dict[str, Any]],
    timing: str,
    timeout: float,
) -> list[dict[str, Any]]:
    rows, _fingerprint, run_meta = run_ssh._run_once(
        target, commands, 1, timeout,
        timing=timing,
        timing_explicit=True,
        mask_credentials_enabled=True,
    )
    if run_meta.get("connection_error"):
        print(f"WARNING: {run_meta['error_stage']}: {run_meta['connection_error']}",
              file=sys.stderr)
    return rows


def _summary(rows: list[dict[str, Any]]) -> str:
    latencies = [row["latency_s"] for row in rows if not row.get("timed_out")]
    if not latencies:
        return "no completed commands"
    return (
        f"n={len(latencies)} min={min(latencies):.4f}s "
        f"median={statistics.median(latencies):.4f}s "
        f"max={max(latencies):.4f}s "
        f"timeouts={sum(1 for row in rows if row.get('timed_out'))}"
    )


def _write_rows(out_dir: Path, target: str, timing: str,
                rows: list[dict[str, Any]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{target}_{timing}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _load_rows(out_dir: Path, target: str, timing: str) -> list[dict[str, Any]]:
    path = out_dir / f"{target}_{timing}.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ── Proxy correlation ─────────────────────────────────────────────────────────

def _parse_ts(value: str) -> float:
    return datetime.datetime.fromisoformat(value).timestamp()


def _load_proxy_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _match_entry(entries: list[dict[str, Any]], used: set[int],
                 start: float, end: float) -> list[dict[str, Any]]:
    """
    Return the single proxy request that belongs to one command.

    A command's LLM request starts a few milliseconds after `t_send` and finishes
    before the prompt arrives, so its start timestamp lies strictly inside
    [t_send, t_send + latency]. The tolerance is asymmetric and small on the
    right on purpose: a generous symmetric window also swallows the next
    command's request, which is only ~20 ms later.

    Each log entry is consumed at most once, so a request can never be counted
    for two commands.
    """
    for index, entry in enumerate(entries):
        if index in used:
            continue
        try:
            ts = _parse_ts(entry["ts"])
        except Exception:
            continue
        if start - 0.05 <= ts <= end + 0.02:
            used.add(index)
            return [entry]
    return []


def _redaction_report(log_text: str) -> dict[str, bool]:
    """Check the log for secrets without ever printing them."""
    env_key = ""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                env_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return {
        "api_key_absent": (env_key == "") or (env_key not in log_text),
        "authorization_header_absent": "authorization" not in log_text.lower(),
        "bearer_absent": "bearer" not in log_text.lower(),
        "sk_prefix_absent": "sk-" not in log_text.lower(),
        "prompt_text_absent": "messages" not in log_text,
    }


def compare(target: str, out_dir: Path, proxy_log: Path) -> int:
    quiet = _load_rows(out_dir, target, "quiet")
    prompt = _load_rows(out_dir, target, "prompt")
    entries = _load_proxy_log(proxy_log)

    by_cmd_prompt = {row["cmd_id"]: row for row in prompt}
    qmap = {row["cmd_id"]: row for row in quiet}
    entries = sorted(entries, key=lambda e: _parse_ts(e["ts"]))
    used: set[int] = set()
    # Attribute the quiet run too, so the unattributed count is only the banner.
    for row in sorted(quiet, key=lambda r: r.get("t_send") or 0):
        start = row.get("t_send")
        if start:
            _match_entry(entries, used, start, start + row["latency_s"])

    lines = [
        f"# Stage 2 smoke - {target}",
        "",
        f"Quiet: {_summary(quiet)}",
        f"Prompt: {_summary(prompt)}",
        f"Proxy requests logged: {len(entries)}",
        "",
        "| Command | Quiet harness (s) | Prompt harness (s) | Proxy requests | Proxy total (s) | Gap: harness minus proxy (s) | Max status | Total tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rows_csv = []
    for cmd_id, row in by_cmd_prompt.items():
        start = row.get("t_send")
        end = start + row["latency_s"] if start else None
        window = _match_entry(entries, used, start, end) if start else []
        proxy_total = sum(e.get("duration_ms") or 0 for e in window) / 1000
        gap = row["latency_s"] - proxy_total if window else None
        tokens = sum(e.get("total_tokens") or 0 for e in window)
        statuses = ",".join(str(e.get("status")) for e in window) or "-"
        quiet_row = qmap.get(cmd_id, {})
        lines.append(
            f"| {cmd_id} | {quiet_row.get('latency_s', '')} | {row['latency_s']:.4f} | "
            f"{len(window)} | {proxy_total:.4f} | "
            f"{'' if gap is None else f'{gap:.4f}'} | {statuses} | {tokens} |"
        )
        rows_csv.append({
            "cmd_id": cmd_id,
            "quiet_latency_s": quiet_row.get("latency_s"),
            "prompt_latency_s": row["latency_s"],
            "proxy_request_count": len(window),
            "proxy_total_s": round(proxy_total, 4),
            "gap_s": None if gap is None else round(gap, 4),
            "statuses": statuses,
            "total_tokens": tokens,
            "output_exact_equal": (
                (quiet_row.get("cleaned_output") or "") == (row.get("cleaned_output") or "")
            ),
        })

    log_text = proxy_log.read_text(encoding="utf-8") if proxy_log.exists() else ""
    redaction = _redaction_report(log_text)
    gaps = [row["gap_s"] for row in rows_csv if row["gap_s"] is not None]
    lines += [
        "",
        "## Harness overhead around the API call (prompt mode)",
        "",
        f"- commands matched to exactly one API request: {len(gaps)}/{len(rows_csv)}",
        f"- gap median: {statistics.median(gaps):.4f} s" if gaps else "- gap median: n/a",
        f"- gap min/max: {min(gaps):.4f} / {max(gaps):.4f} s" if gaps else "- gap min/max: n/a",
        "",
        "The gap is SSH transport, wrapper process I/O and harness bookkeeping",
        "around the API call. It is the part of a command's latency that is not the",
        "model, and it is now measurable instead of being buried in a 0.5 s quiet",
        "period.",
    ]
    lines += [
        "",
        "## Redaction checks on the proxy log",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for name, ok in redaction.items():
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} |")

    status_counts: dict[str, int] = {}
    for entry in entries:
        key = str(entry.get("status"))
        status_counts[key] = status_counts.get(key, 0) + 1
    durations = [e.get("duration_ms") for e in entries
                 if isinstance(e.get("duration_ms"), (int, float))]
    unattributed = len(entries) - len(used)
    lines += [
        "",
        "## Proxy log shape",
        "",
        f"- requests: {len(entries)}",
        f"- attributed to a command (both modes): {len(used)}; "
        f"unattributed (session/banner): {unattributed}",
        f"- statuses: {status_counts}",
        f"- duration_ms median: {statistics.median(durations) if durations else None}",
        f"- usage present on: {sum(1 for e in entries if e.get('usage'))} requests",
        "- keys logged: " + ", ".join(sorted(entries[0].keys())) if entries else "- keys logged: none",
        "",
    ]

    (out_dir / "smoke_summary.md").write_text("\n".join(lines), encoding="utf-8")
    with open(out_dir / "smoke_summary.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows_csv[0])) if rows_csv else None
        if writer:
            writer.writeheader()
            writer.writerows(rows_csv)

    print("\n".join(lines))
    failed = [name for name, ok in redaction.items() if not ok]
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded LLM smoke run")
    parser.add_argument("--target", default="advshellm")
    parser.add_argument("--timing", choices=("quiet", "prompt"), default="quiet")
    parser.add_argument("--commands", default=str(DEFAULT_COMMANDS))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--proxy-log", default=str(PROXY_LOG))
    parser.add_argument("--compare", action="store_true",
                        help="Compare the two saved runs against the proxy log")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if args.compare:
        return compare(args.target, out_dir, Path(args.proxy_log))

    with open(args.commands, encoding="utf-8") as fh:
        commands = yaml.safe_load(fh)["commands"]
    if len(commands) > 5:
        raise SystemExit("ERROR: the smoke run is capped at 5 commands")

    target = _load_target(args.target)
    print(f"[smoke] {args.target}: {len(commands)} commands, timing={args.timing}")
    rows = run_once(target, commands, args.timing, args.timeout)
    path = _write_rows(out_dir, args.target, args.timing, rows)
    print(f"[smoke] {_summary(rows)}")
    print(f"[smoke] written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
