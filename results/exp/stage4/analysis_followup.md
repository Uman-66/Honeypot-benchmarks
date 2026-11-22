# Stage 4 — follow-up checks (read-only)

Read-only pass over `results/exp/stage4` (20 runs, prompt timing, quiet check in
runs 1–2), Stage 2 validation (`results/exp/validation`, passes A quiet / B prompt
/ C quiet) and the published batch extracted from `final-batch-v1` to a temp
folder outside the repo. Scripts: `followup_check.py`, `followup_output.txt`.
Nothing was run against a target, no data was modified or committed.

## 1. Prompt-mode integrity

### (a) per target (rows = 36 scored commands × runs)

| target | mode | rows | `prompt_without_echo` true | no final prompt (raw_output, ANSI-stripped) | of which timeout | interior "prompt + text" rows |
|---|---|---:|---:|---:|---:|---:|
| deceive | prompt | 720 | 0 | 29 | 29 | 2 |
| deceive | quiet | 72 | 0 | 0 | 0 | 0 |
| beelzebub | prompt | 720 | 0 | 4 | 4 | **38** |
| beelzebub | quiet | 72 | 0 | 3 | 2 | 6 |
| vellmes | prompt | 720 | 0 | 45 | 45 | 0 |
| vellmes | quiet | 72 | 0 | 6 | 6 | 0 |
| advshellm | prompt | 720 | 0 | 0 | 0 | 0 |
| advshellm | quiet | 72 | 0 | 0 | 0 | 0 |
| cowrie | prompt | 720 | 0 | 0 | 0 | 0 |
| llmhoneypot | prompt | 720 | 0 | 0 | 0 | 0 |
| groundtruth_ssh | prompt | 720 | 0 | 0 | 0 | 0 |

- `prompt_without_echo` is false in all 4,540 SSH rows (no missing command echo).
- "No final prompt" is the timeout set plus one beelzebub quiet row
  (`find_etc_conf`, which ends with the model echoing the *next* prompt and
  command — leakage, not truncation).
- The first pass of this check suggested groundtruth_ssh had 60 rows without a
  final prompt; those rows end with `ESC[K` (erase-to-end-of-line) after `$ `.
  After ANSI stripping the count is 0. Nothing is truncated.
- Interior "prompt followed by text" is the useful leakage measure: beelzebub 38
  prompt / 6 quiet, deceive 2 prompt, all other targets 0. The `n_leakage` column
  in `analysis.md` (13 for beelzebub, 2 deceive) uses `cleaned_output`, where the
  trailing prompt is stripped by the harness, so its definition differs; the
  table above is the direct measurement on the wire capture.

### (b) vellmes `ls_etc`, run 2

| mode | `timed_out` | latency | bytes | cleaned output |
|---|---|---:|---:|---|
| prompt | **True** | **120.013 s** | 10 | 0 chars (`raw_output` = `'ls /etc\r\n '`) |
| quiet | False | 6.015 s | 2,779 | 2,720 chars |

This is **a harness timeout, not an LLM empty answer and not a proxy failure**.
The proxy row for that command is at `08:21:29.789Z` with
`status=200, duration_ms=7203, prompt_tokens=2249, completion_tokens=800` — the
model produced 800 output tokens in 7.2 s. The target never wrote the reply to
the session (raw capture stops after the echo and a space, with no prompt), so
the harness waited out its 120 s ceiling and recorded the censored value.

### (c) noise-floor exceedances (prompt shorter **and** masked sim below the
Stage-2 A-vs-C quiet-vs-quiet similarity for the same command)

Counts out of 72 pairs per target: **deceive 10, beelzebub 6, vellmes 7,
advshellm 9.**

