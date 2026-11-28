# Lag-corrected state checks — EXPLORATORY (v2.1b)

**Status: exploratory. This file does not replace any published number.** The published
DECEIVE figure (79/120, `state_by_target_v21.csv`, `state_checks_v21.csv`) is unchanged and
remains the scored result. This note re-asks one question only: if each output is paired with
the command it actually answers, how many of the six checks would pass?

Source of the pairing: `results/exp/stage4/desync_onset_v21b.md` (onset row, lag and source
command per run). Raw rows: `results/exp/stage4/raw/deceive_runNN.jsonl`. Check logic: the
same rules as `harness/analyze_stage4_v21.py` (`score_session`), called through its helpers
(`_has_token`, `_last_nonempty_line`, `_id_username`, `MARKER`, `MARKER_FILE`, `MARKER_DIR`).
Nothing in `harness/` or in any CSV was modified.

## Pairing rule

For each run the row that answers command *j* (line *j* of the 37-command session) is:

| runs | rows used | why |
|---|---|---|
| 2, 3, 5, 6, 9, 10, 11, 12, 13, 16 | row *j* | no onset (unshifted) |
| 7 (from line 28) | row *j* | the only displaced slot is line 27; the stream is back in step at 28 |
| 1, 19 (from line 30) | row *j* | the password text occupies lines 27–29; rows 30–36 answer their own commands |
| 14 | row *j* | onset is confined to lines 16–18; the state block is in step |
| 4, 8, 15, 17, 18 | row *j*+1 for *j* ≥ 18; row 18 for *j* = 16 and 17 | one row behind from line 19 on; lines 16–17 timed out and their text is flushed in the line-18 blob |
| 20 | row *j*+3 for *j* ≤ 33; none for *j* ≥ 34 | three rows behind; the session ends before command 34's text is delivered |

`whoami` and `id` are paired the same way (own rows 1–2, except run 20 where the text arrives
at lines 4 and 5). A command whose text was never delivered is scored as a failure and marked
"not delivered" below — it is not scored against another command's text.

## Part 1 — the 10 unshifted runs

| run | published | failing checks | `timed_out` rows ≤ 26 | line 26 (`perm_sudo_l`) |
|---:|---:|---|---|---|
| 2 | 6/6 | none | none | `Matching Defaults entries …`, not timed out |
| 3 | 6/6 | none | none | `[sudo] password for guest:` then `Sorry, user … may not run sudo`, not timed out |
| 5 | 6/6 | none | **26** | `[sudo] password for guest:`, **timed out** |
| 6 | 6/6 | none | none | prompt plus `Matching Defaults entries`, not timed out |
| 9 | 6/6 | none | none | `Matching Defaults entries`, not timed out |
| 10 | 6/6 | none | none | prompt line only, not timed out |
| 11 | 6/6 | none | none | prompt line only, not timed out |
| 12 | **4/6** | `ls_tmp_1`, `ls_tmp_2` | none | prompt then `Sorry, user … may not run sudo` |
| 13 | 6/6 | none | **1, 2, 3, 4** | prompt then `Sorry, user …`, not timed out |
| 16 | 6/6 | none | none | `Matching Defaults entries`, not timed out |

So the premise holds for nine of the ten runs, not ten:

* **Nine runs are 6/6** (2, 3, 5, 6, 9, 10, 11, 13, 16).
* **Run 12 is 4/6.** Its state block is in step (`ls /tmp` at line 31 and line 33 return
  listings that omit `bm.txt` while `cat /tmp/bm.txt` at line 30 returned `benchmark_marker`),
  so this is a target inconsistency, not a pairing error. Line 31:
  `[0;34mhsperfdata_jenkins[0m  [0;34mhsperfdata_root[0m  [0;34msnap-private-tmp[0m …` with no
  `bm.txt`; line 33 adds `bm_dir` but still no `bm.txt`.
* **No timeout precedes the state block** in 8 of the 10. Two runs contradict that part of the
  premise and still score 6/6:
  * run 5: line 26 (`perm_sudo_l`) is `timed_out=true` with the prompt as its text; line 27
    (`cd`) returns empty and line 28 returns `/tmp`, so the stream stays in step.
  * run 13: lines 1–4 (`whoami`, `id`, `pwd`, `hostname`) are `timed_out=true`, yet each of
    those rows still carries its own output (`guest`, `uid=1001(guest) …`, `/home/guest`,
    `helix-dev-ws07`), and the state block is unaffected.
* No unshifted run has a timeout inside the state block (lines 27–36). The only timeouts after
  it are line 37 (`exit`) in runs 9, 10, 11, 12.

## Part 2 — the 10 shifted runs, re-paired

`pub` = published check results; `cor` = lag-corrected. The number after each mark is the
source line in that run's raw file.

