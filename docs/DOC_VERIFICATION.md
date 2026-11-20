# Documentation verification

This log records checks in the order requested. Evidence is read-only and
comes from repository data or repository documentation. No benchmark reruns,
network calls, API calls, Docker commands, or `.env` reads are performed.

## Check 0 — number verification

Status: OK.

- File: `scratch/verify_numbers.py`
- Before: no reproducible number-check script.
- After: the script reads `results/summary.csv`, `results/summary.md`, and raw
  JSONL using explicit UTF-8, reports PASS per target/table field, recomputes
  raw rows, timeout counts by run/command, completed latencies, and ratios to
  the ground-truth SSH median. All current table fields checked PASS; the
  detector row is intentionally excluded from the generated summary section.

## Check 1 — container-start wording

Status: corrected.

- File: `BENCHMARK.md`, Method and Limitations; `README.md`, Known issues.
- Before: “warmed immediately before the batch” and “first run ... cold start”
  contradicted each other.
- After: both documents say containers were freshly started before the batch;
  the cold-start claim was removed.

## Check 2 — completed latency counts

Status: corrected.

- File: `BENCHMARK.md`, Metrics and Results — SSH; `README.md`, Results and
  Known issues.
- Before: the SSH table had no completed-count column and described timeout
  latency as censored without stating the exclusion rule.
- After: the table reports completed counts `180, 180, 180, 171, 175, 164,
  180` for ground truth, Cowrie, AdvancedshelLM, VelLMes, DECEIVE, Beelzebub,
  and llm-honeypot respectively. Both documents state that median/p95 use
  completed commands only and understate latency for targets with timeouts.
- Evidence: `harness/analyze.py` filters `not r.get("timed_out")` before
  `_latency_stats`; raw recomputation is in `scratch/verify_numbers.py`.

## Check 3 — analyzer metric definitions

Status: corrected.

- File: `BENCHMARK.md`, Metrics and definitions.
- Before: fidelity, determinism, shared-command selection, transcript leakage,
  and oversized-output definitions were abbreviated and did not identify the
  exact reference/intersection rules.
- After: definitions now match `harness/analyze.py`: first loaded ground-truth
  output per command, ANSI-stripped 4,000-character comparison cap, 26-command
  non-host-specific/non-timeout intersection, the exact leakage regex and
  final-line exclusion, and `>20,000` character   output counting.

## Check 4 — raw-file collection order

Status: corrected.

- File: `BENCHMARK.md`, Method; `README.md`, reproduction heading.
- Before: the report said targets were interleaved by run.
- After: timestamp evidence is recorded accurately: SSH run 1 began with
  groundtruth SSH, Cowrie, llm-honeypot, and Beelzebub, then AdvancedshelLM,
  DECEIVE, and VelLMes; the same two-pass order repeated for runs 2–5. Galah
  HTTP runs 1–5 followed the first SSH pass, and ground-truth HTTP followed
  Galah run 5.
- Evidence: `Get-ChildItem results\raw\*.jsonl,results\raw_http\*.jsonl`
  sorted by `LastWriteTime`, with timestamps from 2026-11-06 11:33 through
  14:06 local time.

## Check 5 — facts-check link

Status: corrected.

- File: `BENCHMARK.md`, Reproducibility; new `docs/FACTS_CHECK.md`.
- Before: the report linked to gitignored `scratch/FACTS_CHECK.md`.
- After: the data-only verification was copied to `docs/FACTS_CHECK.md` and
  the report links there. Clone commit/license entries that cannot be verified
  remain explicitly UNVERIFIED.

## Check 6 — timeout-table accounting

Status: corrected.

- File: `BENCHMARK.md`, Timeout detail.
- Before: Beelzebub's listed rows summed to 17 while the scored table said 16,
  with no explanation.
- After: a footnote identifies run 1 `exit` as the unscored control row; the
  scored sums are Beelzebub 16, DECEIVE 5, and VelLMes 9.
- Evidence: `docs/FACTS_CHECK.md` and `scratch/verify_numbers.py`.

## Check 7 — command/request manifests

Status: corrected.

- File: `BENCHMARK.md`, Method.
- Before: the HTTP method mix was not stated precisely and the SSH category
  list was described only approximately.
- After: the report states 37 SSH commands (36 scored plus `exit`) and the
  six categories present in `harness/commands.yaml`; it states 20 HTTP
  requests consisting of 17 GET, one HEAD, one OPTIONS, and one POST, with
  three repeated `GET /` requests, matching `harness/http_requests.yaml`.

## Check 8 — pilot figures

Status: corrected.

- File: `BENCHMARK.md`, Pilot vs final comparison.
- Before: the text mentioned summary, raw, and CSV DECEIVE timeout totals
  without identifying the source of 17.
- After: it states directly that pilot summary has Galah 29/100 5xx,
  Beelzebub zero, and DECEIVE 13; available pilot raw JSONL has DECEIVE 14;
  `results_pilot/ssh_commands_long.csv` has 17 (3, 11, 3, 0, 0). The
  discrepancy remains UNVERIFIED.

## Check 9 — empty and unexpected outputs

Status: corrected.

- File: `BENCHMARK.md`, Empty and unexpected outputs.
- Before: the final report omitted the per-target `unexpected_empty` and
  `spurious_nonempty` command counts.
- After: all four LLM SSH targets are listed with the exact dictionaries from
  `results/summary.md`. The report explicitly notes that `ls` and
  `which_python3_gcc` reflect invented filesystem contents/persona, not the
  real host filesystem.

## Check 10 — target configuration

Status: corrected.

- File: `BENCHMARK.md`, Target configuration.
- Before: no consolidated configuration table existed.
- After: the report records stack, model, temperature, max tokens, target
  user/hostname, and principal patch/configuration for every target. Values
  absent from `docker/*.compose.yaml`, `docker/*.Dockerfile`,
  `harness/targets.yaml`, and `docs/PATCH_NOTES.md` are marked “not recorded”
  or “not applicable”; temperature was not generalized across tools.

## Check 11 — command-specific timeout findings

Status: corrected.

- File: `BENCHMARK.md`, Findings supported by the data.
- Before: the report listed aggregate timeout totals but not the requested
  command-level recurrence.
- After: it records VelLMes `ps_aux` 5/5 and `env` 4/5, Beelzebub's three
  state commands 3/5 each, and DECEIVE `cpuinfo`/`ps_aux` in runs 1 and 4.
  Causes remain explicitly UNVERIFIED.

## Check 12 — README commands, paths, flags, and ports

Status: corrected / UNVERIFIED item remains.

- File: `README.md`, Repository layout and Reproduction.
- `Test-Path` passed for the referenced requirements file, scripts, patch files,
  all listed compose files, and harness files. The compose ports match
  `harness/targets.yaml` and `scripts/up_all.ps1`.
- `run_http.py --help` passed and confirmed `--target`, `--runs`, and
  `--timeout`. `run_ssh.py --help` could not execute because the environment
  lacks `paramiko`; source inspection confirms the README flags and defaults.
  The SSH help result is therefore UNVERIFIED at runtime, not treated as a
  documentation fact.

## Check 13 — prohibited wording

Status: corrected.

- Files: `README.md`, `BENCHMARK.md`.
- Before: the search found “safety” in a heading and “prove”/“cannot track
  state” in a limitation sentence.
- After: the heading now says “handling constraints” and the limitation says
  the data do not establish state-tracking capability. A case-insensitive
  search for `best`, `worst`, `outperform`, `proves`, `cannot track state`,
  `undetectable`, `secure`, and `safe` returns no matches.