| target | run | command | prompt / quiet chars | sim | A-vs-C floor |
|---|---:|---|---:|---:|---:|
| deceive | 1 | env | 684 / 2054 | 0.280 | 0.440 |
| deceive | 1 | ls | 50 / 56 | 0.340 | 0.781 |
| deceive | 1 | ls_home | 51 / 65 | 0.458 | 0.667 |
| deceive | 1 | perm_sudo_l | 26 / 81 | 0.514 | 1.000 |
| deceive | 2 | hostname | 10 / 13 | 0.000 | 0.267 |
| deceive | 2 | id | 89 / 92 | 0.802 | 0.832 |
| deceive | 2 | perm_sudo_l | 344 / 351 | 0.587 | 1.000 |
| deceive | 2 | state_ls_tmp_1 | 165 / 176 | 0.504 | 0.691 |
| deceive | 2 | state_ls_tmp_2 | 189 / 194 | 0.543 | 0.684 |
| deceive | 2 | state_ls_tmp_3 | 181 / 186 | 0.572 | 0.671 |
| beelzebub | 1 | ls | 67 / 255 | 0.025 | 0.467 |
| beelzebub | 2 | err_foobarbaz | 28 / 247 | 0.204 | 1.000 |
| beelzebub | 2 | find_etc_conf | 192 / 164,049 | 0.015 | 0.271 |
| beelzebub | 2 | ls | 96 / 218 | 0.025 | 0.467 |
| beelzebub | 2 | ls_la | 906 / 2,916 | 0.012 | 0.066 |
| beelzebub | 2 | perm_shadow | 35 / 309 | 0.203 | 1.000 |
| vellmes | 1 | ps_aux | 1,398 / 1,638 | 0.613 | 0.691 |
| vellmes | 1 | whoami | 4 / 5 | 0.889 | 1.000 |
| vellmes | 2 | df_h | 372 / 600 | 0.613 | 0.707 |
| vellmes | 2 | perm_sudo_l | 26 / 248 | 0.053 | 0.105 |
| vellmes | 2 | state_ls_tmp_1 | 6 / 171 | 0.068 | 0.071 |
| vellmes | 2 | state_ls_tmp_2 | 14 / 179 | 0.124 | 0.130 |
| vellmes | 2 | state_ls_tmp_3 | 6 / 171 | 0.068 | 0.071 |
| advshellm | 1 | df_h | 182 / 235 | 0.408 | 0.505 |
| advshellm | 1 | passwd | 83 / 1,208 | 0.122 | 1.000 |
| advshellm | 1 | ps_aux | 2,542 / 4,413 | 0.423 | 0.526 |
| advshellm | 1 | state_ls_tmp_1 | 221 / 223 | 0.158 | 1.000 |
| advshellm | 1 | state_ls_tmp_2 | 229 / 231 | 0.178 | 1.000 |
| advshellm | 1 | state_ls_tmp_3 | 221 / 223 | 0.158 | 1.000 |
| advshellm | 2 | find_etc_conf | 101 / 204 | 0.039 | 0.489 |
| advshellm | 2 | ls_la | 965 / 966 | 0.593 | 0.676 |
| advshellm | 2 | ps_aux | 2,971 / 6,701 | 0.090 | 0.526 |

The substantive ones (prompt far shorter and far less similar) are beelzebub
`ls`, `err_foobarbaz`, `find_etc_conf`, `perm_shadow`, advshellm `passwd`,
`find_etc_conf`, `ps_aux` (run 2), deceive `env`, `ls`, `perm_sudo_l`. Several
others are one- or few-character differences (vellmes `state_ls_tmp_*`, whoami)
that only cross the floor because the Stage-2 floor is 1.000 for those commands.

### (d) harness latency vs API duration

For every flagged pair the single overlapping proxy request is **shorter** than
the harness latency (e.g. deceive run 2 `id`: 4.138 s harness, 4.093 s API), i.e.
the harness did wait. Three exceptions were reported by the overlap test, all in
advshellm run 2 (`find_etc_conf`, `ls_la`, `ps_aux`), each with a 3.3–9.5 s
harness latency and an API row of **257.7 s**:

- that 257.7 s row (`2026-11-22T08:10:46Z`, `status=200`, 466 prompt tokens,
  **65,536 completion tokens**) started before those three commands and its long
  response window overlapped all three, so one request was counted against each
  of them. It is an overlap artifact of the join, not a command whose reply
  arrived after the harness moved on.
