#!/usr/bin/env python3
"""
harness/validate_prompt_timing.py
Full A/B/C prompt-mode validation for the four LLM SSH honeypots.

Passes per target (fresh container / session per pass):
  A  quiet mode   (published-batch behaviour)
  B  prompt mode  (the new opt-in timing rule)
  C  quiet mode   (second quiet run; A vs C is the noise baseline)

Outputs under results/exp/validation/:
  {target}_{pass}.jsonl          — raw harness records
  {target}_comparison.csv        — per-command A/B/C comparison
  api_proxy_log.jsonl            — proxy log (all requests from this run)
  validation_summary.md          — per-target flagged-command table + latency

Usage (run from repo root):
  # Start api_proxy first (separate terminal):
  #   .venv-harness/Scripts/python harness/api_proxy.py --bind 0.0.0.0 --allow-remote-bind
  .venv-harness/Scripts/python harness/validate_prompt_timing.py
  .venv-harness/Scripts/python harness/validate_prompt_timing.py --target deceive
  .venv-harness/Scripts/python harness/validate_prompt_timing.py --dry-run

API budget: each target uses 3 × 36 non-exit commands maximum (108 LLM calls).
Four targets: 432 calls. Stopped early if proxy log count would exceed 500.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT   = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR))

import yaml         # noqa: E402
import run_ssh      # noqa: E402

TARGETS_YAML  = HARNESS_DIR / "targets.yaml"
COMMANDS_YAML = HARNESS_DIR / "commands.yaml"
OUT_DIR       = REPO_ROOT / "results" / "exp" / "validation"
PROXY_LOG     = OUT_DIR / "api_proxy_log.jsonl"

# LLM targets for this validation (must match targets.yaml names)
LLM_TARGETS = ["deceive", "beelzebub", "vellmes", "advshellm"]

# Budget: stop before issuing this many LLM calls (from proxy log)
API_BUDGET = 500

# Prompt-like regex from analyze.py _SHELL_PROMPT_RE
_TRANSCRIPT_LEAK_RE = re.compile(r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s")

# ANSI/masking rules (subset of analyze.py MASK_RULES) for similarity
_MASK_RE: list[tuple[str, re.Pattern[str]]] = [
    ("<DATE>", re.compile(
        r"\b\d{4}-\d{2}-\d{2}"
        r"(?:[T ]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b")),
    ("<DATE>", re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,]?\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?(?:\s+[A-Z]{2,5})?(?:\s+\d{4})?\b")),
    ("<TIME>", re.compile(r"(?<![\d.:])\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\b")),
    ("<UPTIME>", re.compile(r"\bup\s+\d+\s+(?:days?|hours?|minutes?|mins?)[^,\n]*", re.IGNORECASE)),
    ("<LOAD>", re.compile(r"load averages?:[^\n]*", re.IGNORECASE)),
    ("<PID>", re.compile(r"\bpid[=:\s]+\d+\b", re.IGNORECASE)),
    ("<TTY>", re.compile(r"\bpts/\d+\b")),
]


def _mask(text: str) -> str:
    for placeholder, pattern in _MASK_RE:
        text = pattern.sub(placeholder, text)
    return text


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a[:4000], b[:4000]).ratio()


def _has_transcript_leakage_inside(text: str) -> bool:
    """True if a prompt-like line appears INSIDE (not at the end of) the output."""
    matches = list(_TRANSCRIPT_LEAK_RE.finditer(text))
    if not matches:
        return False
    lines = text.splitlines()
    last_nonempty = next(
        (idx for idx in range(len(lines) - 1, -1, -1) if lines[idx].strip()),
        None,
    )
    if last_nonempty is None:
        return False
    return any(
        text.count("\n", 0, m.start()) < last_nonempty
        for m in matches
    )


def _load_commands() -> list[dict[str, Any]]:
    with open(COMMANDS_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["commands"]


def _load_targets() -> dict[str, dict[str, Any]]:
    with open(TARGETS_YAML, encoding="utf-8") as fh:
        return {t["name"]: t for t in yaml.safe_load(fh)["targets"]}


def _count_proxy_calls() -> int:
    if not PROXY_LOG.exists():
        return 0
    return sum(1 for line in PROXY_LOG.read_text(encoding="utf-8").splitlines() if line.strip())


def _run_pass(
    target: dict[str, Any],
    commands: list[dict[str, Any]],
    timing: str,
    pass_label: str,
    timeout: float = 120.0,
) -> list[dict[str, Any]]:
    print(f"  [{pass_label}] timing={timing} target={target['name']} ...", flush=True)
    rows, _fp, run_meta = run_ssh._run_once(
        target, commands, 1, timeout,
        timing=timing,
        timing_explicit=True,
        mask_credentials_enabled=True,
    )
    if run_meta.get("connection_error"):
        print(f"  [{pass_label}] WARNING: {run_meta['error_stage']}: {run_meta['connection_error']}",
              file=sys.stderr)
    n_to = sum(1 for r in rows if r.get("timed_out"))
    lat = [r["latency_s"] for r in rows if not r.get("timed_out") and "latency_s" in r]
    med = statistics.median(lat) if lat else float("nan")
    print(f"  [{pass_label}] n={len(rows)} timeouts={n_to} median_latency={med:.4f}s", flush=True)
    return rows


def _save_pass(target_name: str, pass_label: str, rows: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{target_name}_{pass_label}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _compare_passes(
    target_name: str,
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    rows_c: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-command A/B/C comparison. Returns list of dicts."""
    a_map = {r["cmd_id"]: r for r in rows_a if r.get("cmd_id") and r.get("cmd_id") != "exit"}
    b_map = {r["cmd_id"]: r for r in rows_b if r.get("cmd_id") and r.get("cmd_id") != "exit"}
    c_map = {r["cmd_id"]: r for r in rows_c if r.get("cmd_id") and r.get("cmd_id") != "exit"}
    all_ids = sorted(set(a_map) | set(b_map) | set(c_map))
    comparison = []
    for cmd_id in all_ids:
        ra = a_map.get(cmd_id, {})
        rb = b_map.get(cmd_id, {})
        rc = c_map.get(cmd_id, {})
        out_a = ra.get("cleaned_output") or ""
        out_b = rb.get("cleaned_output") or ""
        out_c = rc.get("cleaned_output") or ""
        masked_a = _mask(out_a)
        masked_b = _mask(out_b)
        masked_c = _mask(out_c)
        sim_ab = _similarity(masked_a, masked_b)
        sim_ac = _similarity(masked_a, masked_c)
        len_a = len(out_a)
        len_b = len(out_b)
        len_c = len(out_c)
        empty_a = not out_a.strip()
        empty_b = not out_b.strip()
        empty_c = not out_c.strip()
        timed_a = bool(ra.get("timed_out"))
        timed_b = bool(rb.get("timed_out"))
        timed_c = bool(rc.get("timed_out"))
        leak_b = _has_transcript_leakage_inside(out_b)
        leak_a = _has_transcript_leakage_inside(out_a)
        lat_a = ra.get("latency_s")
        lat_b = rb.get("latency_s")
        lat_c = rc.get("latency_s")
        comparison.append({
            "target": target_name,
            "cmd_id": cmd_id,
            "len_a": len_a,
            "len_b": len_b,
            "len_c": len_c,
            "empty_a": empty_a,
            "empty_b": empty_b,
            "empty_c": empty_c,
            "timed_out_a": timed_a,
            "timed_out_b": timed_b,
            "timed_out_c": timed_c,
            "masked_sim_ab": round(sim_ab, 4),
            "masked_sim_ac": round(sim_ac, 4),
            "transcript_leak_inside_a": leak_a,
            "transcript_leak_inside_b": leak_b,
            "latency_a": lat_a,
            "latency_b": lat_b,
            "latency_c": lat_c,
        })
    return comparison


