#!/usr/bin/env python3
"""
harness/recheck_v21b_other.py

Audit of Issues 2, 3 and 4.  Re-uses the v2.1 detectors so the comparison is
like-for-like, but dumps the evidence needed to check every hit by eye and
computes alternative scoring rules.  Writes only *_v21b files.

    python harness/recheck_v21b_other.py
"""

from __future__ import annotations

import csv
import itertools
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_stage4_v21 as v21  # noqa: E402

ENCODING = "utf-8"
STAGE4 = Path("results/exp/stage4")
RAW = STAGE4 / "raw"

NARR_TARGETS = ["advshellm", "beelzebub", "cowrie", "deceive",
                "groundtruth_ssh", "vellmes", "llmhoneypot"]

# A deliberately loose narration probe, used only to look for *misses* in the
# main detector and to read near-misses on the control targets.
LOOSE = re.compile(
    r"\b(?:I|we)\s+(?:am|will|can|need|should|have|see|think|notice|apologize|apologise)\b"
    r"|\bthe user\b|\blet me\b|\blet's\b|\bas an AI\b",
    re.IGNORECASE,
)


def prose_flag(text: str, gt_median_len: float) -> bool:
    """The v2.1 prose rule, reproduced here so this audit does not depend on
    the other script's internal structure."""
    if any(p.search(text) for p in v21.PROSE_BOILERPLATE):
        return False
    if gt_median_len >= v21.PROSE_SHORT_GT_CHARS:
        return False
    if not v21.PROSE_PRONOUN_RE.search(text):
        return False
    sentences = 0
    for sentence in v21.PROSE_SENTENCE_SPLIT_RE.split(text):
        words = sentence.lower().split()
        if len(words) < v21.PROSE_MIN_WORDS:
            continue
        alpha = sum(c.isalpha() or c.isspace() for c in sentence)
        if alpha / max(1, len(sentence)) < v21.PROSE_MIN_ALPHA_RATIO:
            continue
        stops = sum(1 for w in words
                    if w.strip(".,;:!?()\"'") in v21.PROSE_STOPWORDS)
        if stops >= v21.PROSE_MIN_STOPWORDS:
            sentences += 1
    return sentences >= v21.PROSE_MIN_SENTENCES


def rows_by_run(target: str) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for r in v21.load_target(RAW, target):
        out.setdefault(int(r.get("run") or 0), []).append(r)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Issue 2 — narration
# ─────────────────────────────────────────────────────────────────────────────