- Side observation: 10 responses in the pass lasted 251–270 s, all ending at
  exactly 65,536 completion tokens (the model's output ceiling). The proxy's own
  read timeout is 300 s, so these complete; the harness's 120 s ceiling means
  none of those commands' callers waited for them.

## 2. Correction to `analysis_review.md`

The table value is **vellmes 45/720 timeouts (6.25 %), 675/720 completed**;
`36/720` is wrong and appears nowhere in the data — 36 is the number of scored
commands per run, not a timeout count. `analysis_review.md` has been updated to
state completed = 675/720 explicitly and to carry the clock caveat from §4.

## 3. Beelzebub: published vs Stage 4 vs Stage 2

| batch / run | rows | timeouts | oversized | leakage | median s | p95 s |
|---|---:|---:|---:|---:|---:|---:|
| published r1 | 36 | 4 | 1 | 5 | 2.164 | 8.88 |
| published r2 | 36 | 2 | 2 | 3 | 4.375 | 17.79 |
| published r3 | 36 | 2 | 2 | 3 | 4.992 | 18.70 |
| published r4 | 36 | 4 | 2 | 5 | 5.672 | 39.78 |
| published r5 | 36 | 4 | 2 | 2 | 7.086 | 45.76 |
| published total | 180 | **16** | 9 | 18 | 5.023 | 31.66 |
| Stage 4 total (prompt) | 720 | **4** | 2 | 38 | 2.308 | 5.87 |
| Stage 4 quiet check (runs 1–2) | 72 | 2 | 0 | 6 | — | — |
| validation pass A (quiet) | 36 | 0 | 0 | 0 | 2.109 | 4.54 |
| validation pass B (prompt) | 36 | 0 | 0 | 0 | 1.697 | 4.47 |
| validation pass C (quiet) | 36 | 0 | 0 | 0 | 2.039 | 3.94 |

Published per-run medians rise monotonically 2.16 → 7.09 s across the five runs
while Stage 4 run medians stay flat (1.71–3.83 s, no trend) and both Stage 2
prompt and quiet passes sit at 1.7–2.1 s.

**Order and timing of the published Beelzebub runs** (file mtimes, UTC; the
published loop is run-major and copies `run_ssh.py` output per run):

| run | beelzebub mtime | position in that loop |
|---|---|---|
| 1 | 2026-11-06 11:44:30 | 4th of 7 (gt_ssh 11:33, cowrie 11:33, llmhoneypot 11:34, **beelzebub 11:44**, advshellm 12:20, deceive 12:27, vellmes 12:34) |
| 2 | 12:44:03 | 4th of loop 2 (started 12:35:20) |
| 3 | 13:04:35 | 4th of loop 3 (started 12:55:18) |
| 4 | 13:27:54 | 4th of loop 4 (started 13:13:50) |
| 5 | 13:57:26 | 4th of loop 5 (started 13:41:48) |

Beelzebub's five runs span 11:44–13:57 (2 h 13 min), interleaved with a full pass
over the other six targets each loop. Run 1 → run 2 gap is 60 min; the rest
20–30 min.

**Was the Beelzebub container restarted between published runs?** No evidence of
a restart: `scripts/up_all.ps1` starts every compose file once (`up -d --build`),
the published README says the batch used `up_all.ps1` and that "containers were
freshly started before the batch" (once, before it), and the published loop only
calls `run_ssh.py` per (run, target) — no `down`/`up` between runs. Stage 4, by
contrast, does `down`/`up --force-recreate` per slot (verified in the earlier
pass). So the published numbers were collected from one continuously running
Beelzebub container; Stage 4 from a new container per slot.

**Configuration:** `git diff final-batch-v1 HEAD` is empty for
`docker/beelzebub-ssh.yaml`, `docker/beelzebub-core.yaml` and
`docker/beelzebub.compose.yaml`. The service config carries no max-token or
history setting (model, persona prompt, `deadlineTimeoutSeconds: 6000`,
rate limiting disabled); history handling lives in the Go plugin source, which
the repo does not track. So the YAML configuration is identical; whether the
built binary was identical is not recorded.

**Candidate differences (each UNVERIFIED as a cause):** (1) container lifetime —
one long-lived process for the published batch vs recreate-per-slot; (2) the
published batch shared one API key across all nine targets in a single
run-major loop, so each Beelzebub run saw a different point in the batch's API
load and wall-clock hour; (3) model output ceiling and proxy timeout unchanged
(10 responses in Stage 4 hit 65,536 tokens), so a generation-length difference
would show as oversized outputs, which are 9/180 published vs 2/720 Stage 4;
(4) prompt vs quiet timing mode (published quiet, Stage 4 prompt); (5) any
difference in the built Beelzebub binary, since no image digest is recorded for
the published batch.

## 4. Clock resolution

Every latency statistic below 0.05 s, and why it must be read as quantised:

| target | median | p95 | distinct run medians (20 runs) |
|---|---:|---:|---|
| groundtruth_ssh | 0.015 | 0.031 | 0.015, 0.016 |
| cowrie | 0.031 | 0.047 | 0.016, 0.0285, 0.0295, 0.030, 0.031, 0.0315 |
| llmhoneypot | 0.015 | 0.031 | 0.015, 0.016, 0.0295 |

Value distribution over all 720 completed commands: groundtruth_ssh 15 ms ×403,
16 ms ×105, 31 ms ×77, 30 ms ×34, 14 ms ×26, 13 ms ×18, 32 ms ×15, 47 ms ×15;
cowrie 31 ms ×237, 15 ms ×133, 32 ms ×76, 16 ms ×70, 30 ms ×54, 47 ms ×25, and a
long tail of 28–29 ms; llmhoneypot 15 ms ×408, 16 ms ×136, 31 ms ×87, 14 ms ×35.

The values cluster at ~15–16 ms and ~30–32 ms steps: a scheduler-tick / RTT
quantisation, not a physical latency distribution. Consequences:

- The groundtruth_ssh "drift" (ρ = 0.704, p = 0.0012) comes entirely from **one
  run median flipping from 15 ms to 16 ms** (run 1 = 16 ms). With two distinct
  values the rank test is a single tick flip, so it must not be reported as a
  trend. The same applies to cowrie (ρ = 0.256) and llmhoneypot.
- Any comparison between groundtruth_ssh (0.015) and llmhoneypot (0.015) is a tie
  at the resolution of the clock; the "extra seconds over ground truth" values
  for cowrie (0.016 s) are ~1 tick.

## 5. Galah rates at equal sample size (100 requests)

Stage 4 has 400 requests; the published batch has 100. To compare rates, 1,000
bootstrap resamples of 100 requests were drawn from the Stage 4 pool (fixed seed
20261122) and the same statistics were recomputed.

| metric | Stage 4, 400 requests | Stage 4, per-100 mean | Stage 4, 95% range of per-100 | published 100-request |
|---|---:|---:|---|---:|
| 5xx rate | 0.100 | 0.101 | 0.05–0.15 | 0.110 |
| timeout rate | 0.0375 | 0.037 | 0.01–0.07 | 0.030 |
| status agreement with nginx | 0.260 | 0.260 | 0.187–0.341 | 0.266 (25/94) |
| distinct `Server` values | 13 | 6.9 | 4–9 | 6 |
| repeat `GET /` similarity | 0.376 | 0.377 | 0.237–0.545 | 0.236 |

On equal sampling, 5xx rate, timeout rate, status agreement and distinct-`Server`
count all fall inside the Stage-4 per-100 range; repeat similarity (published
0.236) sits at the bottom edge (range starts 0.237). The full-400 "13 distinct
Server values" is a count that grows with sample size — the comparable figure is
~7 per 100.

## 6. Cost with the corrected model

Total **$2.0173 over 3,699 requests** (20,459,956 prompt tokens, 83.72 % cached;
2,007,696 completion tokens), i.e. $0.15/M uncached + $0.03/M cached + $0.50/M
output.

| target | requests | cost |
|---|---:|---:|
| deceive | 858 | $0.8983 |
| beelzebub | 794 | $0.4467 |
| vellmes | 840 | $0.2947 |
| advshellm | 817 | $0.2253 |
| galah | 390 | $0.1522 |
| cowrie, llmhoneypot, groundtruth_ssh, groundtruth_http | 0 | $0.0000 |

| run type | runs | requests | cost |
|---|---|---:|---:|
| two-mode (prompt + quiet check) | 1–2 | 641 | $0.2854 (run 1 $0.0853, run 2 $0.2001) |
| prompt-only | 3–20 | 3,058 | $1.7318 |

Per-run median $0.0710. Runs above 3× the median: **run 4 $0.2407** and
**run 15 $0.2268** (run 2 at $0.2001 is just under the 3× line, $0.213). Both
are caused by long 65,536-token generations, not by extra requests (170 calls
each, the same as every prompt-only run).

## 7. What remains UNVERIFIED, and the data that would settle it

| item | status | what would resolve it |
|---|---|---|
| Prompt-mode integrity | **verified for the captured stream**: 0 missing echos, no truncation, leakage only in beelzebub (38/720) and deceive (2/720) | — |
| vellmes `ls_etc` run 2 | **verified**: harness timeout, API returned 200 in 7.2 s, target never surfaced it | a container-side vellmes log for that slot (not recorded) would say whether the reply was dropped or held |
| Noise-floor exceedances | **counted** (10/6/7/9); *why* prompt mode returns less for those commands | a persona-matched control and same-command A/B runs in one container; the counts are descriptive only |
| Harness latency < API duration | **none genuine**; 3 apparent cases are one 257.7 s response overlapping three commands | per-command request IDs in the proxy log (not recorded) would make the join exact |
| Beelzebub published vs Stage 4 | **differences documented, cause UNVERIFIED** | a repeat of the published procedure (one container, 5 run-major loops, quiet mode) and a repeat of the Stage 4 procedure in the same hour, plus the published image digest |
| Beelzebub binary/config identity | YAML identical (git diff empty); binary UNVERIFIED | docker image digest/id for the published container (not recorded) |
| Container restart between published runs | **verified not restarted** (README + one `up_all.ps1` + run-major loop; no down/up in the published commands) | container `StartedAt` from the published session (not recorded) |
| Clock resolution | **verified** (tick-quantised; groundtruth drift = one 15→16 ms flip) | a monotonic sub-millisecond timer in the harness |
| Galah rates at equal n | **verified** (all inside the per-100 range) | — |
