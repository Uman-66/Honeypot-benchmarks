#!/usr/bin/env python3
"""
harness/analyze.py
Reads results/raw/*.jsonl and results/raw_http/*.jsonl, writes:
  results/summary.md
  results/summary.csv

Standard library + PyYAML only.  No pandas / numpy / matplotlib.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import glob
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    csv.field_size_limit(2**31 - 1)
except OverflowError:
    csv.field_size_limit(2**30)

# ── Constants ─────────────────────────────────────────────────────────────────

ENCODING = "utf-8"
RAW_SSH_DIR  = Path("results/raw")
RAW_HTTP_DIR = Path("results/raw_http")
SUMMARY_MD   = Path("results/summary.md")
SUMMARY_CSV  = Path("results/summary.csv")
COMMANDS_YAML = Path("harness/commands.yaml")
TARGETS_YAML  = Path("harness/targets.yaml")

TRAP_MARKERS = [
    "Filesystem locked",
    "Identity service locked",
    "Process manager locked",
    "System not initialized",
    "Disk subsystem offline",
]

# Commands whose output should be consistent across honest shells
# (host_specific = false)
_COMPARABLE_IDS: set[str] = set()
# Populated after loading commands.yaml

_ANSI_RE  = re.compile(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\[[0-9;]*m')
_LIT_RE   = re.compile(r'(?:\\x1b|\\u001b|\\033)\[[0-9;]*[A-Za-z]')
_THINK_RE = re.compile(r'<think>', re.IGNORECASE)
_FENCE_RE = re.compile(r'```')
_SHELL_PROMPT_RE = re.compile(r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s")
SIMILARITY_TEXT_LIMIT = 4000
_AI_RE    = re.compile(r'as an ai|i cannot|i\'m sorry', re.IGNORECASE)

_SECRET_PATTERNS = ["AKIAIOSFODNN7EXAMPLE", "EXAMPLE"]

def _strip_ansi(s: str) -> str:
    return _LIT_RE.sub('', _ANSI_RE.sub('', s))

# ── Cross-target masking (Stage 2) ────────────────────────────────────────────
#
# Reviewer point (c): ground-truth determinism was never reported, and nothing was
# masked, so a 0.98 on the ground truth and a 0.47 on a honeypot were not measured
# on the same basis.  These rules remove the parts of an output that *must* differ
# between two honest shells because they change between runs, and keep the parts
# that should be stable (command semantics, wording, layout).

MASK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # ISO / RFC3339 dates first, so the clock-time rule cannot eat them piecemeal.
    ("<DATE>", re.compile(
        r"\b\d{4}-\d{2}-\d{2}"
        r"(?:[T ]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b")),
    # `date` output: "Thu Nov  6 14:03:19 UTC 2026"
    ("<DATE>", re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,]?\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?(?:\s+[A-Z]{2,5})?(?:\s+\d{4})?\b")),
    # `ls -l` style: "Nov  6 14:03"
    ("<TIME>", re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+"
        r"\d{1,2}:\d{2}(?::\d{2})?\b")),
    # Bare clock times; the lookbehind keeps "127.0.0.1:8080" out of this rule.
    ("<TIME>", re.compile(r"(?<![\d.:])\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\b")),
    ("<UPTIME>", re.compile(
        r"\bup\s+\d+\s+(?:days?|hours?|minutes?|mins?)[^,\n]*", re.IGNORECASE)),
    ("<LOAD>", re.compile(r"load averages?:[^\n]*", re.IGNORECASE)),
    ("<PID>", re.compile(r"\bpid[=:\s]+\d+\b", re.IGNORECASE)),
    ("<PID>", re.compile(r"\bPID\s+\d+\b")),
    ("<TTY>", re.compile(r"\bpts/\d+\b")),
    # Ports: 4-5 digits after a colon covers the ephemeral range without touching
    # service ports such as :22 or :80.
    ("<EPHEMERAL_PORT>", re.compile(r"(?<=[0-9]):\d{4,5}\b")),
)


def mask_text(text: str, hostnames: Iterable[str] = ()) -> str:
    """Return *text* with the volatile fields above replaced by placeholders."""
    if not text:
        return text
    masked = text
    for placeholder, pattern in MASK_RULES:
        masked = pattern.sub(placeholder, masked)
    # Hostnames are masked literally, and only the ones actually observed in this
    # batch, so a target's invented hostname is removed without guessing at shapes.
    for hostname in sorted(hostnames, key=len, reverse=True):
        if hostname and hostname in masked:
            masked = masked.replace(hostname, "<HOST>")
    return masked


def _collect_hostnames(records_by_target: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Hostnames observed via `hostname` output or a `user@host:` prompt."""
    names: set[str] = set()
    for records in records_by_target.values():
        for record in records:
            text = record.get("cleaned_output") or ""
            if record.get("cmd_id") == "hostname" and text.strip():
                first = text.strip().splitlines()[0].strip()
                if " " not in first and 2 <= len(first) <= 64:
                    names.add(first)
            for match in re.finditer(r"[\w.-]+@([\w.-]+):", text):
                names.add(match.group(1))
    names.discard("")
    return names


