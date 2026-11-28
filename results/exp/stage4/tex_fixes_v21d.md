# v2.1 tex fixes, round d (lag wording, paragraph split, citations, strength, unsourced date)

Branch `report-v2.1-recheck`. Scope actually touched: two files.

* **Edited:** `report/honeypot_report_v2_1.tex` (1341 → 1359 lines).
* **Written:** this file, `results/exp/stage4/tex_fixes_v21d.md`.
* **Not touched:** raw data, any CSV, `docs/FACTS_CHECK.md`, `docs/PATCH_NOTES.md`,
  `report/honeypot_report_v2.tex`, `results/exp/stage4/tex_fixes_v21c.md`.
* No commit, no push.

Table numbering in this file follows the compiled PDF, i.e. the `longtable` at
tex:176 counts as a table. That gives Table 13 = `tab:v21-files` (tex:931),
Table 15 = `tab:v21-narr` (tex:1022), Table 17 = `tab:v21-onset` (tex:1131), the
same numbering the fix list uses.

---

## 1. Recompile result

| Item | Value |
|------|-------|
| Engine | tectonic 0.15.0, `tectonic -X compile honeypot_report_v2_1.tex --keep-logs` |
| Build directory | `%TEMP%\texbuild21d` (outside the repo; no artefacts in the working tree) |
| Exit status | **0** |
| TeX errors (`^! `) | **0** |
| Overfull boxes | **0** |
| Underfull boxes | 30 (v2.1c had 31; paragraph reshaping removed one, none added) |
| Undefined references / citations | **0** |
| Pages | **19** |
| PDF | 139,700 bytes (v2.1c: 139,551) |

---

## 2. Edit list (old → new line numbers)

Old numbering = the 1341-line file before this round. New numbering = the current
1359-line file. Δ is the net line change.

| # | Fix | Old lines | New lines | Δ | Edit |
|--:|-----|-----------|-----------|--:|------|
| E1 | FIX 5 | 234 | 234 | 0 | Dropped the clone date and the `(then still addressed as \texttt{splunk/DECEIVE})` parenthetical: "A fresh clone of the upstream repository has HEAD". |
| E2 | FIX 4 (S6.1) | 967–970 | 967–973 | +3 | Replaced "Whichever rule is used, the gap is a denominator choice, not a defect in the masking …" with wording that only claims consistency. |
| E3 | FIX 1 + FIX 2 (S6.3) | 1086–1112 | 1089–1129 | +14 | Split one 27-line paragraph into four, rewrote the lag sentence, kept every number. |
| E4 | FIX 4 (S6.5) | 1172–1173 | 1189–1191 | +1 | "is a denominator choice" → "is consistent with a denominator choice and his exact rule remains UNVERIFIED". |

Total: +18 lines (1341 → 1359). Line 1085 is unchanged, which is why E3 starts at
new 1089 (old 1086 + 3 from E2) rather than at 1085.

Within E3, FIX 1's target sentence moved from old **1099–1100** to new **1107–1109**.

---

## 3. FIX 1 — lag wording in Section 6.3

**Verify.** `results/exp/stage4/desync_onset_v21b.md:82` is the table "Shifted runs
where the lag changes mid-session":

* runs 4, 8, 15, 17, 18: `desync_onset_v21b.md:87-91` — "18→2, 19→1, then 1 to
  line 36" (each row's note: "sustained one-row lag after the backlog row").
* run 14: `desync_onset_v21b.md:93` — "18→2, then 0 from line 19".
* Why onset lag is 2 and not 1: `desync_onset_v21b.md:129-133` — the `w` row at
  line 18 contains the `ps aux` output (line 16) *followed by* the `cpuinfo`
  output (line 17), and both of those rows are `timed_out=true` with 8 and 29
  bytes. Raw: `results/exp/stage4/raw/deceive_run04.jsonl` L16 (8 bytes,
  `ps aux\r\n`), L17 (29 bytes, `cat /proc/cpuinfo | head -5\r\n`), L18
  (128,521 bytes ending in the cpuinfo tail).

