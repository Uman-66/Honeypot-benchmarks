# TeX fixes — v2.1c

Branch `report-v2.1-recheck`. Work run 2026-11-28. Edited `report/honeypot_report_v2_1.tex`
only; this file is the one new file. No CSV, raw file, harness script or frozen v2 tex was
touched; no `git` command that changes state was run.

**Scope of verification.** Every fix below was checked against the repository *before* editing.
Where the premise did not hold, no edit was made and the item is marked **PREMISE WRONG** with
the evidence. `csv line <n>` is the 1-based line in the named CSV including its header; `L<n>`
is the 1-based JSON line in the named `.jsonl` file.

---

## 1. Compile result

| | |
|---|---|
| Engine | tectonic 0.15.0 (`tectonic -X compile honeypot_report_v2_1.tex --keep-logs`) |
| Where | scratch directory outside the repo (`%TEMP%\texbuild`); build artefacts and the PDF are not in the tree |
| Exit status | 0 |
| Errors (`^!`) | **0** |
| Overfull boxes | **0** |
| Underfull boxes | **31** (was 26 before these edits; the new prose adds lines) |
| Undefined references / citations | **0** |
| Pages | **19** |
| PDF | 139,551 bytes |

The first build after the content edits had one overfull box, 19.3 pt too wide at the narration
table, caused by the new column header. The header was stacked (`\shortstack`) so it states the
definition without widening the table; the table now fits and the final build has no overfull
box.

**Not checked:** the PDF was not opened or visually inspected; no page-by-page layout review was
done beyond the box diagnostics.

---

## 2. Edit list with old and new line numbers

Old file = 1342 lines (reconstructed by reversing each edit, real `difflib` diff), new file =
1341 lines. Line numbers are 1-based.

| # | Fix | Old lines | New lines | Change |
|---|---|---:|---:|---|
| 1 | 9 | 234 | 234 | `\texttt{Cisco-Talos/DECEIVE} on 21 November 2026` → `the upstream repository on 21 November 2026 (then still addressed as \texttt{splunk/DECEIVE})` |
| 2 | 8 | 924 | 924 | `Every v2.1 number is written by` → `Most v2.1 numbers are written by` |
| 3 | 8 | 928 | 928 | added the real sources: `recheck_v21b_det.py` (determinism grid), `recheck_v21b_other.py` (narration, colour codes, rule grid), `desync_onset_v21b.md` (onset table) |
| 4 | 6 | 1024–1025 | 1024–1025 | Table 15 caption now states what "Rows scanned" counts and names `narration_by_target_v21b.csv` for the stricter count |
| 5 | 6 | 1030 | 1030 | header `Outputs scanned` → `\shortstack{Rows scanned\\(non-\texttt{exit},\ non-timeout)}` |
| 6 | 11 | 1046–1047 | 1046–1047 | `v2 scored state with six checks that compared listings against the ground truth's literal contents` → v2 had no state checks; fidelity was a `difflib` character-similarity ratio |
| 7 | 2, 1 | 1085–1087 | 1085–1087 | `the v2.1 account of a prompt-driven cascade is not supported as stated: the shift starts at a timeout` → plain finding + `Every identified onset is preceded by a timeout within the three prior rows` |
| 8 | 1, 3 | 1091–1092 | 1091–1092 | added `Timeouts without a shift also occur (runs~5 and~13), so a timeout is consistent with, not sufficient for, a shift`; `that line` → `line~26 (\texttt{sudo -l})` |
| 9 | 4 | 1094 | 1094 | added the AdvancedshelLM run 6 sentence with L26–L28 and `state_checks_v21.csv` line 32 |
| 10 | 12 | (insert after 1141) | 1142–1143 | new exploratory paragraph before §6.4 |
| 11 | 5 | 1155 | 1157 | ANSI paragraph now cites `literal_ansi_by_target_v21b.csv` and `literal_ansi_hits_v21b.csv` |
| 12 | 10 | 1248–1251 (+1252) | 1250 | removed `The source of this version compiles without errors under XeTeX (tectonic 0.15.0) and the PDF is built from it.` |

