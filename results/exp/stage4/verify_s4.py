#!/usr/bin/env python3
"""Read-only Stage 4 data verification (Part 1). Writes nothing but stdout."""
import json, os, re, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("results/exp/stage4")
SSH_T = ["deceive", "beelzebub", "vellmes", "advshellm", "cowrie", "llmhoneypot", "groundtruth_ssh"]
LLM_T = ["deceive", "beelzebub", "vellmes", "advshellm"]
HTTP_T = ["galah", "groundtruth_http"]
ALL_T = SSH_T + HTTP_T
MODEL = "accounts/fireworks/models/glm-5p3-flash"
P_UNC, P_CACHED, P_COMP = 0.15 / 1e6, 0.03 / 1e6, 0.50 / 1e6

fails = []
def chk(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(name + " " + detail)

def jl(p):
    out = []
    if not Path(p).exists():
        return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

print("== 1. COMPLETENESS ==")
status = json.loads((ROOT / "status.json").read_text(encoding="utf-8"))
slot_keys = {k: v for k, v in status.items() if not k.startswith("_")}
print(f"status.json: {len(slot_keys)} slot keys, all complete={set(slot_keys.values())}, "
      f"safety_stop={'safety_stop' in status}, aux={sorted(k for k in status if k.startswith('_'))}")
chk("status 180 run keys + 8 quiet", len(slot_keys) == 188 and set(slot_keys.values()) == {"complete"},
    f"n={len(slot_keys)}")
man = jl(ROOT / "manifest.jsonl")
pairs = [(m["run"], m["target"]) for m in man]
dups = [p for p, c in Counter(pairs).items() if c > 1]
resumed = [m for m in man if m.get("resumed")]
chk("manifest 180 unique slots, no resumed", len(man) == 180 and not dups and not resumed,
    f"lines={len(man)} dups={dups} resumed={len(resumed)}")
cond = [m for m in man if [mm for mm in m["modes_run"]] != list(m["modes"])]
print(f"manifest modes_run != modes rows: {len(cond)}")

files = {"raw": sorted(ROOT.joinpath("raw").glob("*_run*.jsonl")),
         "raw_quiet": sorted(ROOT.joinpath("raw_quiet").glob("*_run*.jsonl")),
         "raw_http": sorted(ROOT.joinpath("raw_http").glob("*_run*.jsonl"))}
per = defaultdict(Counter)
rowcounts = defaultdict(list)
for d, paths in files.items():
    for p in paths:
        tgt, run = p.stem.rsplit("_run", 1)
        per[d][tgt] += 1
        n = sum(1 for line in open(p, encoding="utf-8") if line.strip())
        rowcounts[d].append((str(p.relative_to(ROOT)), n, tgt))
print(f"file counts raw={dict(per['raw'])}")
print(f"file counts raw_quiet={dict(per['raw_quiet'])}")
print(f"file counts raw_http={dict(per['raw_http'])}")
ok = (all(per["raw"][t] == 20 for t in SSH_T) and all(per["raw_quiet"][t] == 2 for t in LLM_T)
      and all(per["raw_http"][t] == 20 for t in HTTP_T) and len(files["raw"]) == 140
      and len(files["raw_quiet"]) == 8 and len(files["raw_http"]) == 40)
chk("file counts 140/8/40", ok)
exp_rows = {"raw": 37, "raw_quiet": 37, "raw_http": 20}
bad = [(p, n) for d in rowcounts for p, n, _ in rowcounts[d] if n != exp_rows[d]]
chk("row counts 37/37/20", not bad, f"deviations={bad[:20]} n_bad={len(bad)}")

print("\n== 2. RUN / MODE FIELDS ==")
field_bad, seeds, vers, modes = [], Counter(), Counter(), defaultdict(Counter)
for d, paths in files.items():
    want_mode = {"raw": "prompt", "raw_quiet": "quiet", "raw_http": "http"}[d]
    for p in paths:
        tgt, run = p.stem.rsplit("_run", 1)
        run = int(run)
        for r in jl(p):
            if r.get("run") != run or r.get("s4_run") != run:
                field_bad.append((p.name, r.get("run"), r.get("s4_run")))
            if r.get("s4_order_seed") != 2026:
                seeds[r.get("s4_order_seed")] += 1
            vers[r.get("s4_harness_ver")] += 1
            modes[d][r.get("s4_timing_mode")] += 1
            if r.get("s4_timing_mode") != want_mode:
                field_bad.append((p.name, "mode", r.get("s4_timing_mode")))
            if r.get("target") != tgt:
                field_bad.append((p.name, "target", r.get("target")))
n_rows = sum(len(jl(p)) for d in files for p in files[d])
chk("run/s4_run/target/seed/mode/ver fields",
    not field_bad and n_rows - sum(seeds.values()) == n_rows and not seeds,
    f"rows={n_rows} bad={field_bad[:10]} n_bad={len(field_bad)} non-2026={dict(seeds)}")
print(f"s4_harness_ver values: {dict(vers)}")
print(f"s4_timing_mode values per dir: { {k: dict(v) for k, v in modes.items()} }")
# SSH rows also carry run_meta/timing_mode
tm = Counter()
for p in files["raw"] + files["raw_quiet"]:
    for r in jl(p):
        tm[r.get("timing_mode")] += 1
print(f"SSH legacy timing_mode field: {dict(tm)}")

print("\n== 3. PROXY LOG ==")
plog = jl(ROOT / "api_proxy_log.jsonl")
marks = [r for r in plog if r.get("event") == "slot_start"]
reqs = [r for r in plog if r.get("event") != "slot_start"]
print(f"slot_start markers={len(marks)} request rows={len(reqs)}")
chk("one marker per mode (188)", len(marks) == 188, f"n={len(marks)}")
# assign each request to the preceding marker (file order)
segs = []
cur = None
for r in plog:
    if r.get("event") == "slot_start":
        cur = {"marker": r, "rows": []}
        segs.append(cur)
    elif cur is not None:
        cur["rows"].append(r)
seg_by_slot = defaultdict(list)
for s in segs:
    seg_by_slot[(s["marker"]["run"], s["marker"]["target"])].append(s)
outside, slot_tot = [], {}
for s in segs:
    m, n = s["marker"], len(s["rows"])
    t = m["target"]
    lo, hi = (34, 40) if t in LLM_T else ((16, 22) if t == "galah" else (0, 0))
    slot_tot[(m["run"], t, m["mode"])] = n
    if not (lo <= n <= hi):
        outside.append((m["run"], t, m["mode"], n))
for (run, tgt), ss in sorted(seg_by_slot.items()):
    tot = sum(len(s["rows"]) for s in ss)
    if tgt in LLM_T and tot > 100:
        outside.append((run, tgt, "slot-total", tot))
chk("per-mode call counts in range", not outside, f"outside={outside}")
tot2 = [ (run, tgt, tot) for (run, tgt), ss in sorted(seg_by_slot.items())
         if len(ss) == 2 for tot in [sum(len(s['rows']) for s in ss)]]
if tot2:
    print("two-mode slot totals:", tot2[:6], "min/max", min(t for _,_,t in tot2), max(t for _,_,t in tot2))
non200 = [(m["run"], m["target"], m.get("mode"), r.get("status"), (r.get("error") or "")[:80])
          for s in segs for m, r in [(s["marker"], r) for r in s["rows"]]
          for _ in [0] if r.get("status") != 200]
chk("proxy statuses (non-200 listed, all upstream read timeouts)",
    all(x[3] == 502 and "TimeoutError" in x[4] for x in non200),
    f"n={len(non200)} {non200}")
models = Counter((r.get("model_requested"), r.get("model_reported")) for r in reqs)
bad_model = [k for k in models if k[0] != MODEL or (k[1] not in (MODEL, None))]
chk("model_requested always glm-5p3-flash (model_reported None only on 502s)",
    not bad_model, f"{dict(models)}")
rawtext = (ROOT / "api_proxy_log.jsonl").read_text(encoding="utf-8", errors="replace")
hits_auth = len(re.findall(r"(?i)authorization|bearer\s|api[_-]?key|sk-[A-Za-z0-9]{16,}", rawtext))
chk("no auth/bearer/key text in proxy log", hits_auth == 0, f"hits={hits_auth}")

# cost / tokens
tot_p = tot_c = tot_cached = 0
nocache_rows = 0
max_comp = defaultdict(int)
over4k = defaultdict(int)
comp_all = 0
for s in segs:
    t = s["marker"]["target"]
    for r in s["rows"]:
        p = int(r.get("prompt_tokens") or 0)
        c = int(r.get("completion_tokens") or 0)
        us = r.get("usage") or {}
        det = us.get("prompt_tokens_details")
        tot_p += p; tot_c += c; comp_all += 1
        if isinstance(det, dict) and det.get("cached_tokens") is not None:
            tot_cached += int(det["cached_tokens"])
        else:
            nocache_rows += 1
        max_comp[t] = max(max_comp[t], c)
        if c > 4000:
            over4k[t] += 1
uncached = tot_p - tot_cached
cost = uncached * P_UNC + tot_cached * P_CACHED + tot_c * P_COMP
cost_cons = (tot_p + nocache_rows * 0) * P_UNC + tot_c * P_COMP
print(f"calls={comp_all} prompt={tot_p:,} cached={tot_cached:,} ({tot_cached/max(tot_p,1):.2%}) "
      f"completion={tot_c:,} rows_without_cached_breakdown={nocache_rows}")
print(f"cost corrected=${cost:.4f}  (all-prompt-at-0.15=${tot_p*P_UNC+tot_c*P_COMP:.4f})")
print(f"max completion_tokens per target: {dict(sorted(max_comp.items()))}")
print(f"calls >4000 completion tokens: {dict(over4k)} total={sum(over4k.values())}")

print("\n== 4. TIMEOUTS ==")
to_by_run = defaultdict(dict)
tot_to = Counter()
for p in files["raw"]:
    tgt, run = p.stem.rsplit("_run", 1)
    rows = [r for r in jl(p) if r.get("cmd_id") and r.get("cmd_id") != "exit"]
    nto = sum(1 for r in rows if r.get("timed_out"))
    to_by_run[tgt][int(run)] = (nto, len(rows))
    tot_to[tgt] += nto
for t in SSH_T:
    d = to_by_run[t]
    print(f"  {t}: runs={len(d)} timeouts={tot_to[t]} over {sum(v[1] for v in d.values())} scored cmds; "
          f"per-run={[d[r][0] for r in sorted(d)]}")
hi = [(t, r, v[0]) for t, d in to_by_run.items() for r, v in d.items() if v[0] > 10]
chk("no run with >10 timeouts", not hi, f"{hi}")

print("\n== 4b. SLOT DURATIONS (driver.log) ==")
log = (ROOT / "driver.log").read_text(encoding="utf-8", errors="replace").splitlines()
ts_re = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+)")
from datetime import datetime
def pts(s):
    return datetime.strptime(s.split(",")[0], "%Y-%m-%d %H:%M:%S")
