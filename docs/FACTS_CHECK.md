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
| `DECEIVE` | No | UNVERIFIED (no `.git`; nearest upstream revision `cce98f3`, 2026-05-13) | LICENSE = MIT (verified by reading the file and against the upstream `splunk/DECEIVE` `LICENSE`, identical text; an earlier revision of this row said Apache-2.0, which was wrong) |
| `beelzebub` | No | UNVERIFIED | LICENSE = GPL-3.0 (verified by reading the file) |
| `shelLM` | No | UNVERIFIED | LICENSE = CC BY-NC-SA 4.0, NonCommercial (verified by reading the file) |
| `galah` | No | UNVERIFIED | LICENSE = Apache-2.0 (verified by reading the file) |
| `llm-honeypot` | No | UNVERIFIED | no licence file found; no upstream source code is redistributed, but `docker/llmhoneypot.cowrie.cfg` is derived from its `configs/cowrie.cfg` (recorded in `THIRD_PARTY_NOTICES.md`) |
| `cowrie-base` | No | UNVERIFIED; pinned v2.6.1 in docs | `LICENSE.rst` = BSD-3-Clause (Cowrie's 3-clause BSD text, "Copyright (c) 2009-2024 Upi Tamminen, Michel Oosterhof") |
| `cowrie-peek` | No | UNVERIFIED | no licence file found; used as a read-only overlay, not redistributed |

Licence texts are copied verbatim into `LICENSES/`; see `THIRD_PARTY_NOTICES.md` for the
per-tool table, upstream URLs and which tools were modified.

DECEIVE upstream URL, checked 2026-11-21: `https://github.com/splunk/DECEIVE` resolves;
`https://github.com/coverflex-tech/DECEIVE` returns "Repository not found". The upstream
repository tracks `SSH/config.ini.TEMPLATE`, not `SSH/config.ini`.

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
5. Why prompt mode returned less than quiet mode for the 32 quiet-check pairs
   beyond the noise floor.
6. Whether the VelLMes target-side replies (capped 800-token answers produced
   in 4.5-7.8 s) are held or dropped inside the target; no container-side log
   was recorded.
7. Whether residual A-vs-B differences in the Stage 2 validation are artefacts
   or ordinary model variation.
8. Whether galah's write-time masking changes any published baseline count
   (the baseline galah bodies are withheld, so their counts cannot be
   recomputed from the repository).