def _mask_records(
    records_by_target: dict[str, list[dict[str, Any]]],
    hostnames: Iterable[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return a masked copy of *records_by_target* (only cleaned_output changes)."""
    names = set(hostnames) if hostnames is not None else _collect_hostnames(records_by_target)
    masked: dict[str, list[dict[str, Any]]] = {}
    for target, records in records_by_target.items():
        masked[target] = []
        for record in records:
            copy = dict(record)
            if isinstance(copy.get("cleaned_output"), str):
                copy["cleaned_output"] = mask_text(copy["cleaned_output"], names)
            masked[target].append(copy)
    return masked

# ── Data loading ──────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _load_all_ssh() -> dict[str, list[dict[str, Any]]]:
    """Returns {target_name: [all records across all runs]}"""
    data: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(RAW_SSH_DIR.glob("*.jsonl")):
        stem = path.stem  # e.g. deceive_run01
        parts = stem.rsplit("_run", 1)
        if len(parts) != 2:
            continue
        tname = parts[0]
        records = _load_jsonl(path)
        data.setdefault(tname, []).extend(records)
    return data


def _load_all_http() -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(RAW_HTTP_DIR.glob("*.jsonl")):
        stem = path.stem
        parts = stem.rsplit("_run", 1)
        if len(parts) != 2:
            continue
        tname = parts[0]
        records = _load_jsonl(path)
        data.setdefault(tname, []).extend(records)
    return data

# ── Statistics helpers ────────────────────────────────────────────────────────

def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    idx = p / 100 * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _latency_stats(vals: list[float], timeout_count: int = 0) -> dict[str, float]:
    if not vals:
        return {"mean": float("nan"), "median": float("nan"),
                "p95": float("nan"), "max": float("nan"), "n": 0,
                "timeout_count": timeout_count}
    return {
        "mean":   round(statistics.mean(vals), 3),
        "median": round(statistics.median(vals), 3),
        "p95":    round(_pct(vals, 95), 3),
        "max":    round(max(vals), 3),
        "n":      len(vals),
        "timeout_count": timeout_count,
    }


def _comparison_text(text: str) -> tuple[str, bool]:
    normalized = _ANSI_RE.sub("", text)
    return normalized[:SIMILARITY_TEXT_LIMIT], len(normalized) > SIMILARITY_TEXT_LIMIT


def _similarity(
    a: str,
    b: str,
    truncation_counter: list[int] | None = None,
) -> float:
    compared_a, truncated_a = _comparison_text(a)
    compared_b, truncated_b = _comparison_text(b)
    if truncation_counter is not None and (truncated_a or truncated_b):
        truncation_counter[0] += 1
    return difflib.SequenceMatcher(None, compared_a, compared_b).ratio()


def _mean_pairwise_sim(
    texts: list[str],
    truncation_counter: list[int] | None = None,
) -> float:
    if len(texts) < 2:
        return float("nan")
    pairs = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            pairs.append(_similarity(texts[i], texts[j], truncation_counter))
    return round(statistics.mean(pairs), 4) if pairs else float("nan")


def _output_length_stats(outputs: list[str]) -> dict[str, int | float | None]:
    lengths = [len(output) for output in outputs]
    return {
        "median": round(statistics.median(lengths), 1) if lengths else None,
        "p95": round(_pct([float(length) for length in lengths], 95), 1) if lengths else None,
        "max": max(lengths) if lengths else None,
        "oversized_outputs": sum(length > 20_000 for length in lengths),
    }


def _has_transcript_leakage(text: str) -> bool:
    matches = list(_SHELL_PROMPT_RE.finditer(text))
    if not matches:
        return False
    lines = text.splitlines()
    last_nonempty = next(
        (index for index in range(len(lines) - 1, -1, -1) if lines[index].strip()),
        None,
    )
    if last_nonempty is None:
        return False
    return any(
        text.count("\n", 0, match.start()) < last_nonempty
        for match in matches
    )


def _progress(target: str, metric: str) -> None:
    print(f"[analyze] {target}: {metric}", flush=True)

# ── SSH analysis ──────────────────────────────────────────────────────────────

def _analyze_ssh_target(
    tname: str,
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]] | None,
    kind: str,
    cmd_map: dict[str, dict],
    determinism_kinds: set[str] | None = None,
) -> dict[str, Any]:
    """Compute per-target SSH metrics."""
    out: dict[str, Any] = {"target": tname, "kind": kind}

    if not records:
        out["error"] = "no records found"
        return out

    # Only known benchmark commands are usable; exit and connection-error rows
    # are retained in the audit counts but excluded from command metrics.
    known_ids = set(cmd_map)
    cmd_records = [
        r for r in records
        if r.get("cmd_id") in known_ids and r.get("cmd_id") != "exit"
    ]
    truncation_counter = [0]
    _progress(tname, "output lengths")
    outputs = [r.get("cleaned_output") or "" for r in cmd_records]
    out["output_length_stats"] = _output_length_stats(outputs)
    out["transcript_leakage"] = {
        "leaked": sum(_has_transcript_leakage(output) for output in outputs),
        "total": len(outputs),
    }
    out["transcript_leakage"]["rate"] = (
        round(out["transcript_leakage"]["leaked"] / len(outputs), 4)
        if outputs else None
    )
    out["similarity_comparisons_truncated"] = 0
    exit_records = [r for r in records if r.get("cmd_id") == "exit"]
    malformed_records = [
        r for r in records
        if r.get("cmd_id") not in known_ids and r.get("cmd_id") != "exit"
    ]
    run_numbers = [int(r.get("run")) for r in records if str(r.get("run", "")).isdigit()]
    expected_runs = max(run_numbers, default=0)
    expected_commands = len([cid for cid, cmd in cmd_map.items() if cid != "exit"])
    out["accounting"] = {
        "n_expected": expected_runs * expected_commands,
        "n_used": len(cmd_records),
        "n_raw": len(records),
        "n_excluded_exit": len(exit_records),
        "n_excluded_malformed": len(malformed_records),
        "exclusion_reason": (
            "exit records are harness control rows; malformed rows lack a known "
            "command id and are not benchmark observations"
        ),
    }

    # ── Latency ──────────────────────────────────────────────────────────────
    _progress(tname, "latency")
    n_timeout = sum(1 for r in cmd_records if r.get("timed_out"))
    latencies = [
        r["latency_s"] for r in cmd_records
        if r.get("latency_s") is not None and not r.get("timed_out")
    ]
    out["latency_all"] = _latency_stats(latencies, n_timeout)

    cat_latencies: dict[str, list[float]] = {}
    for r in cmd_records:
        cat = r.get("category", "unknown")
        if r.get("latency_s") is not None and not r.get("timed_out"):
            cat_latencies.setdefault(cat, []).append(r["latency_s"])
    out["latency_by_category"] = {
        cat: _latency_stats(vals) for cat, vals in cat_latencies.items()
    }

    # ── Reliability ──────────────────────────────────────────────────────────
    _progress(tname, "reliability")
    n_total   = len(cmd_records)
    n_empty   = sum(1 for r in cmd_records if not (r.get("cleaned_output") or "").strip())
    runs_seen = set(r.get("run") for r in records)
    n_runs    = len(runs_seen)

    # Count runs that had a connection_error in run_meta
    n_conn_err = 0
    for r in records:
        rm = r.get("run_meta") or {}
        if rm.get("connection_error"):
            n_conn_err += 1
            break  # count per-run; rough

    exit_closes = [
        r.get("exit_closes_session", False)
        for r in exit_records
    ]
    out["reliability"] = {
        "n_runs":          n_runs,
        "n_commands_total": n_total,
        "n_timeouts":      n_timeout,
        "timeout_rate":    round(n_timeout / n_total, 4) if n_total else None,
        "n_empty_outputs": n_empty,
        "exit_closes_session_rate": (
            round(sum(exit_closes) / len(exit_closes), 3) if exit_closes else None
        ),
    }

    # ── Artifacts ─────────────────────────────────────────────────────────────
    _progress(tname, "artifacts")
    n_lit_esc = sum(1 for r in cmd_records if r.get("literal_escape_text_present"))
    n_think   = sum(1 for r in cmd_records if _THINK_RE.search(r.get("cleaned_output", "")))
    n_fence   = sum(1 for r in cmd_records if _FENCE_RE.search(r.get("cleaned_output", "")))
    n_ai      = sum(1 for r in cmd_records if _AI_RE.search(r.get("cleaned_output", "")))

    # Prompt contamination: any trap marker visible in cleaned output
    n_contaminated = sum(
        1 for r in cmd_records
        if any(m in (r.get("cleaned_output") or "") for m in TRAP_MARKERS)
    )

    out["artifacts"] = {
        "literal_escape_text_cmds": n_lit_esc,
        "think_tag_cmds":           n_think,
        "markdown_fence_cmds":      n_fence,
        "ai_refusal_cmds":          n_ai,
        "prompt_contamination_cmds": n_contaminated,
    }

    # ── Fidelity vs ground truth (excluded for detector) ─────────────────────
    _progress(tname, "fidelity")
    if kind != "detector" and gt_records:
        # Build map: cmd_id → list of cleaned outputs (gt)
        gt_map: dict[str, list[str]] = {}
        for r in gt_records:
            cid = r.get("cmd_id", "")
            gt_map.setdefault(cid, []).append(r.get("cleaned_output") or "")

        # comparable: host_specific = false
        comparable_ids = {
            cid for cid, cmd in cmd_map.items()
            if not cmd.get("host_specific", True)
        }

        fid_comparable: list[float] = []
        exact_comparable = 0
        total_comparable = 0
        fid_host: list[float] = []

        for r in cmd_records:
            cid = r.get("cmd_id", "")
            if cid not in gt_map:
                continue
            gt_texts = gt_map[cid]
            if not gt_texts:
                continue
            # Use median GT output (most common run)
            gt_ref = gt_texts[0]
            our    = r.get("cleaned_output") or ""
            sim    = _similarity(our, gt_ref, truncation_counter)
            if cid in comparable_ids:
                fid_comparable.append(sim)
                if our.strip() == gt_ref.strip():
                    exact_comparable += 1
                total_comparable += 1
            else:
                fid_host.append(sim)

        out["fidelity"] = {
            "comparable_mean_sim":  round(statistics.mean(fid_comparable), 4) if fid_comparable else None,
            "comparable_exact_rate": round(exact_comparable / total_comparable, 4) if total_comparable else None,
            "n": total_comparable,
            "host_specific_mean_sim_reference_only": round(statistics.mean(fid_host), 4) if fid_host else None,
            "note": "host_specific=true commands are reference only; persona/hostname differences make comparison meaningless",
        }
    elif kind == "detector":
        out["fidelity"] = "excluded (detector target)"

    # ── State consistency ─────────────────────────────────────────────────────
    # Group by run
    by_run: dict[int, dict[str, str]] = {}
    for r in cmd_records:
        run = r.get("run", 0)
        by_run.setdefault(run, {})[r.get("cmd_id", "")] = (r.get("cleaned_output") or "").strip()

    state_checks: list[dict[str, Any]] = []
    for run, cmap in sorted(by_run.items()):
        pwd_after_cd = cmap.get("state_pwd_after_cd", "")
        cat_marker   = cmap.get("state_cat_marker", "")
        ls_tmp1      = cmap.get("state_ls_tmp_1", "")
        ls_tmp2      = cmap.get("state_ls_tmp_2", "")
        ls_tmp3      = cmap.get("state_ls_tmp_3", "")
        whoami_out   = cmap.get("whoami", "").strip().lower()
        id_out       = cmap.get("id", "")
        hostname_out = cmap.get("hostname", "").strip()

        # Extract user from id output: uid=...(user)
        id_user_m = re.search(r'uid=\d+\(([^)]+)\)', id_out)
        id_user = id_user_m.group(1).lower() if id_user_m else None

        def check_value(command_id: str, expected: bool) -> bool | str:
            record = next((r for r in cmd_records
                           if r.get("run") == run and r.get("cmd_id") == command_id), None)
            if record and record.get("timed_out"):
                return "invalid (timeout)"
            return expected

        state_checks.append({
            "run": run,
            "pwd_after_cd_is_tmp": check_value("state_pwd_after_cd", pwd_after_cd == "/tmp"),
            "cat_marker_correct":  check_value("state_cat_marker", "benchmark_marker" in cat_marker),
            "ls_tmp1_has_bm_txt":  check_value("state_ls_tmp_1", "bm.txt" in ls_tmp1),
            "ls_tmp2_has_bm_dir":  check_value("state_ls_tmp_2", "bm_dir" in ls_tmp2),
            "ls_tmp3_no_bm_txt":   check_value("state_ls_tmp_3", "bm.txt" not in ls_tmp3),
            "whoami_matches_id":   check_value("id", (id_user is None) or (whoami_out == id_user)),
        })

    out["state_consistency"] = state_checks
    out["state_valid_denominator"] = sum(
        1 for row in state_checks for value in row.values()
        if value not in ("run", "invalid (timeout)")
    )

    expected_empty_ids: set[str] = set()
    if gt_records:
        gt_by_cmd: dict[str, list[dict[str, Any]]] = {}
        for record in gt_records:
            if record.get("cmd_id") in known_ids:
                gt_by_cmd.setdefault(record["cmd_id"], []).append(record)
        expected_empty_ids = {
            cid for cid, values in gt_by_cmd.items()
            if sum(not (r.get("cleaned_output") or "").strip() for r in values) >= 4
        }
    unexpected_empty: dict[str, int] = {}
    spurious_nonempty: dict[str, int] = {}
    for record in cmd_records:
        cid = record.get("cmd_id", "")
        is_empty = not (record.get("cleaned_output") or "").strip()
        if is_empty and cid not in expected_empty_ids:
            unexpected_empty[cid] = unexpected_empty.get(cid, 0) + 1
        if not is_empty and cid in expected_empty_ids:
            spurious_nonempty[cid] = spurious_nonempty.get(cid, 0) + 1
    out["empty_output_comparison"] = {
        "expected_empty_commands": sorted(expected_empty_ids),
        "unexpected_empty": unexpected_empty,
        "spurious_nonempty": spurious_nonempty,
    }

    # ── LLM determinism (pairwise similarity across runs) ─────────────────────
    # Stage 2 adds "groundtruth" here when the caller asks for it, so the baseline
    # and the honeypots are measured on the same basis.
    if kind in (determinism_kinds or {"llm", "baseline"}):
        _progress(tname, "determinism")
        det: dict[str, float] = {}
        for r in cmd_records:
            cid = r.get("cmd_id", "")
            det.setdefault(cid, []).append(r.get("cleaned_output") or "")
        det_means = {
            cid: _mean_pairwise_sim(texts, truncation_counter)
            for cid, texts in det.items()
            if len(texts) >= 2
        }
        if det_means:
            valid = [v for v in det_means.values() if not math.isnan(v)]
            out["determinism"] = {
                "per_command": det_means,
                "overall_mean": round(statistics.mean(valid), 4) if valid else None,
            }
    out["similarity_comparisons_truncated"] = truncation_counter[0]

    # ── Detector section ─────────────────────────────────────────────────────
    if kind == "detector":
        # Commands whose outputs the llm-honeypot injects trap markers into.
        # Includes ls variants and df variants by id suffix.
        detector_cmds = {
            "pwd", "whoami",
            "ps_aux",
            "ls", "ls_la", "ls_etc", "ls_home",
            "state_ls_tmp_1", "state_ls_tmp_2", "state_ls_tmp_3",
            "df_h",
        }
        det_section: dict[str, Any] = {}
        for r in cmd_records:
            cid = r.get("cmd_id", "")
            if cid not in detector_cmds:
                continue
            found = r.get("trap_markers_found") or []
            visible = [m for m in found if m in (r.get("cleaned_output") or "")]
            det_section.setdefault(cid, []).append({
                "run": r.get("run"),
                "trap_markers_in_raw": found,
                "trap_markers_visible_in_clean": visible,
            })
        out["detector_trap_analysis"] = det_section

    return out


# ── HTTP analysis ─────────────────────────────────────────────────────────────

def _analyze_http_target(
    tname: str,
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]] | None,
    kind: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {"target": tname, "kind": kind}
    truncation_counter = [0]

    if not records:
        out["error"] = "no records found"
        return out

    # Status distribution
    _progress(tname, "status distribution")
    status_counts: dict[str, int] = {}
    for r in records:
        s = str(r.get("status") or "error")
        status_counts[s] = status_counts.get(s, 0) + 1
    out["status_distribution"] = status_counts
    out["5xx_rate"] = round(
        sum(v for k, v in status_counts.items() if k.startswith("5")) / len(records), 4
    )

    # Server header consistency
    _progress(tname, "headers")
    server_vals = [r.get("server_header") for r in records if r.get("server_header")]
    out["server_header_values"] = sorted(set(v for v in server_vals if v))
    out["server_header_constant"] = len(set(v for v in server_vals if v)) <= 1

    # Content-Length mismatches
    _progress(tname, "content length")
    cl_mismatches = sum(
        1 for r in records
        if r.get("content_length_match") is False
    )
    out["content_length_mismatches"] = cl_mismatches

    # Chunked responses
    n_chunked = sum(1 for r in records if r.get("chunked"))
    out["chunked_responses"] = n_chunked

    # Date drift
    drifts = [r["date_drift_s"] for r in records if r.get("date_drift_s") is not None]
    out["date_drift_stats"] = _latency_stats(drifts) if drifts else None

    # Header-name set consistency for same path across runs
    # Group by (method, path)
    by_path: dict[tuple[str, str], list[set[str]]] = {}
    for r in records:
        key = (r.get("method", ""), r.get("path", ""))
        headers = set((r.get("response_headers") or {}).keys())
        by_path.setdefault(key, []).append(headers)
    header_inconsistencies = 0
    for (method, path), header_sets in by_path.items():
        if len(header_sets) > 1:
            ref = header_sets[0]
            if any(hs != ref for hs in header_sets[1:]):
                header_inconsistencies += 1
    out["header_set_inconsistencies_across_runs"] = header_inconsistencies

    # Documentation-example secrets in body
    _progress(tname, "body checks")
    bodies = [r.get("body") or "" for r in records]
    secret_hits = sum(
        1 for b in bodies if any(p in b for p in _SECRET_PATTERNS)
    )
    out["documentation_secret_hits"] = secret_hits

    # Responses mentioning the host port
    port_hits = sum(
        1 for r in records
        if str(r.get("path", "")) and str(r.get("status", "")) != "None"
        and _port_mentioned(r)
    )
    out["responses_mentioning_port"] = port_hits

    # Latency
    _progress(tname, "latency")
    n_http_timeout = sum(1 for r in records if r.get("timed_out"))
    lats = [
        r["latency_s"] for r in records
        if r.get("latency_s") is not None and not r.get("timed_out")
    ]
    out["latency"] = _latency_stats(lats, n_http_timeout)
    out["timeout_count"] = n_http_timeout
    out["timeout_rate"] = round(n_http_timeout / len(records), 4) if records else None

    # Determinism: three GET / repeats
    _progress(tname, "determinism")
    repeat_ids = ["get_root_repeat1", "get_root_repeat2", "get_root_repeat3"]
    repeat_bodies = [
        r.get("body") or ""
        for r in records if r.get("id") in repeat_ids
    ]
    if len(repeat_bodies) >= 2:
        sims = []
        for i in range(len(repeat_bodies)):
            for j in range(i + 1, len(repeat_bodies)):
                sims.append(_similarity(
                    repeat_bodies[i], repeat_bodies[j], truncation_counter
                ))
        out["get_root_repeat_similarity"] = round(statistics.mean(sims), 4) if sims else None
    else:
        out["get_root_repeat_similarity"] = None

    # Status agreement with nginx ground truth on identical paths
    if gt_records and kind != "groundtruth":
        gt_status_map: dict[tuple[str, str], int] = {}
        for r in gt_records:
            key = (r.get("method", ""), r.get("path", ""))
            if r.get("status"):
                gt_status_map[key] = r["status"]
        agreements = 0
        comparisons = 0
        for r in records:
            key = (r.get("method", ""), r.get("path", ""))
            if key in gt_status_map and r.get("status"):
                comparisons += 1
                if r["status"] == gt_status_map[key]:
                    agreements += 1
        out["status_agreement_with_gt"] = {
            "agreements": agreements,
            "comparisons": comparisons,
            "rate": round(agreements / comparisons, 4) if comparisons else None,
        }

    out["similarity_comparisons_truncated"] = truncation_counter[0]
    return out


def _port_mentioned(r: dict[str, Any]) -> bool:
    """True if the response body mentions a port number that looks like a target port."""
    body = r.get("body") or ""
    # Look for common port numbers in context
    common_ports = ["8088", "2226", "2225", "2222", "2223", "2224", "2227", "8022"]
    return any(p in body for p in common_ports)


def _add_shared_fidelity(
    results: list[dict[str, Any]],
    records_by_target: dict[str, list[dict[str, Any]]],
    gt_records: list[dict[str, Any]],
    cmd_map: dict[str, dict[str, Any]],
) -> None:
    """Add command-shared fidelity and a deterministic bootstrap confidence interval."""
    compared = [
        result for result in results
        if result.get("kind") not in {"detector", "groundtruth"}
    ]
    comparable_ids = {
        cid for cid, command in cmd_map.items()
        if cid != "exit" and not command.get("host_specific", True)
    }
    gt_by_cmd: dict[str, str] = {}
    for record in gt_records:
        if record.get("cmd_id") in comparable_ids and record["cmd_id"] not in gt_by_cmd:
            gt_by_cmd[record["cmd_id"]] = record.get("cleaned_output") or ""
    available_by_target: dict[str, set[str]] = {}
    for result in compared:
        target = result["target"]
        available_by_target[target] = {
            cid for cid in comparable_ids
            if any(
                record.get("cmd_id") == cid and not record.get("timed_out")
                for record in records_by_target.get(target, [])
            )
        }
    shared = set(gt_by_cmd)
    for ids in available_by_target.values():
        shared &= ids

    for result in results:
        target = result["target"]
        if target not in available_by_target:
            continue
        _progress(target, "shared fidelity")
        truncation_counter = [result.get("similarity_comparisons_truncated", 0)]
        values_by_command: dict[str, list[float]] = {cid: [] for cid in shared}
        for record in records_by_target.get(target, []):
            cid = record.get("cmd_id")
            if cid in values_by_command and not record.get("timed_out"):
                values_by_command[cid].append(
                    _similarity(
                        record.get("cleaned_output") or "",
                        gt_by_cmd[cid],
                        truncation_counter,
                    )
                )
        command_values = [
            statistics.mean(values)
            for cid, values in sorted(values_by_command.items())
            if values
        ]
        rng = random.Random(20261106)
        bootstrap_means: list[float] = []
        if command_values:
            for _ in range(1000):
                sample = [command_values[rng.randrange(len(command_values))]
                           for _ in command_values]
                bootstrap_means.append(statistics.mean(sample))
        result["fidelity_shared"] = {
            "n": len(command_values),
            "mean_sim": round(statistics.mean(command_values), 4) if command_values else None,
            "bootstrap_95_ci": (
                round(_pct(bootstrap_means, 2.5), 4),
                round(_pct(bootstrap_means, 97.5), 4),
            ) if bootstrap_means else None,
            "note": "difflib ratio is only a proxy; shared commands are non-host-specific and non-timeout for all compared targets",
        }
        result["similarity_comparisons_truncated"] = truncation_counter[0]


# ── Markdown rendering ────────────────────────────────────────────────────────

def _fmt(v: Any, decimals: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return f"{v:.{decimals}f}"
    return str(v)


def _render_latency(d: dict[str, float]) -> str:
    if not d:
        return "—"
    return (
        f"median={_fmt(d.get('median'))}s  p95={_fmt(d.get('p95'))}s  "
        f"(non-timeout n={d.get('n',0)}, timeouts={d.get('timeout_count', 0)})"
    )


def _build_markdown(
    ssh_results: list[dict[str, Any]],
    http_results: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Honeypot Benchmark — Summary Report")
    a("")
    if any(
        res.get("accounting", {}).get("n_used") != res.get("accounting", {}).get("n_expected")
        for res in ssh_results
    ):
        a("> **WARNING: observed rows differ from expected benchmark rows; see each target's documented exclusions.**")
        a("")
    a("> **Caveats and methodology notes**")
    a("> - Similarity to the SSH ground truth is a rough proxy only.")
    a(">   LLM honeypots use different personas, hostnames, and invented filesystems;")
    a(">   direct output comparison is biased against them.")
    a("> - AdvancedshelLM runs an extra wrapper layer (different persona, internal LLM calls),")
    a(">   so latency and output style differ from direct-prompt honeypots.")
    a("> - Beelzebub seeds its conversation with a `pwd`/home exchange before the benchmark")
    a(">   commands arrive, which may affect state-dependent commands.")
    a("> - Cowrie and llm-honeypot share a static fake filesystem; their `ls`, `cat`, and")
    a(">   state commands will always match each other but not necessarily the ground truth.")
    a("> - Different honeypots use different hostnames and usernames; host-specific commands")
    a(">   (marked `host_specific: true`) are listed for reference only and excluded from")
    a(">   fidelity scoring.")
    a("> - The ground truth container is a plain Ubuntu 20.04 system with no special persona;")
    a(">   persona-dependent content in LLM honeypots cannot be expected to match it.")
    a("> - The llm-honeypot detector target is **excluded** from fidelity, similarity,")
    a(">   pairwise determinism, and aggregate averages; it has its own section.")
    a("> - All numbers are computed from files in `results/raw/` and `results/raw_http/`.")
    a(">   If those files are missing, the corresponding fields show `—`.")
    a("")
    a("---")
    a("")

    # ── SSH section ───────────────────────────────────────────────────────────
    a("## SSH Targets")
    a("")

    detector_result: dict[str, Any] | None = None

    for res in ssh_results:
        tname = res["target"]
        kind  = res["kind"]

        if kind == "detector":
            detector_result = res
            continue  # handled separately

        a(f"### {tname}  *(kind: {kind})*")
        a("")

        if res.get("error"):
            a(f"**ERROR**: {res['error']}")
            a("")
            continue

        accounting = res.get("accounting", {})
        a(f"**Accounting:** n_expected={accounting.get('n_expected', '—')}, "
          f"n_used={accounting.get('n_used', '—')}")
        if accounting.get("n_used") != accounting.get("n_expected"):
            excluded = accounting.get("n_expected", 0) - accounting.get("n_used", 0)
            a(f"> **WARNING:** excluded {excluded} rows — "
              f"{accounting.get('exclusion_reason', 'see audit')}.")
        a("")

        # Latency
        lengths = res.get("output_length_stats", {})
        leakage = res.get("transcript_leakage", {})
        a("**Output lengths**")
        a("")
        a(f"- Median: {lengths.get('median', '—')} characters")
        a(f"- p95: {lengths.get('p95', '—')} characters")
        a(f"- Maximum: {lengths.get('max', '—')} characters")
        a(f"- Oversized outputs (>20,000 characters): {lengths.get('oversized_outputs', 0)}")
        a(
            f"- Transcript leakage: {leakage.get('leaked', 0)}/"
            f"{leakage.get('total', 0)}"
        )
        a(
            f"- Similarity comparisons truncated: "
            f"{res.get('similarity_comparisons_truncated', 0)}"
        )
        a("")

        # Latency
        a("**Latency (all commands)**")
        a("")
        a("| Stat | Value |")
        a("|------|-------|")
        lat = res.get("latency_all", {})
        for k in ("median", "p95"):
            a(f"| {k} | {_fmt(lat.get(k))}s |")
        a(f"| n | {lat.get('n', 0)} |")
        a("")

        # Latency by category
        by_cat = res.get("latency_by_category", {})
        if by_cat:
            a("**Latency by category**")
            a("")
            a("| Category | Mean | p95 | n |")
            a("|----------|------|-----|---|")
            for cat, cs in sorted(by_cat.items()):
                a(f"| {cat} | {_fmt(cs.get('mean'))}s | {_fmt(cs.get('p95'))}s | {cs.get('n',0)} |")
            a("")

        # Reliability
        rel = res.get("reliability", {})
        a("**Reliability**")
        a("")
        a(f"- Runs: {rel.get('n_runs', '—')}")
        a(f"- Commands: {rel.get('n_commands_total', '—')}")
        a(f"- Timeouts: {rel.get('n_timeouts', '—')}")
        a(f"- Empty outputs: {rel.get('n_empty_outputs', '—')}")
        ecr = rel.get("exit_closes_session_rate")
        a(f"- exit_closes_session rate: {_fmt(ecr) if ecr is not None else '—'}")
        a("")

        # Artifacts
        art = res.get("artifacts", {})
        a("**LLM Artifacts**")
        a("")
        a(f"- Literal escape codes in output: {art.get('literal_escape_text_cmds', 0)} commands")
        a(f"- `<think>` tags: {art.get('think_tag_cmds', 0)} commands")
        a(f"- Markdown fences: {art.get('markdown_fence_cmds', 0)} commands")
        a(f"- AI-refusal phrases: {art.get('ai_refusal_cmds', 0)} commands")
        a(f"- Prompt contamination (trap markers visible in clean): {art.get('prompt_contamination_cmds', 0)}")
        a("")

        # Fidelity
        fid = res.get("fidelity")
        if fid and isinstance(fid, dict):
            a("**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*")
            a("")
            shared = res.get("fidelity_shared", {})
            a(f"- Mean similarity (difflib ratio): {_fmt(shared.get('mean_sim'), 4)}")
            a(f"- Bootstrap 95% CI: {shared.get('bootstrap_95_ci', '—')}")
            a(f"- Shared command count: {shared.get('n', 0)}")
            a("- difflib ratio is only a proxy.")
            a("")
        elif isinstance(fid, str):
            a(f"**Fidelity**: {fid}")
            a("")

        # State consistency
        sc = res.get("state_consistency", [])
        if sc:
            a("**State Consistency**")
            a("")
            a("| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |")
            a("|-----|----------|------------|---------------|---------------|--------------|-----------|")
            for row in sc:
                a(
                    f"| {row['run']} "
                    f"| {'✓' if row.get('pwd_after_cd_is_tmp') else '✗'} "
                    f"| {'✓' if row.get('cat_marker_correct') else '✗'} "
                    f"| {'✓' if row.get('ls_tmp1_has_bm_txt') else '✗'} "
                    f"| {'✓' if row.get('ls_tmp2_has_bm_dir') else '✗'} "
                    f"| {'✓' if row.get('ls_tmp3_no_bm_txt') else '✗'} "
                    f"| {'✓' if row.get('whoami_matches_id') else '✗'} |"
                )
            a("")

        if sc:
            a(f"State valid denominator: {res.get('state_valid_denominator', 0)} checks")
            a("State result value `invalid (timeout)` denotes a censored dependent command.")
            a("")

        if tname != "groundtruth_ssh":
            empty = res.get("empty_output_comparison", {})
            a("**Empty-output comparison with groundtruth_ssh**")
            a("")
            a(f"- Expected-empty commands (empty in >=4/5 GT runs): "
              f"{empty.get('expected_empty_commands', []) or 'none'}")
            a(f"- unexpected_empty: {empty.get('unexpected_empty', {}) or 'none'}")
            a(f"- spurious_nonempty: {empty.get('spurious_nonempty', {}) or 'none'}")
            a("")

        # Determinism
        det = res.get("determinism")
        if det:
            a(f"**Determinism** (mean pairwise similarity across runs): "
              f"{_fmt(det.get('overall_mean'), 4)}")
            a("")

        a("---")
        a("")

    # ── Detector section ──────────────────────────────────────────────────────
    a("## Detector Target: llm-honeypot")
    a("")
    a("*This target is excluded from all fidelity, similarity, and aggregate metrics.*")
    a("")
    a("The llm-honeypot Cowrie fork hides prompt-injection instructions in ANSI")
    a("conceal sequences (ESC[8m … ESC[0m) in the output of `pwd`, `whoami`, `ps`,")
    a("`ls`, and `df`.  The harness records whether the trap markers appear in the")
    a("raw output and whether they survive ANSI stripping into the cleaned output.")
    a("")

    if detector_result and not detector_result.get("error"):
        lengths = detector_result.get("output_length_stats", {})
        leakage = detector_result.get("transcript_leakage", {})
        a(
            f"**Output lengths:** median={lengths.get('median', '—')}, "
            f"p95={lengths.get('p95', '—')}, max={lengths.get('max', '—')}; "
            f"oversized={lengths.get('oversized_outputs', 0)}"
        )
        a(
            f"**Transcript leakage:** {leakage.get('leaked', 0)}/"
            f"{leakage.get('total', 0)}"
        )
        a(
            f"**Similarity comparisons truncated:** "
            f"{detector_result.get('similarity_comparisons_truncated', 0)}"
        )
        a("")
        det_sec = detector_result.get("detector_trap_analysis", {})
        for cid, runs in sorted(det_sec.items()):
            a(f"**{cid}**")
            a("")
            for entry in runs:
                raw_m = entry.get("trap_markers_in_raw", [])
                vis_m = entry.get("trap_markers_visible_in_clean", [])
                a(f"- Run {entry.get('run')}: "
                  f"markers in raw = {raw_m or 'none'}; "
                  f"visible in clean = {vis_m or 'none'}")
            a("")
    else:
        if detector_result and detector_result.get("error"):
            a(f"**ERROR**: {detector_result['error']}")
        else:
            a("No data found for llm-honeypot.")
    a("")
    a("---")
    a("")

    # ── HTTP section ──────────────────────────────────────────────────────────
    a("## HTTP Targets")
    a("")

    for res in http_results:
        tname = res["target"]
        kind  = res["kind"]
        a(f"### {tname}  *(kind: {kind})*")
        a("")

        if res.get("error"):
            a(f"**ERROR**: {res['error']}")
            a("")
            continue

        # Status distribution
        sd = res.get("status_distribution", {})
        a("**Status distribution**")
        a("")
        a("| Status | Count |")
        a("|--------|-------|")
        for s, n in sorted(sd.items()):
            a(f"| {s} | {n} |")
        a("")
        a(f"- 5xx rate: {_fmt(res.get('5xx_rate'), 4)}")
        a(f"- Timeouts: {res.get('timeout_count', 0)} "
          f"({_fmt(res.get('timeout_rate'), 4)})")
        a("")

        # Server header
        svrs = res.get("server_header_values", [])
        a(f"**Server header values**: {svrs}  "
          f"({'constant' if res.get('server_header_constant') else 'VARIES'})")
        a("")

        # Content-Length and chunked
        a(f"- Content-Length mismatches: {res.get('content_length_mismatches', '—')} "
          f"(excess over groundtruth_http: {res.get('content_length_mismatch_excess', '—')})")
        a(f"- Chunked responses: {res.get('chunked_responses', '—')}")
        a("")

        # Date drift
        dds = res.get("date_drift_stats")
        if dds:
            a(f"**Date drift**: {_render_latency(dds)}")
            a("")

        # Header consistency
        a(f"- Header-name set inconsistencies across runs: {res.get('header_set_inconsistencies_across_runs', '—')}")
        a("")

        # Secrets / port mentions
        a(f"- Documentation-example secrets in body: {res.get('documentation_secret_hits', '—')}")
        a(f"- Responses mentioning target port: {res.get('responses_mentioning_port', '—')}")
        a("")

        # Latency
        a(f"**Latency**: {_render_latency(res.get('latency', {}))}")
        a("")

        # Determinism
        sim = res.get("get_root_repeat_similarity")
        a(f"**GET / repeat similarity**: {_fmt(sim, 4)}")
        a(
            f"**Similarity comparisons truncated:** "
            f"{res.get('similarity_comparisons_truncated', 0)}"
        )
        a("")

        # Ground-truth status agreement
        sag = res.get("status_agreement_with_gt")
        if sag:
            a(f"**Status agreement with nginx ground truth**: "
              f"{sag.get('agreements')}/{sag.get('comparisons')} "
              f"({_fmt(sag.get('rate'), 4)})")
            a("")

        a("---")
        a("")

    return "\n".join(lines)


# ── CSV summary ───────────────────────────────────────────────────────────────

_CSV_SUMMARY_FIELDS = [
    "target", "kind", "track",
    "latency_mean_s", "latency_p95_s",
    "n_timeouts", "n_empty_outputs",
    "literal_escape_cmds", "think_cmds", "fence_cmds", "ai_refusal_cmds",
    "fidelity_comparable_mean_sim", "fidelity_exact_rate",
    "determinism_mean",
    "output_length_median",
    "output_length_p95",
    "output_length_max",
    "oversized_outputs",
    "transcript_leakage",
    "transcript_leakage_total",
    "similarity_comparisons_truncated",
    "exit_closes_session_rate",
]


def _build_csv_rows(
    ssh_results: list[dict[str, Any]],
    http_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for res in ssh_results:
        lat = res.get("latency_all", {})
        rel = res.get("reliability", {})
        art = res.get("artifacts", {})
        fid = res.get("fidelity") or {}
        det = res.get("determinism") or {}
        lengths = res.get("output_length_stats", {})
        leakage = res.get("transcript_leakage", {})
        rows.append({
            "target": res["target"],
            "kind":   res["kind"],
            "track":  "ssh",
            "latency_mean_s":  lat.get("mean"),
            "latency_p95_s":   lat.get("p95"),
            "n_timeouts":      rel.get("n_timeouts"),
            "n_empty_outputs": rel.get("n_empty_outputs"),
            "literal_escape_cmds": art.get("literal_escape_text_cmds"),
            "think_cmds":      art.get("think_tag_cmds"),
            "fence_cmds":      art.get("markdown_fence_cmds"),
            "ai_refusal_cmds": art.get("ai_refusal_cmds"),
            "fidelity_comparable_mean_sim": fid.get("comparable_mean_sim") if isinstance(fid, dict) else None,
            "fidelity_exact_rate":          fid.get("comparable_exact_rate") if isinstance(fid, dict) else None,
            "determinism_mean": det.get("overall_mean"),
            "output_length_median": lengths.get("median"),
            "output_length_p95": lengths.get("p95"),
            "output_length_max": lengths.get("max"),
            "oversized_outputs": lengths.get("oversized_outputs"),
            "transcript_leakage": leakage.get("leaked"),
            "transcript_leakage_total": leakage.get("total"),
            "similarity_comparisons_truncated": res.get(
                "similarity_comparisons_truncated"
            ),
            "exit_closes_session_rate": rel.get("exit_closes_session_rate"),
        })

    for res in http_results:
        lat = res.get("latency", {})
        rows.append({
            "target": res["target"],
            "kind":   res["kind"],
            "track":  "http",
            "latency_mean_s": lat.get("mean"),
            "latency_p95_s":  lat.get("p95"),
            "n_timeouts": None,
            "n_empty_outputs": None,
            "literal_escape_cmds": None,
            "think_cmds": None,
            "fence_cmds": None,
            "ai_refusal_cmds": None,
            "fidelity_comparable_mean_sim": None,
            "fidelity_exact_rate": None,
            "determinism_mean": res.get("get_root_repeat_similarity"),
            "output_length_median": None,
            "output_length_p95": None,
            "output_length_max": None,
            "oversized_outputs": None,
            "transcript_leakage": None,
            "transcript_leakage_total": None,
            "similarity_comparisons_truncated": res.get(
                "similarity_comparisons_truncated"
            ),
            "exit_closes_session_rate": None,
        })

    return rows


def _build_run_rows(
    ssh_data: dict[str, list[dict[str, Any]]],
    http_data: dict[str, list[dict[str, Any]]],
    cmd_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    state_ids = {
        "state_pwd_after_cd", "state_cat_marker", "state_ls_tmp_1",
        "state_ls_tmp_2", "state_ls_tmp_3",
    }
    for target, records in ssh_data.items():
        runs = sorted({r.get("run") for r in records})
        for run in runs:
            current = [
                r for r in records
                if r.get("run") == run and r.get("cmd_id") in cmd_map
                and r.get("cmd_id") != "exit"
            ]
            state = [r for r in current if r.get("cmd_id") in state_ids]
            rows.append({
                "target": target,
                "run": run,
                "track": "ssh",
                "timeouts": sum(bool(r.get("timed_out")) for r in current),
                "empty_outputs": sum(not (r.get("cleaned_output") or "").strip() for r in current),
                "state_checks_passed": sum(
                    not r.get("timed_out") and bool((r.get("cleaned_output") or "").strip())
                    for r in state
                ),
                "state_checks_valid": sum(not r.get("timed_out") for r in state),
            })
    for target, records in http_data.items():
        runs = sorted({r.get("run") for r in records})
        for run in runs:
            current = [r for r in records if r.get("run") == run]
            rows.append({
                "target": target,
                "run": run,
                "track": "http",
                "timeouts": sum(bool(r.get("timed_out")) for r in current),
                "empty_outputs": sum(not (r.get("body") or "").strip() for r in current),
                "state_checks_passed": "",
                "state_checks_valid": "",
            })
    return rows


def _build_audit(
    ssh_data: dict[str, list[dict[str, Any]]],
    target_meta: dict[str, dict[str, Any]],
    cmd_map: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "# Analysis audit",
        "",
        "All counts below were computed from UTF-8 JSONL/CSV inputs; no result input was modified.",
        "",
        "| Target | Raw JSONL rows | CSV rows | Analyzer n_used | n_expected | Exclusions |",
        "|---|---:|---:|---:|---:|---|",
    ]
    csv_rows: list[dict[str, str]] = []
    csv_path = Path("results/ssh_commands_long.csv")
    if csv_path.exists():
        with csv_path.open(encoding=ENCODING, newline="") as fh:
            csv_rows = list(csv.DictReader(fh))
    expected_commands = len([cid for cid in cmd_map if cid != "exit"])
    for target in sorted(ssh_data):
        records = ssh_data[target]
        csv_count = sum(row.get("target") == target for row in csv_rows)
        runs = [int(r["run"]) for r in records if str(r.get("run", "")).isdigit()]
        expected = max(runs, default=0) * expected_commands
        used = sum(r.get("cmd_id") in cmd_map and r.get("cmd_id") != "exit" for r in records)
        exit_count = sum(r.get("cmd_id") == "exit" for r in records)
        malformed = len(records) - used - exit_count
        lines.append(
            f"| {target} | {len(records)} | {csv_count} | {used} | {expected} | "
            f"{exit_count} exit control rows; {malformed} malformed/unknown cmd_id rows; "
            f"{max(0, expected - used)} expected rows absent from raw JSONL |"
        )
    lines += [
        "",
        "## Where rows are dropped",
        "",
        "* `harness/analyze.py:65-75` loads every non-empty JSONL line and silently skips only invalid JSON.",
        "* The command filter in `_analyze_ssh_target` (`harness/analyze.py:162-178`) keeps known command IDs and excludes `exit`; "
        "connection-error rows have an empty `cmd_id` and are therefore excluded as malformed.",
        "* There is no analyzer deduplication and no category-based row drop; categories are only grouping labels "
        "(`harness/analyze.py:185-195`).",
        "* `harness/run_ssh.py:655-680` appends CSV rows independently, so CSV counts can exceed JSONL counts after reruns "
        "or when a run is partially written.",
    ]
    return "\n".join(lines) + "\n"


# ── Stage-2 masked comparison output ──────────────────────────────────────────

_V2_MASK_TABLE: tuple[tuple[str, str, str], ...] = (
    ("ISO dates / RFC3339 timestamps", "2026-11-06T14:03:19Z", "<DATE>"),
    ("`date`-style dates", "Thu Nov  6 14:03:19 UTC 2026", "<DATE>"),
    ("Clock times", "14:03:19", "<TIME>"),
    ("Uptime", "up 3 days,  2:14", "<UPTIME>"),
    ("Load average", "load average: 0.00, 0.01, 0.05", "<LOAD>"),
    ("PIDs", "pid=4711 / PID 4711", "<PID>"),
    ("TTY handles", "pts/3", "<TTY>"),
    ("Ports", "127.0.0.1:54321", "127.0.0.1<EPHEMERAL_PORT>"),
    ("Observed hostnames", "ubuntu-vbox, taken from hostname output and prompts", "<HOST>"),
)

_V2_FIELDS = [
    "target", "kind", "det_unmasked", "det_masked", "det_delta",
    "det_commands", "fidelity_raw_text", "fidelity_masked", "fidelity_delta",
    "fidelity_n", "ci_raw_text", "ci_masked",
]


def _ci_text(interval: Any) -> str:
    if not interval or len(interval) != 2:
        return ""
    return f"{interval[0]:.4f}-{interval[1]:.4f}"


def _v2_rows(
    ssh_data: dict[str, list[dict[str, Any]]],
    gt_records: list[dict[str, Any]],
    cmd_map: dict[str, dict],
    target_meta: dict[str, dict],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Compute determinism and fidelity twice: raw text, then masked."""
    hostnames = _collect_hostnames(ssh_data)
    masked_data = _mask_records(ssh_data, hostnames)
    gt_masked = _mask_records({"groundtruth_ssh": gt_records}, hostnames).get(
        "groundtruth_ssh", []
    )
    determinism_kinds = {"llm", "baseline", "groundtruth"}

    def analyse(
        data: dict[str, list[dict[str, Any]]],
        gt: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tname in sorted(data):
            kind = target_meta.get(tname, {}).get("kind", "unknown")
            result = _analyze_ssh_target(
                tname, data[tname],
                gt if tname != "groundtruth_ssh" else None,
                kind, cmd_map,
                determinism_kinds=determinism_kinds,
            )
            result["kind"] = kind
            results.append(result)
        _add_shared_fidelity(results, data, gt, cmd_map)
        return {result["target"]: result for result in results}

    raw = analyse(ssh_data, gt_records)
    masked = analyse(masked_data, gt_masked)

    rows: list[dict[str, Any]] = []
    for tname in sorted(raw):
        raw_result, masked_result = raw[tname], masked[tname]
        det_raw = (raw_result.get("determinism") or {}).get("overall_mean")
        det_masked = (masked_result.get("determinism") or {}).get("overall_mean")
        fid_raw = (raw_result.get("fidelity_shared") or {}).get("mean_sim")
        fid_masked = (masked_result.get("fidelity_shared") or {}).get("mean_sim")
        rows.append({
            "target": tname,
            "kind": raw_result.get("kind"),
            "det_unmasked": det_raw,
            "det_masked": det_masked,
            "det_delta": (
                round(det_masked - det_raw, 4)
                if det_raw is not None and det_masked is not None else None
            ),
            "det_commands": len(
                (raw_result.get("determinism") or {}).get("per_command") or {}
            ),
            "fidelity_raw_text": fid_raw,
            "fidelity_masked": fid_masked,
            "fidelity_delta": (
                round(fid_masked - fid_raw, 4)
                if fid_raw is not None and fid_masked is not None else None
            ),
            "fidelity_n": (raw_result.get("fidelity_shared") or {}).get("n"),
            "ci_raw_text": _ci_text(
                (raw_result.get("fidelity_shared") or {}).get("bootstrap_95_ci")
            ),
            "ci_masked": _ci_text(
                (masked_result.get("fidelity_shared") or {}).get("bootstrap_95_ci")
            ),
        })
    return rows, hostnames


def _render_v2(rows: list[dict[str, Any]], hostnames: set[str]) -> str:
    fmt = _fmt
    lines: list[str] = [
        "# Stage 2 - masked determinism and fidelity",
        "",
        "Generated by `python harness/analyze.py --masked-report results/exp` from the",
        "**published** raw batch (`results/raw`). Nothing under `results/` was rewritten;",
        "`results/summary.md` and `results/summary.csv` are untouched.",
        "",
        "## Why this file exists",
        "",
        "The published determinism table compares outputs character by character, so a",
        "target whose `date`, `uptime`, `ps` or prompt output embeds a clock value looks",
        "unstable even when it answers the same way every run. The ground truth has the",
        "same problem, but its determinism was never reported, so there was no common",
        "baseline. Every number below is computed twice: once on raw text (the published",
        "method) and once after the masking in `harness/analyze.py`.",
        "",
        "## What masking removes",
        "",
        "| Volatile field | Example | Replaced with |",
        "|---|---|---|",
    ]
    for label, example, placeholder in _V2_MASK_TABLE:
        lines.append(f"| {label} | `{example}` | `{placeholder}` |")
    lines += [
        "",
        f"Observed hostnames masked in this batch ({len(hostnames)}): "
        + (", ".join(f"`{name}`" for name in sorted(hostnames)) or "none"),
        "",
        "## Determinism, all targets, same basis",
        "",
        "Mean pairwise difflib similarity across the five runs of each command, capped",
        "at the first 4,000 characters exactly as in the published analysis.",
        "",
        "| Target | Kind | Determinism, raw text | Determinism, masked | Delta | Commands |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['target']} | {row['kind']} | {fmt(row['det_unmasked'], 4)} | "
            f"{fmt(row['det_masked'], 4)} | {fmt(row['det_delta'], 4)} | "
            f"{row['det_commands']} |"
        )
    lines += [
        "",
        "## Fidelity vs ground truth, raw text and masked",
        "",
        "`raw-text fidelity` is the published metric (`fidelity_shared.mean_sim`):",
        "difflib similarity of each cleaned output against the ground-truth output for",
        "the same command, averaged over the commands every compared target completed",
        "without a timeout. `masked fidelity` repeats it after the masking above.",
        "The 95% interval resamples commands (the analyzer's existing bootstrap), so it",
        "is too narrow for cell-to-cell comparisons - see docs/STAGE2_NOTES.md.",
        "",
        "| Target | Kind | Raw-text fidelity | Masked fidelity | Delta | Shared cmds | 95% CI (raw) | 95% CI (masked) |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['target']} | {row['kind']} | {fmt(row['fidelity_raw_text'], 4)} | "
            f"{fmt(row['fidelity_masked'], 4)} | {fmt(row['fidelity_delta'], 4)} | "
            f"{row['fidelity_n'] if row['fidelity_n'] is not None else '-'} | "
            f"{row['ci_raw_text'] or '-'} | {row['ci_masked'] or '-'} |"
        )
    lines += [
        "",
        "`groundtruth_ssh` has no fidelity row by construction: it is the reference.",
        "It does have a determinism row, which is the point of this file.",
        "",
        "## What persona differences do to fidelity",
        "",
        "Raw-text fidelity compares a target's output with the ground truth's output",
        "character by character, and difflib cannot tell an invented file from a wrong",
        "one. All four SSH LLM targets (DECEIVE, Beelzebub, AdvancedshelLM, VelLMes)",
        "are instructed to act as a video-game developer's Ubuntu box and to include",
        "realistic game source and asset files in directory listings; the ground truth is",
        "a plain Ubuntu container with no such instruction. A persona-following target",
        "therefore loses similarity for doing",
        "what its prompt asks, and a target that ignores its persona scores higher than",
        "one that obeys it. The measured gap is thus persona plus shell fidelity, and",
        "the two cannot be separated without a persona-matched cell. Masking does not",
        "fix this - it removes only the run-to-run noise both sides share, so the masked",
        "column is the cleaner instrument but still not a capability score. Reading it as",
        "one would penalise the most faithful honeypots. The persona-controlled cell is",
        "E5c in `NEXT_EXPERIMENT.md`; until it runs, quote this column as a fidelity",
        "proxy and not as a ranking.",
        "",
        "## Still not comparable",
        "",
        "- Masking equalises clock, PID, uptime, port and hostname noise, not file names,",
        "  permissions, package lists or tool versions. Two honest Ubuntu images still",
        "  differ there.",
        "- The HTTP track (galah, groundtruth_http) is out of scope here: it is not a",
        "  shell transcript and has no per-command determinism.",
        "- `llmhoneypot` is a detector target and is excluded from fidelity by the",
        "  analyzer; its determinism row is still shown.",
        "",
    ]
    return "\n".join(lines)


def _write_masked_report(
    out_dir: Path,
    ssh_data: dict[str, list[dict[str, Any]]],
    gt_records: list[dict[str, Any]],
    cmd_map: dict[str, dict],
    target_meta: dict[str, dict],
) -> int:
    rows, hostnames = _v2_rows(ssh_data, gt_records, cmd_map, target_meta)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = out_dir / "summary_v2.csv"
    with open(summary_csv, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=_V2_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    det_csv = out_dir / "determinism_v2.csv"
    with open(det_csv, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["target", "kind", "det_unmasked", "det_masked",
                        "det_delta", "det_commands"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    summary_md = out_dir / "summary_v2.md"
    summary_md.write_text(_render_v2(rows, hostnames), encoding=ENCODING)

    print(f"Written: {summary_md}")
    print(f"Written: {summary_csv}")
    print(f"Written: {det_csv}")
    print("Left untouched: results/summary.md, results/summary.csv")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze benchmark raw data",
    )
    parser.add_argument(
        "--masked-report",
        metavar="DIR",
        default=None,
        help=(
            "Write the Stage-2 masked comparison into DIR (e.g. results/exp) and "
            "stop. Nothing under results/ is written in this mode."
        ),
    )
    parser.add_argument(
        "--raw-dir",
        metavar="DIR",
        default=None,
        help=(
            "SSH JSONL input directory (default: results/raw). "
            "Does not change the default output locations."
        ),
    )
    parser.add_argument(
        "--http-dir",
        metavar="DIR",
        default=None,
        help=(
            "HTTP JSONL input directory (default: results/raw_http). "
            "Does not change the default output locations."
        ),
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        default=None,
        help=(
            "Output directory for summary.md, summary.csv, summary_by_run.csv and "
            "ANALYSIS_AUDIT.md (default: results/). Has no effect when --masked-report "
            "is used."
        ),
    )
    parser.add_argument(
        "--timing-label",
        metavar="LABEL",
        default=None,
        help=(
            "Optional label appended to the report header (e.g. 'prompt-mode stage4'). "
            "Has no effect on computed statistics."
        ),
    )
    args = parser.parse_args(argv)

    # Resolve input directories (override module constants only inside main(),
    # so imports and tests that touch the constants directly are unaffected).
    global RAW_SSH_DIR, RAW_HTTP_DIR  # noqa: PLW0603
    _orig_ssh_dir  = RAW_SSH_DIR
    _orig_http_dir = RAW_HTTP_DIR
    if args.raw_dir is not None:
        RAW_SSH_DIR = Path(args.raw_dir)
    if args.http_dir is not None:
        RAW_HTTP_DIR = Path(args.http_dir)

    # Resolve output directory
    _out_dir: Path | None = Path(args.out_dir) if args.out_dir else None

    # Load metadata
    try:
        with open(COMMANDS_YAML, encoding=ENCODING) as fh:
            cmd_data = yaml.safe_load(fh)
        cmd_map = {c["id"]: c for c in cmd_data.get("commands", [])}
    except FileNotFoundError:
        print(f"WARNING: {COMMANDS_YAML} not found; fidelity analysis disabled.", file=sys.stderr)
        cmd_map = {}

    try:
        with open(TARGETS_YAML, encoding=ENCODING) as fh:
            tgt_data = yaml.safe_load(fh)
        target_meta = {t["name"]: t for t in tgt_data.get("targets", [])}
    except FileNotFoundError:
        print(f"WARNING: {TARGETS_YAML} not found.", file=sys.stderr)
        target_meta = {}

    # Check input directories exist
    if not RAW_SSH_DIR.exists():
        print(f"WARNING: {RAW_SSH_DIR} not found; no SSH data.", file=sys.stderr)
    if not RAW_HTTP_DIR.exists():
        print(f"WARNING: {RAW_HTTP_DIR} not found; no HTTP data.", file=sys.stderr)

    # Load data
    ssh_data  = _load_all_ssh()
    http_data = _load_all_http()

    # Restore module constants so repeated calls are independent
    RAW_SSH_DIR  = _orig_ssh_dir
    RAW_HTTP_DIR = _orig_http_dir

    # Ground-truth lookups
    gt_ssh_records  = ssh_data.get("groundtruth_ssh", [])
    gt_http_records = http_data.get("groundtruth_http", [])

    # Stage-2 masked comparison: a separate output directory, so the published
    # summary files are never overwritten by the experiment. If this argument is
    # absent the behaviour below is exactly the published pipeline.
    if args.masked_report:
        return _write_masked_report(
            Path(args.masked_report), ssh_data, gt_ssh_records, cmd_map, target_meta
        )

    # ── Analyze SSH ───────────────────────────────────────────────────────────
    ssh_results: list[dict[str, Any]] = []
    present = set(ssh_data.keys())
    ordered = sorted(present)

    for tname in ordered:
        records = ssh_data[tname]
        meta    = target_meta.get(tname, {})
        kind    = meta.get("kind", "unknown")
        result  = _analyze_ssh_target(
            tname, records,
            gt_ssh_records if tname != "groundtruth_ssh" else None,
            kind, cmd_map,
        )
        result["kind"] = kind
        ssh_results.append(result)

    # ── Analyze HTTP ──────────────────────────────────────────────────────────
    http_results: list[dict[str, Any]] = []
    present_h = set(http_data.keys())
    ordered_h = sorted(present_h)

    for tname in ordered_h:
        records = http_data[tname]
        meta    = target_meta.get(tname, {})
        kind    = meta.get("kind", "unknown")
        result  = _analyze_http_target(
            tname, records,
            gt_http_records if tname != "groundtruth_http" else None,
            kind,
        )
        result["kind"] = kind
        http_results.append(result)

    _add_shared_fidelity(ssh_results, ssh_data, gt_ssh_records, cmd_map)
    if gt_http_records:
        gt_excess = sum(
            1 for record in gt_http_records
            if record.get("content_length_match") is False
        )
        for result in http_results:
            result["content_length_mismatch_excess"] = max(
                0, result.get("content_length_mismatches", 0) - gt_excess
            )

    # ── Write outputs ─────────────────────────────────────────────────────────
    # When --out-dir is provided, redirect all four output files there.
    # When omitted, the paths default to the published locations (results/).
    _results_base = _out_dir if _out_dir is not None else Path("results")
    _summary_md   = _results_base / "summary.md"
    _summary_csv  = _results_base / "summary.csv"
    _run_csv      = _results_base / "summary_by_run.csv"
    _audit_md     = _results_base / "ANALYSIS_AUDIT.md"
    _summary_md.parent.mkdir(parents=True, exist_ok=True)

    run_rows = _build_run_rows(ssh_data, http_data, cmd_map)
    md_text = _build_markdown(ssh_results, http_results)
    # Append optional timing label to the report header line
    if args.timing_label:
        md_text = md_text.replace(
            "# Honeypot Benchmark — Summary Report",
            f"# Honeypot Benchmark — Summary Report ({args.timing_label})",
            1,
        )
    md_text += "\n## Per-run accounting\n\n"
    md_text += "| Target | Run | Track | Timeouts | Empty outputs | State checks passed | Valid denominator |\n"
    md_text += "|---|---:|---|---:|---:|---:|---:|\n"
    for row in run_rows:
        md_text += (
            f"| {row['target']} | {row['run']} | {row['track']} | {row['timeouts']} | "
            f"{row['empty_outputs']} | {row['state_checks_passed']} | "
            f"{row['state_checks_valid']} |\n"
        )
    with open(_summary_md, "w", encoding=ENCODING) as fh:
        fh.write(md_text)
    print(f"Written: {_summary_md}")

    csv_rows = _build_csv_rows(ssh_results, http_results)
    with open(_summary_csv, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Written: {_summary_csv}")

    with _run_csv.open("w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["target", "run", "track", "timeouts", "empty_outputs",
                        "state_checks_passed", "state_checks_valid"],
        )
        writer.writeheader()
        writer.writerows(run_rows)
    print(f"Written: {_run_csv}")

    _audit_md.write_text(_build_audit(ssh_data, target_meta, cmd_map), encoding=ENCODING)
    print(f"Written: {_audit_md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