def issue2() -> dict[str, Any]:
    print("[I2] narration review", flush=True)
    hits: list[dict[str, Any]] = []
    per_target: list[dict[str, Any]] = []
    sample: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    gt_short = v21.ground_truth_short_commands(RAW)

    for target in NARR_TARGETS:
        runs = rows_by_run(target)
        n_out = 0
        flagged_outputs = 0
        flagged_sessions: set[int] = set()
        phrase_outputs = 0
        prose_outputs = 0
        for run, recs in sorted(runs.items()):
            for r in recs:
                if (r.get("cmd_id") or "") in ("", "exit") or r.get("timed_out"):
                    continue
                text = r.get("cleaned_output") or ""
                if not text.strip():
                    continue
                n_out += 1
                phrase = v21.narration_hits(text)
                prose = prose_flag(text, gt_short.get(r.get("cmd_id") or "", 10**9))
                if phrase or prose:
                    flagged_outputs += 1
                    flagged_sessions.add(run)
                    if phrase:
                        phrase_outputs += 1
                    if prose:
                        prose_outputs += 1
                    hits.append({
                        "target": target,
                        "run": run,
                        "cmd_id": r.get("cmd_id"),
                        "patterns": ",".join(n for n, _ in phrase) or "prose_rule",
                        "prose_rule": bool(prose),
                        "chars": len(text),
                        "first_300": text[:300].replace("\n", " | "),
                    })
        per_target.append({
            "target": target,
            "outputs_scanned": n_out,
            "outputs_flagged": flagged_outputs,
            "sessions_flagged": len(flagged_sessions),
            "sessions": len(runs),
            "phrase_outputs": phrase_outputs,
            "prose_only_outputs": max(0, flagged_outputs - phrase_outputs),
        })

        # 30 unflagged outputs, longest first, for a false-negative check.
        if target == "beelzebub":
            unflagged = []
            for run, recs in sorted(runs.items()):
                for r in recs:
                    if (r.get("cmd_id") or "") in ("", "exit") or r.get("timed_out"):
                        continue
                    text = r.get("cleaned_output") or ""
                    if not text.strip():
                        continue
                    if v21.narration_hits(text):
                        continue
                    if prose_flag(text, gt_short.get(r.get("cmd_id") or "", 10**9)):
                        continue
                    unflagged.append({
                        "target": target, "run": run, "cmd_id": r.get("cmd_id"),
                        "chars": len(text),
                        "loose_match": bool(LOOSE.search(text)),
                        "first_300": text[:300].replace("\n", " | "),
                    })
            unflagged.sort(key=lambda x: -x["chars"])
            sample = unflagged[:30]

        # Controls: outputs that a loose probe would look at.
        if target != "beelzebub":
            for run, recs in sorted(runs.items()):
                for r in recs:
                    text = r.get("cleaned_output") or ""
                    if LOOSE.search(text) and len(text) < 2000:
                        near_misses.append({
                            "target": target, "run": run, "cmd_id": r.get("cmd_id"),
                            "chars": len(text),
                            "first_200": text[:200].replace("\n", " | "),
                        })

    # Which sessions contain "The user typed"-style narration (the reviewer's
    # most likely 5)?
    style = []
    for target in ("beelzebub",):
        for run, recs in sorted(rows_by_run(target).items()):
            for r in recs:
                text = (r.get("cleaned_output") or "")
                if re.search(r"(?i)^\W*the user\b|\bthe user (?:typed|asked|wants|said|ran|has been|is)\b", text):
                    style.append({"run": run, "cmd_id": r.get("cmd_id"),
                                  "first_200": text[:200].replace("\n", " | ")})

    def dump(name: str, data: list[dict[str, Any]], fallback: list[str]) -> Path:
        p = STAGE4 / name
        with open(p, "w", newline="", encoding=ENCODING) as fh:
            if data:
                w = csv.DictWriter(fh, fieldnames=list(data[0]))
                w.writeheader()
                w.writerows(data)
            else:
                fh.write(",".join(fallback) + "\n")
        print(f"Written: {p}")
        return p

    dump("narration_hits_v21b.csv", hits, ["no_hits"])
    dump("narration_by_target_v21b.csv", per_target, ["no_rows"])
    dump("narration_unflagged_sample_v21b.csv", sample, ["no_rows"])
    dump("narration_controls_loose_v21b.csv", near_misses[:200], ["no_rows"])
    dump("narration_user_style_v21b.csv", style, ["no_rows"])
    return {"hits": hits, "per_target": per_target, "style": style,
            "sample": sample, "near_misses": near_misses}


# ─────────────────────────────────────────────────────────────────────────────
# Issue 3 — state checks
# ─────────────────────────────────────────────────────────────────────────────

SHIFT_MARKERS = ("Permission denied", "cannot access", "No such file")


def desync_evidence(f: dict[str, Any]) -> str:
    """Evidence that a state command received another command's output.

    DECEIVE's shell sometimes lags one command behind, so the text that arrives
    for `pwd` is the `cat /etc/shadow` error, the text for `ls /tmp` is the
    marker read back by `cat`, and so on.  This is a transport/ordering failure,
    not a state error, so it is labelled separately from `direct`.
    """
    outs = f["outputs"]
    pwd = (outs.get("state_pwd_after_cd") or "").strip()
    cat = (outs.get("state_cat_marker") or "").strip()
    ls1 = (outs.get("state_ls_tmp_1") or "").strip()
    ls2 = (outs.get("state_ls_tmp_2") or "").strip()
    if any(m in pwd for m in SHIFT_MARKERS):
        return "pwd received an error from another command"
    if pwd == v21.MARKER:
        return "pwd received the marker text"
    if ls1 == v21.MARKER:
        return "ls_tmp_1 received the marker text"
    if ls1 == "/tmp":
        return "ls_tmp_1 received the pwd output"
    if ls2 == v21.MARKER:
        return "ls_tmp_2 received the marker text"
    if cat and ("bm.txt" in cat or "bm_dir" in cat):
        return "cat_marker received a directory listing"
    return ""