So the old sentence ("five then stay one row behind to the end of the session")
was wrong at the onset row for all five runs, and the premise holds.

**Edit.** tex new 1107–1109:

> `\texttt{cpuinfo}) as one blob; in five of those six the lag is 2 at onset and 1`
> `to the end of the session, and run~14 carries lag~2 at onset and 0 from`
> `line~19.`

**No remaining uniform-one-row claim.** Term grep over the whole tex:

| Term | Hits (old file) | Hits (new file) |
|------|-----------------|-----------------|
| `one row` | 2 — 944 (`one row per run and check`, describing `state_checks_v21.csv`) and 1099 (the lag sentence, removed) | **1** — 944 only, and it is about the state-check table, not lag |
| `one command` | 0 | 0 |
| `one-row` | 0 | 0 |

New tex 1105 ("and the lag for each of the 10 runs"), 1135 (Table 17 caption, "lag
is the row distance to that command") and 1159 (re-pairing) make no uniformity
claim; Table 17 itself lists lags 1, 2 and 3.

---

## 4. FIX 2 — paragraph split in Section 6.3

**Verify.** Old 1085–1112 was a single paragraph carrying three separate topics:
DECEIVE onset evidence, the AdvancedshelLM run 6 confirmation, and the scoring
counts. The numbers are unchanged; the split is:

| New lines | Content |
|-----------|---------|
| 1085–1089 | control statement (unchanged text from old 1085–1086) |
| 1091–1102 | **(a)** DECEIVE onset evidence: 10/20 runs, timeout within the three prior rows, onset−1 in nine runs, run 20 at onset−2/−3, no prompt-only onset, runs 5 and 13 timeouts without shift, line 26 cross-tab 11 = 4 shift + 7 no, 9 without = 6 + 3 |
| 1104–1110 | **(a)** Table 17 description, including the corrected lag wording (FIX 1) |
| 1112–1120 | **(b)** AdvancedshelLM run 6: `advshellm_run06.jsonl` L26–L28, `state_checks_v21.csv` line 32, no timeout in the run, "confirmed there and not established for DECEIVE", prompt-versus-queue UNVERIFIED |
| 1122–1129 | **(c)** scoring: 35/41 cascade, four direct, two timeouts, 77/120, reviewer 72/120 vs 79/120, session-level rule → 72 but Beelzebub 95/120 vs 107, 40 rule combinations, 72/117/107, both UNVERIFIED |

Number audit of the rewritten region — every value from old 1085–1112 is present
exactly once, and no new value was introduced: 10, 20, three, 10 (all), −1, nine,
20, −2, −3, 5, 13, 20, 26, 11, four, seven, nine, six, three, 10 (no onset), 17 (line
18), 18, five, 2, 1, 14, 2, 0, 19, 1, 7, 19, 27, 20, 4, 35, 41, four, two, 77/120,
72/120, 79/120, 72, 95/120, 107, 40, 72, 117, 107.

**Table 17 position and references.** `tab:v21-onset` still sits immediately after
the 6.3 prose and before the exploratory re-pairing paragraph (environment now at
tex:1131–1157, old 1114–1140). The table source is byte-for-byte unchanged — 27
lines, shifted down by the 17 lines added above it — and the caption's `Source:`
line, rows and `\label` are untouched. Its `\ref` moved with the text (new 1104, old 1096)
and resolves: 0 undefined references in the log, and the PDF still numbers it
Table 17.

---

## 5. FIX 3 — which files actually hold 15 outputs in 12 sessions

**PREMISE WRONG.** No edit. The v21 files hold exactly the same numbers as the
`_v21b` files, so there is nothing to re-cite and no CSV was touched.

Counts, parsed with a real CSV reader (the v21 hits file has embedded newlines, so
line-based counting overstates its rows):

| File | Data rows | Distinct (target, run, cmd_id) = outputs | Distinct (target, run) = sessions |
|------|----------:|----------------------------------------:|---------------------------------:|
| `results/exp/stage4/narration_hits_v21.csv` | 48 (one per matched pattern) | **15** | **12** |
| `results/exp/stage4/narration_hits_v21b.csv` | 15 (one per output) | **15** | **12** |
| `results/exp/stage4/narration_by_target_v21.csv:3` | beelzebub: 716 scanned, `15,12` | 15 | 12 |
| `results/exp/stage4/narration_by_target_v21b.csv:3` | beelzebub: 714 scanned, `15,12` | 15 | 12 |

The two hits files hold the *same* 15 `(run, cmd_id)` keys — runs 1, 6, 7, 10, 11,
12, 14, 16, 17, 18, 19, 20 — so 15 outputs in 12 sessions in both. The only
difference is row granularity (48 pattern rows vs 15 output rows) and the preview
column width (`first_200_chars` vs `first_300`).

**Section 6.2 and Table 15 already cite a file that holds 15/12**
(`narration_by_target_v21.csv`), so the citation is correct as it stands.

**Table 13 (`tab:v21-files`, tex:931) stays accurate** after the edits — it was not
touched, and both descriptions match the files:

* `narration_hits_v21.csv` — "every narration hit with its first 200 characters":
  the file has a `first_200_chars` column, and its 48 rows cover every pattern hit.
* `narration_by_target_v21.csv` — "outputs and sessions flagged per target": the
  file's columns are `narration_outputs` and `narration_sessions`, = 15 and 12.

**Residual, flagged not edited (outside FIX 3):** tex:1013 says "the full string is
in `narration_hits_v21.csv`", but that column holds 202 characters (200 plus the
ellipsis) — it is a truncated preview, which is what Table 13 says and what the tex
quotation itself implies with `\ldots`. The quote as printed is inside the stored
202 characters. Wording change if wanted: "the first 200 characters are in
`narration_hits_v21.csv`".

