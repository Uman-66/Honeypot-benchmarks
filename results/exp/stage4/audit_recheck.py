"""Re-check the numbers the final audit could not verify (read-only).

Covers:
  (a) VelLMes ls_etc run 2: prompt row, quiet row and the matching proxy entry.
  (b) groundtruth_ssh prompt-mode latency quantisation and the 20 run medians.
  (c) empty / oversized / interior-prompt-leakage counts per Stage 4 target.
  (e) lifetime-control Spearman values (20,000 permutations, seed 20261122)
      and the Stage 4 Beelzebub fresh-container series.

Run:  .venv-hb\\Scripts\\python.exe results/exp/stage4/audit_recheck.py
"""
from __future__ import annotations

import json
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

STAGE4 = Path(__file__).resolve().parent
ROOT = STAGE4.parents[2]
LIFETIME = ROOT / "results" / "exp" / "lifetime_control" / "beelzebub_persistent"
PROMPT_RE = re.compile(r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s")
SSH = ["advshellm", "beelzebub", "cowrie", "deceive", "groundtruth_ssh", "llmhoneypot", "vellmes"]


def jl(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def scored(path: Path) -> list[dict]:
    return [r for r in jl(path) if r.get("cmd_id") and r.get("cmd_id") != "exit"]


def ends_with_prompt(out: str) -> bool:
    s = (out or "").rstrip()
    if not s:
        return False
    last = s.splitlines()[-1].rstrip()
    return last.endswith("$") or last.endswith("#")


def rank(v: list[float]) -> list[float]:
    """Average ranks for ties (the usual Spearman convention)."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(a: list[float], b: list[float]) -> float:
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else float("nan")


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(rank(xs), rank(ys))


def perm_p(xs: list[float], ys: list[float], draws: int = 20000, seed: int = 20261122) -> tuple[float, float]:
    rho = spearman(xs, ys)
    rng = random.Random(seed)
    rx = rank(xs)
    ry = rank(ys)
    hits = 0
    for _ in range(draws):
        shuffled = ry[:]
        rng.shuffle(shuffled)
        if abs(pearson(rx, shuffled)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, hits / draws


print("== (a) vellmes ls_etc run 2 ==")
vp = [r for r in scored(STAGE4 / "raw/vellmes_run02.jsonl") if r["cmd_id"] == "ls_etc"][0]
vq = [r for r in scored(STAGE4 / "raw_quiet/vellmes_run02.jsonl") if r["cmd_id"] == "ls_etc"][0]
print(f" prompt: timed_out={vp['timed_out']} latency={vp['latency_s']} bytes={vp['bytes']} "
      f"cleaned_len={len(vp.get('cleaned_output') or '')}")
print(f" quiet : timed_out={vq['timed_out']} latency={vq['latency_s']} bytes={vq['bytes']} "
      f"cleaned_len={len(vq.get('cleaned_output') or '')} chars")
reqs = [e for e in jl(STAGE4 / "api_proxy_log.jsonl") if e.get("event") != "slot_start"]
near = [e for e in reqs if 7150 <= float(e.get("duration_ms", 0)) <= 7300 and e.get("status") == 200]
print(f" proxy rows with 7.15-7.30 s and status 200: {len(near)}")
for e in near[:4]:
    u = e.get("usage") or {}
    print(f"   status={e.get('status')} duration_ms={e.get('duration_ms')} "
          f"completion_tokens={u.get('completion_tokens')} prompt_tokens={u.get('prompt_tokens')}")

print("\n== (b) groundtruth_ssh prompt latency quantisation ==")
gt = []
for p in sorted((STAGE4 / "raw").glob("groundtruth_ssh_run*.jsonl")):
    gt += scored(p)
done = [r for r in gt if not r.get("timed_out")]
ms = Counter(round(r["latency_s"] * 1000) for r in done)
print(" ms histogram (top):", ms.most_common(8))
print(" counts 13/14/15/16/30/31/32 ms:", {k: ms.get(k, 0) for k in (13, 14, 15, 16, 30, 31, 32)})
per_run = defaultdict(list)
for r in done:
    per_run[r["run"]].append(r["latency_s"])
meds = [round(statistics.median(v) * 1000) for k, v in sorted(per_run.items())]
print(" per-run medians (ms):", meds)
print(" median-of-medians s:", round(statistics.median([statistics.median(v) for v in per_run.values()]), 4))

print("\n== (c) empty / oversized / interior leakage ==")
for t in SSH:
    rows = []
    for p in sorted((STAGE4 / "raw").glob(f"{t}_run*.jsonl")):
        rows += scored(p)
    empty = sum(1 for r in rows if not (r.get("cleaned_output") or ""))
    over = sum(1 for r in rows if len(r.get("cleaned_output") or "") > 20000)
    interior_clean = sum(1 for r in rows if PROMPT_RE.search(r.get("cleaned_output") or "")
                         and not ends_with_prompt(r.get("cleaned_output")))
    interior_raw = sum(1 for r in rows if PROMPT_RE.search(r.get("raw_output") or "")
                       and not ends_with_prompt(r.get("raw_output")))
    longest = max((len(r.get("cleaned_output") or "") for r in rows), default=0)
    print(f" {t:<16} rows={len(rows)} empty={empty} oversized>20k={over} max_len={longest} "
          f"interior_cleaned={interior_clean} interior_raw={interior_raw}")

print("\n== (e) lifetime control Spearman ==")
data = json.loads((LIFETIME / "lifetime.json").read_text(encoding="utf-8"))
med = [r["median_latency_s"] for r in data["runs_data"]]
tos = [r["timeouts"] for r in data["runs_data"]]
idx = list(range(1, len(med) + 1))
for label, ys in (("median vs run", med), ("timeouts vs run", tos)):
    rho, p = perm_p(idx, ys)
    print(f" {label}: rho={rho:.3f} p={p:.4f} (20,000 permutations, seed 20261122)")

print("\n== (e) Stage 4 Beelzebub fresh series ==")
pr = defaultdict(list)
for p in sorted((STAGE4 / "raw").glob("beelzebub_run*.jsonl")):
    for r in scored(p):
        if not r.get("timed_out"):
            pr[r["run"]].append(r["latency_s"])
fmed = [statistics.median(v) for k, v in sorted(pr.items())]
print(" run medians:", [round(x, 3) for x in fmed])
print(" median-of-medians:", round(statistics.median(fmed), 4))
rho, p = perm_p(list(range(1, len(fmed) + 1)), fmed)
print(f" rho={rho:.3f} p={p:.4f}")