Net line change: −1 (2 lines inserted, 3 removed). `docs/FACTS_CHECK.md` was **not** edited: no
number in it changes.

---

## 3. Fix-by-fix verification

### FIX 1 — overstated ("the shift starts at a timeout") — **DONE**

Runs 5 and 13 verified in the raw rows:

```
deceive_run05.jsonl L26 perm_sudo_l        timed_out=True   '[sudo] password for guest:'
deceive_run05.jsonl L27 state_cd_tmp       timed_out=False  ''
deceive_run05.jsonl L28 state_pwd_after_cd timed_out=False  '/tmp'
```
Run 5 has a timeout at the sudo row and stays in step (`pwd` returns `/tmp`); it scores 6/6 and
has no onset (`desync_onset_v21b.md`, unshifted list; `state_checks_v21.csv` DECEIVE run 5).

```
deceive_run13.jsonl L1 whoami   timed_out=True  'guest'
deceive_run13.jsonl L2 id       timed_out=True  'uid=1001(guest) gid=1001(guest) …'
deceive_run13.jsonl L3 pwd      timed_out=True  '/home/guest'
deceive_run13.jsonl L4 hostname timed_out=True  'helix-dev-ws07'
```
Run 13 has four timeouts, each row still carries its own correct output, and the run does not
shift (6/6).

Necessity direction (10/10 onsets have a timeout within the three prior rows) is unchanged and
was re-checked in `claims_audit_v21b.md` Part 3.3.

### FIX 2 — confusing sentence — **DONE**

Replaced with: "Read against the raw rows, the prompt hypothesis for DECEIVE is not supported by
the onset data (counts below)". The counts follow in the same paragraph (10/10 onsets preceded by
a timeout; prompt cross-tab 4/7/6/3).

### FIX 3 — dangling "that line carries the prompt in 11" — **DONE**

Now reads `line~26 (\texttt{sudo -l})`. Verified by re-deriving from the raw files for all 20
runs (`deceive_runNN.jsonl` L26, `cmd_id=perm_sudo_l`):

| | shifted | not shifted | total |
|---|---:|---:|---:|
| prompt on L26 | 4 (1, 7, 14, 19) | 7 (3, 5, 6, 10, 11, 12, 13) | 11 |
| no prompt on L26 | 6 (4, 8, 15, 17, 18, 20) | 3 (2, 9, 16) | 9 |

This reproduces `claims_audit_v21b.md` Part 3.2 exactly (4/7/6/3, total 11). Line 26 is
`perm_sudo_l` in every run.

### FIX 4 — missing evidence (AdvancedshelLM run 6) — **DONE**

```
advshellm_run06.jsonl L26 perm_sudo_l          timed_out=False  '[sudo] password for admin:'
advshellm_run06.jsonl L27 state_cd_tmp         timed_out=False  'Sorry, try again.\n\n[sudo] password for admin:'
advshellm_run06.jsonl L28 state_pwd_after_cd   timed_out=False  'Sorry, try again.\n\nsudo: 2 incorrect password attempts'
```
Zero `timed_out=True` rows in the whole run (0 of 37). `state_checks_v21.csv` line 32:

```
advshellm,6,pwd_after_cd,state_pwd_after_cd,False,cascade from sudo -l prompt,last line 'sudo: 2 incorrect password attempts'
```

The tex now describes the rows accurately: both L27 and L28 begin `Sorry, try again.`, L27 ends
with a second password prompt, L28 with `sudo: 2 incorrect password attempts`.

### FIX 5 — file names — **PARTLY PREMISE WRONG; edited where the numbers were not in the cited files**