---

## 6. FIX 4 — "not a defect" overstatement (Section 6.1) and Section 6.5

**Verify.** The old sentence claimed the gap is a denominator choice "not a defect in
the masking …", i.e. it asserted the reviewer's rule. The evidence supports only the
narrower statement:

* `results/exp/stage4/determinism_variants_v21.csv:26` (deceive, V12, keep the
  `exit` control row) = **0.5219**, and (36×0.5086 + 1.0000)/37 = 0.5219 → 0.522.
  So the exit-row rule reproduces his number *arithmetically*.
* Every other family of choices moves deceive by ≤ 0.0003:
  V9 no ANSI stripping `:23` = 0.5086, V11 hostnames from prompts `:25` = 0.5086,
  V10 20,000-char cap `:24` = 0.5083 (0.0003 from V0 `:14` = 0.5086).
* But V12 also moves Beelzebub by 0.011 (tex Table 13 rows), which contradicts his
  own statement about the other targets, and dropping censored rows gives 0.5242,
  not 0.522 — so his exact rule remains unverified. The old wording asserted more
  than this.

**Edit E2**, new tex 967–973:

> the gap between his 0.522 and the published 0.509 is **consistent with** a
> denominator choice: the `exit`-row rule reproduces 0.522 arithmetically, and no
> variant of the masking, the prefix cap, the ANSI stripping or the hostname set
> moves the value by more than 0.0003 (Table 13), so none of them can account for
> it. **His exact rule is still UNVERIFIED.** Masking is the one choice that matters
> materially: without it the value is 0.4751.

**Edit E4**, new tex 1189–1191 (Section 6.5):

> The DECEIVE determinism difference is **consistent with** a denominator choice and
> **his exact rule remains UNVERIFIED**, so the number a reader quotes must come with
> its definition.

Both sentences now state the same strength; neither claims the rule.

---

## 7. FIX 5 — unsourced clone date (Section 2.2)

**Premise holds: the date is not recorded, so it was removed and is listed here as
unsourced.**

Searches run over `docs/`, `README.md`, `CHANGELOG.md` and the stage-4 notes for
`21 November`, `2026-11-21`, `21 Nov`, and case-insensitive `clone`:

