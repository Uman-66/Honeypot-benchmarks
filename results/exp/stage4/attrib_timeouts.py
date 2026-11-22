#!/usr/bin/env python3
"""Read-only timeout attribution + completion-token distribution (Part A).

Joins every timed-out SSH row in the Stage 4 raw/ and raw_quiet/ data and in the
Stage 2 validation passes with the matching api_proxy_log entry and classifies
the timeout:

  api      the matched request ran >= the harness timeout (120 s), or started so
           late that an on-time reply was impossible
  target   the proxy replied well before the timeout (API duration printed) but
           the harness never saw the prompt
  unmatched  no proxy request was assigned to the command

Attribution rules:
  * Stage 4: proxy rows carry one ``slot_start`` marker per (run, target, mode).
    A request belongs to the latest marker whose ``ts`` (request START, the proxy
    stamps ``ts`` before forwarding) is <= the request's own ``ts``.  File order
    is by completion, so it must not be used: a 250 s generation is written to
    the log long after the next slot's marker.
  * Stage 2: the validation proxy log has no markers, so windows are built from
    each pass file's own command timestamps.
  * Inside a window every proxy entry is assigned at most once, to the latest
    command whose ``t_send`` <= the request ``ts`` (one-to-one, no reuse).

Writes nothing but stdout.
"""
import glob
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

TIMEOUT = 120.0
NEAR_CEILING = 60000          # "at or near 65,536" completion tokens
CAPS = {"advshellm": 4096, "vellmes": 800}   # documented in BENCHMARK.md / .tex
LLM_TARGETS = ["deceive", "beelzebub", "advshellm", "vellmes"]

ROOT = Path("results/exp/stage4")


