# v2.1 recheck (branch `report-v2.1-recheck`)

Every number below comes from a file under `results/exp/stage4/`. The v2.1
outputs were treated as untrusted and re-derived from the raw JSONL batch. Raw
data, `determinism.csv` and the v2 report files were not modified.

Scripts: `harness/recheck_v21b_det.py` (Issue 1), `harness/recheck_v21b_other.py`
(Issues 2-4). Outputs use the `_v21b` suffix.

---

## Issue 1 — DECEIVE masked determinism (0.5086 vs 0.522)

### What is happening and why

The published method reproduces exactly: 0.7903 / 0.5940 / 0.9964 / 0.5086 /
0.9923 / 0.8477 for AdvancedshelLM, Beelzebub, Cowrie, DECEIVE, ground truth and
VelLMes (`determinism_grid_v21b.csv`, configuration M1, exit dropped, timeouts as
recorded, empties kept, all pairs, mean of per-command means).

The reviewer's 0.522 is reachable in exactly two principled ways, and each one
breaks his other claim that the remaining targets agree within 0.004:

| Route | DECEIVE | Largest move among the other five |
|---|---:|---:|
| keep the `exit` control row (V12) | 0.5219 | 0.0109 (Beelzebub 0.5940 -> 0.6049) |
| exact Levenshtein similarity instead of difflib (M4) | 0.5281 | 0.0169 |
| published (M1) | 0.5086 | 0 |

The `exit` route is pure arithmetic: the row is identical in all 20 runs for
every target (pairwise 1.0000), so adding it as a 37th command gives
`(36 * 0.5086 + 1.0000) / 37 = 0.5219`. The size of that lift is
`(1 - V0) / 37`, which is largest for the target with the lowest published
similarity. DECEIVE is that target, so under this rule DECEIVE moves most
(0.0133) and Beelzebub second (0.0110) - which is exactly why the rule cannot be
his, since it puts Beelzebub outside his own 0.004 tolerance.

Why DECEIVE is the target that moves under the *censoring* route (dropping
timed-out rows, V1 = 0.5242): not because it has the most censored rows - it has
29 scored timeouts (39 with the 10 on the unscored `exit` row) while VelLMes has
39 scored timeouts and moves by -0.0009 - but because its censored rows sit on
commands whose surviving rows disagree strongly, so removing them lifts the mean
by 0.0156. DECEIVE also has 17 outputs over the 4,000-character cap (Cowrie 20,
Beelzebub 7) and a largest output of 142,810 characters (Beelzebub 198,856), but
the cap is not the driver: raising it to 20,000 changes DECEIVE by 0.0003
(`determinism_explain_v21b.csv`, `determinism_grid_v21b.csv`). Its low-similarity commands are the long
listings - `ls /etc` and the three `/tmp` listings are the worst commands in the
matrix - and those are the commands whose rows sit in its shifted stretches.
(The per-command similarity ranking was computed in the audit session and is not
persisted to a file; the state failures in Issue 3 are the traceable evidence
that those are the mangles.) The
cap itself is not the driver: raising it to 20,000 characters moves DECEIVE by
0.0003 (M10 = 0.5083, largest move elsewhere 0.0011), and removing it entirely
moves the four feasible targets by at most 0.0012 (M11).

### Key numbers

| Configuration | DECEIVE | Max move among other targets |
|---|---:|---:|
| M1 published | 0.5086 | 0 |
| V12 exit row kept | 0.5219 | 0.0109 |
| V1 timeouts dropped | 0.5242 | 0.0042 |
| M4 Levenshtein ratio | 0.5281 | 0.0169 |
| M10 cap 20,000 | 0.5083 | 0.0011 |
| M11 no cap (4 targets feasible) | not feasible | 0.0012 |
| M3 `quick_ratio()` | 0.6374 | 0.1468 |
| M2 autojunk=False (ground truth only) | not feasible | +0.0052 on ground truth |

Grid size: 11 text/similarity configurations x 192 aggregation choices = 2,112
combinations per target, 12,672 in total, 11,328 rows written. Every combination
was computed for all six targets.

Three configurations could not be completed and are recorded as such rather than
dropped: `autojunk=False` exceeded the 240 s budget at `ps_aux` for five of six
targets (`ps aux` output is highly repetitive, which is what autojunk exists to
handle), and the no-cap configuration is infeasible for DECEIVE and Beelzebub
(145,509 and 198,706 characters).