| Hit | What it actually records |
|-----|--------------------------|
| `docs/FACTS_CHECK.md:93-94` | `https://github.com/splunk/DECEIVE` answers 301 to Cisco-Talos (checked 2026-11-25); **"on 2026-11-21 the splunk URL resolved directly"** — a URL check on that date, not a clone |
| `docs/PATCH_NOTES.md:47-48` | "Upstream … formerly `splunk/DECEIVE`" — the name, undated |
| `docs/STAGE4_NOTES.md:294` | the first 20-run pass window `2026-11-21T20:55Z .. 2026-11-22T03:12Z` — a run, not a clone |
| `docs/PATCH_NOTES.md:15-17` | "the exact commit hashes of the third-party repositories at clone time were not recorded. The clone date window was **October 31 – November 2, 2026**." |

Nothing records *when the fresh verification clone was made*. The only recorded
clone window (`PATCH_NOTES.md:15-17`) is for the working clones (31 Oct – 2 Nov
2026), a different thing from the fresh clone used to read upstream HEAD, so it
cannot be borrowed to date the 21 November claim.

Net result: the naming at that date **is** supported (`FACTS_CHECK.md:93-94`), the
**clone date is not**. Following the instruction, the date and the parenthetical were
removed together, because the parenthetical's "then" referred to the deleted date.
The upstream name is not lost: tex:232 still says "formerly `splunk/DECEIVE`, which
now answers a permanent redirect to the Cisco-Talos location; checked 25 November
2026".

**Edit E1**, new tex 233–234:

> Cisco-Talos location; checked 25 November 2026). A fresh clone of
> the upstream repository **has HEAD** `cce98f3dcd9de74f32f683998e95aa19b795724e`
> (2026-05-13, MIT licence).

Residual UNVERIFIED, unchanged and still in the tex: the HEAD hash itself is read
from the fresh clone, whose date is unknown, and the surrounding text already says
the exact clone commit stays UNVERIFIED (no `.git` in the local clone).

---

## 8. Final status

| Fix | Status | Evidence file:line |
|-----|--------|--------------------|
| 1 — lag wording (lag 2 at onset, then 1; run 14 → 0) | **done** | `results/exp/stage4/desync_onset_v21b.md:82,87-91,93,129-133`; `results/exp/stage4/raw/deceive_run04.jsonl` L16–L19; outcome at tex:1107–1109 |
| 2 — split the 6.3 paragraph into (a) onset, (b) run 6, (c) scoring | **done** | tex:1085–1129 (old 1085–1112); Table 17 at tex:1131–1157, `\ref` at tex:1104, 0 undefined refs |
| 3 — cite the file that really holds 15 outputs in 12 sessions | **premise wrong**, no edit | `narration_by_target_v21.csv:3` = `716,15,12`; `narration_by_target_v21b.csv:3` = `714,15,12`; both hits files 15 distinct outputs / 12 runs |
| 4 — soften "not a defect", same in 6.5 | **done** | `determinism_variants_v21.csv:14,23,24,25,26`; tex:967–973 and tex:1189–1191 |
| 5 — remove the unsourced clone date | **done** (date unsourced) | `docs/PATCH_NOTES.md:15-17` (only recorded clone window is 31 Oct – 2 Nov 2026); `docs/FACTS_CHECK.md:93-94` (URL check, not a clone); tex:233–234 |

No item needed your decision; one residual wording point is offered in §5 ("the full
string is in `narration_hits_v21.csv`") and one residual UNVERIFIED item stands in §7
(the date of the verification clone).

## 9. Limits of this check

* Only the four itemised passages were changed; the rest of the tex is untouched
  and its other claims were not re-audited here (that is `tex_audit_v21b.md` and
  `claims_audit_v21b.md`).
* "Lag" is a row offset from signature matching (`desync_onset_v21b.md`, method
  section); rows with empty or ambiguous output are excluded there, not classified.
* The compile was run on a copy outside the repo; the PDF and logs stay in
  `%TEMP%\texbuild21d`.