| Number printed | Files that actually hold it | Verdict |
|---|---|---|
| narration 15 outputs / 12 sessions | `narration_hits_v21.csv` (48 pattern rows → 15 distinct outputs, 12 sessions) **and** `narration_hits_v21b.csv` (15 rows) | identical hit set (verified set equality); existing citation correct |
| `narration_by_target_v21.csv` row values 716 / 15 / 12 | that file, exactly | correct as cited |
| ANSI 5 / 17 / 10 outputs and 32 outputs / 6 sessions | **only** `literal_ansi_by_target_v21b.csv` (`ESC_bracket_outputs=5`, `backslash_e_outputs=17`, `bare_sgr_outputs=10`, `outputs_any=32`, `sessions_any=6`) | tex cited nothing; citation added |
| `literal_ansi_by_target_v21.csv` | stores **occurrence** counts (ESC 170, `\e` 1035, bare SGR 223) plus 32 outputs / 6 sessions | cannot supply 5/17/10 |

So the narration citations were already correct; the ANSI per-encoding counts were not in any
cited file and now cite the `_v21b` table. Recomputing DECEIVE over `raw/deceive_runNN.jsonl`
independently gives ESC 5, `\e` 17, bare SGR 10, union 32 outputs in 6 runs — matching `_v21b`.

**v21 vs v21b disagreements (nothing stale; different definitions):**

1. `outputs_scanned`: `narration_by_target_v21.csv` 720/720/720/720/675/691/716;
   `narration_by_target_v21b.csv` and `literal_ansi_by_target_v21b.csv`
   580/560/600/617/576/605/714. Definition, not a stale number — see FIX 6.
2. ANSI encoding column: `_v21` gives occurrences per encoding, `_v21b` gives outputs and
   sessions per encoding. Both agree on 32 outputs / 6 sessions.
3. `_v21b` adds four encodings with zero counts everywhere (`esc_byte`, `\033`, `\x1b`,
   `\u001b`); `_v21` has a single `esc_byte_occurrences` column (0 for every target).
4. `narration_hits_v21b.csv` collapses the per-pattern rows to one row per output and adds a
   `prose_rule` boolean; the output/session set is identical to `_v21`.

No CSV was edited.

### FIX 6 — Table 15 "outputs scanned" — **DONE (definition stated; numbers already matched the cited file)**

Measured over `raw/*.jsonl` (20 runs × 37 rows = 740 rows per target):

| target | all rows | non-`exit` rows | non-exit timed-out | **non-exit, non-timeout** (v21) | **non-empty, non-timeout** (v21b) | non-empty incl. timeouts |
|---|---:|---:|---:|---:|---:|---:|
| ground truth | 740 | 720 | 0 | **720** | **580** | 580 |
| Cowrie | 740 | 720 | 0 | **720** | **560** | 560 |
| llm-honeypot | 740 | 720 | 0 | **720** | **600** | 600 |
| AdvancedshelLM | 740 | 720 | 0 | **720** | **617** | 617 |
| VelLMes | 740 | 720 | 45 | **675** | **576** | 618 |
| DECEIVE | 740 | 720 | 29 | **691** | **605** | 620 |
| Beelzebub | 740 | 720 | 4 | **716** | **714** | 714 |

* `narration_by_target_v21.csv` (the file Table 15 cites) uses **all non-`exit` rows minus
  `timed_out=true` rows**, empty outputs included: `analyze_stage4_v21.py:459`
  (`outputs_scanned = len([r for r in outputs if not r.get("timed_out")])`). Its numbers are
  exactly the current table's: 720/720/720/720/675/691/716. **No mismatch.**
* `narration_by_target_v21b.csv` and `literal_ansi_by_target_v21b.csv` use **non-empty
  `cleaned_output` and `timed_out=false`**: 580/560/600/617/576/605/714. The `_v21`/`_v21b`
  difference on Beelzebub (716 vs 714) is the two timed-out rows that still had text; on
  VelLMes and DECEIVE it is every timed-out row.

Change made: the column header now names the definition (stacked so the table still fits) and
the caption spells it out and points at `narration_by_target_v21b.csv` for the stricter count.
The table keeps the `_v21` numbers because it cites the `_v21` file.