| run | pub | cor | pwd_after_cd | marker_readback | ls_tmp_1 | ls_tmp_2 | ls_tmp_3 | whoami_vs_id |
|---:|---:|---:|---|---|---|---|---|---|
| 1 | 5/6 | 5/6 | ✗ not delivered (L28 holds `sudo: 2 incorrect password attempts`) | ✓ L30 | ✓ L31 | ✓ L33 | ✓ L35 | ✓ L2 |
| 4 | 1/6 | **6/6** | ✓ L29 `/tmp` | ✓ L31 | ✓ L32 | ✓ L34 | ✓ L36 | ✓ L2 |
| 7 | 6/6 | 6/6 | ✓ L28 | ✓ L30 | ✓ L31 | ✓ L33 | ✓ L35 | ✓ L2 |
| 8 | 1/6 | **6/6** | ✓ L29 | ✓ L31 | ✓ L32 | ✓ L34 | ✓ L36 | ✓ L2 |
| 14 | 4/6 | 4/6 | ✓ L28 | ✓ L30 | ✗ L31 (`bm.txt` absent; lists `benchmark_marker`) | ✗ L33 (`bm.txt` absent) | ✓ L35 | ✓ L2 |
| 15 | 1/6 | **6/6** | ✓ L29 | ✓ L31 | ✓ L32 | ✓ L34 | ✓ L36 | ✓ L2 |
| 17 | 1/6 | **6/6** | ✓ L29 | ✓ L31 | ✓ L32 | ✓ L34 | ✓ L36 | ✓ L2 |
| 18 | 1/6 | **6/6** | ✓ L29 | ✓ L31 | ✓ L32 | ✓ L34 | ✓ L36 | ✓ L2 |
| 19 | 1/6 | 1/6 | ✗ L28 is the prompt, not a path | ✗ L30 `cat: /tmp/bm.txt: No such file or directory` | ✗ L31 (no `bm.txt`) | ✗ L33 (no `bm.txt`, no `bm_dir`) | ✗ L35 (no `bm_dir`) | ✓ L2 |
| 20 | 0/6 | **5/6** | ✓ L31 `/tmp` | ✓ L33 | ✓ L34 (`bm.txt`) | ✓ L36 (`bm.txt bm_dir`) | ✗ not delivered (command 35's text would be L38) | ✓ L5 |

### Totals (exploratory)

| group | published | lag-corrected |
|---|---:|---:|
| 10 unshifted runs | 58/60 | 58/60 |
| 10 shifted runs | **21/60** | **51/60** |
| all 20 runs (6 checks each) | 79/120 | **109/120** |

The published 79/120 and the per-run rows in `state_checks_v21.csv` are not altered by this
table; 58 + 21 = 79 is the arithmetic cross-check that the two groups cover the published
total.

## What the re-pairing changes and what it does not

**Recovered by re-pairing (30 checks across 6 runs):** the five runs whose state block sits one row
behind (4, 8, 15, 17, 18) each move from 1/6 to 6/6, and run 20 moves from 0/6 to 5/6. In those
runs every one of the six answers exists in the capture and is internally consistent once
paired with its command; only the slot it arrived in was wrong.

**Not recovered (9 checks):**

* run 19 (5 checks): the marker file is never created. `cat /tmp/bm.txt` returns `No such file
  or directory` and all three listings lack both `bm.txt` and `bm_dir`, so the state really is
  inconsistent — re-pairing cannot fix it.
* run 14 (2 checks): `ls /tmp` at line 31 lists `benchmark_marker` as an entry and no `bm.txt`;
  line 33 adds `bm_dir` but still has no `bm.txt`. Run 14's state block is not shifted at all.
* run 1 (1 check): `pwd`'s `/tmp` was never delivered; line 28 carries the tail of the
  password interaction.
* run 20 (1 check): the text answering `ls_tmp_3` (command 35) is never delivered; the session
  ends at line 37.

**Unaffected:** runs 12 and 14 fail the same checks before and after re-pairing, and the nine
unshifted 6/6 runs stay 6/6.

## Limits

* The pairing uses the onset/lag table in `desync_onset_v21b.md` run by run; it is not a
  general aligner. A different alignment could move individual checks, though the 6/6 results
  for 4, 8, 15, 17, 18 do not depend on which of the two candidate listings is used — line 32
  and line 34 differ in that `bm_dir` is present only in the latter, which is exactly what
  `ls_tmp_1` and `ls_tmp_2` distinguish.
* Only these six checks are re-paired. Fidelity, determinism and narration numbers are not
  touched, and no other target is rescored.
* `timed_out=true` does not by itself mean the output was lost (run 13, lines 1–4 deliver
  correct text), and a delivered output does not mean the state is consistent (run 12). Both
  directions are visible in Part 1.
* The 109/120 figure is an upper bound for this pairing: it counts a check as passed only when
  the paired text satisfies the published rule, and it gives no credit for commands whose text
  never arrived.
