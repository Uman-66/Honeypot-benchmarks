"""Recompute the prompt-versus-quiet comparison over all 288 pairs (runs 1-2).

The analyzer (harness/analyze_stage4.py, _quiet_check) only writes the pairs it
flags, so quiet_check.csv holds a subset, not the full design. This script walks
every (target, run, command) pair for runs 1-2 and writes the complete table.

Similarity uses the analyzer's own helper (harness/analyze.py: ANSI stripped,
prefix capped at 4,000 characters) after the analyzer's masker (mask_text) is
applied, and the Stage 2 quiet-vs-quiet floor is the masked A-vs-C similarity
from results/exp/validation/{target}_comparison.csv.

Report rule (Section 5.6 of the report): a pair is flagged when the prompt-mode
output is shorter than the quiet-mode output AND its similarity is below the
quiet-vs-quiet floor for that command.

Run:  .venv-hb\\Scripts\\python.exe results/exp/stage4/quiet_check_full.py
Out:  results/exp/stage4/quiet_check_full.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

STAGE4 = Path(__file__).resolve().parent
ROOT = STAGE4.parents[2]
sys.path.insert(0, str(ROOT / "harness"))

import analyze  # noqa: E402  (analyzer helpers: mask_text, _similarity)

TARGETS = ("advshellm", "beelzebub", "deceive", "vellmes")
RUNS = (1, 2)


def load(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cid = rec.get("cmd_id")
            if cid and cid != "exit":
                out[cid] = rec
    return out


def floors(target: str) -> dict[str, float]:
    path = ROOT / "results" / "exp" / "validation" / f"{target}_comparison.csv"
    out: dict[str, float] = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out[row["cmd_id"]] = float(row["masked_sim_ac"])
            except (KeyError, ValueError):
                continue
    return out


def main() -> None:
    rows: list[dict] = []
    for target in TARGETS:
        floor = floors(target)
        for run in RUNS:
            p_map = load(STAGE4 / "raw" / f"{target}_run{run:02d}.jsonl")
            q_map = load(STAGE4 / "raw_quiet" / f"{target}_run{run:02d}.jsonl")
            for cid in sorted(set(p_map) & set(q_map)):
                p_out = p_map[cid].get("cleaned_output") or ""
                q_out = q_map[cid].get("cleaned_output") or ""
                p_masked = analyze.mask_text(p_out)
                q_masked = analyze.mask_text(q_out)
                sim_masked = analyze._similarity(p_masked, q_masked)
                sim_raw = analyze._similarity(p_out, q_out)
                fl = floor.get(cid, float("nan"))
                drop = (1.0 - sim_masked) - (1.0 - fl) if fl == fl else float("nan")
                is_shorter = (len(p_out) < len(q_out)) and len(q_out) > 0
                below = (sim_masked < fl) if fl == fl else False
                rows.append({
                    "target": target,
                    "run": run,
                    "cmd_id": cid,
                    "prompt_len": len(p_out),
                    "quiet_len": len(q_out),
                    "sim_masked": round(sim_masked, 4),
                    "noise_floor_ac": round(fl, 4) if fl == fl else None,
                    "drop_vs_floor": round(drop, 4) if drop == drop else None,
                    "is_shorter": is_shorter,
                    "below_floor": below,
                    "flagged_report_rule": bool(is_shorter and below),
                    "sim_unmasked": round(sim_raw, 4),
                    "exceeds_floor_0.05_unmasked": bool(
                        drop == drop and ((1.0 - sim_raw) - (1.0 - fl)) > 0.05
                    ),
                })

    out_path = STAGE4 / "quiet_check_full.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out_path} ({len(rows)} rows)")
    print(f"{'target':<14}{'pairs':>6}{'shorter':>9}{'below':>7}{'flagged':>9}{'an05':>6}")
    for target in TARGETS:
        sub = [r for r in rows if r["target"] == target]
        print(f"{target:<14}{len(sub):>6}"
              f"{sum(r['is_shorter'] for r in sub):>9}"
              f"{sum(r['below_floor'] for r in sub):>7}"
              f"{sum(r['flagged_report_rule'] for r in sub):>9}"
              f"{sum(r['exceeds_floor_0.05_unmasked'] for r in sub):>6}")
    print(f"{'TOTAL':<14}{len(rows):>6}"
          f"{sum(r['is_shorter'] for r in rows):>9}"
          f"{sum(r['below_floor'] for r in rows):>7}"
          f"{sum(r['flagged_report_rule'] for r in rows):>9}"
          f"{sum(r['exceeds_floor_0.05_unmasked'] for r in rows):>6}")


if __name__ == "__main__":
    main()