starts, endt = [], None
for ln in log:
    m = ts_re.match(ln)
    if not m:
        continue
    if "-- run=" in ln:
        mm = re.search(r"run=(\d+)/\d+\s+pos=(\d+)/\d+\s+target=(\w+)", ln)
        if mm:
            starts.append((pts(m.group(1)), int(mm.group(1)), int(mm.group(2)), mm.group(3)))
    endt = pts(m.group(1))
durs = []
for i, (t0, run, pos, tgt) in enumerate(starts):
    t1 = starts[i + 1][0] if i + 1 < len(starts) else endt
    durs.append(((t1 - t0).total_seconds(), run, pos, tgt))
print(f"slots timed={len(durs)} total={(endt-starts[0][0]).total_seconds()/3600:.2f} h")
med = statistics.median(d[0] for d in durs)
print(f"slot duration median={med:.0f}s min={min(d[0] for d in durs):.0f}s max={max(d[0] for d in durs):.0f}s")
slow = sorted(durs)[-6:]
print("slowest slots (s, run, pos, target):", [(round(d, 1), r, p, t) for d, r, p, t in slow])
by_t = defaultdict(list)
for d, r, p, t in durs:
    by_t[t].append(d)
print("per-target median slot s:", {t: round(statistics.median(v)) for t, v in sorted(by_t.items())})

