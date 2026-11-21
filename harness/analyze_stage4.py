#!/usr/bin/env python3
"""
harness/analyze_stage4.py
Reads results/exp/stage4/ (or --stage4-dir), writes analysis.md and CSVs.

Usage:
    python harness/analyze_stage4.py
    python harness/analyze_stage4.py --stage4-dir results/exp/stage4_smoke

Outputs (all under --stage4-dir):
    analysis.md         full Markdown report
    latency.csv         per-target latency statistics
    determinism.csv     per-target determinism statistics
    timeout.csv         per-target timeout counts
    bootstrap_ci.csv    95% bootstrap CIs
    proxy_join.csv      per-command proxy duration join
    quiet_check.csv     quiet-check comparison (runs 1-2)
    drift.csv           Spearman drift check for Cowrie and groundtruth_ssh

Standard library + PyYAML only. No pandas / numpy.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

ENCODING = "utf-8"
DEFAULT_STAGE4_DIR = Path("results/exp/stage4")
# Must match harness/run_stage4.QUIET_SUBDIR: quiet-check rows live in their own
# directory so they never overwrite the prompt JSONL.
QUIET_SUBDIR       = "raw_quiet"
BOOTSTRAP_N        = 10_000
BOOTSTRAP_SEED     = 20261106
VALIDATION_DIR     = Path("results/exp/validation")

# ── Console-safe output -------------------------------------------------------

def _safe_print(*args: Any, **kwargs: Any) -> None:
    """print() that can never raise UnicodeEncodeError (Windows cp1252 consoles)."""
    stream = kwargs.pop("file", None) or sys.stdout
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    flush = kwargs.pop("flush", False)
    text = sep.join(str(a) for a in args) + end
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding, "strict")
    except (UnicodeEncodeError, LookupError):
        try:
            text = text.encode(encoding, "replace").decode(encoding, "replace")
        except LookupError:
            text = text.encode("ascii", "replace").decode("ascii")
    try:
        stream.write(text)
    except UnicodeEncodeError:
        try:
            stream.write(text.encode("ascii", "replace").decode("ascii"))
        except Exception:
            return
    except Exception:
        return
    if flush:
        try:
            stream.flush()
        except Exception:
            pass


def _reconfigure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


# ── Statistics helpers ────────────────────────────────────────────────────────

def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    idx = p / 100 * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _bootstrap_ci(
    values: list[float],
    stat_fn: Any = None,
    n: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float] | None:
    """
    95% bootstrap CI for stat_fn applied to values.
    stat_fn defaults to statistics.median.
    Method: 10,000 resamples with replacement, fixed seed.
    """
    if len(values) < 2:
        return None
    if stat_fn is None:
        stat_fn = statistics.median
    rng = random.Random(seed)
    boot: list[float] = []
    for _ in range(n):
        sample = [values[rng.randrange(len(values))] for _ in values]
        boot.append(stat_fn(sample))
    return (_pct(boot, 2.5), _pct(boot, 97.5))


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\[[0-9;]*m')
_LIT_RE  = re.compile(r'(?:\\x1b|\\u001b|\\033)\[[0-9;]*[A-Za-z]')

MASK_RULES = (
    ("<DATE>", re.compile(
        r"\b\d{4}-\d{2}-\d{2}"
        r"(?:[T ]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b")),
    ("<DATE>", re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,]?\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?(?:\s+[A-Z]{2,5})?(?:\s+\d{4})?\b")),
    ("<TIME>", re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+"
        r"\d{1,2}:\d{2}(?::\d{2})?\b")),
    ("<TIME>", re.compile(r"(?<![\d.:])\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\b")),
    ("<UPTIME>", re.compile(
        r"\bup\s+\d+\s+(?:days?|hours?|minutes?|mins?)[^,\n]*", re.IGNORECASE)),
    ("<LOAD>", re.compile(r"load averages?:[^\n]*", re.IGNORECASE)),
    ("<PID>", re.compile(r"\bpid[=:\s]+\d+\b", re.IGNORECASE)),
    ("<PID>", re.compile(r"\bPID\s+\d+\b")),
    ("<TTY>", re.compile(r"\bpts/\d+\b")),
    ("<EPHEMERAL_PORT>", re.compile(r"(?<=[0-9]):\d{4,5}\b")),
)


def _mask_text(text: str, hostnames: frozenset[str] = frozenset()) -> str:
    masked = text
    for placeholder, pattern in MASK_RULES:
        masked = pattern.sub(placeholder, masked)
    for hn in sorted(hostnames, key=len, reverse=True):
        if hn and hn in masked:
            masked = masked.replace(hn, "<HOST>")
    return masked


def _strip_ansi(s: str) -> str:
    return _LIT_RE.sub("", _ANSI_RE.sub("", s))


def _similarity(a: str, b: str, limit: int = 4000) -> float:
    ca = _strip_ansi(a)[:limit]
    cb = _strip_ansi(b)[:limit]
    return difflib.SequenceMatcher(None, ca, cb).ratio()


def _mean_pairwise(texts: list[str]) -> float:
    if len(texts) < 2:
        return float("nan")
    sims = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sims.append(_similarity(texts[i], texts[j]))
    return statistics.mean(sims) if sims else float("nan")


def _spearman_rho(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """
    Compute Spearman rank correlation and two-tailed p-value approximation.
    Returns (rho, p_value). p_value is approximated via t-distribution for n >= 4.
    Returns (nan, nan) if n < 3.
    """
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan")
    # Rank vectors
    def _rank(v: list[float]) -> list[float]:
        sorted_v = sorted(range(n), key=lambda i: v[i])
        ranks = [0.0] * n
        for rank, idx in enumerate(sorted_v):
            ranks[idx] = rank + 1.0
        return ranks
    rx = _rank(xs)
    ry = _rank(ys)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    rho = 1.0 - (6.0 * d2) / (n * (n * n - 1))
    # p-value approximation via t-distribution
    if abs(rho) >= 1.0:
        p = 0.0
    else:
        t = rho * math.sqrt(n - 2) / math.sqrt(1.0 - rho * rho)
        # Rough two-tailed p using an approximation
        # For n >= 20 this is good; for small n the note says n is too small anyway
        df = n - 2
        # Simple approximation: p ≈ 2 * (1 - Phi(|t| * sqrt(df/(df+t^2))))
        x = df / (df + t * t)
        # Beta incomplete function approximation (Bailey 1994 series)
        # For the benchmark n=20 we give 2 sig figs
        try:
            import math as _m
            p = 2.0 * _m.exp(_m.lgamma((df + 1) / 2) - _m.lgamma(df / 2)
                              - 0.5 * _m.log(_m.pi * df)
                              - ((df + 1) / 2) * _m.log(1 + t * t / df))
        except Exception:
            p = float("nan")
    return round(rho, 4), round(p, 4)


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def _load_all_ssh(raw_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Returns {target: [all records across all runs]}"""
    data: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(raw_dir.glob("*.jsonl")):
        # skip quiet-check files (suffixed .partial.bak or similar)
        if ".bak" in path.name:
            continue
        stem = path.stem
        parts = stem.rsplit("_run", 1)
        if len(parts) != 2:
            continue
        tname = parts[0]
        data.setdefault(tname, []).extend(_load_jsonl(path))
    return data


