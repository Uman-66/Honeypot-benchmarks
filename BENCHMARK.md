# Honeypot Benchmark — Final Report

**Final batch, collected Nov 2026, 5 runs per target, 120 s timeout. Supersedes the
pilot batch.**

**Data**: `results/raw/`, `results/raw_http/`, `results/summary.md`,
`results/summary.csv`, and local HoneyBee summaries.

**Withheld**: nine galah HTTP raw bodies are not published because they contain
model-fabricated credential-like strings; see [`docs/WITHHELD_FILES.md`](docs/WITHHELD_FILES.md)
for their paths, sizes and SHA-256 values. The galah counts below derive from those files.

## Summary

The final batch used five runs per SSH and HTTP target with scripted inputs.
Each SSH run contains 36 scored commands plus the harness `exit` row; each HTTP
run contains 20 requests. Cowrie was a static SSH baseline and Ubuntu/nginx
containers were ground truth. LLM SSH determinism ranged from 0.4664 to 0.8364,
while Cowrie measured 0.9874. Galah returned 11 HTTP 5xx responses in 100
requests and agreed with nginx on 25 of 94 comparable statuses. Beelzebub had
16 scored timeouts and 14/180 transcript-leakage outputs. HoneyBee was evaluated
separately as a generator with n=3 per case; it is not a honeypot. These results
do not rank tools or establish causes for timeout/state patterns.

## Scope and targets

| Target | Track | Runs/rows | Port | Role |
|---|---|---:|---:|---|
| DECEIVE | SSH | 5 × 185 | 8022 | LLM honeypot |
| Beelzebub | SSH | 5 × 185 | 2222 | LLM honeypot |
| Cowrie | SSH | 5 × 185 | 2223 | Static baseline |
| AdvancedshelLM | SSH | 5 × 185 | 2224 | LLM honeypot |
| Ground truth SSH | SSH | 5 × 185 | 2225 | Ubuntu/OpenSSH |
| llm-honeypot | SSH | 5 × 185 | 2227 | Detector target |
| VelLMes | SSH | 5 × 185 | 2228 | LLM honeypot |
| galah | HTTP | 5 × 100 | 8088 | LLM HTTP responder |
| Ground truth HTTP | HTTP | 5 × 100 | 2226 | nginx |
| HoneyBee | Generator | 18 generations | 2229 config | LLM environment generator |

## Method

The SSH list has 37 ordered commands: 36 scored commands plus `exit`. The
observed categories are recon, files, process, errors, permissions, and state.
Host-specific commands are excluded from fidelity scoring. The HTTP list has
20 requests: 17 GET, one HEAD, one OPTIONS, and one POST, including three
repeated `GET /` requests.

The final protocol used a 120-second runner timeout and skipped complete
target/run pairs. Raw-file timestamps show collection in passes: for run 1,
groundtruth SSH, Cowrie, llm-honeypot, and Beelzebub were written first;
AdvancedshelLM, DECEIVE, and VelLMes run 1 were written later. The same
two-stage SSH order repeated for runs 2–5. Galah HTTP runs 1–5 were collected
after the first SSH pass and before the later SSH passes; ground-truth HTTP
runs were written immediately after Galah run 5. The recorded final raw data
retains the runner's per-command timeout fields. Containers were freshly
started before the batch. A single model and shared API endpoint were used by
the LLM targets.

The older pilot batch is reported separately below and is not mixed into final
tables.

## Metrics and definitions

- **Latency** is command/request wall time for completed commands only. SSH
  timeout observations are censored at the runner timeout and excluded from
  median/p95; these latency statistics understate latency for targets with
  timeouts.
- **Fidelity** is the mean `difflib.SequenceMatcher` ratio for each target
  command against the first loaded ground-truth SSH output for that command.
  Host-specific commands are reference-only. Before every comparison, ANSI
  escapes are removed and each text is capped at the first 4,000 characters.