def _flag_prompt_artefacts(
    comparison: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    A difference counts as a prompt-mode artefact if it exceeds the A-vs-C
    noise baseline for the same command.

    Flagged conditions:
    1. B shorter or empty when A is not, AND |len_b - len_a| > |len_c - len_a|
    2. Transcript leakage inside B, but not inside A (AND not just A-vs-C noise)
    3. B timed out when A did not (or vice versa) — always flagged regardless of baseline
    4. B masked_sim_ab < 0.5 AND sim_ac - sim_ab > 0.1 (B is an outlier vs AC noise)
    """
    flags = []
    for row in comparison:
        reasons = []
        len_ab_delta = abs(row["len_b"] - row["len_a"])
        len_ac_delta = abs(row["len_c"] - row["len_a"])
        # Condition 1: shorter or empty
        if row["len_b"] < row["len_a"] or (row["empty_b"] and not row["empty_a"]):
            if len_ab_delta > len_ac_delta:
                reasons.append(
                    f"shorter_or_empty: len_b={row['len_b']} len_a={row['len_a']} "
                    f"(AC_baseline_delta={len_ac_delta})"
                )
        # Condition 2: transcript leakage inside B
        if row["transcript_leak_inside_b"] and not row["transcript_leak_inside_a"]:
            reasons.append("transcript_leak_inside_B_not_A")
        # Condition 3: timeout flip (always flag)
        if row["timed_out_b"] and not row["timed_out_a"]:
            reasons.append("timeout_B_not_A")
        if row["timed_out_a"] and not row["timed_out_b"]:
            reasons.append("timeout_A_not_B")
        # Condition 4: similarity outlier
        sim_drop = row["masked_sim_ac"] - row["masked_sim_ab"]
        if row["masked_sim_ab"] < 0.5 and sim_drop > 0.1:
            reasons.append(
                f"sim_outlier: sim_AB={row['masked_sim_ab']:.4f} "
                f"sim_AC={row['masked_sim_ac']:.4f} drop={sim_drop:.4f}"
            )
        if reasons:
            flags.append({
                "target": row["target"],
                "cmd_id": row["cmd_id"],
                "reasons": reasons,
                "len_a": row["len_a"],
                "len_b": row["len_b"],
                "len_c": row["len_c"],
                "masked_sim_ab": row["masked_sim_ab"],
                "masked_sim_ac": row["masked_sim_ac"],
                "ac_baseline_len_delta": abs(row["len_c"] - row["len_a"]),
                "latency_a": row["latency_a"],
                "latency_b": row["latency_b"],
                "latency_c": row["latency_c"],
            })
    return flags


def _latency_table(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    lats = [r["latency_s"] for r in rows
            if r.get("latency_s") is not None and not r.get("timed_out")
            and r.get("cmd_id") and r.get("cmd_id") != "exit"]
    if not lats:
        return {"label": label, "n": 0, "min": None, "median": None, "p95": None, "max": None}
    lats_sorted = sorted(lats)
    n = len(lats_sorted)
    p95_idx = min(int(0.95 * (n - 1)), n - 1)
    return {
        "label": label,
        "n": n,
        "min": round(min(lats), 4),
        "median": round(statistics.median(lats), 4),
        "p95": round(lats_sorted[p95_idx], 4),
        "max": round(max(lats), 4),
    }


def run_validation(
    targets: list[str],
    dry_run: bool = False,
    timeout: float = 120.0,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    commands = _load_commands()
    target_configs = _load_targets()

    all_comparison: list[dict[str, Any]] = []
    all_flags: list[dict[str, Any]] = []
    latency_summary: list[dict[str, Any]] = []

    if dry_run:
        print("DRY RUN: would run the following passes:")
        for tname in targets:
            for label, timing in [("A", "quiet"), ("B", "prompt"), ("C", "quiet")]:
                print(f"  {tname} pass={label} timing={timing} n_commands={len(commands)}")
        print(f"  Max API calls: {len(targets)} × {len(commands) - 1} × 3 = "
              f"{len(targets) * (len(commands) - 1) * 3}")
        return

    for tname in targets:
        if tname not in target_configs:
            print(f"WARNING: target {tname!r} not found in targets.yaml, skipping", file=sys.stderr)
            continue
        target = target_configs[tname]
        print(f"\n=== {tname} ===", flush=True)

        # Check API budget before each pass
        before_a = _count_proxy_calls()
        if before_a >= API_BUDGET:
            print(f"BUDGET STOP: proxy log has {before_a} entries (budget {API_BUDGET})", file=sys.stderr)
            break

        # Pass A: quiet
        rows_a = _run_pass(target, commands, "quiet", f"{tname}_A", timeout)
        path_a = _save_pass(tname, "passA_quiet", rows_a)
        print(f"  Saved: {path_a}")

        after_a = _count_proxy_calls()
        if after_a >= API_BUDGET:
            print(f"BUDGET STOP: {after_a} proxy calls after pass A (budget {API_BUDGET})", file=sys.stderr)
            break

        # Pass B: prompt
        rows_b = _run_pass(target, commands, "prompt", f"{tname}_B", timeout)
        path_b = _save_pass(tname, "passB_prompt", rows_b)
        print(f"  Saved: {path_b}")

        after_b = _count_proxy_calls()
        if after_b >= API_BUDGET:
            print(f"BUDGET STOP: {after_b} proxy calls after pass B (budget {API_BUDGET})", file=sys.stderr)
            # Still do pass C even with budget hit; passes use same container session
            # so no extra API calls are incurred.
            # Actually exit — conservative budget enforcement.
            break

        # Pass C: quiet (noise baseline)
        rows_c = _run_pass(target, commands, "quiet", f"{tname}_C", timeout)
        path_c = _save_pass(tname, "passC_quiet", rows_c)
        print(f"  Saved: {path_c}")

        # Comparison
        comparison = _compare_passes(tname, rows_a, rows_b, rows_c)
        all_comparison.extend(comparison)
        # Save per-target comparison CSV
        comp_path = OUT_DIR / f"{tname}_comparison.csv"
        if comparison:
            with open(comp_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(comparison[0].keys()))
                writer.writeheader()
                writer.writerows(comparison)
            print(f"  Comparison: {comp_path}")

        # Flagged artefacts
        flags = _flag_prompt_artefacts(comparison)
        all_flags.extend(flags)

        # Latency summary
        latency_summary.append({
            "target": tname,
            "quiet_A": _latency_table(rows_a, "quiet_A"),
            "prompt_B": _latency_table(rows_b, "prompt_B"),
            "quiet_C": _latency_table(rows_c, "quiet_C"),
        })

        after_c = _count_proxy_calls()
        print(f"  API calls so far: {after_c}/{API_BUDGET}", flush=True)

    # Write summary
    _write_summary(all_flags, all_comparison, latency_summary)
    print(f"\nValidation complete. Results in {OUT_DIR}")


def _write_summary(
    flags: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    latency_summary: list[dict[str, Any]],
) -> None:
    lines: list[str] = [
        "# Prompt-mode validation — LLM SSH honeypots",
        "",
        f"Generated: {__import__('datetime').datetime.utcnow().isoformat()}Z",
        f"API calls in proxy log: {_count_proxy_calls()}",
        "",
        "---",
        "",
    ]

    # Per-target flagged commands
    lines += [
        "## Flagged commands (prompt artefacts vs A-vs-C noise baseline)",
        "",
        "A flag is raised when a difference in pass B (prompt mode) exceeds the",
        "A-vs-C noise baseline for the same command on the same target.",
        "",
    ]

    targets_seen = {f["target"] for f in flags}
    all_targets_in_comparison = {r["target"] for r in comparison}

    for tname in [t for t in LLM_TARGETS if t in all_targets_in_comparison]:
        tflags = [f for f in flags if f["target"] == tname]
        tcomp  = [r for r in comparison if r["target"] == tname]
        lines += [
            f"### {tname}",
            "",
            f"Commands checked: {len(tcomp)}  |  Flagged: {len(tflags)}",
            "",
        ]
        if not tflags:
            lines += ["No prompt-mode artefacts detected for this target.", ""]
        else:
            lines += [
                "| cmd_id | Reason | len_A | len_B | len_C | AC_baseline | sim_AB | sim_AC |",
                "|--------|--------|------:|------:|------:|------------:|-------:|-------:|",
            ]
            for f in tflags:
                reasons_str = "; ".join(f["reasons"])
                lines.append(
                    f"| {f['cmd_id']} | {reasons_str} "
                    f"| {f['len_a']} | {f['len_b']} | {f['len_c']} "
                    f"| {f['ac_baseline_len_delta']} "
                    f"| {f['masked_sim_ab']:.4f} | {f['masked_sim_ac']:.4f} |"
                )
            lines += [""]

    # Latency table
    lines += [
        "## Latency per target (harness, non-timeout commands only)",
        "",
        "| Target | Mode | n | Min (s) | Median (s) | p95 (s) | Max (s) |",
        "|--------|------|--:|--------:|-----------:|--------:|--------:|",
    ]
    for entry in latency_summary:
        tname = entry["target"]
        for pass_key in ["quiet_A", "prompt_B", "quiet_C"]:
            lt = entry[pass_key]
            if lt["n"] == 0:
                lines.append(f"| {tname} | {pass_key} | 0 | — | — | — | — |")
            else:
                lines.append(
                    f"| {tname} | {pass_key} | {lt['n']} "
                    f"| {lt['min']:.4f} | {lt['median']:.4f} "
                    f"| {lt['p95']:.4f} | {lt['max']:.4f} |"
                )

    lines += [
        "",
        "---",
        "",
        "## Notes",
        "",
        "- Pass A and C are both quiet mode; A-vs-C captures LLM non-determinism",
        "  plus any container/session state drift between two runs.",
        "- A flag only counts as a prompt-mode artefact if the B-vs-A difference",
        "  is larger than the A-vs-C baseline for the same command.",
        "- Transcript-leakage flags use the _SHELL_PROMPT_RE from analyze.py",
        "  (`r'(?m)^\\s*[\\w.-]+@[\\w.-]+:[^\\n]*[$#]\\s'`) applied to cleaned_output.",
        "",
    ]

    summary_path = OUT_DIR / "validation_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written: {summary_path}")


def run_single_pass(
    target_name: str,
    pass_label: str,
    timing: str,
    timeout: float = 120.0,
) -> None:
    """Run one pass (passA_quiet, passB_prompt, passC_quiet) for a single target."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    commands = _load_commands()
    target_configs = _load_targets()
    if target_name not in target_configs:
        print(f"ERROR: target {target_name!r} not in targets.yaml", file=sys.stderr)
        return
    target = target_configs[target_name]
    rows = _run_pass(target, commands, timing, f"{target_name}_{pass_label}", timeout)
    path = _save_pass(target_name, pass_label, rows)
    print(f"Saved: {path}")


def run_compare_only() -> None:
    """Load all saved passes and generate comparison + summary."""
    all_comparison: list[dict[str, Any]] = []
    all_flags: list[dict[str, Any]] = []
    latency_summary: list[dict[str, Any]] = []

    for tname in LLM_TARGETS:
        path_a = OUT_DIR / f"{tname}_passA_quiet.jsonl"
        path_b = OUT_DIR / f"{tname}_passB_prompt.jsonl"
        path_c = OUT_DIR / f"{tname}_passC_quiet.jsonl"
        if not (path_a.exists() and path_b.exists() and path_c.exists()):
            print(f"WARNING: missing pass files for {tname}, skipping", file=sys.stderr)
            continue

        def _load_jsonl(p: Path) -> list[dict[str, Any]]:
            return [
                json.loads(line)
                for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        rows_a = _load_jsonl(path_a)
        rows_b = _load_jsonl(path_b)
        rows_c = _load_jsonl(path_c)

        comparison = _compare_passes(tname, rows_a, rows_b, rows_c)
        all_comparison.extend(comparison)

        comp_path = OUT_DIR / f"{tname}_comparison.csv"
        if comparison:
            with open(comp_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(comparison[0].keys()))
                writer.writeheader()
                writer.writerows(comparison)
            print(f"Comparison CSV: {comp_path}")

        flags = _flag_prompt_artefacts(comparison)
        all_flags.extend(flags)

        latency_summary.append({
            "target": tname,
            "quiet_A": _latency_table(rows_a, "quiet_A"),
            "prompt_B": _latency_table(rows_b, "prompt_B"),
            "quiet_C": _latency_table(rows_c, "quiet_C"),
        })

    _write_summary(all_flags, all_comparison, latency_summary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prompt-mode validation for LLM SSH honeypots"
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Comma-separated target names (default: all four LLM targets)",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--pass-label",
        default=None,
        dest="pass_label",
        help="Single pass label (passA_quiet, passB_prompt, passC_quiet). "
             "Requires --target and --timing. Runs one pass and exits.",
    )
    parser.add_argument(
        "--timing",
        choices=("quiet", "prompt"),
        default=None,
        help="Timing mode for single-pass run (required with --pass-label)",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        dest="compare_only",
        help="Load saved pass files and generate comparison/summary only",
    )
    args = parser.parse_args(argv)

    if args.compare_only:
        run_compare_only()
        return 0

    if args.pass_label:
        if not args.target:
            print("ERROR: --pass-label requires --target", file=sys.stderr)
            return 1
        if not args.timing:
            print("ERROR: --pass-label requires --timing", file=sys.stderr)
            return 1
        for tname in args.target.split(","):
            run_single_pass(tname.strip(), args.pass_label, args.timing, args.timeout)
        return 0

    if args.target:
        targets = [n.strip() for n in args.target.split(",")]
    else:
        targets = list(LLM_TARGETS)

    run_validation(targets, dry_run=args.dry_run, timeout=args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
