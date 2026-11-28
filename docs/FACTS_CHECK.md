# FACTS_CHECK.md
# Verification of Benchmark Data and Environment State

## a) Per-Target Accounting and Timeouts

### SSH Targets (5 runs x 37 commands = 185 rows in raw JSONL; 5 exit rows excluded by analyzer leaving 180 scored commands)

- **advshellm**: 185 rows; timeouts per run [0, 0, 0, 0, 0], total 0.
- **beelzebub**: 185 rows; scored timeouts [4, 2, 2, 4, 4], total 16; all raw rows [5, 2, 2, 4, 4], total 17 because run 1 `exit` timed out.
- **cowrie**: 185 rows; timeouts per run [0, 0, 0, 0, 0], total 0.
- **deceive**: 185 rows; timeouts per run [2, 0, 1, 2, 0], total 5.
- **groundtruth_ssh**: 185 rows; timeouts per run [0, 0, 0, 0, 0], total 0.
- **llmhoneypot**: 185 rows; timeouts per run [0, 0, 0, 0, 0], total 0.
- **vellmes**: 185 rows; timeouts per run [2, 2, 1, 2, 2], total 9.

### HTTP Targets (5 runs x 20 requests = 100 rows in raw JSONL)

- **galah**: 100 rows; timeouts per run [1, 1, 0, 0, 1], total 3.
- **groundtruth_http**: 100 rows; timeouts per run [0, 0, 0, 0, 0], total 0.

### Timed-out Commands

Source: `results/raw/*.jsonl`, field `timed_out == True`.

| Target | Command ID | Runs timed out | Runs |
|---|---|---:|---|
| beelzebub | exit | 1 | 1 |
| beelzebub | id | 1 | 4 |
| beelzebub | os_release | 1 | 4 |
| beelzebub | passwd | 1 | 5 |
| beelzebub | state_cat_marker | 3 | 1, 3, 5 |
| beelzebub | state_echo_marker | 3 | 1, 4, 5 |
| beelzebub | state_ls_tmp_3 | 3 | 1, 4, 5 |
| beelzebub | state_rm_marker | 2 | 2, 3 |
| beelzebub | state_rmdir_bm_dir | 1 | 1 |
| beelzebub | whoami | 1 | 2 |
| deceive | cpuinfo | 2 | 1, 4 |
| deceive | perm_sudo_l | 1 | 3 |
| deceive | ps_aux | 2 | 1, 4 |
| vellmes | env | 4 | 1, 2, 4, 5 |
| vellmes | ps_aux | 5 | 1, 2, 3, 4, 5 |

HTTP request timeouts for Galah were `/server-status` in run 1 and
`/favicon.ico` in runs 2 and 5.

## b) DECEIVE State Checks and Coinciding Timeouts

DECEIVE failed state checks in runs 1 and 4 for the `pwd`, marker-read, and
temporary-file/directory listing checks. Runs 2, 3, and 5 passed all six
checks. Timeout commands were run 1: `ps_aux`, `cpuinfo`; run 2: none; run 3:
`perm_sudo_l`; run 4: `ps_aux`, `cpuinfo`; run 5: none. Any causal link is
UNVERIFIED.

## c) File Existence Audit

| Path / Pattern | Exists? | Details |
|---|---|---|
| `results/honeybee/summary_rescored.json` | Yes | Present |
| `results/honeybee_max16384/` | No | Absent; TODO |
| `results/honeybee/UI_TESTS.md` | No | Absent |
| `harness/api_probe.py` | Yes | Present |
| `results_pilot/summary.md` | Yes | Present |
| `scripts/copy_logs.ps1` | Yes | Present |
| `patches/*.patch` | Yes | HoneyBee and VelLMes patch files present |
| `tests/` | Yes | Present |

Nine galah HTTP raw bodies are deliberately not tracked; their paths, sizes and SHA-256
values are recorded in `docs/WITHHELD_FILES.md`. Their absence here is the reason the
galah rows in `results/summary.md` cannot be recomputed from this repository alone.

## d) Third-Party Clone Commit Hashes and Licenses

