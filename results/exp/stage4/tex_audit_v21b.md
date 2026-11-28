# v2.1 tex audit — `report/honeypot_report_v2_1.tex`

Branch `report-v2.1-recheck`. Read of the frozen `report/honeypot_report_v2.tex` only for the
package comparison; it was not modified.

**Files written by this audit:** `report/honeypot_report_v2_1.tex` (14 hunks, +14 lines:
1327 → 1341) and this file. No commits, no pushes, no changes to raw data, CSVs, or the frozen
v2 tex. The compiled PDF and the TeX installation live in the system temp directory, not in the
repository.

---

## 1. Compile status — COMPILED (tectonic 0.15.0)

| Step | Result |
|---|---|
| `pdflatex`, `xelatex`, `lualatex`, `latexmk`, `tectonic` on PATH | all MISSING |
| `pip install tectonic` | no such distribution (`No matching distribution found`) |
| `/c/texlive`, `C:\Program Files\MiKTeX` | not present |
| Network | reachable (pip index answered, GitHub release download HTTP 200) |
| Compiler used | `tectonic 0.15.0` (x86_64-pc-windows-msvc), 19,268,177-byte release zip unpacked to `%TEMP%\tectbin`, outside the repo |

Command (from a scratch copy of the tex, so no build artefacts land in the repo):

```
tectonic -X compile honeypot_report_v2_1.tex --keep-logs
```

| Metric | First successful compile | Final compile |
|---|---|---|
| Engine errors | 0 | **0** |
| Pages | 18 | **19** |
| Overfull `\hbox` | 20 | **0** |
| Underfull `\hbox` | 9 | **26** (loose lines only, see §6) |
| Undefined references / citations | 0 | **0** |
| Duplicate `\label` | 0 | **0** |
| `Overfull \vbox` | 0 | 0 |
| PDF | built | built, 137,574 bytes, 19 pages |

Tectonic resolves the standard `lm`, `lmtt`, `TS1` fonts and all ten packages from its bundle,
so every `\usepackage` in the preamble exists in a standard TeX Live set. The source is CRLF;
TeX accepts this (no isolated CR, see §3).

The 26 underfull warnings are all `badness`-only (over-stretched interword glue inside the
margin); none is an overflow. §6 records where they are and why they remain.

---

## 2. Errors found and fixed (old → new line numbers)

### 2.1 Fatal error

```
! Missing $ inserted.
<inserted text> $
l.1119 ...ate\_cd\_tmp} & 1 & \texttt{perm\_sudo_l}
```

`\texttt{perm\_sudo_l}` has an escaped first underscore and a **raw** second one, so TeX left
text mode for math. The same table had five more `ps_aux` cells with a raw underscore. Twelve
characters on nine lines were affected; TeX stops at the first, so the other eleven were found
with a static scan rather than one compile per error:

```
line 1119 col 51 '_'  :: \texttt{perm_sudo_l}     line 1123 col 37 '_' :: \texttt{ps_aux}
line 1119 col 56 '_'  :: \texttt{perm_sudo_l}     line 1124 col 37 '_' :: \texttt{ps_aux}
line 1120 col 36 '_'  :: \texttt{ps_aux}          line 1125 col 37 '_' :: \texttt{ps_aux}
line 1121 col 51 '_'  :: \texttt{perm_sudo_l}     line 1126 col 37 '_' :: \texttt{ps_aux}
line 1121 col 56 '_'  :: \texttt{perm_sudo_l}     line 1127 col 52 '_' :: \texttt{perm_sudo_l}
line 1122 col 36 '_'  :: \texttt{ps_aux}          line 1127 col 57 '_' :: \texttt{perm_sudo_l}
```

Fixed by escaping both underscores on all nine rows (hunk 11 below).

### 2.2 Every edit with old and new line numbers

Line numbers are physical lines in the file as it stood before this audit (1327 lines) and as it
stands now (1341 lines). "insert" means new lines added between the two old lines named.

