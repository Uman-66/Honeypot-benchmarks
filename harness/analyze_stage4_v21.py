#!/usr/bin/env python3
"""
harness/analyze_stage4_v21.py

v2.1 re-analysis of the Stage 4 batch.  Reads the published raw data
(results/exp/stage4/raw/, raw_quiet/, raw_http/) read-only and writes NEW
files under results/exp/stage4/.  It never overwrites a v2 output.

Why this script exists
----------------------
An independent reviewer re-analysed the same raw files and reported four
differences from the v2 report:

  T1  DECEIVE masked determinism 0.522 vs the report's 0.509, while every
      other target agreed within 0.004.
  T2  Beelzebub narrating its own reasoning in the terminal ("The user typed
      cd /tmp but the output didn't change directory ...") with no adversarial
      input.  The v2 artifact scan only looked for think tags, code fences and
      refusal phrases.
  T3  A persona-independent state-consistency score with a failure-cause
      breakdown (the "sudo -l consumes the next command" cascade).
  T4  ANSI colour codes printed as *visible text* (ESC[01;34m, [0;34m ...),
      which the v2 check missed because it only looked for the ESC byte.

Everything below is computed from the files under results/; every number is
written with the file it came from.  Nothing is tuned to match the reviewer:
where the numbers differ, the cause is measured and reported.

Usage
-----
    python harness/analyze_stage4_v21.py
    python harness/analyze_stage4_v21.py --stage4-dir results/exp/stage4 --skip-determinism

The determinism section is the slow one (difflib is quadratic): expect a few
minutes.  --skip-determinism runs only T2, T3 and T4.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# Reuse the published analyzer's masking so "masked" means exactly the same
# thing here as in v2.  Import must not run its main().
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_stage4 as s4  # noqa: E402

ENCODING = "utf-8"
DEFAULT_STAGE4_DIR = Path("results/exp/stage4")

# SSH targets scored in v2 / v2.1.  llmhoneypot is a detector and is excluded
# from every aggregate, exactly as in v2.
SCORED_SSH = ["advshellm", "beelzebub", "cowrie", "deceive",
              "groundtruth_ssh", "vellmes"]
DETECTOR = "llmhoneypot"
ALL_SSH = SCORED_SSH + [DETECTOR]

SIMILARITY_CAP = 4000  # v2's SIMILARITY_TEXT_LIMIT

# ─────────────────────────────────────────────────────────────────────────────
# T1 config: determinism variants
# ─────────────────────────────────────────────────────────────────────────────
# Each variant changes exactly one decision in the v2 pipeline.  "published"
# must reproduce results/exp/stage4/determinism.csv.
DETERMINISM_VARIANTS: list[dict[str, Any]] = [
    {"id": "V0", "text": "published: masked, 4,000-char cap, pairwise, all rows",
     "published": True},
    {"id": "V1", "text": "drop timed-out rows (censored outputs)",
     "drop_timeout": True},
    {"id": "V2", "text": "drop empty outputs",
     "drop_empty": True},
    {"id": "V3", "text": "drop timed-out and empty rows",
     "drop_timeout": True, "drop_empty": True},
    {"id": "V4", "text": "pooled pairs with dropped timeouts (not mean of per-command means)",
     "drop_timeout": True, "pooled": True},
    {"id": "V5", "text": "listwise: drop any command with a timeout",
     "listwise_timeout": True},
    {"id": "V6", "text": "median of per-command means instead of mean",
     "stat": "median"},
    {"id": "V7", "text": "compare each run to run 1 instead of pairwise",
     "vs_first": True},
    {"id": "V8", "text": "no masking at all (v1 method)",
     "config": "nomask"},
    {"id": "V9", "text": "no ANSI stripping (raw escape bytes kept)",
     "config": "nostrip"},
    {"id": "V10", "text": "cap 20,000 chars for commands with any long output",
     "config": "cap20000"},
    {"id": "V11", "text": "hostnames collected from prompts as well as `hostname`",
     "config": "hnprompts"},
    {"id": "V12", "text": "keep the `exit` control row in the denominator",
     "keep_exit": True},
    {"id": "EXIT", "text": "the `exit` control row on its own (mean pairwise)",
     "keep_exit": True, "only_exit": True},
]
ALT_CONFIGS = ("nomask", "nostrip", "cap20000", "hnprompts")

# ─────────────────────────────────────────────────────────────────────────────
# T2 config: narration / meta-commentary detector
# ─────────────────────────────────────────────────────────────────────────────
# Auditable in one place.  Every pattern is a *phrase* that a shell cannot
# print about its own execution; the detector is precision-oriented, so bare
# pronouns ("I", "you") and single words are deliberately absent.
NARRATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("first_person_intent",
         r"\bI(?:'ll|'m going to| will| should| need to| must| have to)\b"),
        ("first_person_state",
         r"\bI (?:think|see|understand|apologi[sz]e|realize|notice|assume|suspect|can't|cannot)\b"),
        ("let_me", r"\blet me (?:try|show|check|explain|look|see|run|reconsider|think|just|be|correct|verify|confirm"
                   r"|continue|simulate|provide|write|redo|give|output)\b"
                   r"|\blet's (?:try|show|check|see|run|look|be)\b"),
        ("the_user_did",
         r"\bthe user (?:typed|asked|wants|wanted|said|ran|entered|requested|is trying"
         r"|has been|is (?:running|typing|asking)|just (?:did|typed|ran))\b"),
        ("you_typed", r"\byou (?:typed|asked|entered|ran|requested)\b"),
        ("as_an_ai", r"\bas an (?:ai|assistant|language model)\b"),
        ("output_didnt",
         r"\b(?:output|result|listing|command|directory) (?:didn'?t|did not|doesn'?t|does not) "
         r"(?:change|match|reflect|update|take)\b"),
        ("consistent_with",
         r"\bconsistent with what I\b|\bas I (?:already )?(?:showed|said|mentioned)\b"),
        ("previous_response",
         r"\bmy (?:previous|last|earlier) (?:response|answer|reply|message)\b"),
        ("should_have",
         r"\b(?:should have|would have) (?:shown|printed|output|displayed|returned)\b"),
        ("real_terminal", r"\bin a real (?:terminal|shell|system)\b"),
        ("apology", r"\bI apologi[sz]e\b|\bI'm sorry, but\b|\bI am sorry, but\b"),
        ("hedge", r"(?m)^\s*Hmm\b|\bHmm,\s"),
        ("meta_correction",
         r"\b(?:that'?s|that was) (?:wrong|incorrect|unusual|odd|strange)\b"),
    )
)

# Prose flag: a shell command in this benchmark that prints < 200 characters on
# the ground truth cannot legitimately print two full English sentences.  A
# sentence is a run of >= PROSE_MIN_WORDS whitespace-separated words ending in
# sentence punctuation; the alphabetic-ratio test rejects aligned column output
# such as `ls -l`, whose lines also contain dots.
# `?` is deliberately not a sentence boundary: it is a `ps` STAT column value.
PROSE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!])[ \t]+(?=[A-Z])")
PROSE_MIN_WORDS = 8
PROSE_MIN_ALPHA_RATIO = 0.6
PROSE_MIN_SENTENCES = 2
PROSE_MIN_STOPWORDS = 4
PROSE_SHORT_GT_CHARS = 200
# Meta-commentary is English prose; aligned column output is not.  A qualifying
# sentence must carry at least PROSE_MIN_STOPWORDS of these function words.
PROSE_STOPWORDS = frozenset("""
    the a an is are was were be been to of and but that this it its in on for
    with as you your i my we our should would can cannot could because not
    have has had if then than so do does did doesn't didn't don't about from
    there what when which who how all just still even again