| Clone | Has `.git` | Commit | License |
|---|---|---|---|
| `honeybee` | Yes | `dbf62c42604eeae2cfbfd4d36b99bef65555c303` | LICENSE = Apache-2.0 (verified by reading the file) |
| `VelLMes-AI-Deception-Framework` | Yes | `192fa5084df84b38a16f6581939fd3143c350181` | LICENSE = GPL-**2.0** (verified by reading the file; an earlier revision of this row said GPL-3.0, which was wrong) |
| `DECEIVE` | No | UNVERIFIED (no `.git`; nearest upstream revision `cce98f3`, 2026-05-13) | LICENSE = MIT (verified by reading the file and against the upstream `DECEIVE` `LICENSE`, identical text; an earlier revision of this row said Apache-2.0, which was wrong) |
| `beelzebub` | No | UNVERIFIED | LICENSE = GPL-3.0 (verified by reading the file) |
| `shelLM` | No | UNVERIFIED | LICENSE = CC BY-NC-SA 4.0, NonCommercial (verified by reading the file) |
| `galah` | No | UNVERIFIED | LICENSE = Apache-2.0 (verified by reading the file) |
| `llm-honeypot` | No | UNVERIFIED | no licence file found; no upstream source code is redistributed, but `docker/llmhoneypot.cowrie.cfg` is derived from its `configs/cowrie.cfg` (recorded in `THIRD_PARTY_NOTICES.md`) |
| `cowrie-base` | No | UNVERIFIED; pinned v2.6.1 in docs | `LICENSE.rst` = BSD-3-Clause (Cowrie's 3-clause BSD text, "Copyright (c) 2009-2024 Upi Tamminen, Michel Oosterhof") |
| `cowrie-peek` | No | UNVERIFIED | no licence file found; used as a read-only overlay, not redistributed |

Licence texts are copied verbatim into `LICENSES/`; see `THIRD_PARTY_NOTICES.md` for the
per-tool table, upstream URLs and which tools were modified.

Beelzebub upstream URL, checked 2026-11-22: `https://github.com/beelzebub-labs/beelzebub`
is canonical; `https://github.com/mariocandela/beelzebub` resolves but redirects there
(HTTP 200 after redirect).

DECEIVE upstream URL: `https://github.com/Cisco-Talos/DECEIVE`. The former
`https://github.com/splunk/DECEIVE` answers `301 Moved Permanently` to it (checked
2026-11-25); on 2026-11-21 the splunk URL resolved directly, which is consistent with a
repository transfer between those dates. `https://github.com/coverflex-tech/DECEIVE`
returns "Repository not found". The upstream repository tracks
`SSH/config.ini.TEMPLATE`, not `SSH/config.ini`.

## e) Verified mismatches and source distinctions

- SSH and HTTP metrics in `results/summary.md` match the final raw-data
  accounting. `summary.csv` reports mean latency and all-comparable fidelity;
  the Markdown report uses median latency and shared fidelity.
- Beelzebub's scored timeout total is 16. The raw total is 17 because the run 1
  `exit` control row timed out; `exit` is excluded from the scored 180.
- Pilot DECEIVE reports 13 timeouts in `results_pilot/summary.md`; the pilot
  raw files contain 14, while `results_pilot/ssh_commands_long.csv` contains
  17. These are different source/accounting views; the cause is UNVERIFIED.

## f) DECEIVE output-cap evidence (read-only)

- `DECEIVE/SSH/config.ini` line 61: `temperature = 0.2`; line 67:
  `trimmer_max_tokens = 64000` (a history trimmer, not an output cap).
- `DECEIVE/SSH/ssh_server.py` line 429: `ChatOpenAI(**kwargs)` is constructed
  from model, temperature, api_key and tiktoken model name (lines 421-428) with
  no `max_tokens` argument, so replies are uncapped per request.
- Consequence in the data: the published batch has 2 oversized DECEIVE outputs
  (max 135,108 characters); Stage 4 has 6 (max 142,810 characters) and six
  requests that reach the 65,536-token model ceiling
  (`results/exp/stage4/analysis.md`, `analysis_timeouts.md`).

## g) Final UNVERIFIED list

1. DECEIVE clone commit (no `.git` in the local clone; nearest upstream
   revision `cce98f3`, 2026-05-13).
2. Which of the two DECEIVE `config.ini` files ran either batch (both name the
   same model and temperature).
3. Whether the built Beelzebub binary was identical between `final-batch-v1`
   and Stage 4 (the YAML files are identical).
4. Cause of the Beelzebub difference between the batches and of the rising
   latency in the single-container control (confounds: ceiling generations,
   time of day, n=10).
5. Why prompt mode returned less than quiet mode for the 33 quiet-check pairs
   (of 288) beyond the noise floor.
6. Whether the VelLMes target-side replies (capped 800-token answers produced
   in 4.5-7.8 s) are held or dropped inside the target; no container-side log
   was recorded.
7. Whether residual A-vs-B differences in the Stage 2 validation are artefacts
   or ordinary model variation.
8. Whether galah's write-time masking changes any published baseline count
   (the baseline galah bodies are withheld, so their counts cannot be
   recomputed from the repository).

## h) v2.1 re-analysis (2026-11-25)

All numbers below come from `harness/analyze_stage4_v21.py`, run against the
published raw files. Nothing under `results/exp/stage4/raw*` was modified and no
v2 output file was overwritten; every table has a `_v21` CSV.

### h.1 Masked determinism, DECEIVE (source: `results/exp/stage4/determinism_variants_v21.csv`)

| Variant | Definition | DECEIVE |
|---|---|---:|
| V0 | published: masked, 4,000-char cap, pairwise, all rows | 0.5086 |
| V1 | drop timed-out rows | 0.5242 |
| V2 | drop empty outputs | 0.5182 |
| V3 | drop timed-out and empty rows | 0.5194 |
| V4 | pooled pairs, timeouts dropped | 0.5167 |
| V5 | listwise: drop any command with a timeout | 0.4799 |
| V6 | median of per-command means | 0.4771 |
| V7 | each run against run 1 | 0.5748 |
| V8 | no masking | 0.4751 |
| V9 | no ANSI stripping | 0.5086 |
| V10 | 20,000-character cap for long outputs | 0.5083 |
| V11 | hostnames also from prompts | 0.5086 |
| V12 | keep the `exit` control row | 0.5219 |
| EXIT | the `exit` row on its own | 1.0000 |

V0 reproduces `determinism.csv` for all six scored targets (0.7903 / 0.5940 /
0.9964 / 0.5086 / 0.9923 / 0.8477).

Two variants land near the reviewer's 0.522 and neither is confirmed:

- **V12 (keep the `exit` control row).** For DECEIVE that row is a perfectly
  stable 37th command (mean pairwise 1.0000, the same for every target), so
  `(36 x 0.5086 + 1.0000) / 37 = 0.5219`, which rounds to his 0.522. But V12
  moves Beelzebub by 0.011 (0.5940 to 0.6049), so it does not reproduce his
  statement that the other targets agree within 0.004.
- **V1 (drop censored rows).** 0.5242, i.e. 0.002 from his value, and every
  other target moves by at most 0.004 at three decimals (Beelzebub 0.594 to
  0.598), but it does not give 0.522.

In both cases the gap is a denominator/censoring choice, not a bug: masking,
ANSI stripping, the 4,000-character cap and the hostname set each change the
value by at most 0.0003 (V8, V9, V10, V11). The published number excludes
`exit` because it is a harness control row (`harness/analyze.py`,
`n_excluded_exit`) and counts a timed-out row as an empty output; the report
keeps 0.509 on that definition. The reviewer's exact rule is UNVERIFIED
(item 9 below).

### h.2 Narration and prose (source: `narration_by_target_v21.csv`, `narration_hits_v21.csv`)

| Target | Outputs scanned | Narration outputs | Sessions | Prose-only outputs | Any flag (sessions) |
|---|---:|---:|---:|---:|---:|
| AdvancedshelLM | 720 | 0 | 0 | 0 | 0 (0) |
| Beelzebub | 716 | 15 | 12 | 0 | 15 (12) |
| Cowrie | 720 | 0 | 0 | 0 | 0 (0) |
| DECEIVE | 691 | 0 | 0 | 0 | 0 (0) |
| ground truth | 720 | 0 | 0 | 0 | 0 (0) |
| VelLMes | 675 | 0 | 0 | 0 | 0 (0) |
| llm-honeypot | 720 | 0 | 0 | 0 | 0 (0) |

15 matched outputs in 12 of 20 Beelzebub sessions; ground truth, Cowrie and the
other five targets are 0. The detector is 14 named phrases plus a prose rule
(two sentences of 8+ words with 4+ function words and a personal pronoun, in a
command whose ground truth is under 200 characters). It is heuristic; the CSV
lists every hit. The v2.1b recheck hand-classified all 14 v2.1 hits as genuine
(precision 14/14) and found two misses (runs 20 and 8); "the user has been",
"let me continue/simulate/..." and "they/them/their" were added, which detects
run 20 and takes the count to 15. Run 8 leaks a tool definition rather than
narrating the terminal, so it is counted only in the broad figure
(16 outputs / 13 sessions).

False positives found during tuning, before the reported run: an early version
of the prose rule fired on `w`/`ps aux` column output (the STAT column contains
`?`, which split every row into a "sentence") and on the standard sudo lecture
and Ubuntu login banner. The rule now splits only on `.` and `!`, requires four
function words, requires a personal pronoun, and excludes that boilerplate. The
only remaining prose-only hit is Beelzebub run 7, which is narration on
inspection.

### h.3 Persona-independent state checks (source: `state_by_target_v21.csv`)

| Target | Passed / 120 | pwd | marker | ls1 | ls2 | ls3 | whoami=id | Cascade | Direct | Timeout |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ground truth | 120 | 20 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 |
| Cowrie | 120 | 20 | 20 | 20 | 20 | 20 | 20 | 0 | 0 | 0 |
| VelLMes | 119 | 20 | 20 | 20 | 20 | 20 | 19 | 0 | 1 | 0 |
| AdvancedshelLM | 116 | 19 | 20 | 20 | 20 | 20 | 17 | 1 | 3 | 0 |
| Beelzebub | 107 | 16 | 19 | 18 | 17 | 17 | 20 | 8 | 5 | 0 |
| DECEIVE | 79 | 12 | 13 | 11 | 11 | 13 | 19 | 35 | 4 | 2 |

Denominator is 20 runs x 6 checks = 120 per target; the detector target is
excluded. Failures keep the label recorded in `state_checks_v21.csv`; the label
is not a mechanism claim. Read against the raw rows, 10 of DECEIVE's 20 runs
have a row whose output belongs to an earlier command, and all 10 have a
`timed_out=true` row within the three before the onset (onset-1 in nine runs,
onset-2/-3 in run 20). No run starts shifting on the prompt alone, and the
prompt-versus-queue mechanism is **UNVERIFIED**. Per-run onset, lag and the
3-row timeout check: `desync_onset_v21b.md`. Per-run failure detail is in
`state_checks_v21.csv`.

Against the reviewer's figures:

| Target | Reviewer | This scorer | Difference |
|---|---:|---:|---:|
| ground truth | 120 | 120 | 0 |
| Cowrie | 120 | 120 | 0 |
| VelLMes | 117 | 119 | +2 |
| AdvancedshelLM | 116 | 116 | 0 |
| Beelzebub | 107 | 107 | 0 |
| DECEIVE | 72 | 79 | +7 |

Five of six match or differ by one check. Beelzebub matched after the v2.1b
fix: `_tokens` compared `bm_dir/` literally, so a present directory was scored
as missing in run 10 `state_ls_tmp_3`; stripping the trailing `/` gives 107. The
DECEIVE gap is not explained by a single rule (h.6, item 10) and VelLMes' by one
`whoami` that returns an empty string.

The v2.1b cause split is 35 cascade / 4 direct / 2 timeout for DECEIVE, not
30 / 9 / 2. The `cascade` label is kept as the CSV field name, but the v2.1b
explanation of it (a prompt cascade) is superseded: an onset is identifiable
in 10 of 20 runs and every onset has a
`timed_out=true` row within the three before it (`desync_onset_v21b.md`), so the
shift is timeout-ordered, not prompt-ordered; the mechanism is **UNVERIFIED**.
Two DECEIVE passes (runs 13 and 17, `whoami_vs_id`) rest
on a timed-out `id` row that had already printed its `uid=` line; counting a
timeout as no evidence gives 77/120 instead of 79/120.

### h.4 Visible literal ANSI (source: `literal_ansi_by_target_v21.csv`)

| Target | Outputs | Sessions | `ESC[` | `\e[` | bare SGR |
|---|---:|---:|---:|---:|---:|
| DECEIVE | 32 | 6 | 170 | 1,035 | 223 |
| every other target | 0 | 0 | 0 | 0 | 0 |

Those three numbers are *occurrences*. As outputs and sessions
(`literal_ansi_by_target_v21b.csv`): `ESC[` 5 outputs in 1 session (run 2),
`\e[` 17 outputs in 3 sessions (runs 4, 5, 9), bare SGR 10 outputs in 2 sessions
(runs 12, 19). The reviewer's count of 5 is **exactly** the `ESC[` set: five
outputs in run 2 (`ls_etc`, `ls_home`, `state_ls_tmp_1`, `state_ls_tmp_2`,
`state_ls_tmp_3`), all hand-checked; each is literal text printed in the output,
not a control byte. No `raw/*.jsonl` file contains a `0x1b` byte, and `ESC[` is
the four ASCII characters `0x45 0x53 0x43 0x5b`. v2 reports no visible-colour count for DECEIVE: the only ANSI
finding in v2 is the detector target's concealed markers, and the run-time
`literal_escape_text_present` flag is set on 76 DECEIVE rows but is evaluated on
`raw_output` against the `\x1b[` / `\u001b[` / `\033[` literal forms
(`harness/run_ssh.py`, `_has_literal_escape`), so it neither counts visible
`ESC[` in `cleaned_output` nor the bare SGR form. Every match is in
`literal_ansi_hits_v21.csv` with its surrounding text.

### h.5 DECEIVE upstream URL

`https://github.com/splunk/DECEIVE` answers `301 Moved Permanently` to
`https://github.com/Cisco-Talos/DECEIVE` (checked 2026-11-25 with `curl -I`, and
the Cisco-Talos repository listing shows the project last updated 2026-11-07).
`README.md`, `THIRD_PARTY_NOTICES.md`, `docs/PATCH_NOTES.md` and the v2.1 report
source use the new URL and note the former location once. The local clone commit
stays UNVERIFIED.

### h.6 New UNVERIFIED items

9. The exact definition behind the reviewer's 0.522 for DECEIVE. V12 reproduces
   the digits and V1 reproduces his tolerance on the other targets; no single
   variant tested satisfies both.
10. Why the reviewer's state-check score for DECEIVE is 72/120 where this scorer
    gives 79/120. 48 = 8 x 6 would mean eight sessions failing all six checks;
    this scorer has six such sessions plus partial failures in four others. The
    per-check breakdown above is the evidence for the difference; no single rule
    difference was identified.
11. Why VelLMes scores 119 here and 117 in the reviewer's run (one `whoami`
    returning an empty string, which a different rule may score differently).