| # | Old lines | New lines | Change | Reason |
|---|---|---|---|---|
| 1 | insert after 22 | **new 23–25** | `% Long unbreakable tokens …` (2 comment lines) + `\setlength{\emergencystretch}{3em}` | overfull lines pushed by long `\texttt` paths/hashes; lets TeX stretch instead of bleeding into the margin |
| 2 | 264 | **267** | `accounts/fireworks/models/glm-5p3-flash` → 3 × `\allowbreak{}` between path segments | overfull 27.35 pt |
| 3 | 315 | **318** | `results/exp/stage4/analysis\_followup.md` → `…stage4/\allowbreak{}analysis…` | overfull 32.22 pt |
| 4 | insert after 330 | **new 334** | `\setlength{\tabcolsep}{5pt}` before `tab:v1-ssh`'s `tabularx` | overfull 4.50 pt in alignment (8 columns) |
| 5 | 431 | **435** | `\_read\_until\_prompt\_settled` → `\_read\_until\_\allowbreak{}prompt\_settled` | overfull 28.23 pt |
| 6 | 569 | **573** | `\setlength{\tabcolsep}{4pt}` → `{3pt}` for `tab:s4-ssh` | table box 9.82 pt wider than `\textwidth` |
| 7 | 877 | **881** | `results/exp/lifetime\_control/beelzebub\_persistent/` → break after `lifetime\_control/` | overfull 92.19 pt |
| 8 | 1087–1088 | **1091–1095** | added the 4/7/6/3 sudo cross-tab sentence (§4f) | professor's item (f) was not in the tex |
| 9 | 1097 | **1104–1105** | added "Counting the two timeout-labelled rows as no evidence … gives 77/120" | professor's item (c), the 77 variant |
| 10 | 1102 | **1110–1111** | `24 rule combinations` → `40 rule combinations` + `(\texttt{state\_rules\_v21b.csv})` | stale count; the CSV has 40 combos (§7) |
| 11 | 1119–1127 | **1128–1136** | 12 raw `_` escaped (`perm\_sudo\_l`, `ps\_aux`) | the fatal error in §2.1 |
| 12 | 1143–1144 | **1152–1153** | added `5 outputs`, `17 outputs`, `10 outputs` per encoding | professor's item (d), per-form counts |
| 13 | 1173 | **1182** | `results/exp/stage4/determinism.csv` → break after `stage4/` | overfull 80.01 pt |
| 14 | 1236 | **1245–1250** | added low-recall note + compile statement to Limitations | professor's item (h) |

Only hunks 8–10, 12 and 14 change words. Hunks 1–7, 11 and 13 are typographic: no sentence,
number or claim is altered, and where a `\allowbreak{}` sits inside an identifier the rendered
text is unchanged unless the line actually breaks there.

---

## 3. Static checks (all pass on the final file)

| Check | Result |
|---|---|
| Balanced `{}` | final depth 0, no negative depth |
| `\begin`/`\end` per environment | balanced: 16 `table`, 9 `tabular`, 7 `tabularx`, 3 `itemize`, 1 each of `longtable`, `thebibliography`, `document`, `abstract`, `center`, `quote`, `enumerate` |
| `\ref`/`\eqref`/`\cite` keys | 33 labels, 33 references, 0 undefined; 12 `\bibitem`, 12 cited, none orphaned |
| Duplicate labels | none |
| Raw tab / CR / backspace / FF / ESC byte | 0 / 0 isolated (CRLF endings only) / 0 / 0 / 0 |
| Non-UTF-8 bytes | none (file decodes as UTF-8, 0 non-ASCII characters) |
| Tabular column count vs cells per row | 17 tables, all rows match their `tabular`/`tabularx`/`longtable` spec, `\multicolumn` spans expanded |
| `\texttt{}` with raw `_ % & # ^` | 0 remaining (12 fixed in §2.1) |
| `\e[` / `ESC[` literals | written as `\texttt{\textbackslash e[01;34m}`, `\texttt{ESC[01;34m}`, `\texttt{[0;34m}`, `\texttt{[38;5;33m}` — render as literal text, no control bytes (tex 1150–1158) |
| `\usepackage` set vs frozen v2 | identical lists: geometry, fontenc, inputenc, lmodern, booktabs, tabularx, longtable, array, enumitem, hyperref. Nothing added, nothing removed, no macro used before definition |