- **Determinism** is the mean pairwise `SequenceMatcher` similarity across
  non-empty run outputs for the same target/command, using that same
  ANSI-stripped 4,000-character cap.
- **Shared commands** are the 26 non-host-specific commands that have a
  non-timeout observation for every compared target; shared fidelity averages
  command means over this intersection.
- **Oversized output** means a command output longer than 20,000 characters;
  the metric counts such command outputs per target.
- **Transcript leakage** counts a command output when the analyzer's multiline
  regex `(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s` finds a shell prompt before
  the final non-empty output line. The final legitimate trailing prompt is
  excluded.
- **HTTP status agreement** compares matching method/path status values with
  ground-truth nginx.

## Results — SSH

`n_used=n_expected=180` for every scored target.

| Target | Median/p95 s | n completed | Timeouts | Empty | Fidelity (95% CI; 26 shared) | Determinism | Oversized | Leakage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| groundtruth_ssh | 0.562/0.579 | 180 | 0 | 35 | — | — | 0 | 0/180 |
| cowrie | 0.563/0.610 | 180 | 0 | 40 | 0.5877 (0.4203–0.7438) | 0.9874 | 0 | 0/180 |
| advshellm | 1.922/4.504 | 180 | 0 | 26 | 0.5947 (0.4336–0.7386) | 0.7836 | 0 | 0/180 |
| vellmes | 1.687/4.874 | 171 | 9 | 25 | 0.6070 (0.4601–0.7506) | 0.8364 | 0 | 0/180 |
| deceive | 1.984/10.361 | 175 | 5 | 27 | 0.4731 (0.3493–0.5858) | 0.4664 | 2 (max 135,108) | 0/180 |
| beelzebub | 5.023/31.656 | 164 | 16 | 16 | 0.3737 (0.2319–0.5239) | 0.6800 | 9 (max 239,959) | 14/180 |
| llmhoneypot | detector | 180 | 0 | 30 | excluded | excluded | 0 | 0/180 |

The shared-command fidelity values above are from `fidelity_shared` in the
Markdown summary. `summary.csv` also contains an all-available-command
fidelity column; those values are not interchangeable.

### Timeout detail

| Target | Command | Runs timed out | Run numbers |
|---|---|---:|---|
| beelzebub | exit | 1 | 1 |
| beelzebub | id | 1 | 4 |
| beelzebub | os_release | 1 | 4 |
| beelzebub | passwd | 1 | 5 |
| beelzebub | state_cat_marker | 3 | 1,3,5 |
| beelzebub | state_echo_marker | 3 | 1,4,5 |
| beelzebub | state_ls_tmp_3 | 3 | 1,4,5 |
| beelzebub | state_rm_marker | 2 | 2,3 |
| beelzebub | state_rmdir_bm_dir | 1 | 1 |
| beelzebub | whoami | 1 | 2 |
| deceive | cpuinfo | 2 | 1,4 |
| deceive | perm_sudo_l | 1 | 3 |
| deceive | ps_aux | 2 | 1,4 |
| vellmes | env | 4 | 1,2,4,5 |
| vellmes | ps_aux | 5 | 1,2,3,4,5 |

The Beelzebub timeout rows sum to 17 because the table includes the run 1
`exit` control row. The scored total is 16 after excluding `exit`; DECEIVE's
rows sum to 5 and VelLMes's rows sum to 9, matching the scored table.

DECEIVE state checks failed in runs 1 and 4 for `pwd`, the marker read, and
the `ls` checks; `whoami==id` failed once in AdvancedshelLM run 4 and once in
Beelzebub run 4. Causes are UNVERIFIED.

The detector target's injected strings were visible after ANSI stripping in
all five runs for all 11 monitored command IDs.

### Empty and unexpected outputs

The analyzer compares command emptiness with ground truth; these are counts
of command outputs, not unique commands. For the LLM SSH targets:

| Target | `unexpected_empty` | `spurious_nonempty` |
|---|---|---|
| AdvancedshelLM | `whoami: 1` | `ls: 5`; `which_python3_gcc: 5` |
| Beelzebub | `state_cat_marker: 3`; `state_ls_tmp_3: 3`; `os_release: 1`; `passwd: 1`; `whoami: 1`; `id: 1` | `ls: 5`; `which_python3_gcc: 5`; `state_cd_tmp: 5`; `state_mkdir_bm_dir: 5`; `state_rm_marker: 3`; `state_echo_marker: 2`; `state_rmdir_bm_dir: 4` |
| DECEIVE | `os_release: 5`; `err_ls_root: 5` | `which_python3_gcc: 5` |
| VelLMes | `ps_aux: 2`; `cpuinfo: 2`; `state_pwd_after_cd: 2`; `state_cat_marker: 2`; `state_ls_tmp_2: 2`; `state_ls_tmp_3: 2` | `ls: 5`; `which_python3_gcc: 5`; `state_cd_tmp: 2`; `state_echo_marker: 2`; `state_mkdir_bm_dir: 2`; `state_rm_marker: 2`; `state_rmdir_bm_dir: 2` |

The `ls` and `which_python3_gcc` spurious-nonempty entries reflect invented
filesystem contents/persona differences in the target output; they are not
claims about the real host filesystem.

## Results — HTTP

Galah produced 11/100 5xx responses, six errors including three timeouts, six
distinct `Server` header values, 12 header-name-set inconsistencies, 0.2364
`GET /` repeat similarity, 25/94 status agreements with nginx, five
documentation-example secret hits, and 19 target-port mentions. Its latency
median/p95 was 3.531/8.887 seconds. Ground-truth nginx had zero 5xx responses,
a constant `Server` header, 1.0000 repeat similarity, and a 0.015-second
median.

## HoneyBee

HoneyBee is an LLM generator, not a honeypot. The evaluation used model
`glm-5p3-flash`, temperature 0.2, max tokens 8192, and n=3 per
generator/case cell (18 generations). Docker Compose was clean in 6/6 cases,
Dockerfile in 4/6, and Nuclei in 3/6. Length-limited results were 5/18, all
in the PostgreSQL case. Grafana was clean in 9/9 generations; PostgreSQL was
clean in 4/9. The scorer was revised after initial results; original outputs
remain in `results/honeybee/validity.json`. No security verdict is inferred.

## Target configuration

Values below are configuration values recorded in the compose/Dockerfile,
target, or patch documentation. “Not recorded” means no value was found in
those sources; it is not an inferred default.

| Target | Stack | Model | Temperature | Max tokens | User / hostname | Main patch or configuration |
|---|---|---|---:|---:|---|---|
| DECEIVE | Python 3.11-slim + DECEIVE | `accounts/fireworks/models/glm-5p3-flash` | 0.2 (`SSH/config.ini`) | none — no output cap (`SSH/ssh_server.py`) | guest / not recorded | `strip_llm_output`, Fireworks env/base URL, exit sentinel, lazy imports |
| Beelzebub | upstream Go image + mounted YAML | `accounts/fireworks/models/glm-5p3-flash` | not exposed by plugin config | not exposed by plugin config | guest / ubuntu | API-key/host fallback; benchmark service/core configs |
| AdvancedshelLM | Python 3.11-slim + shelLM | `accounts/fireworks/models/glm-5p3-flash` | 0.2 | 4096 | guest / not recorded | Fireworks client, exit handling, env fallback, wrapper |
| VelLMes | Python 3.11-slim + VelLMes | `accounts/fireworks/models/glm-5p3-flash` | 0.2 | 800 | user / not recorded | SSH wrapper and benchmark config |
| galah | Go 1.22 builder + Debian slim | `accounts/fireworks/models/glm-5p3-flash` | 0.2 | not recorded | not applicable / not recorded | response cleaning, Fireworks entrypoint/config |
| Cowrie | official Cowrie image digest | not applicable | not applicable | not applicable | root / ubuntu | mounted Cowrie config; no upstream source edit |
| llm-honeypot | Cowrie v2.6.1 overlay | not applicable | not applicable | not applicable | root / not recorded | rewritten overlay Dockerfile and Cowrie v2.6.1 pin |
| Ground truth SSH | Ubuntu 20.04 + OpenSSH | not applicable | not applicable | not applicable | guest / ubuntu | benchmark Dockerfile/compose PTY and PAM changes |
| Ground truth HTTP | Ubuntu 20.04 + nginx 1.18.0 package | not applicable | not applicable | not applicable | not applicable / not recorded | benchmark Dockerfile/compose |
| HoneyBee | Python 3.11-slim + Streamlit | `accounts/fireworks/models/glm-5p3-flash` | 0.2 | 8192 | not applicable / not applicable | disabled deploy path and empty-generation UI handling |

