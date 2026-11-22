#!/usr/bin/env python3
"""Read-only Stage 4 follow-up checks (points 1,3,4,6). Prints tables."""
import json, re, statistics, sys, importlib.util
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

R = Path("results/exp/stage4")
PUB = Path(r"C:\Users\Uman\AppData\Local\Temp\s4pub\results\raw")
VAL = Path("results/exp/validation")

spec = importlib.util.spec_from_file_location("az", "harness/analyze_stage4.py")
az = importlib.util.module_from_spec(spec)
spec.loader.exec_module(az)

def jl(p):
    out = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out

def clean(p): return [r for r in jl(p) if r.get("cmd_id") and r.get("cmd_id") != "exit"]

PROMPT_RE = re.compile(r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s")
def ends_with_prompt(o):
    s = (o or "").rstrip()
    if not s:
        return False
    last = s.splitlines()[-1]
    return last.rstrip().endswith("$") or last.rstrip().endswith("#")

LLM = ["deceive", "beelzebub", "vellmes", "advshellm"]
SSH = LLM + ["cowrie", "llmhoneypot", "groundtruth_ssh"]

print("== 1a. PROMPT-MODE INTEGRITY ==")
hdr = f"{'target':16}{'mode':8}{'rows':>6}{'no_echo':>9}{'no_final':>10}{'interior':>10}"
print(hdr)
for t in SSH:
    for d, mode in ((R / "raw", "prompt"), (R / "raw_quiet", "quiet")):
        rows = []
        for p in sorted(d.glob(f"{t}_run*.jsonl")):
            rows += clean(p)
        if not rows:
            continue
        ne = sum(1 for r in rows if r.get("prompt_without_echo") is True)
        nf = sum(1 for r in rows if not ends_with_prompt(r.get("cleaned_output")))
        it = sum(1 for r in rows if PROMPT_RE.search(r.get("cleaned_output") or "")
                 and not ends_with_prompt(r.get("cleaned_output")))
        print(f"{t:16}{mode:8}{len(rows):>6}{ne:>9}{nf:>10}{it:>10}")

print("\n== 1b. vellmes ls_etc run 2 ==")
vt = [r for r in clean(R / "raw/vellmes_run02.jsonl") if r["cmd_id"] == "ls_etc"][0]
vq = [r for r in clean(R / "raw_quiet/vellmes_run02.jsonl") if r["cmd_id"] == "ls_etc"][0]
print(f"prompt: timed_out={vt['timed_out']} latency={vt['latency_s']} bytes={vt['bytes']} "
      f"cleaned_len={len(vt.get('cleaned_output') or '')} raw={vt.get('raw_output')!r}")
print(f"quiet : timed_out={vq['timed_out']} latency={vq['latency_s']} bytes={vq['bytes']} "
      f"cleaned_len={len(vq.get('cleaned_output') or '')}")

# proxy overlap match for the prompt row
plog = jl(R / "api_proxy_log.jsonl")
reqs = [r for r in plog if r.get("event") != "slot_start"]
def ep(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
t0 = float(vt["t_send"]); t1 = t0 + float(vt["latency_s"])
near = [r for r in reqs if ep(r["ts"]) <= t1 + 5 and ep(r["ts"]) + (r.get("duration_ms") or 0) / 1000 >= t0 - 5]
print(f"proxy requests overlapping the 120 s window: {len(near)}")
for r in near:
    print(f"  status={r.get('status')} dur_ms={r.get('duration_ms')} start={r['ts']} "
          f"prompt={r.get('prompt_tokens')} completion={r.get('completion_tokens')} err={(r.get('error') or '')[:40]}")

print("\n== 1c. NOISE-FLOOR EXCEEDANCES (prompt shorter AND sim < A-vs-C quiet noise) ==")
hostnames = {}
for t in LLM:
    hs = set()
    for p in sorted((R / "raw").glob(f"{t}_run*.jsonl")):
        for r in clean(p):
            if r["cmd_id"] == "hostname":
                first = (r.get("cleaned_output") or "").strip().splitlines()
                if first:
                    hs.add(first[0].strip())
    hostnames[t] = frozenset(hs)

def masked(t, o): return az._mask_text(o or "", hostnames[t])

flagged_all = {}
for t in LLM:
    floor = {}
    a = {r["cmd_id"]: r.get("cleaned_output") or "" for r in clean(VAL / f"{t}_passA_quiet.jsonl")}
    c = {r["cmd_id"]: r.get("cleaned_output") or "" for r in clean(VAL / f"{t}_passC_quiet.jsonl")}
    for cid in set(a) & set(c):
        floor[cid] = az._similarity(masked(t, a[cid]), masked(t, c[cid]))
    pr, qr = {}, {}
    for rn in (1, 2):
        for r in clean(R / "raw" / f"{t}_run{rn:02d}.jsonl"):
            pr[(rn, r["cmd_id"])] = r
        for r in clean(R / "raw_quiet" / f"{t}_run{rn:02d}.jsonl"):
            qr[(rn, r["cmd_id"])] = r
    fl = []
    for k in sorted(set(pr) & set(qr)):
        po, qo = pr[k].get("cleaned_output") or "", qr[k].get("cleaned_output") or ""
        if len(po) < len(qo):
            s = az._similarity(masked(t, po), masked(t, qo))
            f = floor.get(k[1])
            if f is not None and s < f:
                fl.append({"run": k[0], "cmd": k[1], "plen": len(po), "qlen": len(qo),
                           "sim": round(s, 4), "floor": round(f, 4),
                           "lat": pr[k]["latency_s"], "t_send": pr[k].get("t_send"),
                           "row": pr[k]})
    flagged_all[t] = fl
    print(f"{t}: pairs=72 flagged={len(fl)}")
    for x in fl:
        print(f"   run{x['run']:>2} {x['cmd']:22} plen={x['plen']:>6} qlen={x['qlen']:>6} "
              f"sim={x['sim']:.3f} floor={x['floor']:.3f} lat={x['lat']}")

print("\n== 1d. harness latency vs overlapping API duration for flagged pairs ==")
bad = []
for t, fl in flagged_all.items():
    for x in fl:
        r = x["row"]
        if r.get("t_send") is None:
            print(f"{t} run{x['run']} {x['cmd']}: no t_send")
            continue
        s = float(r["t_send"]); e = s + float(r["latency_s"])
        hits = [rr for rr in reqs
                if ep(rr["ts"]) < e and ep(rr["ts"]) + (rr.get("duration_ms") or 0) / 1000 > s]
        durs = [rr.get("duration_ms") or 0 for rr in hits]
        maxd = max(durs) if durs else None
        flag = (maxd is not None and float(r["latency_s"]) * 1000 < maxd)
        if flag:
            bad.append((t, x["run"], x["cmd"], r["latency_s"], maxd, [h.get("status") for h in hits]))
        print(f"{t:11} run{x['run']} {x['cmd']:22} lat={r['latency_s']:>7} n_api={len(hits)} "
              f"api_max_ms={maxd} status={[h.get('status') for h in hits]} "
              f"{'LATENCY<API' if flag else ''}")
print("cases where harness latency < API duration:", bad or "none")

print("\n== 3. BEELZEBUB: published vs Stage 4 vs Stage 2 ==")
def stats(rows, label):
    to = sum(1 for r in rows if r.get("timed_out"))
    lat = [r["latency_s"] for r in rows if r.get("latency_s") is not None and not r.get("timed_out")]
    over = sum(1 for r in rows if len(r.get("cleaned_output") or "") > 20_000)
    leak = sum(1 for r in rows if PROMPT_RE.search(r.get("cleaned_output") or "")
               and not ends_with_prompt(r.get("cleaned_output")))
    print(f"  {label}: rows={len(rows)} timeouts={to} median={statistics.median(lat) if lat else None} "
          f"p95={az._pct(lat,95) if lat else None} oversized={over} leakage={leak}")
    return dict(rows=len(rows), to=to, med=statistics.median(lat) if lat else None, over=over, leak=leak)

pub = {}
for rn in range(1, 6):
    pub[rn] = stats(clean(PUB / f"beelzebub_run{rn:02d}.jsonl"), f"published run{rn}")
print("  published totals:", {k: round(v, 3) if isinstance(v, float) else v
                             for k, v in stats([r for rn in pub for r in clean(PUB / f"beelzebub_run{rn:02d}.jsonl")],
                                               "published all").items()})
s4 = {}
for rn in range(1, 21):
    s4[rn] = stats(clean(R / "raw" / f"beelzebub_run{rn:02d}.jsonl"), f"stage4 run{rn}")
print("\n Stage 2 validation beelzebub:")
for letter, kind in (("A", "quiet"), ("B", "prompt"), ("C", "quiet")):
    p = VAL / f"beelzebub_pass{letter}_{kind}.jsonl"
    if p.exists():
        stats(clean(p), f"pass{letter} {kind}")

print("\n published file mtimes (repo working tree, read-only):")
for p in sorted(Path("results/raw").glob("*_run*.jsonl")):
    pass
mt = []
for p in sorted(Path("results/raw").glob("*.jsonl")):
    mt.append((p.stat().st_mtime, p.name))
mt.sort()
for m, n in mt:
    if "run01" in n or "beelzebub" in n:
        print(f"  {datetime.fromtimestamp(m).isoformat(sep=' ')}  {n}")
print(" published beelzebub file mtimes:")
for rn in range(1, 6):
    p = Path(f"results/raw/beelzebub_run{rn:02d}.jsonl")
    print(f"  run{rn}: {datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=' ')}")
print(" earliest/latest across targets:",
      datetime.fromtimestamp(mt[0][0]).isoformat(sep=' '), "->",
      datetime.fromtimestamp(mt[-1][0]).isoformat(sep=' '))

print("\n== 4. CLOCK RESOLUTION ==")
for t in ("groundtruth_ssh", "cowrie", "llmhoneypot"):
    vals = []
    for rn in range(1, 21):
        vals += [r["latency_s"] for r in clean(R / "raw" / f"{t}_run{rn:02d}.jsonl")
                 if r.get("latency_s") is not None and not r.get("timed_out")]
    print(f"  {t}: distinct latency values={dict(Counter(vals).most_common(8))}")
for t in SSH:
    med = []
    for rn in range(1, 21):
        lat = [r["latency_s"] for r in clean(R / "raw" / f"{t}_run{rn:02d}.jsonl")
               if r.get("latency_s") is not None and not r.get("timed_out")]
        med.append(statistics.median(lat))
    print(f"  {t}: run medians distinct={sorted(set(med))}")

print("\n== 6. COST BY TARGET / RUN TYPE ==")
P_UNC, P_CACHED, P_COMP = 0.15 / 1e6, 0.03 / 1e6, 0.50 / 1e6
segs = []
cur = None
for r in plog:
    if r.get("event") == "slot_start":
        cur = {"m": r, "rows": []}
        segs.append(cur)
    elif cur is not None:
        cur["rows"].append(r)
per_t = defaultdict(lambda: [0, 0.0]); per_run = defaultdict(lambda: [0, 0.0])
tot = 0.0; n = 0
for s in segs:
    m = s["m"]
    c = 0.0
    for r in s["rows"]:
        p = int(r.get("prompt_tokens") or 0); cp = int(r.get("completion_tokens") or 0)
        det = (r.get("usage") or {}).get("prompt_tokens_details")
        cached = int(det["cached_tokens"]) if isinstance(det, dict) and det.get("cached_tokens") is not None else 0
        c += (p - cached) * P_UNC + cached * P_CACHED + cp * P_COMP
        n += 1
    per_t[m["target"]][0] += len(s["rows"]); per_t[m["target"]][1] += c
    per_run[m["run"]][0] += len(s["rows"]); per_run[m["run"]][1] += c
    tot += c
print(f"total=${tot:.4f} requests={n}")
for t, (k, c) in sorted(per_t.items()):
    print(f"  {t:16} calls={k:>5} cost=${c:.4f}")
med = statistics.median(c for _, c in per_run.values())
print(f"per-run median=${med:.4f}")
for rn in sorted(per_run):
    k, c = per_run[rn]
    tag = "TWO-MODE" if rn in (1, 2) else "prompt-only"
    flag = "  <-- >3x median" if c > 3 * med else ""
    print(f"  run{rn:02d} {tag:12} calls={k:>4} cost=${c:.4f}{flag}")
print("two-mode runs total=$%.4f  prompt-only total=$%.4f" % (
    sum(per_run[r][1] for r in (1, 2)), sum(per_run[r][1] for r in range(3, 21))))