`microtype` was tested as a further remedy (it is in TeX Live and loads under XeTeX) and
**rejected**: at the chosen stretch it changed 7 → 6 overfull and left the 16 underfull untouched,
i.e. it bought nothing for a new preamble dependency. It is not in the file.

---

## 4. Part 2 — the professor's items, as they now stand in the tex

| Item | Verdict | Where (tex line) | What the tex says / what the source says |
|---|---|---|---|
| **a.** DECEIVE 0.509 vs 0.522, exit-row arithmetic, Beelzebub 0.594/0.605 caveat, "his exact rule UNVERIFIED" | **PASS** | 957–970, 983–996 | `\((36\times0.5086 + 1.0000)/37 = 0.5219\)`, which rounds to 0.522` (960); `His exact rule is therefore UNVERIFIED` (966). Source `determinism_variants_v21.csv`: deceive V0 0.5086, V12 0.5219, EXIT 1.0 ✔. Beelzebub caveat is stated as a magnitude — "moves Beelzebub by 0.011" (961) — the two endpoints 0.594 → 0.6049 are in the CSV and 0.594 is in `tab:s4-ssh`; **0.605 is not printed literally**. |
| **b.** Narration: 15 outputs / 12 sessions, run-6 example, precision wording, never "undercounted" | **PARTIAL** | 1004–1017, 1032–1038 | `A broader detector finds 15 outputs in 12 of the 20 Beelzebub sessions` (1004–1005) ✔ `narration_by_target_v21.csv` beelzebub = 15 / 12. Run-6 quote present (1006–1010). `It is precision-oriented and heuristic, not a classifier` (1016). No occurrence of "undercounted" anywhere. **The "16/13 broad" figure is NOT FOUND**: `narration_by_target_v21b.csv` also gives 15 / 12, and `narration_controls_loose_v21b.csv` holds a header only (8 bytes, 1 line, no rows). Nothing in the repo supports 16 / 13, so it is neither in the tex nor addable. |
| **c.** Six state checks, per-target table, 35/4/2, his 72/117/107, 117 not reproducible, lag-corrected 109/120 | **PASS** (after 2 additions) | table 1072–1077; 1082–1083; 1105; 1107–1113 | Table matches `state_by_target_v21.csv` row for row (GT 120, Cowrie 120, VelLMes 119, advshellm 116, Beelzebub 107, DECEIVE 79; per-check columns and 35/4/2 all equal). His numbers: `The reviewer reports 72/120 rather than 79/120` (1107) and `none reproduces his 72, 117 and 107 together` (1111–1112); `state_rules_v21b.csv` contains no row with DECEIVE 117, so "not reproducible" holds. **Added by this audit:** the 77 variant (1105), traced to `recheck_v21b.md:224` "79 (77 if timeouts are no evidence)". **109/120 is absent from the tex** and `grep 109` returns only three DOIs — correct, since it is exploratory and unpublished. |
| **d.** Visible ANSI: 5/1, 17/3, 10/2, total 32/6, literal text not 0x1b | **PASS** (after 1 addition) | 1150–1158 | Totals were already there: `finds 32 DECEIVE outputs in 6 of 20 sessions` (1150–1151). Per-form counts **added** (1152–1153) and re-derived from `literal_ansi_hits_v21.csv`: `ESC_bracket` 5 outputs / 1 session (run 2), `backslash_e` 17 / 3 (runs 4, 5, 9), `bare_sgr` 10 / 2 (runs 12, 19), union 32 / 6. Literal-text claim at 1156–1158: `no raw DECEIVE file contains a \texttt{0x1b} byte, and \texttt{ESC[} is the four ASCII characters`. |
| **e.** DECEIVE citation → Cisco-Talos, "formerly splunk/DECEIVE, redirects", no bare splunk/DECEIVE | **PASS** | 231–234, 1309–1313 | `\url{https://github.com/Cisco-Talos/DECEIVE}. Formerly \url{https://github.com/splunk/DECEIVE}, which redirects to the Cisco-Talos repository (checked 25 November 2026).` `grep splunk` returns exactly two hits, both inside those "formerly / redirects" notes (232, 1313). No bare citation remains. |
| **f.** Desync wording: lag 1–3 at onset, 0–3 at end, 10/20, timeout in the 3 rows before onset, 1/10 unshifted, sudo neither necessary nor sufficient, mechanism UNVERIFIED | **PASS** (after 1 addition) | 1087–1090, 1091–1094, 1096–1099, table 1128–1136, 1106 | `In 10 of DECEIVE's 20 runs` (1087) ✔; `in all 10 a row within the three before that onset had \texttt{timed\_out=true}` (1088–1089) ✔ `desync_onset_v21b.md` summary. End-of-session lags 0–3 are present as facts (five runs one row behind at 1096–1097; run 14 returns to synchrony = 0 at 1097; run 20 three rows behind at 1099). **Added:** `four of those runs shift and seven do not … six shift and three do not, so the prompt is neither necessary nor sufficient` (1092–1094) — exactly the 4/7/6/3 cross-tab in `desync_onset_v21b.md` ("Of those 11, 4 are followed by a shift … and 7 are not"; "the other 6 … no prompt on that line"). `The prompt-versus-queue mechanism is UNVERIFIED` (1106). **"1/10 unshifted runs with one timeout" is NOT FOUND** in any artefact (the md reports unshifted runs only as NOT FOUND, with no timeout column), so it is not in the tex. **No overstrong wording remains:** `grep` finds no "one command", no "cascade from the sudo prompt", no "one-row" claim and no "confirmed" claim; the only "one row" is `one row per run and check` in a table caption, and the only "confirmed" is `neither is confirmed`. |
| **g.** Unchanged v2 numbers still present and unaltered | **PASS** | 71, 554, 852–853, 696–700, 763–780, 76, 589 | 3,699 requests (71, 554) ✔; `$2.0173` (554, 852); `20,459,956` prompt tokens and `2,007,696` completion tokens (852–853) ✔; galah `0.100 (40/400)`, `0.0375 (15/400)`, `0.260 (95/366)`, `13` distinct `Server` values (696–699) ✔; 86 timed-out rows and 9/66/11 (763–780) ✔; medians `2.18--2.39` (76, 589) ✔. None of these lines was touched by any hunk. |
| **h.** Limitations: scripted checks, heuristic detector, rule differences, other-target desync low recall, compile status | **PASS** (after 1 addition) | 1163, 1168–1169, 1172, 1242, 1245–1250 | `The state checks are scripted, six per session` (1163); `phrase list with a prose heuristic: it is precision-oriented … recall is unknown` (1168–1169); `Where this section's counts differ from the reviewer's, the difference is recorded and left UNVERIFIED` (1172); `phrase list with a heuristic prose rule` (1242). **Added:** `a row that matches no signature is recorded as no onset rather than as synchronised; the same screen applied to another target would therefore be low-recall and is not a negative test` and `compiles without errors under Xe\TeX{} (tectonic 0.15.0)` (1245–1250). |

---

## 5. Part 3 — every number added in v2.1, against its source

| Number | Tex line | Source | Verdict |
|---|---|---|---|
| 0.5086 (V0) | 983 | `determinism_variants_v21.csv` deceive V0 | MATCH |
| 0.5242 (V1) | 984 | same, V1 | MATCH |
| 0.5182 (V2) | 985 | V2 | MATCH |
| 0.5194 (V3) | 986 | V3 | MATCH |
| 0.5167 (V4) | 987 | V4 | MATCH |
| 0.4799 (V5) | 988 | V5 | MATCH |
| 0.4771 (V6) | 989 | V6 | MATCH |
| 0.5748 (V7) | 990 | V7 | MATCH |
| 0.4751 (V8) | 991 | V8 | MATCH |
| 0.5086 (V9) | 992 | V9 | MATCH |
| 0.5083 (V10) | 993 | V10 | MATCH |
| 0.5086 (V11) | 994 | V11 | MATCH |
| 0.5219 (V12) | 995 | V12 | MATCH |
| 1.0000 (exit row alone) | 996 | EXIT | MATCH |
| (36×0.5086 + 1.0000)/37 = 0.5219 → 0.522 | 960 | recomputed: 19.3096/37 = 0.52188 | MATCH |
| "moves Beelzebub by 0.011" | 961 | 0.594 → 0.6049 = 0.0109 | MATCH |
| 0.5242 "0.002 from his value" | 962 | 0.5242 − 0.522 = 0.0022 | MATCH |
| "every other target … at most 0.004" | 962 | V0→V1 deltas: advshellm 0.0000, beelzebub +0.0042, cowrie 0.0000, vellmes −0.0009 | MATCH |
| "at most 0.0003" (masking/cap/ANSI/hostnames) | 963–965 | V9 0.5086, V10 0.5083, V11 0.5086 vs V0 0.5086 | MATCH |
| 0.4751 "without it" | 970 | V8 | MATCH |
| 15 outputs / 12 sessions | 1004–1005, 1038 | `narration_by_target_v21.csv` beelzebub 15 / 12 | MATCH |
| 720 / 675 / 691 / 716 scanned | 1032–1038 | same CSV `outputs_scanned` | MATCH |
| 120, 119, 116, 107, 79 | 1072–1077 | `state_by_target_v21.csv` | MATCH |
| per-check 20/19/18/17/16/12/13/11 columns | 1072–1077 | same CSV, six `*_passed` columns | MATCH |
| 35 cascade / 4 direct / 2 timeout | 1082–1083, 1077 | same CSV `fail_cascade/direct/timeout` | MATCH |
| 77/120 (timeouts as no evidence) | 1105 (added) | `recheck_v21b.md:224`; `state_rules_v21b.csv` `observed,fail,marker,*` | MATCH |
| 72 / 95 | 1107–1109 | `state_rules_v21b.csv` `desync_all6,fail,marker,*` = deceive 72, beelzebub 95 | MATCH |
| 40 rule combinations | 1110 (corrected from 24) | `state_rules_v21b.csv`: 40 rows, 40 distinct combinations | MATCH (24 was MISMATCH) |
| "no rule gives 117" | 1111–1112 | no row of `state_rules_v21b.csv` has deceive 117 | MATCH |
| 10 of 20 shifted runs | 1087 | `desync_onset_v21b.md` "Shifted runs: 10 — runs 1, 4, 7, 8, 14, 15, 17, 18, 19, 20" | MATCH |
| onset lags 1, 2, 3 and onset rows 27/18/4 | table 1128–1136 | same md per-run table | MATCH |
| 4/7/6/3 sudo cross-tab | 1092–1094 (added) | same md: 11 prompt runs → 4 shift / 7 not; 9 others → 6 shift / 3 not | MATCH |
| 32 outputs / 6 sessions | 1150–1151 | `literal_ansi_by_target_v21.csv` deceive 32 / 6; hits CSV union 32 / 6 | MATCH |
| ESC[ 5 / 1 | 1152 (added) | `literal_ansi_hits_v21.csv` form `ESC_bracket` | MATCH |
| \e[ 17 / 3 | 1153 (added) | form `backslash_e` | MATCH |
| bare 10 / 2 | 1153 (added) | form `bare_sgr` | MATCH |
| 0x1b byte count 0, `ESC[` = 45 53 43 5b | 1156–1158 | hits CSV `esc_byte_occurrences` = 0 for every target | MATCH |

No mismatch remains after hunk 10. The one number I changed (24 → 40) is argued in §7.

---

## 6. Underfull boxes — 26 remain, all loose lines, none overflowing

Every remaining warning is `Underfull \hbox (badness …) in paragraph/alignment`, i.e. a
justified line whose interword glue is stretched, with the text still inside the margin. They
cluster where a line must hold a long unbreakable identifier:

| Lines | Cause |
|---|---|
| 228–245 | 40-character commit hash `cce98f3d…` — deliberately not broken, so the neighbouring line is loose |
| 266–269, 269–279, 279–285, 312–320 | the `config.ini` / `analysis_followup.md` paths (shortened, but the surrounding prose still has to stretch) |
| 347, 428 | table cells in `tab:v1-ssh` and `tab:abac` |
| 416, 657 (×2), 689, 889 (×2), 976, 1025 | table captions ending in a long `\texttt` source path |
| 431–438, 876–883, 1201–1205 (×3) | the `\_read\_until\_prompt\_settled`, lifetime-control path and Findings bullet paragraphs |
| 1294–1298 (×3), 1312–1316 (×2), 1321–1324 | bibliography entries with `doi:`/`\url` strings |

Measured trade-off (same source, only the preamble value changed):

| `\emergencystretch` | overfull | underfull |
|---|---|---|
| 0 | 17 | 16 |
| 0.5em | 12 | 16 |
| 1em | 7 | 16 |
| 2em | 3 | 20 |
| **3em (chosen)** | **0** | **26** |

I chose the setting with zero overfull boxes, because an overfull box prints text outside the
margin while an underfull one only spaces a line loosely. The alternative — `\raggedright` for
captions and the bibliography, or breaking every identifier mid-name — would reach zero warnings
but change the document's appearance and make paths harder to copy. **Not done here.**

---

## 7. Open items (not fixable from the repository as it stands)

1. **Narration "16 outputs / 13 sessions (broad)"** — NOT FOUND. `narration_by_target_v21.csv`
   and    `narration_by_target_v21b.csv` both give 15 / 12 and `narration_controls_loose_v21b.csv`
   holds a header only (8 bytes, 1 line, no rows). Either the loose-control run was never written or the figure came
   from a run not in this tree. The tex states 15 / 12 only.
2. **"1 of 10 unshifted runs has a timeout in the 3 rows before onset"** — NOT FOUND.
   `desync_onset_v21b.md` records the ten unshifted runs as "no attributable onset" and prints no
   timeout column for them. Re-deriving it needs a new read of the raw files, which this audit
   did not do; the tex therefore omits the comparison and says only that the prompt is neither
   necessary nor sufficient.
3. **`recheck_v21b.md:227` is internally inconsistent.** It says "Rules tested: 24 combinations"
   but then enumerates five cascade policies × 2 timeout × 2 listing × 2 pwd = 40, and
   `state_rules_v21b.csv` has 40 rows (40 distinct combinations). The tex now says 40 and cites
   the CSV. The markdown note still says 24 — I did not edit it, since only the tex and this
   audit file were in scope.
4. **`state_rules_v21b.csv` contains no row that yields DECEIVE 79.** Its `observed,fail,marker`
   rows give 77, and `observed,pass,marker` gives 81; 79 comes from `state_by_target_v21.csv`
   (35 + 4 + 2 failures out of 120), which is the file the state table actually cites. The two
   files therefore disagree by the two timeout rows under a same-named policy value. Nothing was
   changed; the tex cites the table's own source and states the 77 variant separately.
5. **0.605 is not printed literally** in the determinism paragraph; it says "moves Beelzebub by
   0.011". If he wants the two endpoints spelled out, add `0.594 → 0.6049`.
6. **VelLMes 117 and DECEIVE 72 remain unreproducible** (no rule in the 40 gives 117; the 72 rule
   puts Beelzebub at 95). Unchanged from the earlier audit; the tex states both as UNVERIFIED.
7. **109/120 (lag-corrected)** is absent from the tex and should stay absent: it is exploratory,
   appears in no report version, and `grep 109` in the tex returns only three DOIs.

---

## 8. Summary

The document had one real LaTeX error — a raw underscore inside `\texttt` in
`tab:v21-onset`, which halted the build at old line 1119 — plus eleven more of the same kind on
neighbouring rows. With those fixed, tectonic 0.15.0 builds it cleanly: **0 errors, 0 overfull
boxes, 0 undefined references, 19 pages**. Twenty overfull boxes were removed by a stretch
allowance, five in-path break points and two `\tabcolsep` reductions; 26 loose-line underfull
warnings remain and are itemised, because removing them would mean ragged-right captions or
breaking identifiers. Given a compiler was absent from the machine, I installed tectonic into the
temp directory (not the repo) rather than reporting UNCOMPILED.

Of the professor's eight items, five were already satisfied (a, e, g fully; c and d in part).
Three additions close the gaps: the 4/7/6/3 sudo cross-tab (f), the per-encoding ANSI counts
(d) and the 77 variant (c), plus two limitation sentences (h). One number was wrong and is now
corrected: 24 → 40 rule combinations, against a CSV that holds 40. Two figures he asked for —
narration 16/13 and the 1-in-10 unshifted timeout — do not exist anywhere in the tree and are
listed as open rather than invented.