### Configuration values that need a caveat

DECEIVE has **no output-token cap**. `ChatOpenAI` is constructed without `max_tokens` in
`DECEIVE/SSH/ssh_server.py`, and the only token limit in that file is
`trimmer_max_tokens = 64000` (`DECEIVE/SSH/config.ini`), which trims the conversation history sent
to the backend rather than capping the reply. That is why DECEIVE produced 2 oversized outputs,
with a maximum of 135,108 characters.

Beelzebub's temperature and max-token values are **not exposed by the plugin configuration**: the
`plugin:` block of `docker/beelzebub-ssh.yaml` sets neither, and the plugin source that would apply
a default is not present in this tree (`beelzebub/plugins/` contains only `imports_gen.go`). They
are therefore unknown at runtime, and "not recorded" in the table above should be read that way.

## Findings supported by the data

- Static emulation and LLM targets had different measured determinism:
  Cowrie 0.9874 versus 0.4664–0.8364 for the LLM SSH targets.
- Galah varied across HTTP responses while nginx did not: six versus one
  `Server` header value, 0.2364 versus 1.0000 repeat similarity, and 25/94
  status agreement with nginx.
- Large-output and transcript-leakage observations were present in Beelzebub
  (9 oversized, 14/180 leakage) and large outputs were also present in DECEIVE
  (2, maximum 135,108).
- Timeouts were command-specific: VelLMes `ps_aux` timed out in 5/5 runs and
  `env` in 4/5; Beelzebub `state_cat_marker`, `state_echo_marker`, and
  `state_ls_tmp_3` each timed out in 3/5; DECEIVE `cpuinfo` and `ps_aux`
  timed out in runs 1 and 4. Causes are UNVERIFIED.
- Median LLM SSH latency was 3.0x (VelLMes), 3.4x (AdvancedshelLM), 3.5x
  (DECEIVE), and 8.9x (Beelzebub) the 0.562-second ground-truth median.
- Pilot and final batches differ for some targets; the cause is UNVERIFIED.
- llm-honeypot's injected strings were visible after ANSI stripping.

## Things the data does not show

The overlapping fidelity confidence intervals do not support ranking tools.
The DECEIVE state failures do not establish its state-tracking capability.
These scripted measurements do not establish attacker detectability, HoneyBee
output security, or behavior beyond this model, endpoint, and sample.

## Limitations and threats to validity

There were five runs, one shared model/API endpoint, scripted commands, freshly
started containers, censored timeout latencies, and a character-similarity proxy. Personas,
hostnames, and filesystem fixtures differ across targets. Shared API load can
affect timeout and latency patterns. HoneyBee has n=3 per cell and static
validity checks only. These constraints limit generalization.

## Pilot vs final comparison

The pilot is older data collected with the earlier analyzer and 90-second
timeout. It is not mixed with the final tables. Direct source checks show
Galah 29/100 5xx responses and Beelzebub zero timeouts in
`results_pilot/summary.md`. DECEIVE has 13 timeouts in that summary, 14 in
the available pilot raw JSONL (runs 1–5: 0, 11, 3, 0, 0), and 17 in
`results_pilot/ssh_commands_long.csv` (runs 1–5: 3, 11, 3, 0, 0). The number
17 therefore comes from the pilot CSV, not the available raw JSONL; the
accounting difference is UNVERIFIED.