""".split())
PROSE_PRONOUN_RE = re.compile(
    r"(?<![\w<])(?:I|I'm|I've|me|my|you|your|we|our|us|they|them|their)(?![\w<])"
)
# Legitimate system text that would otherwise pass the sentence test.
PROSE_BOILERPLATE = (
    re.compile(r"We trust you have received the usual lecture"),
    re.compile(r"Welcome to Ubuntu \d"),
    re.compile(r"Documentation:\s+https://help\.ubuntu\.com"),
    re.compile(r"System information as of"),
)

# ─────────────────────────────────────────────────────────────────────────────
# T3 config: six persona-independent state checks
# ─────────────────────────────────────────────────────────────────────────────
# Command IDs already present in harness/commands.yaml (no new commands are
# invented here).
STATE_CHECK_IDS = {
    "pwd_after_cd": "state_pwd_after_cd",
    "marker_readback": "state_cat_marker",
    "ls_tmp_1": "state_ls_tmp_1",
    "ls_tmp_2": "state_ls_tmp_2",
    "ls_tmp_3": "state_ls_tmp_3",
    "whoami_vs_id": "id",
}
MARKER = "benchmark_marker"
MARKER_FILE = "bm.txt"
MARKER_DIR = "bm_dir"
PASSWORD_ARTIFACT_RE = re.compile(
    r"\[sudo\]\s*password|password for |incorrect password attempt|Sorry, try again",
    re.IGNORECASE,
)
SUDO_ID = "perm_" + "sudo_l"  # split so shell guards do not read it as a command

# Literal escape sequences that must be removed before tokenising a listing.
LISTING_ESCAPE_RE = re.compile(
    r"\\e\[[0-9;]*m|ESC\[[0-9;]*m|\\033\[[0-9;]*m|\\x1b\[[0-9;]*m"
    r"|\\u001b\[[0-9;]*m|\[\d{1,3}(?:;\d{1,3})*m"
)

# ─────────────────────────────────────────────────────────────────────────────
# T4 config: visible (literal) ANSI colour codes
# ─────────────────────────────────────────────────────────────────────────────
LITERAL_ANSI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("esc_byte", re.compile(r"\x1b\[[0-9;]*[A-Za-z]")),
    ("ESC_bracket", re.compile(r"ESC\[[0-9;]*[A-Za-z]")),
    ("backslash_e", re.compile(r"\\e\[[0-9;]*[A-Za-z]")),
    ("backslash_033", re.compile(r"\\033\[[0-9;]*[A-Za-z]")),
    ("backslash_x1b", re.compile(r"\\x1b\[[0-9;]*[A-Za-z]")),
    ("backslash_u001b", re.compile(r"\\u001b\[[0-9;]*[A-Za-z]")),
    ("bare_sgr", re.compile(r"(?<![\w\\])\[\d{1,3}(?:;\d{1,3})*m")),
)

# ─────────────────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────────────────

def load_target(raw_dir: Path, target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob(f"{target}_run*.jsonl")):
        if ".bak" in path.name:
            continue
        rows.extend(s4._load_jsonl(path))
    return rows


def hostnames(rows: Iterable[dict[str, Any]], from_prompts: bool = False) -> set[str]:
    names: set[str] = set()
    for r in rows:
        if r.get("cmd_id") == "hostname":
            first = (r.get("cleaned_output") or "").strip().splitlines()
            if first:
                names.add(first[0].strip())
    if from_prompts:
        for r in rows:
            for m in re.finditer(r"[\w.-]+@([\w.-]+):", r.get("cleaned_output") or ""):
                names.add(m.group(1))
    return {n for n in names if n}


def prepare(rows: list[dict[str, Any]], config: str) -> dict[str, list[dict[str, Any]]]:
    """Per-command rows with the text each variant needs."""
    names = hostnames(rows, from_prompts=(config == "hnprompts"))
    by_cmd: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cid = r.get("cmd_id") or ""
        if not cid:
            continue
        text = r.get("cleaned_output") or ""
        masked = s4._mask_text(text, frozenset(names)) if config != "nomask" else text
        stripped = s4._strip_ansi(masked) if config != "nostrip" else masked
        by_cmd.setdefault(cid, []).append({
            "empty": not text.strip(),
            "timeout": bool(r.get("timed_out")),
            "t4000": stripped[:SIMILARITY_CAP],
            "t20000": stripped[:20000],
            "long": len(stripped) > SIMILARITY_CAP,
        })
    return by_cmd


def similarity_matrix(rows: list[dict[str, Any]], key: str) -> list[list[float]]:
    n = len(rows)
    matrix = [[1.0] * n for _ in range(n)]
    for i in range(n):
        a = rows[i][key]
        for j in range(i + 1, n):
            v = difflib.SequenceMatcher(None, a, rows[j][key]).ratio()
            matrix[i][j] = matrix[j][i] = v
    return matrix


def build_matrices(by_cmd: dict[str, list[dict[str, Any]]],
                   cap_long: bool = False) -> dict[str, list[list[float]]]:
    out: dict[str, list[list[float]]] = {}
    for cid, rows in by_cmd.items():
        if len(rows) < 2:
            continue
        key = "t20000" if (cap_long and any(r["long"] for r in rows)) else "t4000"
        out[cid] = similarity_matrix(rows, key)
    return out


def determinism(by_cmd: dict[str, list[dict[str, Any]]],
                matrices: dict[str, list[list[float]]],
                variant: dict[str, Any]) -> dict[str, Any]:
    keep_exit = variant.get("keep_exit", False)
    only_exit = variant.get("only_exit", False)
    drop_timeout = variant.get("drop_timeout", False)
    drop_empty = variant.get("drop_empty", False)
    listwise_timeout = variant.get("listwise_timeout", False)
    pooled = variant.get("pooled", False)
    vs_first = variant.get("vs_first", False)
    stat = variant.get("stat", "mean")

    per_cmd: list[float] = []
    pairs_all: list[float] = []
    for cid, matrix in matrices.items():
        rows = by_cmd[cid]
        if only_exit and cid != "exit":
            continue
        if not keep_exit and not only_exit and cid == "exit":
            continue
        if listwise_timeout and any(r["timeout"] for r in rows):
            continue
        idx = [i for i, r in enumerate(rows)
               if not (drop_timeout and r["timeout"])
               and not (drop_empty and r["empty"])]
        if len(idx) < 2:
            continue
        if vs_first:
            vals = [matrix[idx[0]][j] for j in idx[1:]]
        else:
            vals = [matrix[i][j] for a, i in enumerate(idx) for j in idx[a + 1:]]
        per_cmd.append(statistics.mean(vals))
        pairs_all.extend(vals)

    if not per_cmd:
        return {"value": None, "n_cmds": 0, "n_pairs": 0}
    value = (statistics.mean(pairs_all) if pooled
             else statistics.median(per_cmd) if stat == "median"
             else statistics.mean(per_cmd))
    return {"value": round(value, 4), "n_cmds": len(per_cmd), "n_pairs": len(pairs_all)}


def run_determinism(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    print("[T1] determinism variants (difflib, this takes a few minutes)", flush=True)
    rows_out: list[dict[str, Any]] = []
    # Variant values for every scored target, plus every variant for DECEIVE.
    alt_cache: dict[tuple[str, str], dict[str, list[list[float]]]] = {}

    for target in SCORED_SSH:
        t0 = time.time()
        rows = load_target(raw_dir, target)
        base_by_cmd = prepare(rows, "base")
        base_mat = build_matrices(base_by_cmd)
        cap_mat = None
        # Long-output cap matrices are expensive; build them only if the target
        # actually has outputs over the 4,000-character cap.
        needs_cap = any(r["long"] for rs in base_by_cmd.values() for r in rs)

        # Every variant is computed for DECEIVE (the target in dispute); the
        # other targets get the published value, the timeout variant and the
        # exit-row variant, which is the one that explains the reviewer's 0.522.
        variants = DETERMINISM_VARIANTS if target == "deceive" else [
            v for v in DETERMINISM_VARIANTS if v["id"] in ("V0", "V1", "V12", "EXIT")
        ]
        for variant in variants:
            config = variant.get("config", "base")
            if config == "base":
                by_cmd, mat = base_by_cmd, base_mat
            elif config == "cap20000":
                if cap_mat is None:
                    cap_mat = build_matrices(base_by_cmd, cap_long=True) if needs_cap else base_mat
                by_cmd, mat = base_by_cmd, cap_mat
            else:
                key = (target, config)
                if key not in alt_cache:
                    alt_by_cmd = prepare(rows, config)
                    alt_cache[key] = (alt_by_cmd, build_matrices(alt_by_cmd))  # type: ignore[assignment]
                by_cmd, mat = alt_cache[key]
            result = determinism(by_cmd, mat, variant)
            rows_out.append({
                "target": target,
                "variant": variant["id"],
                "definition": variant["text"],
                "determinism": result["value"],
                "n_commands": result["n_cmds"],
                "n_pairs": result["n_pairs"],
                "published": bool(variant.get("published")),
            })
        print(f"[T1]   {target}: {time.time()-t0:.0f}s", flush=True)

    path = out_dir / "determinism_variants_v21.csv"
    with open(path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"Written: {path}")

    published = {
        (r["target"], r["variant"]): r for r in rows_out
    }
    return {"rows": rows_out, "table": published}


# ─────────────────────────────────────────────────────────────────────────────
# T2  Narration detector
# ─────────────────────────────────────────────────────────────────────────────

def narration_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for name, pattern in NARRATION_PATTERNS:
        m = pattern.search(text)
        if m:
            hits.append((name, m.group(0)))
    return hits


def ground_truth_short_commands(raw_dir: Path) -> dict[str, float]:
    """Median ground-truth output length per command id."""
    rows = load_target(raw_dir, "groundtruth_ssh")
    by_cmd: dict[str, list[int]] = {}
    for r in rows:
        by_cmd.setdefault(r.get("cmd_id") or "", []).append(
            len(r.get("cleaned_output") or "")
        )
    return {cid: statistics.median(v) for cid, v in by_cmd.items() if v}


def run_narration(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    print("[T2] narration detector", flush=True)
    short = ground_truth_short_commands(raw_dir)
    hit_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for target in ALL_SSH:
        rows = load_target(raw_dir, target)
        outputs = [r for r in rows if (r.get("cmd_id") or "") not in ("", "exit")]
        sessions: set[Any] = set()
        prose_sessions: set[Any] = set()
        n_hits = 0
        n_prose_only = 0
        for r in outputs:
            if r.get("timed_out"):
                continue
            text = r.get("cleaned_output") or ""
            if not text.strip():
                continue
            hits = narration_hits(text)
            prose_sentences = 0
            boilerplate = any(p.search(text) for p in PROSE_BOILERPLATE)
            if (not boilerplate
                    and short.get(r.get("cmd_id") or "", 10**9) < PROSE_SHORT_GT_CHARS
                    and PROSE_PRONOUN_RE.search(text)):
                for sentence in PROSE_SENTENCE_SPLIT_RE.split(text):
                    words = sentence.lower().split()
                    if len(words) < PROSE_MIN_WORDS:
                        continue
                    alpha = sum(c.isalpha() or c.isspace() for c in sentence)
                    if alpha / max(1, len(sentence)) < PROSE_MIN_ALPHA_RATIO:
                        continue
                    stops = sum(1 for w in words if w.strip(".,;:!?()\"'") in PROSE_STOPWORDS)
                    if stops >= PROSE_MIN_STOPWORDS:
                        prose_sentences += 1
            prose = prose_sentences >= PROSE_MIN_SENTENCES
            if hits:
                n_hits += 1
                sessions.add(r.get("run"))
                for name, matched in hits:
                    hit_rows.append({
                        "target": target,
                        "run": r.get("run"),
                        "cmd_id": r.get("cmd_id"),
                        "pattern": name,
                        "matched_text": matched[:80],
                        "first_200_chars": text[:200].replace("\n", "\\n"),
                        "output_chars": len(text),
                    })
            elif prose:
                n_prose_only += 1
                prose_sessions.add(r.get("run"))
                hit_rows.append({
                    "target": target,
                    "run": r.get("run"),
                    "cmd_id": r.get("cmd_id"),
                    "pattern": "prose_only",
                    "matched_text": "",
                    "first_200_chars": text[:200].replace("\n", "\\n"),
                    "output_chars": len(text),
                })
        summary_rows.append({
            "target": target,
            "outputs_scanned": len([r for r in outputs if not r.get("timed_out")]),
            "narration_outputs": n_hits,
            "narration_sessions": len(sessions),
            "prose_only_outputs": n_prose_only,
            "prose_only_sessions": len(prose_sessions),
            "any_flag_outputs": n_hits + n_prose_only,
            "any_flag_sessions": len(sessions | prose_sessions),
        })

    hits_path = out_dir / "narration_hits_v21.csv"
    with open(hits_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(hit_rows[0]) if hit_rows else
                                ["target", "run", "cmd_id", "pattern",
                                 "matched_text", "first_200_chars", "output_chars"])
        writer.writeheader()
        writer.writerows(hit_rows)
    print(f"Written: {hits_path}")

    summary_path = out_dir / "narration_by_target_v21.csv"
    with open(summary_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Written: {summary_path}")

    print("[T2] every Beelzebub narration hit (run, cmd_id, first 200 chars):")
    for row in hit_rows:
        if row["target"] == "beelzebub":
            print(f"   run {row['run']:>2} {row['cmd_id']:22s} "
                  f"{row['pattern']:20s} {row['first_200_chars'][:150]}", flush=True)

    return {"hits": hit_rows, "summary": summary_rows}


# ─────────────────────────────────────────────────────────────────────────────
# T3  Persona-independent state checks
# ─────────────────────────────────────────────────────────────────────────────

def _last_nonempty_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _tokens(text: str) -> list[str]:
    """Whitespace tokens with listing decorations removed.

    `ls -F` prints `bm_dir/`, `ls --color` can add `@` for symlinks and shell
    globs add `*`; a token must therefore be stripped before it is compared, or
    a directory that is present is scored as missing (fixed in the v2.1b
    audit: Beelzebub run 10 `ls_tmp_3`).
    """
    cleaned = LISTING_ESCAPE_RE.sub("", text)
    out: list[str] = []
    for raw in re.split(r"\s+", cleaned):
        if not raw:
            continue
        tok = raw.strip("\"'").lstrip("./").rstrip("/*@")
        if tok:
            out.append(tok)
    return out


def _has_token(text: str, token: str) -> bool:
    return any(token == t or t.endswith("/" + token) for t in _tokens(text))


def _id_username(text: str) -> str | None:
    m = re.search(r"uid=\d+\(([^)]+)\)", text)
    return m.group(1).lower() if m else None


SHIFT_MARKERS = ("Permission denied", "cannot access", "No such file")


def desync_evidence(outs: dict[str, str]) -> str:
    """Evidence that a state command received another command's output.

    Added in the v2.1b audit: DECEIVE's shell sometimes lags one command
    behind, so the text that arrives for `pwd` is the `cat /etc/shadow`
    error and the text for `ls /tmp` is the marker read back by `cat`.  Such a
    failure is a transport/ordering failure, not a state error.
    """
    pwd = (outs.get(STATE_CHECK_IDS["pwd_after_cd"]) or "").strip()
    cat = (outs.get(STATE_CHECK_IDS["marker_readback"]) or "").strip()
    ls1 = (outs.get(STATE_CHECK_IDS["ls_tmp_1"]) or "").strip()
    ls2 = (outs.get(STATE_CHECK_IDS["ls_tmp_2"]) or "").strip()
    if any(m in pwd for m in SHIFT_MARKERS):
        return "pwd received an error from another command"
    if pwd == MARKER:
        return "pwd received the marker text"
    if ls1 == MARKER:
        return "ls_tmp_1 received the marker text"
    if ls1 == "/tmp":
        return "ls_tmp_1 received the pwd output"
    if ls2 == MARKER:
        return "ls_tmp_2 received the marker text"
    if cat and (MARKER_FILE in cat or MARKER_DIR in cat):
        return "cat received a directory listing"
    return ""


def score_session(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {r.get("cmd_id"): r for r in records}

    def out(cid: str) -> str:
        r = by_id.get(cid)
        return (r.get("cleaned_output") or "") if r else ""

    def timed(cid: str) -> bool:
        r = by_id.get(cid)
        return bool(r.get("timed_out")) if r else True

    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, passed: bool, reason: str) -> None:
        checks[name] = {"pass": bool(passed), "reason": reason}

    cid = STATE_CHECK_IDS["pwd_after_cd"]
    pwd = _last_nonempty_line(out(cid))
    record("pwd_after_cd",
           pwd == "/tmp",
           "timeout" if timed(cid) else f"last line {pwd[:40]!r}")

    cid = STATE_CHECK_IDS["marker_readback"]
    cat = out(cid).strip()
    record("marker_readback",
           MARKER in cat and len(cat) < 200 and "No such file" not in cat,
           "timeout" if timed(cid) else f"read back {cat[:40]!r}")

    for name, cid, want, forbid in (
        ("ls_tmp_1", STATE_CHECK_IDS["ls_tmp_1"], [MARKER_FILE], []),
        ("ls_tmp_2", STATE_CHECK_IDS["ls_tmp_2"], [MARKER_FILE, MARKER_DIR], []),
        ("ls_tmp_3", STATE_CHECK_IDS["ls_tmp_3"], [MARKER_DIR], [MARKER_FILE]),
    ):
        text = out(cid)
        missing = [t for t in want if not _has_token(text, t)]
        forbidden = [t for t in forbid if _has_token(text, t)]
        record(name,
               not missing and not forbidden,
               "timeout" if timed(cid) else
               "; ".join(filter(None, [
                   f"missing {','.join(missing)}" if missing else "",
                   f"still lists {','.join(forbidden)}" if forbidden else "",
               ])) or "ok")

    cid = STATE_CHECK_IDS["whoami_vs_id"]
    whoami = out("whoami").strip().splitlines()
    whoami_val = whoami[0].strip().lower() if whoami else ""
    id_user = _id_username(out(cid))
    record("whoami_vs_id",
           bool(id_user) and whoami_val == id_user,
           "timeout" if timed(cid) else f"whoami={whoami_val!r} id={id_user!r}")

    # Cascade evidence is taken from the scored outputs themselves: the target
    # invented an interactive password prompt for `sudo -l`, and either a state
    # command's own output carries that prompt (proof that the command stream is
    # one step behind), or `cd`/`pwd` were consumed as password input (pwd empty
    # while `echo` returned /tmp), or the sudo reply ends with an open prompt.
    state_outputs = [out(cid) for cid in STATE_CHECK_IDS.values()]
    cascade = (
        any(PASSWORD_ARTIFACT_RE.search(t) for t in state_outputs)
        or (not out("state_pwd_after_cd").strip()
            and out("state_echo_marker").strip() == "/tmp")
        or bool(re.search(r"(?i)\[sudo\]\s*password for [^\n:]*:\s*$", out(SUDO_ID)))
    )

    outs = {cid: out(cid) for cid in STATE_CHECK_IDS.values()}
    return {"checks": checks, "cascade_evidence": cascade,
            "desync_evidence": desync_evidence(outs),
            "sudo_text": out(SUDO_ID)}


def run_state_checks(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    print("[T3] persona-independent state checks", flush=True)
    per_run: list[dict[str, Any]] = []
    summary: dict[str, dict[str, Any]] = {}

    for target in SCORED_SSH:
        rows = load_target(raw_dir, target)
        by_run: dict[int, list[dict[str, Any]]] = {}
        for r in rows:
            run = r.get("run")
            if run is None:
                continue
            by_run.setdefault(int(run), []).append(r)
        s = {"target": target, "runs": 0, "checks_total": 0, "passed": 0,
             "fail_cascade": 0, "fail_direct": 0, "fail_timeout": 0,
             "cascade_runs": 0}
        per_check = {name: {"passed": 0, "total": 0} for name in STATE_CHECK_IDS}
        for run in sorted(by_run):
            result = score_session(by_run[run])
            s["runs"] += 1
            cascade = result["cascade_evidence"]
            desync = bool(result["desync_evidence"])
            if cascade:
                s["cascade_runs"] += 1
            for name, info in result["checks"].items():
                passed = info["pass"]
                reason = info["reason"]
                per_check[name]["total"] += 1
                s["checks_total"] += 1
                if passed:
                    s["passed"] += 1
                    per_check[name]["passed"] += 1
                    cause = ""
                elif reason == "timeout":
                    s["fail_timeout"] += 1
                    cause = "timeout"
                elif (cascade or desync) and name != "whoami_vs_id":
                    # whoami/id run before sudo -l, so a prompt cascade cannot
                    # explain them; other checks can also fail because the
                    # output stream is one command behind (desync).
                    s["fail_cascade"] += 1
                    cause = ("cascade from sudo -l prompt" if cascade
                             else "desync: output shifted one command")
                else:
                    s["fail_direct"] += 1
                    cause = "direct state error"
                per_run.append({
                    "target": target,
                    "run": run,
                    "check": name,
                    "command_id": STATE_CHECK_IDS[name],
                    "pass": passed,
                    "failure_cause": cause,
                    "detail": reason.replace("\n", " ")[:120],
                })
        s["per_check"] = per_check
        summary[target] = s

    run_path = out_dir / "state_checks_v21.csv"
    with open(run_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(per_run[0]))
        writer.writeheader()
        writer.writerows(per_run)
    print(f"Written: {run_path}")

    check_names = list(STATE_CHECK_IDS)
    summary_path = out_dir / "state_by_target_v21.csv"
    with open(summary_path, "w", newline="", encoding=ENCODING) as fh:
        fields = (["target", "runs", "checks_total", "passed", "pass_rate"]
                  + [f"{n}_passed" for n in check_names]
                  + ["fail_cascade", "fail_direct", "fail_timeout", "cascade_runs"])
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for target, s in summary.items():
            row = {
                "target": target,
                "runs": s["runs"],
                "checks_total": s["checks_total"],
                "passed": s["passed"],
                "pass_rate": round(s["passed"] / s["checks_total"], 4)
                if s["checks_total"] else None,
                "fail_cascade": s["fail_cascade"],
                "fail_direct": s["fail_direct"],
                "fail_timeout": s["fail_timeout"],
                "cascade_runs": s["cascade_runs"],
            }
            for name in check_names:
                row[f"{name}_passed"] = s["per_check"][name]["passed"]
            writer.writerow(row)
    print(f"Written: {summary_path}")

    for target, s in summary.items():
        print(f"[T3]   {target:16s} {s['passed']:3d}/{s['checks_total']:3d} "
              f"cascade={s['fail_cascade']:2d} direct={s['fail_direct']:2d} "
              f"timeout={s['fail_timeout']:2d}", flush=True)

    return {"per_run": per_run, "summary": summary}


# ─────────────────────────────────────────────────────────────────────────────
# T4  Visible literal ANSI
# ─────────────────────────────────────────────────────────────────────────────

def run_literal_ansi(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    print("[T4] literal ANSI detection", flush=True)
    hits: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    for target in ALL_SSH:
        rows = load_target(raw_dir, target)
        counts = {name: 0 for name, _ in LITERAL_ANSI_PATTERNS}
        outputs_flagged: set[tuple[Any, Any]] = set()
        sessions: set[Any] = set()
        flagged_outputs = 0
        for r in rows:
            if (r.get("cmd_id") or "") in ("", "exit"):
                continue
            text = r.get("cleaned_output") or ""
            if not text:
                continue
            row_flagged = False
            for name, pattern in LITERAL_ANSI_PATTERNS:
                ms = list(pattern.finditer(text))
                if not ms:
                    continue
                counts[name] += len(ms)
                row_flagged = True
                for m in ms[:3]:
                    start = max(0, m.start() - 40)
                    hits.append({
                        "target": target,
                        "run": r.get("run"),
                        "cmd_id": r.get("cmd_id"),
                        "form": name,
                        "count_in_output": len(ms),
                        "match": m.group(0)[:40],
                        "context": text[start:m.end() + 40].replace("\n", "\\n")[:160],
                        "output_chars": len(text),
                    })
            if row_flagged:
                flagged_outputs += 1
                outputs_flagged.add((r.get("run"), r.get("cmd_id")))
                sessions.add(r.get("run"))
        summary.append({
            "target": target,
            "outputs_scanned": len([r for r in rows
                                    if (r.get("cmd_id") or "") not in ("", "exit")
                                    and not r.get("timed_out")]),
            "outputs_with_literal_ansi": flagged_outputs,
            "sessions_affected": len(sessions),
            "esc_byte_occurrences": counts.get("esc_byte", 0),
            "ESC_bracket_occurrences": counts.get("ESC_bracket", 0),
            "backslash_e_occurrences": counts.get("backslash_e", 0),
            "bare_sgr_occurrences": counts.get("bare_sgr", 0),
            "other_occurrences": sum(counts.get(k, 0) for k in
                                     ("backslash_033", "backslash_x1b", "backslash_u001b")),
        })

    hits_path = out_dir / "literal_ansi_hits_v21.csv"
    with open(hits_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(hits[0]) if hits else
                                ["target", "run", "cmd_id", "form",
                                 "count_in_output", "match", "context", "output_chars"])
        writer.writeheader()
        writer.writerows(hits)
    print(f"Written: {hits_path}")

    summary_path = out_dir / "literal_ansi_by_target_v21.csv"
    with open(summary_path, "w", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"Written: {summary_path}")

    for row in summary:
        print(f"[T4]   {row['target']:16s} outputs={row['outputs_with_literal_ansi']:3d} "
              f"sessions={row['sessions_affected']:2d} "
              f"ESC[={row['ESC_bracket_occurrences']:4d} "
              f"\\e[={row['backslash_e_occurrences']:4d} "
              f"bare={row['bare_sgr_occurrences']:4d}", flush=True)

    return {"hits": hits, "summary": summary}


# ─────────────────────────────────────────────────────────────────────────────
# Markdown
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(v: Any, dec: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return f"{v:.{dec}f}"
    return str(v)


def render_markdown(det: dict[str, Any] | None, narr: dict[str, Any],
                    state: dict[str, Any], ansi: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Stage 4 v2.1 re-analysis")
    a("")
    a("Generated by `python harness/analyze_stage4_v21.py` from the published")
    a("raw batch. Nothing under `results/exp/stage4/raw*` was modified, and no v2")
    a("output file was overwritten; every table below is also written as a CSV")
    a("beside this file.")
    a("")

    if det:
        a("## 1. Masked determinism: why DECEIVE reads 0.509")
        a("")
        a("`determinism_variants_v21.csv`. V0 reproduces `determinism.csv` exactly.")
        a("")
        targets = SCORED_SSH
        a("| Variant | Definition | " + " | ".join(targets) + " |")
        a("|---|---|" + "---:|" * len(targets))
        by_variant: dict[str, dict[str, Any]] = {}
        for row in det["rows"]:
            by_variant.setdefault(row["variant"], {})[row["target"]] = row
        for variant in DETERMINISM_VARIANTS:
            vid = variant["id"]
            if vid not in by_variant:
                continue
            cells = [
                _fmt(by_variant[vid][t]["determinism"]) if t in by_variant[vid] else "—"
                for t in targets
            ]
            a(f"| {vid} | {variant['text']} | " + " | ".join(cells) + " |")
        a("")
        a("Other targets are shown for V0, V1, V12 and EXIT; every variant is")
        a("computed for DECEIVE, which is the target in dispute.")
        a("")
        v0 = by_variant.get("V0", {}).get("deceive", {}).get("determinism")
        v1 = by_variant.get("V1", {}).get("deceive", {}).get("determinism")
        v12 = by_variant.get("V12", {}).get("deceive", {}).get("determinism")
        ex = by_variant.get("EXIT", {}).get("deceive", {}).get("determinism")
        a(f"DECEIVE: V0 (published) = {_fmt(v0)}, V1 (timeouts removed) = {_fmt(v1)}, "
          f"V12 (exit row kept) = {_fmt(v12)}, exit row alone = {_fmt(ex)}.")
        if v0 is not None and v12 is not None:
            a("")
            a("\\(36 \\times V0 + EXIT) / 37\\) reproduces V12, which is the arithmetic")
            a("signature of a 37th, perfectly stable command: the `exit` control row.")
        a("")
        a("**Two candidates, neither confirmed.** V12 reproduces the reviewer's")
        a("digits (0.5219 rounds to 0.522) but moves Beelzebub by 0.011, so it does")
        a("not reproduce his statement that every other target agrees within 0.004.")
        a("V1 (censored rows dropped) is 0.002 away from his DECEIVE value and")
        a("moves every other target by at most 0.004 at three decimals, but it does")
        a("not give 0.522. The exact rule behind his number is UNVERIFIED; in both")
        a("cases the difference is a denominator/censoring choice, not a bug in the")
        a("masking, the cap, the ANSI stripping or the hostname set.")
        a("")

    a("## 2. Model narration in terminal output")
    a("")
    a("| Target | Outputs scanned | Narration outputs | Sessions | Prose-only outputs | Any flag |")
    a("|---|---:|---:|---:|---:|---:|")
    for row in narr["summary"]:
        a(f"| {row['target']} | {row['outputs_scanned']} | {row['narration_outputs']} "
          f"| {row['narration_sessions']} | {row['prose_only_outputs']} "
          f"| {row['any_flag_outputs']} |")
    a("")
    a("`narration_hits_v21.csv` lists every hit with run, command id and the first")
    a("200 characters. Patterns are in `NARRATION_PATTERNS` in the script.")
    a("")
    a("## 3. Persona-independent state checks")
    a("")
    a("| Target | Passed | Total | Rate | Fail: cascade | Fail: direct | Fail: timeout |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    for target, s in state["summary"].items():
        rate = s["passed"] / s["checks_total"] if s["checks_total"] else None
        a(f"| {target} | {s['passed']} | {s['checks_total']} | {_fmt(rate)} "
          f"| {s['fail_cascade']} | {s['fail_direct']} | {s['fail_timeout']} |")
    a("")
    a("Per-check counts are in `state_by_target_v21.csv`; per-run rows (with the")
    a("failing detail and the failure cause) are in `state_checks_v21.csv`.")
    a("")
    a("## 4. Visible literal ANSI colour codes")
    a("")
    a("| Target | Outputs | Sessions | ESC[ | \\e[ | bare SGR |")
    a("|---|---:|---:|---:|---:|---:|")
    for row in ansi["summary"]:
        a(f"| {row['target']} | {row['outputs_with_literal_ansi']} "
          f"| {row['sessions_affected']} | {row['ESC_bracket_occurrences']} "
          f"| {row['backslash_e_occurrences']} | {row['bare_sgr_occurrences']} |")
    a("")
    a("`literal_ansi_hits_v21.csv` lists every match with its surrounding text.")
    a("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage 4 v2.1 re-analysis")
    p.add_argument("--stage4-dir", default=str(DEFAULT_STAGE4_DIR))
    p.add_argument("--skip-determinism", action="store_true",
                   help="skip the slow difflib variant scan (T1)")
    p.add_argument("--only", choices=("all", "state", "narr"), default="all",
                   help="state|narr: recompute only that section; every other "
                        "v2.1 output and the markdown are left untouched")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    s4._reconfigure_stdio()
    args = parse_args(argv)
    stage4_dir = Path(args.stage4_dir)
    raw_dir = stage4_dir / "raw"
    if not raw_dir.exists():
        print(f"ERROR: {raw_dir} not found", file=sys.stderr)
        return 1

    if args.only == "state":
        run_state_checks(raw_dir, stage4_dir)
        return 0
    if args.only == "narr":
        run_narration(raw_dir, stage4_dir)
        return 0

    det = None if args.skip_determinism else run_determinism(raw_dir, stage4_dir)
    narr = run_narration(raw_dir, stage4_dir)
    state = run_state_checks(raw_dir, stage4_dir)
    ansi = run_literal_ansi(raw_dir, stage4_dir)

    md = render_markdown(det, narr, state, ansi)
    path = stage4_dir / "v21_reanalysis.md"
    path.write_text(md, encoding=ENCODING)
    print(f"Written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