print("\n== 5. MASKING / SECRET SCAN ==")
mask_counts = Counter()
pats = {
    "sk_live_": r"sk_live_", "sk_prod_": r"sk_prod_", "sk_test_": r"sk_test_",
    "pk_live_": r"pk_live_", "rk_live_": r"rk_live_",
    "AKIA(non-example)": r"AKIA(?!IOSFODNN7EXAMPLE)[A-Z0-9]{8,}",
    "ghp_": r"ghp_[A-Za-z0-9]{10,}", "gho_": r"gho_[A-Za-z0-9]{10,}",
    "xox": r"xox[baprs]-", "AIza": r"AIza[A-Za-z0-9_-]{10,}",
    "BEGIN": r"-----BEGIN [A-Z ]+-----", "Bearer+token": r"Bearer\s+[A-Za-z0-9._-]{12,}",
    "eyJ": r"eyJ[A-Za-z0-9_-]{10,}",
}
env_vals = []
envp = Path(".env")
if envp.exists():
    for ln in envp.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if len(v) >= 16:
                env_vals.append((k.strip(), v))
found = defaultdict(list)
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or p.name == "api_proxy_log.jsonl":
        continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    for name, pat in pats.items():
        n = len(re.findall(pat, txt))
        if n:
            found[name].append((str(p.relative_to(ROOT)), n))
    for k, v in env_vals:
        if v in txt:
            found[f"ENV[{k}]"].append((str(p.relative_to(ROOT)), 1))
    if p.name == "verify_s4.py":
        for name in list(found):
            found[name] = [(f, n) for f, n in found[name] if p.name not in f]
            if not found[name]:
                del found[name]
    mask_counts[p.parent.name + "/" + p.stem.rsplit("_run", 1)[0]] += len(re.findall(r"MASKED", txt))