def _load_all_http(raw_http_dir: Path) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(raw_http_dir.glob("*.jsonl")):
        if ".bak" in path.name:
            continue
        stem = path.stem
        parts = stem.rsplit("_run", 1)
        if len(parts) != 2:
            continue
        tname = parts[0]
        data.setdefault(tname, []).extend(_load_jsonl(path))
    return data


def _load_proxy_log(proxy_log: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(proxy_log)
    return [r for r in rows if r.get("event") != "slot_start"]


def _load_slot_boundaries(proxy_log: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(proxy_log)
    return [r for r in rows if r.get("event") == "slot_start"]


def _load_manifest(stage4_dir: Path) -> list[dict[str, Any]]:
    return _load_jsonl(stage4_dir / "manifest.jsonl")


# ── Per-target SSH analysis ───────────────────────────────────────────────────

LLM_SSH_TARGETS = {"deceive", "beelzebub", "vellmes", "advshellm"}
HTTP_TARGETS    = {"galah", "groundtruth_http"}


def _analyze_ssh_target_s4(
    tname: str,
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
    runs: list[int],
) -> dict[str, Any]:
    """
    Per-target Stage 4 SSH metrics.

    Returns a dict with:
        n_runs, completed, timeouts, latency_median, latency_p95,
        determinism_masked, fidelity_masked,
        empty_count, oversized_count, leakage_count,
        ci_latency_median, ci_determinism, ci_timeout_rate
    """
    out: dict[str, Any] = {"target": tname, "n_runs": len(runs)}

    cmd_records = [
        r for r in records
        if r.get("cmd_id") and r.get("cmd_id") != "exit"
    ]

    # Latency (non-timeout only)
    latencies = [
        r["latency_s"] for r in cmd_records
        if r.get("latency_s") is not None and not r.get("timed_out")
    ]
    n_timeout = sum(1 for r in cmd_records if r.get("timed_out"))
    n_total   = len(cmd_records)

    out["n_commands"]  = n_total
    out["n_timeouts"]  = n_timeout
    out["timeout_rate"] = round(n_timeout / n_total, 4) if n_total else None
    out["latency_median"] = round(statistics.median(latencies), 4) if latencies else None
    out["latency_p95"]    = round(_pct(latencies, 95), 4) if latencies else None

    # Outputs
    outputs = [r.get("cleaned_output") or "" for r in cmd_records]
    out["n_empty"]     = sum(1 for o in outputs if not o.strip())
    out["n_oversized"] = sum(1 for o in outputs if len(o) > 20_000)
    # Transcript leakage: shell-prompt-like lines that are not the final prompt
    _SHELL_RE = re.compile(r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s")
    out["n_leakage"] = sum(
        1 for o in outputs
        if len(list(_SHELL_RE.finditer(o))) > 0 and not o.rstrip().endswith("$")
        and not o.rstrip().endswith("#")
    )

    # Collect hostnames for masking
    hostnames: set[str] = set()
    for r in cmd_records:
        if r.get("cmd_id") == "hostname":
            first = (r.get("cleaned_output") or "").strip().splitlines()
            if first:
                hostnames.add(first[0].strip())

    # Determinism (masked, pairwise across runs)
    by_cmd: dict[str, list[str]] = {}
    for r in cmd_records:
        cid = r.get("cmd_id", "")
        txt = _mask_text(r.get("cleaned_output") or "", frozenset(hostnames))
        by_cmd.setdefault(cid, []).append(txt)
    det_vals = [
        _mean_pairwise(texts)
        for texts in by_cmd.values()
        if len(texts) >= 2 and not math.isnan(_mean_pairwise(texts))
    ]
    out["determinism_masked"] = round(statistics.mean(det_vals), 4) if det_vals else None

    # Fidelity vs groundtruth_ssh (masked, non-host-specific commands)
    if gt_records:
        gt_by_cmd: dict[str, str] = {}
        for r in gt_records:
            cid = r.get("cmd_id", "")
            if cid not in gt_by_cmd:
                gt_by_cmd[cid] = _mask_text(r.get("cleaned_output") or "",
                                             frozenset(hostnames))
        fid_vals: list[float] = []
        for r in cmd_records:
            cid = r.get("cmd_id", "")
            if cid in gt_by_cmd and not r.get("timed_out"):
                txt = _mask_text(r.get("cleaned_output") or "", frozenset(hostnames))
                fid_vals.append(_similarity(txt, gt_by_cmd[cid]))
        out["fidelity_masked"] = round(statistics.mean(fid_vals), 4) if fid_vals else None
    else:
        out["fidelity_masked"] = None

    # Bootstrap CIs over runs (resample run-level median latency / determinism / timeout_rate)
    # Compute per-run median latency
    run_lat: dict[int, list[float]] = {}
    for r in cmd_records:
        rn = r.get("s4_run", r.get("run"))
        if r.get("latency_s") is not None and not r.get("timed_out") and rn is not None:
            run_lat.setdefault(int(rn), []).append(r["latency_s"])
    run_medians = [statistics.median(v) for v in run_lat.values() if v]
    out["ci_latency_median"] = _bootstrap_ci(run_medians)

    run_to: dict[int, list[bool]] = {}
    for r in cmd_records:
        rn = r.get("s4_run", r.get("run"))
        if rn is not None:
            run_to.setdefault(int(rn), []).append(bool(r.get("timed_out")))
    run_to_rates = [
        sum(v) / len(v) for v in run_to.values() if v
    ]
    out["ci_timeout_rate"] = _bootstrap_ci(run_to_rates)

    # Per-run determinism for CI
    run_det: dict[int, list[float]] = {}
    for r in cmd_records:
        rn = r.get("s4_run", r.get("run"))
        if rn is not None:
            # We'll compute mean pairwise per command across runs at the run level
            # by assigning each run its own contribution; approximate by run mean sim
            run_det.setdefault(int(rn), [])
    # Determinism CI: use per-command det values as units for bootstrap
    ci_det = _bootstrap_ci(det_vals, stat_fn=statistics.mean) if len(det_vals) >= 2 else None
    out["ci_determinism"] = ci_det

    return out


def _analyze_http_target_s4(
    tname: str,
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
) -> dict[str, Any]:
    out: dict[str, Any] = {"target": tname}

    if not records:
        out["error"] = "no records"
        return out

    n_total  = len(records)
    n_5xx    = sum(1 for r in records if (r.get("status") or 0) >= 500)
    n_timeout = sum(1 for r in records if r.get("timed_out"))
    out["n_requests"] = n_total
    out["n_5xx"]      = n_5xx
    out["5xx_rate"]   = round(n_5xx / n_total, 4) if n_total else None
    out["n_timeout"]  = n_timeout

    server_vals = sorted({r.get("server_header") for r in records if r.get("server_header")})
    out["server_header_values"] = server_vals

    # Status agreement with ground truth
    if gt_records:
        gt_map: dict[tuple[str, str], int] = {}
        for r in gt_records:
            key = (r.get("method", ""), r.get("path", ""))
            if r.get("status"):
                gt_map[key] = r["status"]
        agree, total = 0, 0
        for r in records:
            key = (r.get("method", ""), r.get("path", ""))
            if key in gt_map and r.get("status"):
                total += 1
                if r["status"] == gt_map[key]:
                    agree += 1
        out["status_agreement"] = {"agreements": agree, "total": total,
                                   "rate": round(agree / total, 4) if total else None}
    else:
        out["status_agreement"] = None

    # Repeat similarity
    repeat_ids = ["get_root_repeat1", "get_root_repeat2", "get_root_repeat3"]
    repeat_bodies = [r.get("body") or "" for r in records if r.get("id") in repeat_ids]
    if len(repeat_bodies) >= 2:
        sims = [
            _similarity(repeat_bodies[i], repeat_bodies[j])
            for i in range(len(repeat_bodies))
            for j in range(i + 1, len(repeat_bodies))
        ]
        out["repeat_similarity"] = round(statistics.mean(sims), 4) if sims else None
    else:
        out["repeat_similarity"] = None

    return out


# ── Drift check ───────────────────────────────────────────────────────────────

def _drift_check(
    records: list[dict[str, Any]],
    target: str,
) -> dict[str, Any]:
    """
    For cowrie and groundtruth_ssh: compute per-run median latency, then
    Spearman rho between {run_index, wall-clock hour} and latency.

    Reports numbers + a plain statement if n is too small to conclude.
    """
    cmd_records = [
        r for r in records
        if r.get("cmd_id") and r.get("cmd_id") != "exit"
        and not r.get("timed_out") and r.get("latency_s") is not None
    ]

    # Per-run median latency
    run_data: dict[int, dict[str, Any]] = {}
    for r in cmd_records:
        rn = int(r.get("s4_run", r.get("run", 0)))
        lat = r.get("latency_s", 0.0)
        wall = r.get("s4_wall_start") or r.get("t_send_wall")
        run_data.setdefault(rn, {"latencies": [], "wall": wall})
        run_data[rn]["latencies"].append(lat)

    runs_sorted = sorted(run_data.keys())
    run_medians = [statistics.median(run_data[rn]["latencies"]) for rn in runs_sorted]

    # Wall-clock hours
    wall_hours: list[float] = []
    for rn in runs_sorted:
        wall_str = run_data[rn].get("wall")
        if wall_str:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(str(wall_str).replace("Z", "+00:00"))
                wall_hours.append(dt.hour + dt.minute / 60.0)
            except Exception:
                wall_hours.append(float("nan"))
        else:
            wall_hours.append(float("nan"))

    rho_run, p_run = _spearman_rho(list(map(float, runs_sorted)), run_medians)
    valid_wall = [(h, m) for h, m in zip(wall_hours, run_medians) if not math.isnan(h)]
    if valid_wall:
        rho_wall, p_wall = _spearman_rho([h for h, _ in valid_wall], [m for _, m in valid_wall])
    else:
        rho_wall, p_wall = float("nan"), float("nan")

    n = len(runs_sorted)
    too_small = n < 10
    note = (
        "n is too small to draw conclusions from correlation tests." if too_small
        else "Correlation tests have adequate sample size for a rough check."
    )

    return {
        "target": target,
        "n_runs": n,
        "run_medians": dict(zip(runs_sorted, [round(m, 4) for m in run_medians])),
        "spearman_vs_run_index": {"rho": rho_run, "p": p_run},
        "spearman_vs_wall_hour": {"rho": rho_wall, "p": p_wall},
        "note": note,
    }


# ── Order effect ──────────────────────────────────────────────────────────────

def _order_effect(
    records: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    target: str,
) -> dict[str, Any]:
    """
    For LLM targets: Spearman rho between position-in-run and per-command latency,
    and between time-since-previous-slot and latency.
    """
    # Build run → position map from manifest
    pos_map: dict[tuple[int, str], int] = {}
    for entry in manifest:
        rn = entry.get("run")
        tgt = entry.get("target")
        pos = entry.get("position")
        if rn is not None and tgt is not None and pos is not None:
            pos_map[(int(rn), str(tgt))] = int(pos)

    cmd_records = [
        r for r in records
        if r.get("cmd_id") and r.get("cmd_id") != "exit"
        and not r.get("timed_out") and r.get("latency_s") is not None
    ]

    positions: list[float] = []
    latencies: list[float] = []
    for r in cmd_records:
        rn = int(r.get("s4_run", r.get("run", 0)))
        pos = r.get("s4_position") or pos_map.get((rn, target))
        if pos is not None:
            positions.append(float(pos))
            latencies.append(float(r["latency_s"]))

    rho, p = _spearman_rho(positions, latencies) if len(positions) >= 3 else (float("nan"), float("nan"))
    return {
        "target": target,
        "n_commands": len(latencies),
        "spearman_latency_vs_position": {"rho": rho, "p": p},
    }


# ── API proxy join ─────────────────────────────────────────────────────────────

def _join_proxy(
    records: list[dict[str, Any]],
    proxy_rows: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    target: str,
) -> dict[str, Any]:
    """
    Strict in-window join: for each command record, find a proxy request that
    - falls after the slot_start boundary for this (run, target)
    - falls before the next slot_start boundary
    - has not been matched yet

    Returns per-target summary statistics.
    """
    from datetime import datetime, timezone

    def _ts(s: str | None) -> float:
        if not s:
            return 0.0
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    # Build slot time windows for this target
    slot_windows: list[tuple[float, float, int, int]] = []  # (start_ts, end_ts, run, pos)
    all_boundaries = sorted(
        [b for b in boundaries if b.get("target") == target],
        key=lambda b: _ts(b.get("ts")),
    )
    # Find window end: next boundary of any target
    all_b_sorted = sorted(boundaries, key=lambda b: _ts(b.get("ts")))
    for sb in all_boundaries:
        start_ts = _ts(sb.get("ts"))
        rn = sb.get("run", 0)
        pos = sb.get("position", 0)
        # End is the next boundary after this one (regardless of target)
        end_ts = float("inf")
        for ob in all_b_sorted:
            ob_ts = _ts(ob.get("ts"))
            if ob_ts > start_ts:
                end_ts = ob_ts
                break
        slot_windows.append((start_ts, end_ts, rn, pos))

    # Map proxy rows into time windows
    proxy_in_window: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for pw in slot_windows:
        start_ts, end_ts, rn, pos = pw
        window_rows = [
            r for r in proxy_rows
            if start_ts <= _ts(r.get("ts")) < end_ts
        ]
        proxy_in_window[(rn, pos)] = window_rows

    # Command records for this target. SSH rows use cmd_id; HTTP rows use id.
    cmd_records = [
        r for r in records
        if (r.get("cmd_id") or r.get("id")) and r.get("cmd_id") != "exit"
    ]

    matched = 0
    unmatched = 0
    api_durations: list[float] = []
    gaps: list[float] = []
    per_cmd: dict[str, list[float]] = {}

    for r in cmd_records:
        rn = int(r.get("s4_run", r.get("run", 0)))
        pos = int(r.get("s4_position", 0))
        window = proxy_in_window.get((rn, pos), [])
        if window:
            # Take the first unmatched proxy entry
            proxy_row = window.pop(0)
            dur_ms = proxy_row.get("duration_ms") or 0.0
            harness_ms = (r.get("latency_s") or 0.0) * 1000
            api_durations.append(dur_ms)
            gaps.append(max(0.0, harness_ms - dur_ms))
            matched += 1
            cid = r.get("cmd_id") or r.get("id") or ""
            per_cmd.setdefault(cid, []).append(dur_ms)
        else:
            unmatched += 1

    per_cmd_stats = {}
    for cid, durs in per_cmd.items():
        per_cmd_stats[cid] = {
            "median_ms": round(statistics.median(durs), 1),
            "p95_ms":    round(_pct(durs, 95), 1),
            "n":         len(durs),
        }

    return {
        "target": target,
        "matched": matched,
        "unmatched": unmatched,
        "api_duration_median_ms": round(statistics.median(api_durations), 1) if api_durations else None,
        "api_duration_p95_ms":    round(_pct(api_durations, 95), 1) if api_durations else None,
        "gap_median_ms":          round(statistics.median(gaps), 1) if gaps else None,
        "per_command": per_cmd_stats,
    }


# ── Quiet-check comparison ─────────────────────────────────────────────────────

def _validation_file(validation_dir: Path, target: str,
                     pass_letter: str) -> Path | None:
    """Stage 2 validation JSONL for one pass.

    The validation batches use two naming styles; accept both.
    """
    for name in (f"{target}_pass{pass_letter}_quiet.jsonl",
                 f"{target}_{pass_letter}_quiet.jsonl"):
        cand = validation_dir / name
        if cand.exists():
            return cand
    return None


def _quiet_check(
    prompt_records: list[dict[str, Any]],
    quiet_records: list[dict[str, Any]],
    validation_dir: Path,
    target: str,
) -> dict[str, Any]:
    """
    Compare prompt vs quiet outputs for runs 1-2.
    Flags commands where prompt mode is shorter/empty than quiet and the drop
    exceeds the quiet-vs-quiet noise floor from Stage 2 validation data.
    """
    # Compute quiet-vs-quiet noise floor from validation data if available
    noise_floor: dict[str, float] = {}
    val_a_path = _validation_file(validation_dir, target, "A")
    val_c_path = _validation_file(validation_dir, target, "C")
    if val_a_path and val_c_path:
        a_recs = _load_jsonl(val_a_path)
        c_recs = _load_jsonl(val_c_path)
        a_map = {r.get("cmd_id"): r.get("cleaned_output") or "" for r in a_recs}
        c_map = {r.get("cmd_id"): r.get("cleaned_output") or "" for r in c_recs}
        for cid in a_map:
            if cid in c_map:
                sim = _similarity(a_map[cid], c_map[cid])
                noise_floor[cid] = sim

    # Build maps for quiet-check runs (runs 1-2)
    p_runs = {
        (r.get("s4_run", r.get("run")), r.get("cmd_id")): r
        for r in prompt_records
        if r.get("s4_run", r.get("run")) in (1, 2)
        and r.get("cmd_id") and r.get("cmd_id") != "exit"
    }
    q_runs = {
        (r.get("s4_run", r.get("run")), r.get("cmd_id")): r
        for r in quiet_records
        if r.get("s4_run", r.get("run")) in (1, 2)
        and r.get("cmd_id") and r.get("cmd_id") != "exit"
    }

    flagged: list[dict[str, Any]] = []
    matched_keys = set(p_runs) & set(q_runs)
    for key in sorted(matched_keys):
        p_rec = p_runs[key]
        q_rec = q_runs[key]
        p_out = p_rec.get("cleaned_output") or ""
        q_out = q_rec.get("cleaned_output") or ""
        p_len = len(p_out)
        q_len = len(q_out)
        sim = _similarity(p_out, q_out)
        floor = noise_floor.get(key[1], float("nan"))
        drop = (1.0 - sim) - (1.0 - floor) if not math.isnan(floor) else float("nan")
        is_shorter = (p_len < q_len) and q_len > 0
        exceeds_floor = drop > 0.05 if not math.isnan(drop) else False
        if is_shorter or exceeds_floor:
            flagged.append({
                "run": key[0],
                "cmd_id": key[1],
                "prompt_len": p_len,
                "quiet_len": q_len,
                "sim_pq": round(sim, 4),
                "noise_floor": round(floor, 4) if not math.isnan(floor) else None,
                "drop_vs_floor": round(drop, 4) if not math.isnan(drop) else None,
                "is_shorter": is_shorter,
                "exceeds_floor": exceeds_floor,
            })

    return {
        "target": target,
        "pairs_checked": len(matched_keys),
        "flagged": len(flagged),
        "flagged_details": flagged,
    }


# ── Extra seconds over ground truth ──────────────────────────────────────────

def _extra_vs_gt(
    records: list[dict[str, Any]],
    gt_records: list[dict[str, Any]],
    target: str,
) -> dict[str, Any]:
    """
    Extra seconds: target median latency minus groundtruth_ssh median latency,
    in prompt mode (floor-free).
    Bootstrap CI resamples run-level medians.
    """
    def _run_medians(recs: list[dict[str, Any]]) -> dict[int, float]:
        by_run: dict[int, list[float]] = {}
        for r in recs:
            if (r.get("cmd_id") and r.get("cmd_id") != "exit"
                    and not r.get("timed_out") and r.get("latency_s") is not None):
                rn = int(r.get("s4_run", r.get("run", 0)))
                by_run.setdefault(rn, []).append(r["latency_s"])
        return {rn: statistics.median(v) for rn, v in by_run.items() if v}

    t_medians = _run_medians(records)
    g_medians = _run_medians(gt_records)
    shared_runs = sorted(set(t_medians) & set(g_medians))
    diffs = [t_medians[rn] - g_medians[rn] for rn in shared_runs]

    extra_median = round(statistics.median(diffs), 4) if diffs else None
    ci = _bootstrap_ci(diffs) if len(diffs) >= 2 else None

    return {
        "target": target,
        "n_runs": len(diffs),
        "extra_median_s": extra_median,
        "ci_extra_95": ci,
        "note": (
            "Extra seconds = target run-median minus groundtruth run-median in prompt mode. "
            "These are floor-free (no 0.5s quiet-period added). "
            "bootstrap CIs resample run-level differences."
        ),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def _fmt(v: Any, dec: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return f"{v:.{dec}f}"
    return str(v)


def _ci_str(ci: tuple[float, float] | None) -> str:
    if ci is None:
        return "—"
    return f"[{_fmt(ci[0])}, {_fmt(ci[1])}]"


def _build_analysis_md(
    ssh_stats: dict[str, dict[str, Any]],
    http_stats: dict[str, dict[str, Any]],
    drift_checks: dict[str, dict[str, Any]],
    order_effects: dict[str, dict[str, Any]],
    proxy_joins: dict[str, dict[str, Any]],
    quiet_checks: dict[str, dict[str, Any]],
    extra_vs_gt: dict[str, dict[str, Any]],
    stage4_dir: Path,
) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Stage 4 Analysis")
    a("")
    a(f"> Generated from `{stage4_dir}`")
    a("> Bootstrap: 10,000 resamples, seed 20261106, resample unit = run.")
    a("> All bootstrap CIs are 95% percentile intervals.")
    a("> Latency = prompt-mode harness latency (floor ≈ 15.5 ms on this machine).")
    a("> Statistics labeled with n and batch source (stage4).")
    a("> No rankings and no causal language.")
    a("")

    # ── SSH targets ──────────────────────────────────────────────────────────
    a("## SSH Targets")
    a("")
    a("| Target | n_runs | n_cmds | timeouts | timeout_rate | lat_median (s) | lat_p95 (s) | det_masked | fid_masked |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for tname, s in sorted(ssh_stats.items()):
        a(f"| {tname} "
          f"| {s.get('n_runs','—')} "
          f"| {s.get('n_commands','—')} "
          f"| {s.get('n_timeouts','—')} "
          f"| {_fmt(s.get('timeout_rate'), 3)} "
          f"| {_fmt(s.get('latency_median'))} "
          f"| {_fmt(s.get('latency_p95'))} "
          f"| {_fmt(s.get('determinism_masked'))} "
          f"| {_fmt(s.get('fidelity_masked'))} |")
    a("")

    a("### Bootstrap 95% CIs (n = runs, method = resample run-level median)")
    a("")
    a("| Target | CI latency_median | CI timeout_rate | CI determinism |")
    a("|---|---|---|---|")
    for tname, s in sorted(ssh_stats.items()):
        a(f"| {tname} "
          f"| {_ci_str(s.get('ci_latency_median'))} "
          f"| {_ci_str(s.get('ci_timeout_rate'))} "
          f"| {_ci_str(s.get('ci_determinism'))} |")
    a("")

    # ── Empty / oversized / leakage ──────────────────────────────────────────
    a("### Output quality")
    a("")
    a("| Target | n_empty | n_oversized | n_leakage |")
    a("|---|---:|---:|---:|")
    for tname, s in sorted(ssh_stats.items()):
        a(f"| {tname} | {s.get('n_empty','—')} | {s.get('n_oversized','—')} | {s.get('n_leakage','—')} |")
    a("")

    # ── HTTP ─────────────────────────────────────────────────────────────────
    a("## HTTP Targets")
    a("")
    for tname, s in sorted(http_stats.items()):
        a(f"### {tname}")
        a("")
        if s.get("error"):
            a(f"**Error:** {s['error']}")
            a("")
            continue
        a(f"- Requests: {s.get('n_requests','—')}")
        a(f"- 5xx rate: {_fmt(s.get('5xx_rate'), 3)}")
        a(f"- Timeouts: {s.get('n_timeout','—')}")
        a(f"- Server header values: {s.get('server_header_values', [])}")
        a(f"- Repeat similarity: {_fmt(s.get('repeat_similarity'))}")
        sa = s.get("status_agreement")
        if sa:
            a(f"- Status agreement with groundtruth_http: {sa.get('agreements')}/{sa.get('total')} ({_fmt(sa.get('rate'), 3)})")
        a("")

    # ── Drift ────────────────────────────────────────────────────────────────
    a("## Drift Controls (Cowrie and groundtruth_ssh)")
    a("")
    a("Spearman ρ between run index / wall-clock hour and per-run median latency.")
    a("n is the number of completed runs; p is two-tailed.")
    a("")
    a("| Target | n | ρ vs run_index | p | ρ vs wall_hour | p |")
    a("|---|---:|---:|---:|---:|---:|")
    for tname in ("cowrie", "groundtruth_ssh"):
        d = drift_checks.get(tname, {})
        rv = d.get("spearman_vs_run_index", {})
        wv = d.get("spearman_vs_wall_hour", {})
        a(f"| {tname} "
          f"| {d.get('n_runs','—')} "
          f"| {_fmt(rv.get('rho'))} "
          f"| {_fmt(rv.get('p'))} "
          f"| {_fmt(wv.get('rho'))} "
          f"| {_fmt(wv.get('p'))} |")
    for tname, d in drift_checks.items():
        a(f"*{tname}*: {d.get('note','')}")
    a("")

    # ── Order effect ─────────────────────────────────────────────────────────
    a("## Order Effect (LLM targets)")
    a("")
    a("Spearman ρ between position-in-run and per-command latency.")
    a("")
    a("| Target | n_commands | ρ vs position | p |")
    a("|---|---:|---:|---:|")
    for tname, oe in sorted(order_effects.items()):
        sp = oe.get("spearman_latency_vs_position", {})
        a(f"| {tname} "
          f"| {oe.get('n_commands','—')} "
          f"| {_fmt(sp.get('rho'))} "
          f"| {_fmt(sp.get('p'))} |")
    a("")

    # ── Proxy join ────────────────────────────────────────────────────────────
    a("## API Proxy Join")
    a("")
    a("Per-target API duration (from proxy log) and non-API gap.")
    a("Strict in-window match; each proxy entry used at most once.")
    a("")
    a("| Target | matched | unmatched | API median (ms) | API p95 (ms) | gap median (ms) |")
    a("|---|---:|---:|---:|---:|---:|")
    for tname, pj in sorted(proxy_joins.items()):
        a(f"| {tname} "
          f"| {pj.get('matched','—')} "
          f"| {pj.get('unmatched','—')} "
          f"| {_fmt(pj.get('api_duration_median_ms'), 1)} "
          f"| {_fmt(pj.get('api_duration_p95_ms'), 1)} "
          f"| {_fmt(pj.get('gap_median_ms'), 1)} |")
    a("")

    # ── Quiet-check ───────────────────────────────────────────────────────────
    a("## Quiet-Check Comparison (runs 1–2)")
    a("")
    a("Per-command: prompt vs quiet output length and masked similarity.")
    a("Flags where prompt is shorter/empty than quiet and drop > quiet-vs-quiet noise floor.")
    a("")
    for tname, qc in sorted(quiet_checks.items()):
        a(f"### {tname}")
        a(f"Pairs checked: {qc.get('pairs_checked','—')}, flagged: {qc.get('flagged','—')}")
        if qc.get("flagged_details"):
            a("")
            a("| run | cmd_id | prompt_len | quiet_len | sim_pq | floor | drop | shorter | >floor |")
            a("|---|---|---:|---:|---:|---:|---:|---|---|")
            for fl in qc["flagged_details"]:
                a(f"| {fl.get('run')} | {fl.get('cmd_id')} | {fl.get('prompt_len')} "
                  f"| {fl.get('quiet_len')} | {_fmt(fl.get('sim_pq'))} "
                  f"| {_fmt(fl.get('noise_floor'))} | {_fmt(fl.get('drop_vs_floor'))} "
                  f"| {fl.get('is_shorter')} | {fl.get('exceeds_floor')} |")
        a("")

    # ── Extra vs ground truth ────────────────────────────────────────────────
    a("## Extra Seconds Over Ground Truth (prompt mode, floor-free)")
    a("")
    a("Target run-median minus groundtruth_ssh run-median. Bootstrap CI resamples run differences.")
    a("")
    a("| Target | n_runs | extra_median (s) | 95% CI |")
    a("|---|---:|---:|---|")
    for tname, ev in sorted(extra_vs_gt.items()):
        a(f"| {tname} "
          f"| {ev.get('n_runs','—')} "
          f"| {_fmt(ev.get('extra_median_s'))} "
          f"| {_ci_str(ev.get('ci_extra_95'))} |")
    a("")
    a(f"*Note: {next(iter(extra_vs_gt.values()), {}).get('note', '')}*")
    a("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage 4 analyzer")
    p.add_argument("--stage4-dir", default=str(DEFAULT_STAGE4_DIR),
                   help=f"Stage 4 output directory (default: {DEFAULT_STAGE4_DIR})")
    p.add_argument("--validation-dir", default=str(VALIDATION_DIR),
                   help=f"Stage 2 validation directory for quiet-check baseline (default: {VALIDATION_DIR})")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdio()
    args = parse_args(argv)
    stage4_dir = Path(args.stage4_dir)
    val_dir    = Path(args.validation_dir)

    raw_dir   = stage4_dir / "raw"
    rawh_dir  = stage4_dir / "raw_http"
    quiet_dir = stage4_dir / QUIET_SUBDIR
    proxy_log = stage4_dir / "api_proxy_log.jsonl"

    if not stage4_dir.exists():
        _safe_print(f"ERROR: stage4-dir {stage4_dir} does not exist.", file=sys.stderr)
        return 1

    _safe_print(f"[analyze_stage4] Loading SSH data from {raw_dir}...")
    ssh_prompt_data = _load_all_ssh(raw_dir) if raw_dir.exists() else {}
    quiet_data = _load_all_ssh(quiet_dir) if quiet_dir.exists() else {}
    # Quiet-check rows are kept in their own directory by the driver (so they can
    # never overwrite the prompt JSONL). They are excluded from the prompt-mode
    # statistics but used for the prompt-vs-quiet comparison below.
    all_ssh: dict[str, list[dict[str, Any]]] = {
        t: list(recs) for t, recs in ssh_prompt_data.items()
    }
    for tname, recs in quiet_data.items():
        all_ssh.setdefault(tname, []).extend(recs)
    ssh_data = {
        t: [r for r in recs if r.get("s4_timing_mode") != "quiet"]
        for t, recs in all_ssh.items()
    }
    n_quiet_rows = sum(1 for recs in quiet_data.values() for _ in recs)
    if quiet_data:
        _safe_print(f"[analyze_stage4] Quiet-check rows from {quiet_dir}: {n_quiet_rows}")
    _safe_print(f"[analyze_stage4] Loading HTTP data from {rawh_dir}...")
    http_data = _load_all_http(rawh_dir) if rawh_dir.exists() else {}

    gt_records  = ssh_data.get("groundtruth_ssh", [])
    gt_h_records = http_data.get("groundtruth_http", [])

    proxy_rows  = _load_proxy_log(proxy_log)
    boundaries  = _load_slot_boundaries(proxy_log)
    manifest    = _load_manifest(stage4_dir)

    # Collect run numbers per target
    runs_by_target: dict[str, list[int]] = {}
    for tname, recs in ssh_data.items():
        runs_by_target[tname] = sorted({
            int(r.get("s4_run", r.get("run", 0)))
            for r in recs if r.get("s4_run", r.get("run")) is not None
        })

    _safe_print("[analyze_stage4] Analyzing SSH targets...")
    ssh_stats: dict[str, dict[str, Any]] = {}
    for tname, records in ssh_data.items():
        runs = runs_by_target.get(tname, [])
        ssh_stats[tname] = _analyze_ssh_target_s4(tname, records, gt_records, runs)

    _safe_print("[analyze_stage4] Analyzing HTTP targets...")
    http_stats: dict[str, dict[str, Any]] = {}
    for tname, records in http_data.items():
        http_stats[tname] = _analyze_http_target_s4(tname, records, gt_h_records)

    _safe_print("[analyze_stage4] Drift checks...")
    drift_checks: dict[str, dict[str, Any]] = {}
    for tname in ("cowrie", "groundtruth_ssh"):
        if tname in ssh_data:
            drift_checks[tname] = _drift_check(ssh_data[tname], tname)

    _safe_print("[analyze_stage4] Order effects...")
    order_effects: dict[str, dict[str, Any]] = {}
    for tname in LLM_SSH_TARGETS:
        if ssh_data.get(tname):
            order_effects[tname] = _order_effect(ssh_data[tname], manifest, tname)

    _safe_print("[analyze_stage4] Proxy join...")
    proxy_joins: dict[str, dict[str, Any]] = {}
    for tname in list(LLM_SSH_TARGETS) + list(LLM_SSH_TARGETS & set(ssh_data)):
        if ssh_data.get(tname):
            proxy_joins[tname] = _join_proxy(
                ssh_data[tname], list(proxy_rows), list(boundaries), tname
            )
    for tname in {"galah"}:
        if tname in http_data:
            proxy_joins[tname] = _join_proxy(
                http_data[tname], list(proxy_rows), list(boundaries), tname
            )

    _safe_print("[analyze_stage4] Quiet-check comparison...")
    quiet_checks: dict[str, dict[str, Any]] = {}
    for tname in LLM_SSH_TARGETS:
        if tname in ssh_data:
            # Prompt records: s4_timing_mode == "prompt" (raw/),
            # quiet records: raw_quiet/
            prompt_recs = [r for r in all_ssh.get(tname, [])
                           if r.get("s4_timing_mode") == "prompt"]
            quiet_recs  = [r for r in all_ssh.get(tname, [])
                           if r.get("s4_timing_mode") == "quiet"]
            if prompt_recs or quiet_recs:
                quiet_checks[tname] = _quiet_check(prompt_recs, quiet_recs, val_dir, tname)

    _safe_print("[analyze_stage4] Extra vs ground truth...")
    extra_vs_gt_map: dict[str, dict[str, Any]] = {}
    for tname, records in ssh_data.items():
        if tname != "groundtruth_ssh" and gt_records:
            extra_vs_gt_map[tname] = _extra_vs_gt(records, gt_records, tname)

    # Build Markdown
    _safe_print("[analyze_stage4] Writing analysis.md...")
    md = _build_analysis_md(
        ssh_stats, http_stats, drift_checks, order_effects,
        proxy_joins, quiet_checks, extra_vs_gt_map, stage4_dir,
    )
    analysis_path = stage4_dir / "analysis.md"
    analysis_path.write_text(md, encoding=ENCODING)
    _safe_print(f"Written: {analysis_path}")

    # Write CSVs
    _write_csvs(stage4_dir, ssh_stats, http_stats, drift_checks,
                extra_vs_gt_map, proxy_joins)

    return 0


def _write_csvs(
    stage4_dir: Path,
    ssh_stats: dict[str, dict[str, Any]],
    http_stats: dict[str, dict[str, Any]],
    drift_checks: dict[str, dict[str, Any]],
    extra_vs_gt: dict[str, dict[str, Any]],
    proxy_joins: dict[str, dict[str, Any]],
) -> None:
    # latency.csv
    lat_path = stage4_dir / "latency.csv"
    with open(lat_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "target", "n_runs", "n_commands", "n_timeouts", "timeout_rate",
            "latency_median_s", "latency_p95_s",
            "ci_latency_lo", "ci_latency_hi",
        ], extrasaction="ignore")
        writer.writeheader()
        for tname, s in sorted(ssh_stats.items()):
            ci = s.get("ci_latency_median") or (None, None)
            writer.writerow({
                "target": tname,
                "n_runs": s.get("n_runs"),
                "n_commands": s.get("n_commands"),
                "n_timeouts": s.get("n_timeouts"),
                "timeout_rate": s.get("timeout_rate"),
                "latency_median_s": s.get("latency_median"),
                "latency_p95_s": s.get("latency_p95"),
                "ci_latency_lo": ci[0],
                "ci_latency_hi": ci[1],
            })
    _safe_print(f"Written: {lat_path}")

    # determinism.csv
    det_path = stage4_dir / "determinism.csv"
    with open(det_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "target", "determinism_masked", "ci_det_lo", "ci_det_hi",
            "fidelity_masked",
        ], extrasaction="ignore")
        writer.writeheader()
        for tname, s in sorted(ssh_stats.items()):
            ci = s.get("ci_determinism") or (None, None)
            writer.writerow({
                "target": tname,
                "determinism_masked": s.get("determinism_masked"),
                "ci_det_lo": ci[0],
                "ci_det_hi": ci[1],
                "fidelity_masked": s.get("fidelity_masked"),
            })
    _safe_print(f"Written: {det_path}")

    # drift.csv
    drift_path = stage4_dir / "drift.csv"
    with open(drift_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "target", "n_runs",
            "rho_vs_run", "p_vs_run",
            "rho_vs_wall", "p_vs_wall",
        ], extrasaction="ignore")
        writer.writeheader()
        for tname, d in sorted(drift_checks.items()):
            rv = d.get("spearman_vs_run_index", {})
            wv = d.get("spearman_vs_wall_hour", {})
            writer.writerow({
                "target": tname,
                "n_runs": d.get("n_runs"),
                "rho_vs_run": rv.get("rho"),
                "p_vs_run": rv.get("p"),
                "rho_vs_wall": wv.get("rho"),
                "p_vs_wall": wv.get("p"),
            })
    _safe_print(f"Written: {drift_path}")

    # extra vs gt
    extra_path = stage4_dir / "extra_vs_gt.csv"
    with open(extra_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "target", "n_runs", "extra_median_s", "ci_lo", "ci_hi",
        ], extrasaction="ignore")
        writer.writeheader()
        for tname, ev in sorted(extra_vs_gt.items()):
            ci = ev.get("ci_extra_95") or (None, None)
            writer.writerow({
                "target": tname,
                "n_runs": ev.get("n_runs"),
                "extra_median_s": ev.get("extra_median_s"),
                "ci_lo": ci[0],
                "ci_hi": ci[1],
            })
    _safe_print(f"Written: {extra_path}")

    # proxy_join.csv
    proxy_path = stage4_dir / "proxy_join.csv"
    with open(proxy_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "target", "matched", "unmatched",
            "api_duration_median_ms", "api_duration_p95_ms", "gap_median_ms",
        ], extrasaction="ignore")
        writer.writeheader()
        for tname, pj in sorted(proxy_joins.items()):
            writer.writerow({
                "target": tname,
                "matched": pj.get("matched"),
                "unmatched": pj.get("unmatched"),
                "api_duration_median_ms": pj.get("api_duration_median_ms"),
                "api_duration_p95_ms": pj.get("api_duration_p95_ms"),
                "gap_median_ms": pj.get("gap_median_ms"),
            })
    _safe_print(f"Written: {proxy_path}")


if __name__ == "__main__":
    sys.exit(main())
