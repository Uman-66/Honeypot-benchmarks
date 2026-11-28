#!/usr/bin/env python3
"""
harness/recheck_v21b_det.py

Audit of Issue 1: DECEIVE masked determinism (0.5086 published vs 0.522
reviewer).  Re-derives everything from the raw JSONL files; writes NEW files
with the _v21b suffix and never touches determinism.csv or the v2/v2.1 outputs.

Grid
----
Every choice below is enumerated and every target is computed for every
combination:

    exit row          kept / dropped                              (2)
    timed-out rows    as recorded / as empty / dropped / pair-only (4)
    empty outputs     kept / dropped                              (2)
    pair definition   all / consecutive / vs run 1 / vs medoid    (4)
    aggregation       mean of per-command means / pooled / per-run (3)
                                                             = 192
    text/mask/cap/sim 11 cached matrix configurations            (11)

so 2,112 combinations per target, 12,672 in total.  The matrix
configurations are the expensive dimension (difflib is quadratic), so each is
built once per target and cached; the 192 aggregation choices are then cheap.
Configurations that would take longer than TIME_BUDGET_PER_CONFIG are recorded
as "time_limit" instead of being silently dropped.

Similarity functions
--------------------
difflib  SequenceMatcher(...).ratio(), autojunk True and False
quick    SequenceMatcher(...).quick_ratio()
lev      exact Levenshtein distance via Myers' bit-parallel algorithm, mapped
         to 1 - dist / max(len(a), len(b))

Usage
-----
    python harness/recheck_v21b_det.py
    python harness/recheck_v21b_det.py --targets deceive beelzebub
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import pickle
import re
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_stage4 as s4  # noqa: E402

ENCODING = "utf-8"
STAGE4 = Path("results/exp/stage4")
RAW = STAGE4 / "raw"
CACHE = Path("results/exp/stage4/.cache_v21b")

SCORED = ["advshellm", "beelzebub", "cowrie", "deceive", "groundtruth_ssh", "vellmes"]

# Published v2 values (must be reproduced by M1, exit dropped, timeouts as
# recorded, empties kept, all pairs, mean of per-command means).
PUBLISHED = {
    "advshellm": 0.7903, "beelzebub": 0.5940, "cowrie": 0.9964,
    "deceive": 0.5086, "groundtruth_ssh": 0.9923, "vellmes": 0.8477,
}
REVIEWER_DECEIVE = 0.522
REVIEWER_TOL = 0.004
HIT_TOL = 0.0005

TIME_BUDGET_PER_CONFIG = 240.0     # seconds per (target, matrix config)
NO_CAP_MAX_LEN = 60_000            # above this, difflib with no cap is skipped

# ─────────────────────────────────────────────────────────────────────────────
# Levenshtein (Myers bit-parallel, exact)
# ─────────────────────────────────────────────────────────────────────────────

def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    pm: dict[str, int] = {}
    for i, ch in enumerate(a):
        pm[ch] = pm.get(ch, 0) | (1 << i)
    full = (1 << len(a)) - 1
    high = 1 << (len(a) - 1)
    vp, vn, score = full, 0, len(a)
    for ch in b:
        pmj = pm.get(ch, 0)
        x = pmj | vn
        d0 = (((vp + (x & vp)) & full) ^ vp) | x
        hp = vn | (~(d0 | vp) & full)
        hn = d0 & vp
        if hp & high:
            score += 1
        elif hn & high:
            score -= 1
        hp = ((hp << 1) | 1) & full
        hn = (hn << 1) & full
        vp = (hn | (~(d0 | hp) & full)) & full
        vn = (hp & d0) & full
    return score


def _lev_ratio(a: str, b: str) -> float:
    n = max(len(a), len(b))
    if n == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / n


def _self_test() -> None:
    """Exactness check of the bit-parallel distance against a DP table."""
    import random
    rng = random.Random(7)

    def dp(a: str, b: str) -> int:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]

    for _ in range(200):
        a = "".join(rng.choice("abc\n 01") for _ in range(rng.randint(0, 40)))
        b = "".join(rng.choice("abc\n 01") for _ in range(rng.randint(0, 40)))
        assert levenshtein(a, b) == dp(a, b), (a, b, levenshtein(a, b), dp(a, b))


# ─────────────────────────────────────────────────────────────────────────────
# Text variants
# ─────────────────────────────────────────────────────────────────────────────

TS_RE = re.compile(r"\b(?:[A-Z][a-z]{2}\s+\d{1,2}|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}(?::\d{2})?)\b")
PID_RE = re.compile(r"\b(?:pid|PID)[=: ]\s*\d+\b|\b\d{2,6}\b")


def hostnames(rows: list[dict[str, Any]]) -> frozenset[str]:
    names = set()
    for r in rows:
        if r.get("cmd_id") == "hostname":
            first = (r.get("cleaned_output") or "").strip().splitlines()
            if first:
                names.add(first[0].strip())
    return frozenset(n for n in names if n)


def texts_for(row: dict[str, Any], names: frozenset[str]) -> dict[tuple[str, str], str]:
    """Every (source, mask) text this row can contribute."""
    cleaned = row.get("cleaned_output") or ""
    raw = row.get("raw_output") or ""
    ansi = s4._strip_ansi(raw)          # real ESC bytes removed from the raw capture
    out = {}
    for src, text in (("cleaned", cleaned), ("raw", raw), ("ansi", ansi)):
        out[(src, "hostname")] = s4._mask_text(text, names)
        out[(src, "none")] = text
        out[(src, "ts_pid")] = PID_RE.sub("<N>", TS_RE.sub("<TS>", text))
    return out


def load_target(target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(RAW.glob(f"{target}_run*.jsonl")):
        if ".bak" in path.name:
            continue
        rows.extend(s4._load_jsonl(path))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Matrix configurations
# ─────────────────────────────────────────────────────────────────────────────

CONFIGS: list[dict[str, Any]] = [
    {"id": "M1",  "source": "cleaned", "mask": "hostname", "cap": 4000,  "sim": "diff_aj",
     "text": "published: cleaned_output, hostnames masked, 4,000 cap, SequenceMatcher.ratio (autojunk on)"},
    {"id": "M2",  "source": "cleaned", "mask": "hostname", "cap": 4000,  "sim": "diff_aj_false",
     "text": "as M1 but autojunk=False"},
    {"id": "M3",  "source": "cleaned", "mask": "hostname", "cap": 4000,  "sim": "quick",
     "text": "as M1 but quick_ratio()"},
    {"id": "M4",  "source": "cleaned", "mask": "hostname", "cap": 4000,  "sim": "lev",
     "text": "as M1 but exact Levenshtein ratio 1 - d/max(n,m)"},
    {"id": "M5",  "source": "cleaned", "mask": "none",     "cap": 4000,  "sim": "diff_aj",
     "text": "as M1 but no masking"},
    {"id": "M6",  "source": "cleaned", "mask": "ts_pid",   "cap": 4000,  "sim": "diff_aj",
     "text": "as M1 but only timestamps/PIDs masked"},
    {"id": "M7",  "source": "raw",     "mask": "hostname", "cap": 4000,  "sim": "diff_aj",
     "text": "raw_output instead of cleaned_output (echo not removed), hostnames masked"},
    {"id": "M8",  "source": "raw",     "mask": "none",     "cap": 4000,  "sim": "diff_aj",
     "text": "raw_output, no masking"},
    {"id": "M9",  "source": "ansi",    "mask": "none",     "cap": 4000,  "sim": "diff_aj",
     "text": "raw_output with real ESC sequences stripped, no masking"},
    {"id": "M10", "source": "cleaned", "mask": "hostname", "cap": 20000, "sim": "diff_aj",
     "text": "as M1 but 20,000-char cap"},
    {"id": "M11", "source": "cleaned", "mask": "hostname", "cap": 0,     "sim": "diff_aj",
     "text": "as M1 but no cap"},
]


def sim_fn(name: str):
    if name == "diff_aj":
        return lambda a, b: difflib.SequenceMatcher(None, a, b, autojunk=True).ratio()
    if name == "diff_aj_false":
        return lambda a, b: difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if name == "quick":
        return lambda a, b: difflib.SequenceMatcher(None, a, b).quick_ratio()
    if name == "lev":
        return _lev_ratio
    raise ValueError(name)


def row_meta(target: str, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per-command row flags; cheap and independent of the matrix config."""
    by_cmd: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cid = r.get("cmd_id") or ""
        if not cid:
            continue
        by_cmd.setdefault(cid, []).append({
            "empty": not (r.get("cleaned_output") or "").strip(),
            "timeout": bool(r.get("timed_out")),
        })
    return by_cmd