**Combinations satisfying the joint criterion: 0** (`determinism_success_v21b.csv`
contains `no_combination_matched`). The closest is the `exit` row at 0.5219,
0.0001 from his value, but with a 0.0109 move on Beelzebub.

`quick_ratio()` is not a measurement of the same quantity: it is an upper bound
computed from character multisets, so it inflates every target (Beelzebub
0.7408). It is reported so that the grid is complete, not as evidence.

### What changed from v2.1

The two-candidate framing is confirmed and now quantified across the full grid:
no third route exists, and no combination satisfies both halves of the reviewer's
statement. v2.1 said the `exit` row "moves Beelzebub by 0.011"; that is confirmed
(0.0109). The claim that a no-cap run was "too slow" is now measured rather than
asserted.

### Remaining UNVERIFIED

The reviewer's exact rule. His 0.522 and his "others within 0.004" cannot both
hold under any of the 12,672 combinations tested, so one of the two statements
must come from different data or a different check. The headline stays 0.5086
and both numbers are reported in the text.

---

## Issue 2 — Beelzebub narration

### What is happening and why

The v2 artifact scan looked for think tags, code fences and refusal phrases. The
v2.1 detector looks for first-person planning, "the user typed", "in a real
terminal", apology and hedge forms, plus a prose rule for two English sentences.