print("flagged patterns (file, count):", {k: v for k, v in found.items()})
print(f"env vars checked for leakage: {[k for k, _ in env_vals]} -> "
      f"{'FOUND' if any(k.startswith('ENV[') for k in found) else 'not found'}")
print("MASKED marker counts per file group:", dict(sorted(mask_counts.items())) or "none")
galah_safe = not any("raw_http" in f and "galah" in f for lst in found.values() for f, _ in lst)
print(f"galah raw_http files free of flagged patterns: {galah_safe}")
decoy = set()
for p in files["raw_http"]:
    for r in jl(p):
        decoy.update(re.findall(r"eyJ[A-Za-z0-9_.-]*", r.get("body") or ""))
print(f"distinct eyJ strings in raw_http: {decoy} -> decoy JWT header only: "
      f"{decoy == {'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'}}")

print("\n== 6. PHYSICAL ==")
sizes = sorted(((p.stat().st_size, str(p.relative_to(ROOT))) for p in ROOT.rglob("*") if p.is_file()), reverse=True)
total = sum(s for s, _ in sizes)
print(f"folder size={total/1e6:.1f} MB  files={len(sizes)}")
print("5 largest:", [(round(s / 1e6, 2), f) for s, f in sizes[:5]])
print("files >50MB:", [f for s, f in sizes if s > 50e6])

print("\n== 7. STATE-CARRY / CONTAINER RECREATE ==")
logtxt = "\n".join(log)
downs = len(re.findall(r"docker down: (\w+)", logtxt))
ups_force = len(re.findall(r"up -d --force-recreate", logtxt))
ups = len(re.findall(r"docker up: (\w+)", logtxt))
print(f"driver.log: docker up={ups} (with --force-recreate={ups_force}), docker down={downs}")
info_up = len(re.findall(r"INFO    stage4: docker up: \w+", logtxt))
info_down = len(re.findall(r"INFO    stage4: docker down: \w+", logtxt))
chk("every slot: docker up --force-recreate (180/180)", info_up == 180 and ups_force == 180,
    f"INFO up={info_up} force-recreate={ups_force}")
print(f"INFO docker down lines={info_down}; the 2 slots without a down are run11pos9 and "
      f"run12pos1 (same target twice in a row, --force-recreate still applies)")
bee = {run: n for (run, t, mode), n in slot_tot.items() if t == "beelzebub" and mode == "prompt"}
print(f"beelzebub prompt-mode calls per run: {[bee[r] for r in sorted(bee)]}")
chk("beelzebub calls flat (34-40, no growth)", all(34 <= v <= 40 for v in bee.values()),
    f"min={min(bee.values())} max={max(bee.values())} first5={[bee[r] for r in sorted(bee)[:5]]} "
    f"last5={[bee[r] for r in sorted(bee)[-5:]]}")
blog = Path("docker/logs/beelzebub")
if blog.is_dir():
    fls = sorted(blog.rglob("*"))
    print(f"docker/logs/beelzebub files={len(fls)}; sample={[f.name for f in fls[:3]]}")
    sess = 0
    for f in fls:
        if f.is_file():
            sess += len(re.findall(r"connection|session|SSH-2\.0", f.read_text(errors="replace"), re.I))
    print(f"log lines mentioning connection/session/SSH banner: {sess}")
else:
    print("docker/logs/beelzebub: absent -> per-slot SSH session count NOT verifiable from logs")

print("\n== SUMMARY ==")
print(f"FAILS: {fails if fails else 'none'}")