def session_facts(recs: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {r.get("cmd_id"): r for r in recs}

    def out(cid: str) -> str:
        return (by_id.get(cid, {}).get("cleaned_output") or "")

    def timed(cid: str) -> bool:
        return bool(by_id.get(cid, {}).get("timed_out", True))

    res = v21.score_session(recs)
    checks = {k: v["pass"] for k, v in res["checks"].items()}
    # alternative listing rule: the three listings must be byte-identical
    listings = [out(v21.STATE_CHECK_IDS[k]).strip()
                for k in ("ls_tmp_1", "ls_tmp_2", "ls_tmp_3")]
    identical = len(set(listings)) == 1 and all(listings)
    # stricter pwd: exactly /tmp on the last non-empty line AND no sudo prompt
    pwd_raw = out(v21.STATE_CHECK_IDS["pwd_after_cd"])
    strict_pwd = (v21._last_nonempty_line(pwd_raw) == "/tmp"
                  and not v21.PASSWORD_ARTIFACT_RE.search(pwd_raw))
    return {
        "checks": checks,
        "cascade": bool(res["cascade_evidence"]),
        "desync_evidence": desync_evidence({"outputs": {cid: out(cid) for cid in set(v21.STATE_CHECK_IDS.values()) | {"whoami", "state_echo_marker"}}}),
        "timeout_ids": [k for k, cid in v21.STATE_CHECK_IDS.items() if timed(cid)],
        "identical_listings": identical,
        "strict_pwd": strict_pwd,
        "sudo_text": res["sudo_text"],
        "outputs": {cid: out(cid) for cid in set(v21.STATE_CHECK_IDS.values()) | {"whoami", "state_echo_marker"}},
    }


def issue3() -> dict[str, Any]:
    print("[I3] state-check audit", flush=True)
    targets = ["advshellm", "beelzebub", "cowrie", "deceive", "groundtruth_ssh", "vellmes"]
    per_session: dict[str, dict[int, dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    cascade_evidence: list[dict[str, Any]] = []

    for target in targets:
        runs = rows_by_run(target)
        per_session[target] = {}
        for run, recs in sorted(runs.items()):
            f = session_facts(recs)
            per_session[target][run] = f
            for name, passed in f["checks"].items():
                if passed:
                    continue
                cid = v21.STATE_CHECK_IDS[name]
                own = f["outputs"].get(cid) or ""
                if name in f["timeout_ids"]:
                    cause = "timeout"
                elif v21.PASSWORD_ARTIFACT_RE.search(own):
                    cause = "cascade_prompt"
                elif f["desync_evidence"]:
                    cause = "desync"
                elif f["cascade"]:
                    cause = "cascade_session"
                else:
                    cause = "direct"
                failures.append({
                    "target": target, "run": run, "check": name, "command_id": cid,
                    "timeout": name in f["timeout_ids"],
                    "cascade_session": f["cascade"],
                    "desync": bool(f["desync_evidence"]),
                    "cause": cause,
                    "desync_evidence": f["desync_evidence"],
                    "output_first_200": own.replace("\n", " | ")[:200],
                })
            if f["cascade"]:
                carriers = [cid for cid, txt in f["outputs"].items()
                            if v21.PASSWORD_ARTIFACT_RE.search(txt)]
                cascade_evidence.append({
                    "target": target, "run": run,
                    "sudo_l_first_200": (f["sudo_text"] or "").replace("\n", " | ")[:200],
                    "commands_carrying_prompt": ",".join(sorted(carriers)),
                    "pwd_output": (f["outputs"].get("state_pwd_after_cd") or "").replace("\n", " | ")[:120],
                    "echo_output": (f["outputs"].get("state_echo_marker") or "").replace("\n", " | ")[:120],
                })

    # ── alternative rules ───────────────────────────────────────────────────
    rule_rows: list[dict[str, Any]] = []
    for cascade_policy, tmo_policy, listing_policy, pwd_policy in itertools.product(
            ("observed", "cascade_all6", "cascade_after_sudo",
             "desync_all6", "desync_or_cascade_all6"),
            ("fail", "pass"),
            ("marker", "identical"),
            ("lenient", "strict")):
        row = {"cascade_policy": cascade_policy, "timeout_policy": tmo_policy,
               "listing_policy": listing_policy, "pwd_policy": pwd_policy}
        for target in targets:
            passed = 0
            total = 0
            for run, f in per_session[target].items():
                for name, ok in f["checks"].items():
                    total += 1
                    if name in f["timeout_ids"]:
                        ok = (tmo_policy == "pass")
                    elif listing_policy == "identical" and name.startswith("ls_tmp"):
                        ok = f["identical_listings"]
                    elif pwd_policy == "strict" and name == "pwd_after_cd":
                        ok = f["strict_pwd"]
                    hit = (
                        (cascade_policy in ("cascade_all6", "cascade_after_sudo",
                                            "desync_or_cascade_all6") and f["cascade"])
                        or (cascade_policy in ("desync_all6", "desync_or_cascade_all6")
                            and f["desync_evidence"])
                    )
                    if hit:
                        if cascade_policy == "cascade_after_sudo" and name == "whoami_vs_id":
                            pass
                        else:
                            ok = False
                    passed += 1 if ok else 0
            row[target] = passed
            row[f"{target}_total"] = total
        rule_rows.append(row)

    for name, data in (("state_failures_v21b.csv", failures),
                       ("state_cascade_evidence_v21b.csv", cascade_evidence),
                       ("state_rules_v21b.csv", rule_rows)):
        p = STAGE4 / name
        with open(p, "w", newline="", encoding=ENCODING) as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        print(f"Written: {p}")

    # which rules reproduce each reviewer number
    want = {"deceive": 72, "vellmes": 117, "beelzebub": 107}
    matches = []
    for row in rule_rows:
        if all(row[t] == want[t] for t in want):
            matches.append(row)
    print(f"[I3] rules matching all three reviewer numbers: {len(matches)}")
    for t in want:
        exact = [r for r in rule_rows if r[t] == want[t]]
        print(f"[I3]   {t}: {len(exact)} rule(s) give {want[t]}")
    return {"sessions": per_session, "failures": failures, "rules": rule_rows,
            "cascade_evidence": cascade_evidence}


# ─────────────────────────────────────────────────────────────────────────────
# Issue 4 — visible colour codes, counted as outputs and as sessions
# ─────────────────────────────────────────────────────────────────────────────

def issue4() -> dict[str, Any]:
    print("[I4] literal ANSI, outputs vs sessions", flush=True)
    encodings = ["esc_byte", "ESC_bracket", "backslash_e", "backslash_033",
                 "backslash_x1b", "backslash_u001b", "bare_sgr"]
    summary: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []

    for target in NARR_TARGETS:
        runs = rows_by_run(target)
        per_enc_out = {e: 0 for e in encodings}
        per_enc_sess = {e: set() for e in encodings}
        all_sess: set[int] = set()
        n_out = 0
        for run, recs in sorted(runs.items()):
            for r in recs:
                if (r.get("cmd_id") or "") in ("", "exit") or r.get("timed_out"):
                    continue
                text = r.get("cleaned_output") or ""
                if not text.strip():
                    continue
                n_out += 1
                anyhit = False
                for name, pat in v21.LITERAL_ANSI_PATTERNS:
                    found = pat.findall(text)
                    if found:
                        per_enc_out[name] += 1
                        per_enc_sess[name].add(run)
                        anyhit = True
                        hits.append({
                            "target": target, "run": run, "cmd_id": r.get("cmd_id"),
                            "encoding": name, "occurrences": len(found),
                            "chars": len(text),
                            "sample": found[0][:40] if found else "",
                            "first_200": text[:200].replace("\n", " | "),
                        })
                if anyhit:
                    all_sess.add(run)
        row = {"target": target, "outputs_scanned": n_out,
               "outputs_any": sum(1 for _ in [0]) and 0, "sessions_any": len(all_sess)}
        flagged = {h["run"] for h in hits if h["target"] == target}
        row["outputs_any"] = len({(h["run"], h["cmd_id"]) for h in hits if h["target"] == target})
        row["sessions_any"] = len(flagged)
        for e in encodings:
            row[f"{e}_outputs"] = per_enc_out[e]
            row[f"{e}_sessions"] = len(per_enc_sess[e])
        summary.append(row)

    for name, data in (("literal_ansi_by_target_v21b.csv", summary),
                       ("literal_ansi_hits_v21b.csv", hits)):
        p = STAGE4 / name
        with open(p, "w", newline="", encoding=ENCODING) as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        print(f"Written: {p}")
    for row in summary:
        print(f"[I4]   {row['target']:16s} outputs={row['outputs_any']:3d} "
              f"sessions={row['sessions_any']:2d} ESC[={row['ESC_bracket_outputs']}"
              f" bs_e={row['backslash_e_outputs']} bare={row['bare_sgr_outputs']}")
    return {"summary": summary, "hits": hits}


def main() -> int:
    issue2()
    issue3()
    issue4()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
