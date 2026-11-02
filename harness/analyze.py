#!/usr/bin/env python3
"""
harness/analyze.py
Reads results/raw/*.jsonl and results/raw_http/*.jsonl, writes:
  results/summary.md
  results/summary.csv

Standard library + PyYAML only.  No pandas / numpy / matplotlib.
"""

from __future__ import annotations

import csv
import difflib
import glob
import hashlib
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

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
_AI_RE    = re.compile(r'as an ai|i cannot|i\'m sorry', re.IGNORECASE)

_SECRET_PATTERNS = ["AKIAIOSFODNN7EXAMPLE", "EXAMPLE"]

def _strip_ansi(s: str) -> str:
    return _LIT_RE.sub('', _ANSI_RE.sub('', s))

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


def _latency_stats(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"mean": float("nan"), "median": float("nan"),
                "p95": float("nan"), "max": float("nan"), "n": 0}
    return {
        "mean":   round(statistics.mean(vals), 3),
        "median": round(statistics.median(vals), 3),
        "p95":    round(_pct(vals, 95), 3),
        "max":    round(max(vals), 3),
        "n":      len(vals),
    }


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _mean_pairwise_sim(texts: list[str]) -> float:
    if len(texts) < 2:
        return float("nan")
    pairs = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            pairs.append(_similarity(texts[i], texts[j]))
    return round(statistics.mean(pairs), 4) if pairs else float("nan")

# ── SSH analysis ──────────────────────────────────────────────────────────────

def _analyze_ssh_target(
    tname: str,
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]] | None,
    kind: str,
    cmd_map: dict[str, dict],
) -> dict[str, Any]:
    """Compute per-target SSH metrics."""
    out: dict[str, Any] = {"target": tname, "kind": kind}

    if not records:
        out["error"] = "no records found"
        return out

    # Separate exit records from normal commands
    cmd_records = [r for r in records if r.get("cmd_id") != "exit"]
    exit_records = [r for r in records if r.get("cmd_id") == "exit"]

    # ── Latency ──────────────────────────────────────────────────────────────
    latencies = [r["latency_s"] for r in cmd_records if r.get("latency_s") is not None]
    out["latency_all"] = _latency_stats(latencies)

    cat_latencies: dict[str, list[float]] = {}
    for r in cmd_records:
        cat = r.get("category", "unknown")
        if r.get("latency_s") is not None:
            cat_latencies.setdefault(cat, []).append(r["latency_s"])
    out["latency_by_category"] = {
        cat: _latency_stats(vals) for cat, vals in cat_latencies.items()
    }

    # ── Reliability ──────────────────────────────────────────────────────────
    n_total   = len(cmd_records)
    n_timeout = sum(1 for r in cmd_records if r.get("timed_out"))
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
        "n_empty_outputs": n_empty,
        "exit_closes_session_rate": (
            round(sum(exit_closes) / len(exit_closes), 3) if exit_closes else None
        ),
    }

    # ── Artifacts ─────────────────────────────────────────────────────────────
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
            sim    = _similarity(our, gt_ref)
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

        state_checks.append({
            "run": run,
            "pwd_after_cd_is_tmp": pwd_after_cd == "/tmp",
            "cat_marker_correct":  "benchmark_marker" in cat_marker,
            "ls_tmp1_has_bm_txt":  "bm.txt" in ls_tmp1,
            "ls_tmp2_has_bm_dir":  "bm_dir" in ls_tmp2,
            "ls_tmp3_no_bm_txt":   "bm.txt" not in ls_tmp3,
            "whoami_matches_id":   (id_user is None) or (whoami_out == id_user),
        })

    out["state_consistency"] = state_checks

    # ── LLM determinism (pairwise similarity across runs) ─────────────────────
    if kind in ("llm", "baseline"):
        det: dict[str, float] = {}
        for r in cmd_records:
            cid = r.get("cmd_id", "")
            det.setdefault(cid, []).append(r.get("cleaned_output") or "")
        det_means = {
            cid: _mean_pairwise_sim(texts)
            for cid, texts in det.items()
            if len(texts) >= 2
        }
        if det_means:
            valid = [v for v in det_means.values() if not math.isnan(v)]
            out["determinism"] = {
                "per_command": det_means,
                "overall_mean": round(statistics.mean(valid), 4) if valid else None,
            }

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

    if not records:
        out["error"] = "no records found"
        return out

    # Status distribution
    status_counts: dict[str, int] = {}
    for r in records:
        s = str(r.get("status") or "error")
        status_counts[s] = status_counts.get(s, 0) + 1
    out["status_distribution"] = status_counts
    out["5xx_rate"] = round(
        sum(v for k, v in status_counts.items() if k.startswith("5")) / len(records), 4
    )

    # Server header consistency
    server_vals = [r.get("server_header") for r in records if r.get("server_header")]
    out["server_header_values"] = sorted(set(v for v in server_vals if v))
    out["server_header_constant"] = len(set(v for v in server_vals if v)) <= 1

    # Content-Length mismatches
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
    lats = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    out["latency"] = _latency_stats(lats)

    # Determinism: three GET / repeats
    repeat_ids = ["get_root_repeat1", "get_root_repeat2", "get_root_repeat3"]
    repeat_bodies = [
        r.get("body") or ""
        for r in records if r.get("id") in repeat_ids
    ]
    if len(repeat_bodies) >= 2:
        sims = []
        for i in range(len(repeat_bodies)):
            for j in range(i + 1, len(repeat_bodies)):
                sims.append(_similarity(repeat_bodies[i], repeat_bodies[j]))
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

    return out