def load(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def ts(row):
    return datetime.fromisoformat(row["ts"])


def pct(vals, p):
    if not vals:
        return float("nan")
    v = sorted(vals)
    k = p / 100.0 * (len(v) - 1)
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


class Window:
    def __init__(self, origin, target, run, mode, start, end):
        self.origin = origin        # "stage4" | "validation"
        self.target = target
        self.run = run
        self.mode = mode
        self.start = start
        self.end = end
        self.reqs = []

    def contains(self, t):
        return self.start <= t < self.end


def stage4_windows(proxy_log):
    rows = load(proxy_log)
    marks = [(i, r) for i, r in enumerate(rows) if r.get("event") == "slot_start"]
    out = []
    for n, (i, m) in enumerate(marks):
        start = ts(m)
        end = ts(marks[n + 1][1]) if n + 1 < len(marks) else start + timedelta(hours=6)
        out.append(Window("stage4", m["target"], m["run"], m["mode"], start, end))
    wins = sorted(out, key=lambda w: w.start)
    for r in rows:
        if r.get("event"):
            continue
        t = ts(r)
        own = None
        for w in wins:
            if w.start <= t:
                own = w
            else:
                break
        if own is not None:
            own.reqs.append(r)
    return wins


def validation_windows(proxy_log, pass_files):
    rows = load(proxy_log)
    wins = []
    best_run = {}
    for f in pass_files:
        recs = [r for r in load(f) if r.get("t_send") is not None]
        if not recs:
            continue
        name = Path(f).name
        target = name.split("_pass")[0]
        mode = "quiet" if "quiet" in name else "prompt"
        run = best_run.get(target, 0) + 1
        best_run[target] = run
        t0 = min(r["t_send"] for r in recs) - 2.0
        t1 = max(r["t_send"] + (r.get("latency_s") or 0.0) for r in recs) + TIMEOUT + 5.0
        wins.append(Window("validation", target, run, mode,
                           datetime.fromtimestamp(t0, timezone.utc),
                           datetime.fromtimestamp(t1, timezone.utc)))
    wins.sort(key=lambda w: w.start)
    for r in rows:
        t = ts(r)
        for w in wins:
            if w.contains(t):
                w.reqs.append(r)
                break
    return wins


def assign(windows, commands):
    """Assign each proxy entry to at most one command (latest t_send <= req ts)."""
    for c in commands:
        c["_api"] = []
        c["_assigned"] = False
    for w in windows:
        w.reqs.sort(key=lambda r: ts(r))
        cmds = sorted(
            (c for c in commands
             if c.get("t_send") is not None and c["target"] == w.target
             and c["mode"] == w.mode and w.contains(
                 datetime.fromtimestamp(c["t_send"], timezone.utc))),
            key=lambda c: c["t_send"])
        j = 0
        for r in w.reqs:
            t = ts(r).timestamp()
            owner = None
            while j < len(cmds) and cmds[j]["t_send"] <= t + 0.25:
                owner = cmds[j]
                j += 1
            if owner is not None:
                owner["_api"].append(r)
                owner["_assigned"] = True


def w_run(c):
    return c.get("s4_run", c.get("run"))


def classify(row):
    api = row.get("_api") or []
    if not api:
        return "unmatched", None, None, None
    durs = [r.get("duration_ms", 0) / 1000.0 for r in api]
    delays = [ts(r).timestamp() - row["t_send"] for r in api]
    dmax, dmin_delay = max(durs), min(delays)
    comp = max((int(r.get("completion_tokens") or 0) for r in api), default=0)
    if dmax >= TIMEOUT or (dmin_delay + dmax) >= TIMEOUT:
        return "api", dmax, dmin_delay, comp
    return "target", dmax, dmin_delay, comp


def collect_stage4():
    cmds = []
    for d, mode in (("raw", "prompt"), ("raw_quiet", "quiet")):
        for p in sorted((ROOT / d).glob("*_run*.jsonl")):
            target, run = p.stem.rsplit("_run", 1)
            for r in load(p):
                if not r.get("cmd_id"):
                    continue
                r["target"], r["mode"], r["run"] = target, mode, int(run)
                cmds.append(r)
    wins = stage4_windows(ROOT / "api_proxy_log.jsonl")
    return wins, cmds


def collect_validation():
    files = sorted(glob.glob("results/exp/validation/*_pass*.jsonl"))
    cmds = []
    for f in files:
        name = Path(f).name
        target = name.split("_pass")[0]
        mode = "quiet" if "quiet" in name else "prompt"
        for r in load(f):
            if not r.get("cmd_id"):
                continue
            r["target"], r["mode"] = target, mode
            cmds.append(r)
    wins = validation_windows("results/exp/validation/api_proxy_log.jsonl", files)
    return wins, cmds


def report(origin, wins, cmds):
    assign(wins, cmds)
    to_rows = [c for c in cmds
               if c.get("timed_out") and c.get("cmd_id") != "exit"]
    classes = Counter()
    dur_by_class = defaultdict(list)
    per_target = defaultdict(Counter)
    per_cmd = defaultdict(Counter)
    rows_detail = []
    near_ceiling = 0
    for c in to_rows:
        cls, dmax, delay, comp = classify(c)
        classes[cls] += 1
        per_target[(c["target"], c["mode"])][cls] += 1
        per_cmd[(c["target"], c["cmd_id"])][cls] += 1
        if dmax is not None:
            dur_by_class[cls].append(dmax)
        if comp is not None and comp >= NEAR_CEILING:
            near_ceiling += 1
        rows_detail.append((c["target"], c["mode"], w_run(c), c["cmd_id"], cls,
                            dmax, delay, comp, len(c.get("_api") or [])))

    print(f"\n{'='*78}\n{origin.upper()}: {len(to_rows)} timed-out rows "
          f"over {len(cmds)} rows\n{'='*78}")
    print("class totals:", dict(classes))
    print("\nper target/mode:")
    for k in sorted(per_target):
        print(f"  {k[0]:16s} {k[1]:6s} {dict(per_target[k])}")
    print("\nAPI duration (s) by class:")
    for cls in ("api", "target", "unmatched"):
        d = dur_by_class.get(cls, [])
        if d:
            print(f"  {cls:8s} n={len(d):3d} min={min(d):7.1f} p50={pct(d,50):7.1f} "
                  f"p90={pct(d,90):7.1f} max={max(d):7.1f}")
        else:
            print(f"  {cls:8s} n=0")
    print(f"\ntimed-out rows whose matched completion_tokens >= {NEAR_CEILING}: "
          f"{near_ceiling}")
    print("\nper command (timed-out only):")
    for k in sorted(per_cmd):
        print(f"  {k[0]:16s} {k[1]:22s} {dict(per_cmd[k])}")
    print("\nrow detail (target, mode, run, cmd, class, api_s, start_delay_s, "
          "completion_tokens, matched_rows):")
    for d in sorted(rows_detail):
        print("  " + " | ".join(
            f"{v:.1f}" if isinstance(v, float) else str(v) for v in d))
    return to_rows, classes


def token_distribution(name, cmds):
    print(f"\n{'='*78}\nCOMPLETION TOKENS (timeout-joined attribution) — {name}\n{'='*78}")
    by = defaultdict(list)
    for c in cmds:
        for r in c.get("_api") or []:
            if (r.get("path") or "").endswith("/chat/completions"):
                by[c["target"]].append((int(r.get("completion_tokens") or 0),
                                        int((r.get("usage") or {}).get(
                                            "completion_tokens_details", {})
                                            .get("reasoning_tokens") or 0)))
    for t in sorted(by):
        vals = [v for v, _ in by[t]]
        reasons = [rr for _, rr in by[t]]
        cap = CAPS.get(t)
        over = sum(1 for v in vals if cap is not None and v > cap)
        print(f"  {t:14s} n={len(vals):4d} p50={pct(vals,50):8.1f} "
              f"p95={pct(vals,95):9.1f} max={max(vals):7d} "
              f"cap={cap if cap is not None else 'none/unknown'} over_cap={over} "
              f"reasoning_max={max(reasons) if reasons else 0}")


def main():
    w4, c4 = collect_stage4()
    report("stage 4 (raw/ + raw_quiet/)", w4, c4)
    token_distribution("stage 4", c4)
    wv, cv = collect_validation()
    report("stage 2 validation passes", wv, cv)

    print(f"\n{'='*78}\nPROXY-LOG-ORDER vs REQUEST-START ATTRIBUTION\n{'='*78}")
    rows = load(ROOT / "api_proxy_log.jsonl")
    big = [(i, r) for i, r in enumerate(rows)
           if (r.get("completion_tokens") or 0) >= NEAR_CEILING]
    marks = [(i, r) for i, r in enumerate(rows) if r.get("event") == "slot_start"]
    print(f"{len(big)} requests with completion_tokens >= {NEAR_CEILING}")
    for i, r in big:
        prev = [m for _, m in marks if ts(m) <= ts(r)]
        fwd = None
        j = i - 1
        while j >= 0:
            if rows[j].get("event") == "slot_start":
                fwd = rows[j]
                break
            j -= 1
        start_owner = prev[-1]["target"] if prev else "?"
        file_owner = fwd["target"] if fwd else "?"
        print(f"  {r['ts']} dur={r['duration_ms']/1000:6.0f}s "
              f"comp={r['completion_tokens']:6d} "
              f"reasoning={(r.get('usage') or {}).get('completion_tokens_details', {}).get('reasoning_tokens')} "
              f"start_owner={start_owner:12s} file_order_owner={file_owner}")


if __name__ == "__main__":
    main()