### FIX 7 — "14 named phrases" — **PREMISE WRONG (no edit)**

`NARRATION_PATTERNS` in `harness/analyze_stage4_v21.py:112-142` contains exactly **14**
patterns: `first_person_intent`, `first_person_state`, `let_me`, `the_user_did`, `you_typed`,
`as_an_ai`, `output_didnt`, `consistent_with`, `previous_response`, `should_have`,
`real_terminal`, `apology`, `hedge`, `meta_correction`. The v21b re-run adds **none**: it calls
`v21.narration_hits(text)` (`harness/recheck_v21b_other.py:98`), and `recheck_v21b_other.py`
contains no `NARRATION*` symbol of its own (0 matches). The four kinds the tex lists
(first-person intent, "the user typed", "output didn't change", "in a real terminal", "as an
AI", apology, hedge) all exist under those names. The count and the listed kinds stand, so the
sentence was left alone.

Only nit, not changed: these are regular expressions, not fixed phrases, so "14 named patterns"
would be marginally more precise than "14 named phrases".

### FIX 8 — provenance claim — **DONE**

The old sentence attributed every v2.1 number to `harness/analyze_stage4_v21.py`, which is false
for the onset table, the rule grid, the 77/120 variant and the lag counts. All five names now in
the tex exist:

| name | exists | what it actually produces |
|---|---|---|
| `harness/analyze_stage4_v21.py` | yes | determinism variants (`:376`), narration, state checks, ANSI; `determinism_variants_v21.csv`, `narration_by_target_v21.csv`, `state_checks_v21.csv`, `state_by_target_v21.csv`, `literal_ansi_*_v21.csv` |
| `harness/recheck_v21b_det.py` | yes (untracked, new) | `determinism_grid_v21b.csv:449` — the 2,112-combination determinism grid |
| `harness/recheck_v21b_other.py` | yes (untracked, new) | `state_rules_v21b.csv:347`, `narration_by_target_v21b.csv:185`, `literal_ansi_by_target_v21b.csv:420` |
| `desync_onset_v21b.md` | yes (untracked, new) | the onset table and lag counts (hand-written read-only pass; no script in the repo writes it) |
| `state_rules_v21b.csv` | yes (untracked, new) | 40 rule combinations |

### FIX 9 — clone date — **DONE**

`docs/FACTS_CHECK.md:92-94`: the former `https://github.com/splunk/DECEIVE` "answers `301 Moved
Permanently` to" Cisco-Talos "(checked 2026-11-25); **on 2026-11-21 the splunk URL resolved
directly**, which is consistent with a repository transfer between those dates."
`docs/PATCH_NOTES.md:48-49` says the same. So on the clone date the repository was addressed as
`splunk/DECEIVE`, and the sentence now says so.

Residual, unchanged and still flagged in the tex: the clone *date* itself (21 November 2026) is
not recorded in `FACTS_CHECK` or `PATCH_NOTES`, and `FACTS_CHECK.md:77,125` keep the clone
commit UNVERIFIED (no `.git` in the local clone). The surrounding sentences still say so.

### FIX 10 — compile sentence — **DONE**

Removed from Limitations. The sentence now lives only here:

> The source compiles with tectonic 0.15.0 (XeTeX engine): exit 0, 0 errors, 0 overfull boxes,
> 0 undefined references or citations, 19 pages, PDF 139,551 bytes.

### FIX 11 — v2 claim ("six checks that compared listings against the ground truth's literal contents") — **DONE (the claim was false)**

v2 has **no state checks at all**. What v2 scored was *fidelity*: each command's output against
the ground-truth output for the same command, as a `difflib.SequenceMatcher().ratio()`
character-similarity (`harness/analyze_stage4.py:163-166`, used at `:370-371`), on ANSI-stripped
prefixes capped at 4,000 characters (`honeypot_report_v2.tex:300`), described in the v2
limitations as "a character-similarity proxy for fidelity and determinism"
(`honeypot_report_v2.tex:949`). There is no "six checks" anywhere in v2 and no listing-versus-
literal-contents comparison. The sentence now says v2 had no per-session state checks and that
its fidelity score was a character-similarity ratio, which is what the reviewer's six checks are
contrasted with.

### FIX 12 — exploratory 109/120 — **DONE**

New paragraph at `:1142` (end of §6.3, before §6.4), labelled exploratory and unpublished:

* 109/120 overall; shifted runs 21/60 → 51/60; unshifted 58/60 (`state_lagcorrected_v21b.md`
  totals table);
* nine checks still fail for substantive reasons: run 19 five, run 14 two, run 1 one, run 20 one
  (5+2+1+1 = 9, same file);
* independent reproduction with a different pairing method: `claims_audit_v21b.md` Part 7
  (forward search, all 20 per-run scores identical);
* "the published figure remains 79/120" stated explicitly.

---

## 4. Term grep requested

| term | hits in `report/honeypot_report_v2_1.tex` | lines |
|---|---:|---|
| `confirmed` | 1 | 957 ("neither is confirmed", determinism) |
| `one command` | 0 | — |
| `one-row` | 0 | — |
| `cascade from` | 0 | — (the label lives in `state_checks_v21.csv`, not in the report) |

`confirmed` at 957 is a determinism statement, not a claim about the artefact; no change made.

---

## 5. Final table

| Fix | Status | Evidence file:line |
|---|---|---|
| 1 overstated timeout | **done** | `raw/deceive_run05.jsonl` L26–L28; `raw/deceive_run13.jsonl` L1–L4; `desync_onset_v21b.md` unshifted list |
| 2 confusing sentence | **done** | `honeypot_report_v2_1.tex:1085-1086`; counts at `:1087-1093` |
| 3 dangling "that line" | **done** | `raw/deceive_runNN.jsonl` L26 (`perm_sudo_l`); cross-tab 4/7/6/3 = `claims_audit_v21b.md` Part 3.2 |
| 4 AdvancedshelLM run 6 | **done** | `raw/advshellm_run06.jsonl` L26–L28; `state_checks_v21.csv:32`; 0 timeouts in run 6 |
| 5 file names | **partly premise wrong** — narration citations already correct; ANSI counts only in `_v21b`, citation added | `literal_ansi_by_target_v21b.csv:2`; `literal_ansi_by_target_v21.csv:2`; `narration_hits_v21.csv` / `narration_hits_v21b.csv` |
| 6 outputs scanned | **done** — table matches its cited `_v21` file; header + caption now state the definition | `narration_by_target_v21.csv:3`; `analyze_stage4_v21.py:459`; `narration_by_target_v21b.csv:3`; `literal_ansi_by_target_v21b.csv:2` |
| 7 "14 named phrases" | **premise wrong** — exactly 14 patterns, no v21b additions | `analyze_stage4_v21.py:112-142`; `recheck_v21b_other.py:98` |
| 8 provenance | **done** | `honeypot_report_v2_1.tex:924,928`; `recheck_v21b_det.py:449`; `recheck_v21b_other.py:185,347,420` |
| 9 clone date | **done** (rename supported); clone date itself still unsourced | `docs/FACTS_CHECK.md:92-94`; `docs/PATCH_NOTES.md:48-49` |
| 10 compile sentence | **done** — moved here | `honeypot_report_v2_1.tex:1250` (sentence gone); compile result §1 above |
| 11 v2 claim | **done** — claim was false | `harness/analyze_stage4.py:163-166,370-371`; `honeypot_report_v2.tex:300,949` |
| 12 109/120 exploratory | **done** | `state_lagcorrected_v21b.md` totals; `claims_audit_v21b.md` Part 7 |

No item needs a decision from you. The only unevidenced item left in the touched passage is the
clone date in FIX 9, which the sentence already frames as UNVERIFIED for its commit.