12. Whether the narration detector's prose rule would fire on larger corpora;
    on this batch it fires once (Beelzebub run 7) and never on a control. After
    the v2.1b pattern additions every hit is a phrase hit, so the prose-only
    count is 0 there.
13. Whether DECEIVE's command/output desync is caused by its password prompt or
    by its queue handling. The onset is measurable: 10/20 runs, and every onset
    has a `timed_out=true` row within the three before it
    (`desync_onset_v21b.md`). The mechanism is not measured; `cascade` is kept
    only as a CSV field name.
14. Whether the reviewer's narration count of 5 sessions is the literal
    "The user ..." rule. The sessions are possibly 1, 6, 18, 19, 20 (the guess
    that matches 5 of the phrase's 7 sessions), a subset of this scorer's 12;
    that mapping is an inference, not confirmed.
15. Whether the run-8 leaked tool definition should count as narration; it is
    counted as borderline (broad 16 outputs / 13 sessions, strict 15 / 12).

### h.7 v2.1b determinism grid (source: `determinism_grid_v21b.csv`)

The published method reproduces `determinism.csv` exactly. 11 text/similarity
configurations x 192 aggregation choices = 2,112 combinations per target,
12,672 in total, 11,328 rows written.

| Configuration | DECEIVE | Largest move among the other five |
|---|---:|---:|
| M1 published | 0.5086 | 0 |
| V12 (`exit` row kept) | 0.5219 | 0.0109 (Beelzebub) |
| M4 exact Levenshtein ratio | 0.5281 | 0.0169 |
| M10 cap 20,000 | 0.5083 | 0.0011 |
| M11 no cap (4 targets feasible) | not feasible | 0.0012 |
| M3 `quick_ratio()` | 0.6374 | 0.1468 |
| M2 autojunk=False (ground truth only) | not feasible | +0.0052 on ground truth |

**No combination satisfies both halves of the reviewer's statement
(|DECEIVE - 0.522| <= 0.0005 and every other target within 0.004 of the
published value): 0 of 12,672.** `autojunk=False` exceeded a 240 s per-target
budget at `ps_aux` for five of six targets, and the no-cap configuration is
infeasible for DECEIVE and Beelzebub (145,509 and 198,706 characters).
`quick_ratio()` is an upper bound from character multisets, not the same
quantity, and is listed only for completeness.