## Reproducibility

Use the UTF-8 Windows commands and interleaved protocol in [README.md](README.md).
The analyzer writes Markdown, CSV, and audit summaries from local raw JSONL.
The final data also includes [results/summary.md](results/summary.md) and the
read-only facts verification in [docs/FACTS_CHECK.md](docs/FACTS_CHECK.md).

## Later measurements (Stage 2 and Stage 4)

The numbers above are the published final batch and are unchanged. Two later
stages were collected on branch `stage4-driver`; the full write-up is
[`report/honeypot_report_v2.tex`](report/honeypot_report_v2.tex) and the data
are under [`results/exp/`](results/exp/).

- **Harness latency floor (Stage 2).** The default quiet rule records a command
  only after 0.5 s of silence, so every latency above includes a measured floor
  of 0.547--0.563 s (`results/exp/floor.md`). Prompt timing replies in about
  16 ms, limited by the 15.6 ms Windows timer tick.
- **Prompt-mode validation.** Three passes (quiet/prompt/quiet) on the four LLM
  SSH targets, 452 API calls, zero `prompt_without_echo` rows
  (`results/exp/validation/`).
- **Stage 4 pass.** 9 targets x 20 runs, prompt timing, shuffled order (seed
  2026), fresh container per slot, 180 completed slots, 3,699 proxy requests,
  $2.0173 at the corrected cached-token price model
  (`results/exp/stage4/analysis.md`, `analysis_review.md`).
- **Stage 4 SSH medians.** 2.18--2.39 s for the four LLM SSH targets against
  0.015 s for ground truth, with 0/720 (AdvancedshelLM), 4/720 (Beelzebub),
  29/720 (DECEIVE) and 45/720 (VelLMes) timeouts
  (`results/exp/stage4/latency.csv`, `timeout.csv`).
- **Timeout attribution.** Of 86 timed-out rows, 9 were API-side (241--291 s,
  all ending at 65,536 completion tokens), 66 target-side and 11 unmatched
  (`results/exp/stage4/analysis_timeouts.md`).
- **Token caps.** AdvancedshelLM peaks at 4,096 and VelLMes at 800, exactly
  their documented caps; only the uncapped targets reach 65,536.
- **Beelzebub lifetime control.** Ten sessions in one container show a rising
  median (3.88 to 5.95 s) and 6/360 timeouts, while the fresh-container series
  stays flat; the cause is UNVERIFIED
  (`results/exp/lifetime_control/beelzebub_persistent/lifetime.json`).
- **Galah at equal n.** Per-100 resampling of the 400 Stage 4 requests gives
  5xx 0.101 and status agreement 0.260, consistent with the 0.110 and 0.266
  reported above (`results/exp/stage4/analysis_followup.md`).

## Future work

Repeat the benchmark across more runs, models, temperatures, and independently
loaded API endpoints. Add a controlled state test, a human/agent attacker
evaluation, and a separate HoneyBee security review.

## License

My own work — the harness, Docker configuration, wrapper scripts and documentation —
is under the MIT licence; see [`LICENSE`](LICENSE).

The benchmarked third-party tools (DECEIVE, Beelzebub, AdvancedshelLM, VelLMes,
galah, HoneyBee, Cowrie, llm-honeypot) keep their own upstream licences. Those
texts are reproduced verbatim in [`LICENSES/`](LICENSES/), and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) lists each tool with its
upstream URL, pinned commit where known, licence, and whether it was modified.
The patches in `patches/` are derivative works of the upstream files they modify
and remain under those upstream licences (Apache-2.0 for HoneyBee, GPL-2.0 for
VelLMes). No third-party source code is redistributed in this repository.