def build_matrix_config(target: str, cfg: dict[str, Any]) -> tuple[
        dict[str, list[list[float]]] | None, str]:
    """Build (or load) one (target, config) matrix set.  Cached on disk."""
    rows = load_target(target)
    names = hostnames(rows)
    by_cmd: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cid = r.get("cmd_id") or ""
        if not cid:
            continue
        text = texts_for(r, names)[(cfg["source"], cfg["mask"])]
        if cfg["cap"]:
            text = text[: cfg["cap"]]
        by_cmd.setdefault(cid, []).append({"text": text})

    maxlen = max((len(r["text"]) for rs in by_cmd.values() for r in rs), default=0)
    if cfg["cap"] == 0 and maxlen > NO_CAP_MAX_LEN:
        return None, f"skipped: longest output {maxlen:,} chars; no-cap difflib not time-feasible"

    key = hashlib.sha256(
        f"{target}|{cfg['source']}|{cfg['mask']}|{cfg['cap']}|{cfg['sim']}".encode()
    ).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    cpath = CACHE / f"{target}_{key}.pkl"
    if cpath.exists():
        with open(cpath, "rb") as fh:
            return pickle.load(fh), "cached"

    fn = sim_fn(cfg["sim"])
    t0 = time.time()
    out: dict[str, list[list[float]]] = {}
    for cid, rs in by_cmd.items():
        if len(rs) < 2:
            continue
        n = len(rs)
        m = [[1.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                m[i][j] = m[j][i] = fn(rs[i]["text"], rs[j]["text"])
        out[cid] = m
        if time.time() - t0 > TIME_BUDGET_PER_CONFIG:
            return None, f"time_limit: exceeded {TIME_BUDGET_PER_CONFIG:.0f}s at command {cid}"
    with open(cpath, "wb") as fh:
        pickle.dump(out, fh)
    return out, f"built in {time.time() - t0:.1f}s ({maxlen} max chars)"


def _worker(task: tuple[str, str]) -> tuple[str, str, dict[str, list[list[float]]] | None, str]:
    target, cfg_id = task
    cfg = next(c for c in CONFIGS if c["id"] == cfg_id)
    mats, st = build_matrix_config(target, cfg)
    return target, cfg_id, mats, st


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation grid
# ─────────────────────────────────────────────────────────────────────────────

EXIT_LEVELS = ("dropped", "kept")
TIMEOUT_LEVELS = ("recorded", "empty", "dropped", "pair_excluded")
EMPTY_LEVELS = ("kept", "dropped")
PAIR_LEVELS = ("all", "consecutive", "vs_first", "vs_medoid")
AGG_LEVELS = ("cmd_mean", "pooled", "run_mean")


def _pairs(idx: list[int], how: str, matrix: list[list[float]]) -> list[tuple[int, int]]:
    if how == "all":
        return [(idx[a], idx[b]) for a in range(len(idx)) for b in range(a + 1, len(idx))]
    if how == "consecutive":
        return [(idx[a], idx[a + 1]) for a in range(len(idx) - 1)]
    if how == "vs_first":
        return [(idx[0], idx[b]) for b in range(1, len(idx))]
    # vs_medoid: the run with the highest mean similarity to the other kept runs
    best, best_val = idx[0], -1.0
    for i in idx:
        vals = [matrix[i][j] for j in idx if j != i]
        if vals and statistics.mean(vals) > best_val:
            best, best_val = i, statistics.mean(vals)
    return [(best, j) for j in idx if j != best]


def evaluate(by_cmd: dict[str, list[dict[str, Any]]],
             mats: dict[str, list[list[float]]],
             exit_level: str, tmo: str, empty: str, pair_how: str, agg: str) -> dict[str, Any]:
    per_cmd: list[float] = []
    all_pairs: list[float] = []
    per_run_acc: dict[int, list[float]] = {}

    for cid, matrix in mats.items():
        rs = by_cmd[cid]
        if cid == "exit" and exit_level == "dropped":
            continue
        idx = [i for i, r in enumerate(rs) if not (empty == "dropped" and r["empty"])]
        if tmo == "dropped":
            idx = [i for i in idx if not rs[i]["timeout"]]
        if len(idx) < 2:
            continue
        pairs = _pairs(idx, pair_how, matrix)
        vals: list[float] = []
        for i, j in pairs:
            ti, tj = rs[i]["timeout"], rs[j]["timeout"]
            if tmo == "pair_excluded" and (ti or tj):
                continue
            if tmo == "empty" and (ti or tj):
                # a censored row contributes no text: 1.0 only if both are censored
                vals.append(1.0 if (ti and tj) else 0.0)
                continue
            vals.append(matrix[i][j])
        if not vals:
            continue
        per_cmd.append(statistics.mean(vals))
        all_pairs.extend(vals)
        if agg == "run_mean":
            for i, j in pairs:
                if tmo == "pair_excluded" and (rs[i]["timeout"] or rs[j]["timeout"]):
                    continue
                per_run_acc.setdefault(i, []).append(matrix[i][j])
                per_run_acc.setdefault(j, []).append(matrix[i][j])

    if not per_cmd:
        return {"value": None, "n_cmds": 0, "n_pairs": 0}
    if agg == "pooled":
        value = statistics.mean(all_pairs)
    elif agg == "run_mean":
        value = statistics.mean([statistics.mean(v) for v in per_run_acc.values() if v])
    else:
        value = statistics.mean(per_cmd)
    return {"value": round(value, 6), "n_cmds": len(per_cmd), "n_pairs": len(all_pairs)}


# ─────────────────────────────────────────────────────────────────────────────
# Per-target explanation statistics
# ─────────────────────────────────────────────────────────────────────────────

def explain_stats(target: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cmd: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_cmd.setdefault(r.get("cmd_id") or "", []).append(r)
    n = len(rows)
    timeouts = sum(1 for r in rows if r.get("timed_out"))
    empty = sum(1 for r in rows if not (r.get("cleaned_output") or "").strip())
    long_rows = [r for r in rows if len(r.get("cleaned_output") or "") > 4000]
    maxlen = max((len(r.get("cleaned_output") or "") for r in rows), default=0)
    per_cmd_timeouts = {cid: sum(1 for r in rs if r.get("timed_out")) for cid, rs in by_cmd.items()}
    worst_t = sorted(per_cmd_timeouts.items(), key=lambda kv: -kv[1])[:3]
    return {
        "target": target,
        "rows": n,
        "timeouts": timeouts,
        "timeout_rate": round(timeouts / n, 4) if n else None,
        "empty_outputs": empty,
        "long_outputs_gt4000": len(long_rows),
        "max_len": maxlen,
        "timeouts_by_cmd": "; ".join(f"{c}={v}" for c, v in worst_t if v),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="*", default=SCORED)
    ap.add_argument("--out-dir", default=str(STAGE4))
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    _self_test()
    out_dir = Path(args.out_dir)

    grid: list[dict[str, Any]] = []
    status: list[dict[str, Any]] = []
    explain: list[dict[str, Any]] = []

    tasks = [(t, c["id"]) for t in args.targets for c in CONFIGS]
    built: dict[tuple[str, str], dict[str, list[list[float]]]] = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for target, cfg_id, mats, st in pool.map(_worker, tasks):
            status.append({"target": target, "config": cfg_id, "status": st,
                           "definition": next(c["text"] for c in CONFIGS if c["id"] == cfg_id)})
            if mats is not None:
                built[(target, cfg_id)] = mats
            print(f"[I1] {target:16s} {cfg_id:3s} {st}  ({time.time()-t0:.0f}s)", flush=True)

    for target in args.targets:
        t_tgt = time.time()
        rows = load_target(target)
        explain.append(explain_stats(target, rows))
        by_cmd_meta = row_meta(target, rows)
        for cfg in CONFIGS:
            mats = built.get((target, cfg["id"]))
            if mats is None:
                continue
            by_cmd = by_cmd_meta
            for ex in EXIT_LEVELS:
                for tmo in TIMEOUT_LEVELS:
                    for em in EMPTY_LEVELS:
                        for ph in PAIR_LEVELS:
                            for ag in AGG_LEVELS:
                                res = evaluate(by_cmd, mats, ex, tmo, em, ph, ag)
                                grid.append({
                                    "target": target, "config": cfg["id"],
                                    "exit_row": ex, "timeout_rows": tmo,
                                    "empty_outputs": em, "pair_definition": ph,
                                    "aggregation": ag, "determinism": res["value"],
                                    "n_commands": res["n_cmds"], "n_pairs": res["n_pairs"],
                                })
        print(f"[I1] {target:16s} aggregation done in {time.time()-t_tgt:.1f}s", flush=True)

    grid_path = out_dir / "determinism_grid_v21b.csv"
    with open(grid_path, "w", newline="", encoding=ENCODING) as fh:
        w = csv.DictWriter(fh, fieldnames=list(grid[0]))
        w.writeheader()
        w.writerows(grid)
    status_path = out_dir / "determinism_configs_v21b.csv"
    with open(status_path, "w", newline="", encoding=ENCODING) as fh:
        w = csv.DictWriter(fh, fieldnames=list(status[0]))
        w.writeheader()
        w.writerows(status)
    explain_path = out_dir / "determinism_explain_v21b.csv"
    with open(explain_path, "w", newline="", encoding=ENCODING) as fh:
        w = csv.DictWriter(fh, fieldnames=list(explain[0]))
        w.writeheader()
        w.writerows(explain)

    # ── reproduce published + success search ────────────────────────────────
    by_combo: dict[tuple, dict[str, float]] = {}
    for r in grid:
        if r["determinism"] is None:
            continue
        k = (r["config"], r["exit_row"], r["timeout_rows"], r["empty_outputs"],
             r["pair_definition"], r["aggregation"])
        by_combo.setdefault(k, {})[r["target"]] = r["determinism"]

    combined = [k for k, v in by_combo.items() if len(v) == len(SCORED)]
    print(f"[I1] combos with all {len(SCORED)} targets: {len(combined)} of {len(by_combo)}")

    repro = [k for k, v in by_combo.items()
             if len(v) == len(SCORED)
             and all(abs(v[t] - PUBLISHED[t]) <= 0.00005 for t in SCORED)]
    print(f"[I1] combos reproducing determinism.csv exactly: {len(repro)} -> {repro[:3]}")

    hits = []
    for k in combined:
        v = by_combo[k]
        if abs(v["deceive"] - REVIEWER_DECEIVE) <= HIT_TOL and all(
                abs(v[t] - PUBLISHED[t]) <= REVIEWER_TOL for t in SCORED if t != "deceive"):
            hits.append(k)
    hit_rows = []
    for k in hits:
        v = by_combo[k]
        hit_rows.append({
            "config": k[0], "exit_row": k[1], "timeout_rows": k[2],
            "empty_outputs": k[3], "pair_definition": k[4], "aggregation": k[5],
            **{f"{t}": v[t] for t in SCORED},
            "max_other_delta": round(max(abs(v[t] - PUBLISHED[t]) for t in SCORED
                                         if t != "deceive"), 6),
        })
    hit_path = out_dir / "determinism_success_v21b.csv"
    with open(hit_path, "w", newline="", encoding=ENCODING) as fh:
        if hit_rows:
            w = csv.DictWriter(fh, fieldnames=list(hit_rows[0]))
            w.writeheader()
            w.writerows(hit_rows)
        else:
            fh.write("no_combination_matched\n")
    print(f"[I1] combinations meeting the success criterion: {len(hit_rows)}")

    for k in repro[:3]:
        print("[I1] repro:", k, by_combo[k])
    for r in hit_rows[:10]:
        print("[I1] hit:", r["config"], r["exit_row"], r["timeout_rows"], r["empty_outputs"],
              r["pair_definition"], r["aggregation"], "dec=", r["deceive"],
              "max_other_delta=", r["max_other_delta"])
    for p in (grid_path, status_path, explain_path, hit_path):
        print(f"Written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