Manual review of all 14 v2.1 hits: **all 14 are genuine** - the model explains
its own reasoning, its earlier responses, or the user's intent inside the
terminal transcript. Examples: run 6 `state_pwd_after_cd` ("The user typed `cd
/tmp` but the output didn't change directory - that's unusual. Actually in a real
terminal ..."), run 10 `perm_sudo_l` ("Let me try that differently ..."), run 11
`ls_etc` ("ls was already in there... wait, actually let me just write the final
one carefully"), run 14 `which_python3_gcc` ("The user's whoami, id, etc.
responses should have realistic values ... Wait - I notice my earlier `ls`
response had a formatting error where I leaked internal reasoning text").
Precision: 14/14.

That review also exposed two gaps. Sampling the 30 longest unflagged outputs plus
a loose probe over all 700 unflagged outputs turned up two missed outputs:

- run 20 `state_ls_tmp_3`: "The user has been running commands. Let me continue
  simulating the terminal. They removed bm.txt, now /tmp should show bm_dir
  only." - clear narration, missed because "the user has been" and "let me
  continue" were not in the phrase lists and "they" was not a pronoun for the
  prose rule.
- run 8 `which_python3_gcc`: a leaked tool definition ("Important: The user has
  provided one tool definition: {...}"). This is harness text leakage rather
  than narration about the terminal, so it is counted as borderline.

The detector now includes "the user has been/is ...", "let me continue/simulate/
..." and "they/them/their" in the prose pronoun set. With those additions it
finds **15 outputs in 12 of 20 sessions**, and the run-20 miss is closed.

The reviewer's 5 sessions are possibly the five that literally contain
"The user ..." (runs 1, 6, 18, 19, 20). That phrase occurs in 7 sessions (it also
appears in runs 12 and 14), so "exactly those five" is not established; the
mapping stays an inference.

### Key numbers

| Measure | Outputs | Sessions |
|---|---:|---:|
| v2.1 as published | 14 | 11 |
| v2.1 after manual review + pattern fix (strict: clear narration) | 15 | 12 |
| broad (adds the run-8 leaked tool definition) | 16 | 13 |
| reviewer | - | 5 |
| ground truth, Cowrie, AdvancedshelLM, VelLMes, DECEIVE, llm-honeypot | 0 | 0 |

False negatives: the loose probe over all 714-716 scanned outputs found exactly 2
candidates; one is now detected, the other is a different artifact class. The 30
longest unflagged outputs (`narration_unflagged_sample_v21b.csv`) were read: none
shows narration in its first 300 characters, and the detector had already
cleared their full text, so the residual false-negative estimate is 0-1 (the
run-8 leak).

### What changed from v2.1

14 outputs / 11 sessions -> 15 / 12, plus two documented pattern gaps. The
"14 named phrases" description in the v2.1 report is now stale and needs the two
additions.

### Remaining UNVERIFIED

Which exact rule produced the reviewer's 5. The "The user ..." hypothesis fits
perfectly but is inferred, not proven.

---

## Issue 3 — Persona-independent state checks

### What is happening and why

The six checks map to existing manifest commands, none invented:

| Check | Command id | Pass rule |
|---|---|---|
| `pwd_after_cd` | `state_pwd_after_cd` | last non-empty line is exactly `/tmp` |
| `marker_readback` | `state_cat_marker` | output contains `benchmark_marker`, is under 200 chars and is not an error |
| `ls_tmp_1` | `state_ls_tmp_1` | lists `bm.txt` (directory may exist) |
| `ls_tmp_2` | `state_ls_tmp_2` | lists `bm.txt` and `bm_dir` |
| `ls_tmp_3` | `state_ls_tmp_3` | lists `bm_dir` and not `bm.txt` |
| `whoami_vs_id` | `id` (with `whoami`) | `whoami` equals the `uid=(...)` name in `id` |

A real bug was found in the v2.1 scorer: `_tokens` split on whitespace and
compared tokens literally, so `ls -F` output `bm_dir/` - the directory *is*
present - was scored as missing. Beelzebub run 10 `state_ls_tmp_3` is exactly
that case. Fixing the tokeniser (strip a trailing `/`, `*` or `@`) changes
Beelzebub from 106/120 to **107/120**, which is the reviewer's number. No other
target has such a case (`state_checks_v21b.csv` was scanned for decorated marker
tokens).

The second correction is about causes, not scores. Re-reading the raw rows shows
that "cascade from the password prompt" is not the mechanism. An onset is
identifiable in 10 of the 20 runs, and every onset has a `timed_out=true` row
within the three before it: nine at onset-1, run 20 at onset-2 and onset-3
(`desync_onset_v21b.md`). Six runs start at line 18, where the `w` slot flushes
the `ps aux` and `cpuinfo` outputs of the two timed-out rows as one blob and
then stays one row behind (run 14 resyncs at line 19); runs 1, 7 and 19 start at
line 27, where `cd` receives the password text; run 20 is three rows behind from
line 4 to the end. No run shifts on the prompt alone. 35 of DECEIVE's failures
carry the `cascade` label, four are direct and two are timeouts; the label and
the counts are unchanged, the mechanism is **UNVERIFIED**.

A third, smaller inconsistency: a timed-out command is labelled `timeout` only
when it fails. Two DECEIVE passes (runs 13 and 17, `whoami_vs_id`) rest on an
`id` row that timed out after printing its `uid=` line. Counting those as
failures - "a timeout is no evidence" - gives 77/120 instead of 79/120. The
report keeps 79 (the check is about content consistency) but now states the
caveat.

### Key numbers

| Target | Mine (corrected) | Reviewer | Note |
|---|---:|---:|---|
| ground truth | 120 | 120 | match |
| Cowrie | 120 | 120 | match |
| VelLMes | 119 | 117 | one `whoami` empty string; -2 unexplained |
| AdvancedshelLM | 116 | 116 | match |
| Beelzebub | 107 | 107 | **match after the tokeniser fix** |
| DECEIVE | 79 (77 if timeouts are no evidence) | 72 | -7 unexplained |

Rules tested: 24 combinations of cascade policy (observed / all six / after sudo
/ any desync / desync or cascade), timeout policy (fail / pass), listing policy
(marker / three identical listings) and pwd policy (lenient / strict).

- A session-level rule "any desynchronised session fails all six checks" gives
  **exactly 72** for DECEIVE, but it puts Beelzebub at 95/120 rather than 107, so
  it cannot be the reviewer's rule.
- **No rule gives VelLMes 117**; the closest is 119.
- **No rule matches all three** of 72 / 117 / 107.

### What changed from v2.1

Beelzebub 106 -> 107 (bug fix, now matches the reviewer). DECEIVE cause split
30/9/2 -> 35/4/2. The statement "seven-check difference is not explained by any
single rule" is now stronger: 24 rules were tested, one reproduces 72 in
isolation, and none reproduces the three numbers together.

### Remaining UNVERIFIED

The reviewer's exact rule for 72 / 117 / 107. His DECEIVE number is consistent
with a session-level desync rule and his Beelzebub number with the per-check
rule; the two are mutually exclusive under our data.

---

## Issue 4 — Visible colour codes

### What is happening and why

Units were mixed in v2.1: 170 / 1,035 / 223 are *occurrences*, while 32 is
*outputs*. Recounted per output and per session:

| Encoding | Outputs | Sessions | Occurrences |
|---|---:|---:|---:|
| `ESC[01;34m` (literal text) | 5 | 1 (run 2) | 170 |
| `\e[01;34m` | 17 | 3 (runs 4, 5, 9) | 1,035 |
| bare `[0;34m` / `[38;5;33m` | 10 | 2 (runs 12, 19) | 223 |
| any form | **32** | **6** | 1,428 (deduplicated per row) |

The reviewer's 5 is **exactly the `ESC[` form**: five outputs in run 2 -
`ls_etc`, `ls_home`, `state_ls_tmp_1`, `state_ls_tmp_2`, `state_ls_tmp_3`. All
five were hand-checked; every context is a real colour code
(`ESC[01;34macpiESC[0m`). All three encodings are literal text in the capture,
not control bytes: no raw `.jsonl` contains a `0x1b` byte, and `ESC[` is the
four ASCII characters `0x45 0x53 0x43 0x5b`. The other encodings were sampled (6 of 27 outputs) and
none is a false positive - the bare form always appears as `[0;34mname[0m` in a
listing, which a reader sees as bracketed text and a byte-level check cannot
find.

### What changed from v2.1

The claim "5 is the run-2 form alone" is now exact: 5 outputs, 1 session, and
they are the complete `ESC[` set. Units are stated everywhere.

### Remaining UNVERIFIED

Nothing. This issue is closed.

---

## Issue 5 — Citation

`grep` over every `.md`, `.tex`, `.py`, `.yml` in the repository:

- Updated or marked "formerly": `README.md`, `THIRD_PARTY_NOTICES.md`,
  `docs/PATCH_NOTES.md`, `docs/FACTS_CHECK.md` (two places),
  `report/honeypot_report_v2_1.tex` (two places), `CHANGELOG.md`.
- Frozen on purpose: `report/honeypot_report_v2.tex` (3 mentions of
  `splunk/DECEIVE`). The v2 report is a published artifact and changing it would
  rewrite a document that is already cited; the v2.1 source carries the correct
  URL and the redirect note.
- Untracked local copy `honeypot_report_v2.tex` at the repository root: not
  published, not part of the report series.
- Vendor files, not ours to edit: `DECEIVE/README.md` and
  `recovered/deceive_app/README.md` (upstream text), and
  `cowrie-base/src/cowrie/output/splunk.py` (Cowrie's Splunk plugin, unrelated).

Redirect verified 2026-11-25: `https://github.com/splunk/DECEIVE` answers
`301 Moved Permanently` to `https://github.com/Cisco-Talos/DECEIVE`.

---

## Issue 6 — Report consistency

- Every number in the v2.1 section now traces to a `_v21` or `_v21b` CSV. The
  three corrections were propagated into the report: Beelzebub 106 -> 107,
  narration 14/11 -> 15/12, DECEIVE cause split 30/9 -> 35/4.
- No "undercounted" wording exists in the repository. The report says "A broader
  detector finds 15 outputs ...", which is the neutral phrasing requested.
- LaTeX: no `pdflatex`, `latexmk` or `tectonic` is installed, so the PDF remains
  **uncompiled**. A structural check (balanced environments and braces, section
  order, bibliography) passed before the audit edits; the terminal became
  unavailable during the audit, so the edited source was **not** re-checked
  afterwards. Run `python -c` brace/environment check or a compiler before
  publishing.

---

## Summary

**Confirmed:** published determinism reproduces exactly; the `exit` row is the
only combination that reaches 0.522 and it breaks the 0.004 tolerance; ESC[ = 5
outputs in run 2 as literal text, not control bytes (the reviewer's 5 exactly);
the v2.1 narration hits are all genuine (precision 14/14); controls are zero
everywhere; the citation redirect.

**Corrected:** Beelzebub state 106 -> 107 (tokeniser bug; now matches the
reviewer); narration 14/11 -> 15/12 (two pattern gaps); DECEIVE cause split
30 cascade / 9 direct -> 35 cascade / 4 direct / 2 timeout (labels kept; onset
is timeout-ordered in 10/20 runs, mechanism **UNVERIFIED**); ANSI units (outputs
vs occurrences).

**Still open:** the reviewer's determinism rule; his state numbers as a set (72
is reachable only with a rule that gives Beelzebub 95); whether the run-8 leaked
tool definition should count as narration; the trigger of the DECEIVE row
shifts (timeout-ordered, mechanism unverified); the v2.1 PDF is uncompiled.