def _port_mentioned(r: dict[str, Any]) -> bool:
    """True if the response body mentions a port number that looks like a target port."""
    body = r.get("body") or ""
    # Look for common port numbers in context
    common_ports = ["8088", "2226", "2225", "2222", "2223", "2224", "2227", "8022"]
    return any(p in body for p in common_ports)


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
        f"mean={_fmt(d.get('mean'))}s  median={_fmt(d.get('median'))}s  "
        f"p95={_fmt(d.get('p95'))}s  max={_fmt(d.get('max'))}s  (n={d.get('n',0)})"
    )


def _build_markdown(
    ssh_results: list[dict[str, Any]],
    http_results: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Honeypot Benchmark — Summary Report")
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

        # Latency
        a("**Latency (all commands)**")
        a("")
        a("| Stat | Value |")
        a("|------|-------|")
        lat = res.get("latency_all", {})
        for k in ("mean", "median", "p95", "max"):
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
            a(f"- Mean similarity (difflib ratio): {_fmt(fid.get('comparable_mean_sim'), 4)}")
            a(f"- Exact-match rate: {_fmt(fid.get('comparable_exact_rate'), 4)}")
            a(f"- Host-specific similarity (reference only): {_fmt(fid.get('host_specific_mean_sim_reference_only'), 4)}")
            a(f"- _{fid.get('note', '')}_")
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
        a("")

        # Server header
        svrs = res.get("server_header_values", [])
        a(f"**Server header values**: {svrs}  "
          f"({'constant' if res.get('server_header_constant') else 'VARIES'})")
        a("")

        # Content-Length and chunked
        a(f"- Content-Length mismatches: {res.get('content_length_mismatches', '—')}")
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
            "exit_closes_session_rate": None,
        })

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
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

    # Ground-truth lookups
    gt_ssh_records  = ssh_data.get("groundtruth_ssh", [])
    gt_http_records = http_data.get("groundtruth_http", [])

    # ── Analyze SSH ───────────────────────────────────────────────────────────
    ssh_results: list[dict[str, Any]] = []
    ssh_order = [
        "deceive", "beelzebub", "cowrie", "advshellm",
        "llmhoneypot", "groundtruth_ssh",
    ]
    present = set(ssh_data.keys())
    ordered = [n for n in ssh_order if n in present] + \
              sorted(present - set(ssh_order))

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
    http_order = ["galah", "groundtruth_http"]
    present_h = set(http_data.keys())
    ordered_h = [n for n in http_order if n in present_h] + \
                sorted(present_h - set(http_order))

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

    # ── Write outputs ─────────────────────────────────────────────────────────
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)

    md_text = _build_markdown(ssh_results, http_results)
    with open(SUMMARY_MD, "w", encoding=ENCODING) as fh:
        fh.write(md_text)
    print(f"Written: {SUMMARY_MD}")

    csv_rows = _build_csv_rows(ssh_results, http_results)
    with open(SUMMARY_CSV, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Written: {SUMMARY_CSV}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
