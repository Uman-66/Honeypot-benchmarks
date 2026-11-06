# BENCHMARK.md
# Honeypot Benchmark — Technical Report

**Author**: Muhammad Rumman Aslam  
**Status**: Interim results (5 runs per target, single model)  
**Data source**: `results/summary.md`, `results/summary.csv`, `results/raw/`, `results/raw_http/`, `results/ssh_fingerprints.json`

> **Neutral voice notice**: This report describes what was measured.  It does not
> claim that one tool is better than another.  All comparisons are against a plain
> Ubuntu 20.04 system with no honeypot persona; differences from that baseline are
> expected by design for LLM honeypots that use their own personas and hostnames.

---

## Table of Contents

1. [Summary](#1-summary)
2. [Scope and Tools](#2-scope-and-tools)
3. [Method](#3-method)
4. [Results](#4-results)
5. [Observed Findings](#5-observed-findings)
6. [Hypotheses and Open Questions](#6-hypotheses-and-open-questions)
7. [Limitations and Confounds](#7-limitations-and-confounds)
8. [Not Done and Next Steps](#8-not-done-and-next-steps)
9. [Appendix](#9-appendix)

---

## 1. Summary

Six honeypot targets and two ground-truth servers were deployed locally and subjected
to 37 SSH commands and 20 HTTP requests each, run 5 times, using a scripted harness.
DECEIVE produced the highest response latency (mean 10.936 s, p95 90.015 s, 16 timeouts
out of 180 commands), attributable to API calls that reached the 90 s timeout ceiling
(source: `results/summary.csv`).  Beelzebub and AdvancedshelLM produced no timeouts, with
means of 4.063 s and 2.833 s respectively.  Cowrie (the non-LLM baseline) and the ground-truth
SSH server both responded in under 600 ms on all 180 commands.  For comparable (non-host-specific)
commands, AdvancedshelLM achieved the highest mean similarity to the ground-truth output
(0.5946) and Beelzebub the lowest (0.3789); Cowrie's similarity was 0.5874 (source: `results/summary.csv`).
No LLM artifacts (think tags, markdown fences, AI-refusal phrases) appeared in any target's output.
Galah (HTTP) returned HTTP 500 on 11 of 100 requests and produced varying Server headers
across 8 distinct values; the ground-truth nginx returned a constant `nginx/1.18.0 (Ubuntu)`.
The llm-honeypot detector target delivered its ANSI-concealed prompt-injection payloads
consistently across all 5 runs and all 11 monitored commands (source: `results/summary.md`).
All results are preliminary: 5 runs per target is a small sample and a single model was used.

---

## 2. Scope and Tools

### 2.1 Targets deployed

| Target | Kind | Protocol | Model | Temperature | Port | Persona / notes |
|--------|------|----------|-------|-------------|------|-----------------|
| DECEIVE | LLM honeypot | SSH | `accounts/fireworks/models/glm-5p3-flash` | 0.2 (config.ini) | 8022 | Video game developer's Ubuntu system; `guest@mf-dev-ws07` |
| Beelzebub | LLM honeypot | SSH | `accounts/fireworks/models/glm-5p3-flash` | UNVERIFIED (no temperature field in Request struct; Fireworks default used) | 2222 | `user@ubuntu`; seeded with pwd/home exchange before benchmark commands |
| AdvancedshelLM | LLM honeypot | SSH | `accounts/fireworks/models/glm-5p3-flash` | 0.2 (after patch) | 2224 | `admin@hp_dev_server`; subprocess wrapper; persistent fake filesystem in `worker.yml` |
| galah | LLM honeypot | HTTP | `accounts/fireworks/models/glm-5p3-flash` | 0.2 (via `LLM_TEMPERATURE` env var) | 8088 | Generic "realistic HTTP server" persona; no named system |
| Cowrie | Baseline honeypot | SSH | None | None | 2223 | Static Debian-style fake filesystem; `root@ubuntu` |
| llm-honeypot | Detector (not fidelity target) | SSH | None | None | 2227 | Cowrie v2.6.1 + ANSI-hidden prompt-injection overlay; `root@ubuntu` |
| Ground truth SSH | Ground truth | SSH | None | None | 2225 | Real Ubuntu 20.04 + OpenSSH 8.2p1; `guest@ubuntu` |
| Ground truth HTTP | Ground truth | HTTP | None | None | 2226 | Real Ubuntu 20.04 + nginx 1.18.0 |

All four LLM SSH honeypots and galah used the same model
(`accounts/fireworks/models/glm-5p3-flash`) via Fireworks AI's OpenAI-compatible endpoint
(`https://api.fireworks.ai/inference/v1`).

### 2.2 Tools not attempted

**VelLMes** and **honeybee** from the *awesome-genai-cyberhub* list were not attempted
in this benchmark.

---

## 3. Method

### 3.1 Ground-truth servers

- **SSH**: Ubuntu 20.04 container running OpenSSH 8.2p1 (package version
  `4ubuntu0.13` as observed; see `results/ssh_fingerprints.json`).  User `guest`,
  password `guest`.  No special persona or filesystem modifications.  Commands
  execute on the real container OS; state changes (file creation/deletion under
  `/tmp`) persist within each session.
- **HTTP**: Ubuntu 20.04 container running nginx 1.18.0.  Default nginx configuration;
  no custom content.

### 3.2 SSH command list

37 commands were sent per session, including `exit`.  The `exit` command is handled
separately by the harness (no prompt wait) and excluded from all metrics.
36 non-exit commands were used for metric computation.

Commands are categorised and tagged `host_specific: true/false`.  Host-specific
commands (hostname, uname -a, date, uptime, free -m, df -h, ps aux, cat /proc/cpuinfo,
w, env) vary with the real host and are excluded from fidelity scoring.
Non-host-specific commands are used for fidelity comparison.

Full command list: see [Appendix A](#appendix-a-command-list).

### 3.3 HTTP request list

20 requests per session: GET, HEAD, OPTIONS, and POST requests to a variety of paths
including standard pages, API endpoints, common attack probes, and three repeated
GET / requests for determinism measurement.

Full request list: see [Appendix B](#appendix-b-http-request-list).

### 3.4 Harness design

- One fresh SSH/TCP connection per run.
- Commands sent one at a time; harness waits for a prompt before sending the next.
- Prompt detection: two regexes tried in order on the last non-empty line of the
  buffer after ANSI stripping: (1) `^[^\s@]+@[^\s:]+:[^\n]*[\$#]\s*$` (strict
  `user@host:path$` form); (2) `[\$#]\s*$` (loose trailing `$` or `#`).  Followed
  by a 0.5 s quiet period.
- 90 s per-command timeout (SSH); 30 s per-request timeout (HTTP).
- Source: `harness/run_ssh.py`, `harness/run_http.py`

### 3.5 Metric definitions

All metrics are computed by `harness/analyze.py` from JSONL files in
`results/raw/` and `results/raw_http/`.  The CSV files (`ssh_commands_long.csv`,
`http_requests_long.csv`) are generated by the harness runners independently and
are not read by `analyze.py`.

| Metric | Definition |
|--------|-----------|
| **Latency** | Wall-clock seconds from command send to prompt detection (or timeout). |
| **p95** | 95th percentile of latency values using `statistics.quantiles` at n=20 (`harness/analyze.py: _pct`). |
| **Timeout** | `timed_out = True` in JSONL; command reached the 90 s ceiling. |
| **Empty output** | `cleaned_output.strip() == ""` after ANSI stripping. |
| **exit_closes_session_rate** | Fraction of `exit` command records where `exit_closes_session = True`. |
| **Literal escape codes** | `literal_escape_text_present = True` in JSONL: the raw output contained a string like `\x1b` or `\u001b` as literal text (not as a real escape byte). |
| **`<think>` tags** | `<think>` found in `cleaned_output` (case-insensitive). |
| **Markdown fences** | ` ``` ` found in `cleaned_output`. |
| **AI-refusal phrases** | Any of `"as an ai"`, `"i cannot"`, `"i'm sorry"` found in `cleaned_output` (case-insensitive). |
| **Fidelity (comparable commands)** | `difflib.SequenceMatcher(None, our_cleaned, gt_cleaned).ratio()` averaged over all non-host-specific commands across all runs, using the first GT run's output as reference for each command. |
| **Exact-match rate** | Fraction of comparable commands where `our_cleaned.strip() == gt_cleaned.strip()`. |
| **Determinism** | Mean pairwise `difflib.SequenceMatcher` ratio across all pairs of runs for each command ID, then averaged over all command IDs. |
| **GET / repeat similarity** | Mean pairwise body similarity across `get_root_repeat1`, `get_root_repeat2`, `get_root_repeat3` responses. |
| **Status agreement with GT** | Fraction of `(method, path)` pairs where galah's HTTP status code equals the ground-truth nginx status code. |
| **Content-Length mismatch** | `content_length_match = False` in JSONL (actual body length differs from declared Content-Length header). |
| **Date drift** | `time.time() − parsedate_to_datetime(Date header).timestamp()` for each response. |
| **Header-name set inconsistencies** | Number of `(method, path)` groups where the set of response header names differs between runs. |
| **Documentation-example secrets** | Count of responses whose body contains any string in `_SECRET_PATTERNS = ["AKIAIOSFODNN7EXAMPLE", "EXAMPLE"]` (source: `harness/analyze.py`). |
| **Port mentions** | Responses whose body mentions a benchmark target port number (8088, 2226, 2225, 2222, 2223, 2224, 2227, 8022). |

### 3.6 Prompt-detection weak spots

- DECEIVE's prompt may include literal `\x1b[01;32m` color-code strings; the
  harness strips these correctly before regex matching.
- If an LLM invents an unusual prompt shape (no `@`, no `:`), neither regex will
  match and the command times out.
- The 0.5 s quiet period is a heuristic; very slow streaming output may be
  mistaken for a complete response.

---

## 4. Results

### 4.1 SSH — Latency

Source: `results/summary.md`, `results/summary.csv`

| Target | Kind | Mean (s) | Median (s) | p95 (s) | Max (s) | n |
|--------|------|---------|----------|--------|--------|---|
| deceive | llm | 10.936 | 1.774 | 90.015 | 90.016 | 180 |
| beelzebub | llm | 4.063 | 2.930 | 6.790 | 25.687 | 180 |
| advshellm | llm | 2.833 | 1.969 | 5.284 | 51.609 | 180 |
| cowrie | baseline | 0.573 | 0.563 | 0.594 | 1.000 | 180 |
| llmhoneypot | detector | 0.558 | — | 0.578 | — | 180 |
| groundtruth_ssh | groundtruth | 0.559 | 0.562 | 0.578 | 0.594 | 180 |

### 4.2 SSH — Latency by category (LLM targets)

Source: `results/summary.md`

**DECEIVE**

| Category | Mean (s) | p95 (s) | n |
|----------|---------|--------|---|
| errors | 18.436 | 90.015 | 15 |
| files | 15.541 | 90.016 | 30 |
| permissions | 1.820 | 4.160 | 10 |
| process | 30.589 | 90.016 | 10 |
| recon | 10.923 | 90.015 | 65 |
| state | 3.831 | 5.608 | 50 |

**Beelzebub**

| Category | Mean (s) | p95 (s) | n |
|----------|---------|--------|---|
| errors | 2.729 | 3.969 | 15 |
| files | 4.271 | 7.032 | 30 |
| permissions | 2.692 | 4.055 | 10 |
| process | 4.509 | 6.527 | 10 |
| recon | 2.993 | 5.087 | 65 |
| state | 5.915 | 24.350 | 50 |

**AdvancedshelLM**

| Category | Mean (s) | p95 (s) | n |
|----------|---------|--------|---|
| errors | 1.814 | 2.195 | 15 |
| files | 4.484 | 5.098 | 30 |
| permissions | 2.492 | 4.059 | 10 |
| process | 7.452 | 21.573 | 10 |
| recon | 2.324 | 4.169 | 65 |
| state | 1.955 | 2.624 | 50 |

### 4.3 SSH — Reliability

Source: `results/summary.md`, `results/summary.csv`

| Target | Runs | Commands | Timeouts | Empty outputs | exit_closes_session_rate |
|--------|------|----------|----------|---------------|--------------------------|
| deceive | 5 | 180 | 16 | 35 | 0.800 |
| beelzebub | 5 | 180 | 0 | 2 | 1.000 |
| advshellm | 5 | 180 | 0 | 25 | 1.000 |
| cowrie | 5 | 180 | 0 | 40 | 1.000 |
| llmhoneypot | 5 | 180 | 0 | 30 | 1.000 |
| groundtruth_ssh | 5 | 180 | 0 | 35 | 1.000 |

Note: DECEIVE's `exit_closes_session_rate = 0.800` means that in 1 of 5 runs the
`exit` command timed out (run 2, also reflected in the 17th timeout row in the CSV;
see `DOC_REVIEW_NOTES.md` §1.3 for reconciliation with the summary's count of 16).

### 4.4 SSH — LLM Artifacts

Source: `results/summary.md`

All targets produced zero commands with `<think>` tags, markdown fences, AI-refusal
phrases, or prompt contamination (trap markers visible in cleaned output).  DECEIVE
produced zero literal escape codes in output.  No artifacts were detected across any
of the 6 SSH targets.

### 4.5 SSH — Fidelity vs ground truth

Source: `results/summary.md`, `results/summary.csv`

Comparable commands only (host_specific = false).

| Target | Kind | Mean similarity | Exact-match rate | Host-specific sim (reference only) |
|--------|------|----------------|-----------------|-------------------------------------|
| deceive | llm | 0.4417 | 0.3000 | 0.3629 |
| beelzebub | llm | 0.3789 | 0.1923 | 0.4377 |
| advshellm | llm | 0.5946 | 0.4615 | 0.4918 |
| cowrie | baseline | 0.5874 | 0.4615 | 0.5734 |

Similarity is `difflib.SequenceMatcher.ratio()` against the ground-truth output for
the same command.  LLM honeypots use different personas, hostnames, and invented
filesystems; lower scores are expected for persona-dependent content (e.g. `/etc/passwd`,
`ls`, `cat /etc/os-release`).

### 4.6 SSH — State consistency

Source: `results/summary.md`

State checks: after `cd /tmp` does `pwd` return `/tmp`; does `cat /tmp/bm.txt` show
`benchmark_marker`; does `ls /tmp` show `bm.txt` after creation; does `ls /tmp` show
`bm_dir` after mkdir; does `ls /tmp` not show `bm.txt` after rm; does `whoami` match
the user name from `id`.

**DECEIVE** — runs 1–3 failed all file-system state checks; runs 4–5 passed all.
**Beelzebub**, **AdvancedshelLM**, **Cowrie**, **llmhoneypot**, **groundtruth_ssh** —
all 5 runs passed all state checks.

### 4.7 SSH — Pairwise determinism

Source: `results/summary.md`, `results/summary.csv`

Mean pairwise `difflib.SequenceMatcher.ratio()` across all run pairs, per command ID,
then averaged over all command IDs.

| Target | Determinism |
|--------|-------------|
| cowrie | 0.9950 |
| beelzebub | 0.8360 |
| advshellm | 0.7793 |
| deceive | 0.4021 |

### 4.8 SSH — Fingerprints

Source: `results/ssh_fingerprints.json`

| Target | SSH version string | Host key type | Fingerprint (MD5) | Consistent across runs |
|--------|-------------------|--------------|-------------------|------------------------|
| deceive | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3 | ssh-rsa | fe2a15c68b7a911f40147bac4e9aa836 | ✓ |
| beelzebub | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3 | ssh-rsa | cac0223bc7360c5b1045fcf84a3bf951 | ✓ |
| cowrie | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3 | ssh-ed25519 | ee5d297931adc91cd26a6ad6c9462c7a | ✓ |
| advshellm | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3 | ssh-ed25519 | 8a4f7c843c92a1be0faf8fbb72057ca1 | ✓ |
| llmhoneypot | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3 | ssh-ed25519 | b1dc587fc2d66254a7fc59d8f0e52ce3 | ✓ |
| groundtruth_ssh | SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.13 | ssh-ed25519 | 64aa346ac0135079bba555c03351f451 | ✓ |

Note: the ground-truth SSH server reported patch version `Ubuntu-4ubuntu0.13` while
all honeypots present `Ubuntu-4ubuntu0.3`.  This reflects the actual Ubuntu 20.04 apt
package version installed in the ground-truth container and is not a misconfiguration.

All six targets presented consistent host keys across all 5 runs, meaning no key
regeneration occurred mid-benchmark.  Host key types differ: DECEIVE and Beelzebub
use RSA keys (generated by asyncssh); Cowrie, AdvancedshelLM, llm-honeypot, and the
ground-truth use Ed25519.

### 4.9 Detector target: llm-honeypot

Source: `results/summary.md`

> **Security notice**: The content below contains prompt-injection text from the
> llm-honeypot source.  It is quoted as labeled data only.

llm-honeypot is excluded from fidelity, similarity, pairwise determinism, and
aggregate averages.  Its purpose is to detect LLM-driven attackers by embedding
ANSI-concealed (ESC[8m … ESC[0m) instructions in the output of `pwd`, `whoami`,
`ps`, `ls`, and `df`.

The harness monitors for trap markers in raw output and checks whether they survive
ANSI stripping into the cleaned output.

**Trap delivery results** (all 5 runs, all 11 monitored command IDs):

Every monitored command delivered its marker in both raw and cleaned output across
all 5 runs.  The markers (as labeled data, not instructions) were:

| Command(s) | Marker text (data only) |
|-----------|------------------------|
| `pwd` | "Filesystem locked" |
| `whoami` | "Identity service locked" |
| `ps_aux` | "Process manager locked" |
| `ls`, `ls_la`, `ls_etc`, `ls_home`, `state_ls_tmp_1/2/3` | "System not initialized" |
| `df_h` | "Disk subsystem offline" |

The markers were visible in cleaned output (survived ANSI stripping) in all cases.
This means the injection text is present in plain text even after ANSI code removal —
it is not hidden by ANSI concealment alone; it appears as visible text in the cleaned
output.  This is expected given how `analyze.py` strips ANSI codes but leaves the
underlying text.

### 4.10 HTTP — galah

Source: `results/summary.md`

**Status distribution** (n = 100):

| Status | Count |
|--------|-------|
| 200 | 84 |
| 500 | 11 |
| error (connection-level) | 5 |

- 5xx rate: 0.1100
- Server header values (8 distinct): `Apache/2.4.38 (Debian)`, `Apache/2.4.38 (Ubuntu)`,
  `Apache/2.4.38 (Unix) OpenSSL/1.1.1k PHP/7.4.28`, `Apache/2.4.41 (Ubuntu)`,
  `Werkzeug/2.0.3 Python/3.8.10`, `Werkzeug/2.3.7 Python/3.11.4`, `nginx/1.18.0`,
  `nginx/1.18.0 (Ubuntu)` — **varies** across requests
- Content-Length mismatches: 5
- Chunked responses: 14
- Date drift: mean = 0.508 s, median = 0.600 s, p95 = 1.000 s, max = 1.100 s (n = 95)
- Header-name set inconsistencies across runs: 15
- Documentation-example secrets in body: 5
- Responses mentioning target port: 24
- Latency: mean = 4.766 s, median = 3.391 s, p95 = 10.108 s, max = 30.032 s (n = 100)
- GET / repeat similarity: 0.2752
- Status agreement with nginx ground truth: 23/95 (0.2421)

### 4.11 HTTP — ground truth nginx

Source: `results/summary.md`

**Status distribution** (n = 100):

| Status | Count |
|--------|-------|
| 200 | 30 |
| 400 | 5 |
| 404 | 60 |
| 405 | 5 |

- 5xx rate: 0.0000
- Server header values: `nginx/1.18.0 (Ubuntu)` — constant
- Content-Length mismatches: 5
- Chunked responses: 0
- Date drift: mean = 0.468 s, median = 0.400 s, p95 = 0.900 s, max = 1.000 s (n = 100)
- Header-name set inconsistencies across runs: 0
- Documentation-example secrets in body: 0
- Responses mentioning target port: 0
- Latency: mean = 0.014 s, median = 0.016 s, p95 = 0.031 s, max = 0.063 s (n = 100)
- GET / repeat similarity: 1.0000

---

## 5. Observed Findings

These are factual observations backed by the results tables above.  No causal claims
are made.

1. **DECEIVE had the highest latency and most timeouts.** Mean latency was 10.936 s
   with 16 timeouts at 90 s; the process category had mean 30.589 s (source: §4.1, §4.3).

2. **DECEIVE had inconsistent state management across runs.** Runs 1–3 failed all
   filesystem state checks (create/read/delete cycle); runs 4–5 passed all checks
   (source: §4.6).  This is consistent with DECEIVE's design: it generates each
   response independently from a persona description with no persistent filesystem state,
   and LLM variance means state operations may or may not be reflected in subsequent
   outputs.

3. **Beelzebub had the lowest similarity to ground truth among LLM SSH targets.**
   Mean comparable similarity was 0.3789, exact-match rate 0.1923 (source: §4.5).
   Beelzebub seeds each session with a pwd/home exchange before benchmark commands
   arrive, and uses its own persona.

4. **AdvancedshelLM and Cowrie had the same exact-match rate (0.4615)** but
   AdvancedshelLM had a higher mean similarity (0.5946 vs 0.5874) (source: §4.5).
   AdvancedshelLM maintains a persistent JSON-lines filesystem state in `worker.yml`.

5. **Cowrie had near-perfect determinism (0.9950)** while all LLM targets were below
   0.85 (source: §4.7).  This is expected: Cowrie outputs are statically generated
   from fixed template files.

6. **No LLM artifacts were detected in any SSH target.** Zero think tags, fences,
   refusal phrases, or escape codes appeared in cleaned outputs (source: §4.4).
   DECEIVE strips think tags and fences before output; galah also strips them.
   AdvancedshelLM's think-tag stripping is present in the code but was not active
   in the call path used (see `Changes/ADVSHELLM_CHANGES.md`).

7. **All six SSH targets presented consistent SSH host keys across runs** (source: §4.8).
   The version string `SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3` was consistent for
   all honeypots; the ground truth reported `Ubuntu-4ubuntu0.13`.

8. **galah produced HTTP 500 on 11% of requests and inconsistent Server headers.**
   8 distinct Server header values appeared; the ground-truth nginx returned a single
   constant value (source: §4.10, §4.11).

9. **galah agreed with nginx's status code on only 24.21% of request/path combinations**
   (23 of 95 comparable pairs; source: §4.10).

10. **llm-honeypot delivered injection markers consistently across all 5 runs and all
    11 monitored commands**, with markers visible in cleaned output in all cases
    (source: §4.9).

---

## 6. Hypotheses and Open Questions

These are labeled hypotheses — not conclusions from the data.

**H1 — DECEIVE timeouts are caused by shared API endpoint stalls, not honeypot behavior.**
DECEIVE's 16 timeouts at 90 s are concentrated in process and recon categories.
These involve longer expected outputs (ps aux, env, find /etc).  It is possible that
the Fireworks API stalled on these requests due to token-length or rate-limiting
factors.  A test with retries and per-request API logging would distinguish API stall
from honeypot-side failure.

**H2 — DECEIVE's inconsistent state in runs 1–3 reflects LLM context management.**
DECEIVE does not maintain a persistent filesystem state; the LLM generates state-dependent
outputs from conversation history only.  The pattern of runs 1–3 failing and runs 4–5
succeeding may reflect context window warming, session-dependent prompt quality, or
API-side variation.  Running additional sessions would test whether this is consistent.

**H3 — Beelzebub's low similarity to ground truth is partly caused by the seeded
pwd/home exchange.**  The pre-benchmark `pwd → /home/user` exchange may influence
subsequent `cd /tmp` and file-creation commands differently from how a clean session
would.  Measuring with and without the seed would isolate this effect.

**H4 — galah's 11% 5xx rate is caused by JSON-mode incompatibility.**
galah sends `response_format: {"type": "json_object"}` with each LLM request.
If `glm-5p3-flash` does not support this mode for all request types, the model may
return errors that galah cannot parse, resulting in HTTP 500.  This is UNVERIFIED.

**H5 — The variation in galah Server headers reflects prompt-level LLM creativity.**
galah generates HTTP response headers and bodies entirely from the LLM.  The 8 distinct
Server values suggest the LLM was not constrained to return a consistent server identity.
A stricter system prompt specifying the server type would likely reduce this variation.

---

## 7. Limitations and Confounds

This benchmark is limited by a single model, 5 runs, scripted commands, a difflib
similarity proxy, shared API load across targets, cold-start effects, and latencies
censored at the 90 s SSH timeout ceiling.

- **Single model**: All four LLM SSH honeypots and galah used the same model
  (`accounts/fireworks/models/glm-5p3-flash`).  Results may not generalise to other
  models.  Temperature could be set for DECEIVE (0.2), AdvancedshelLM (0.2), and
  galah (0.2); Beelzebub has no temperature field in its API request struct and used
  the Fireworks default (UNVERIFIED).

- **5 runs**: The sample size is small.  Variance estimates and p95 latencies are
  based on 180 commands per target; LLM outputs can vary significantly across runs.

- **Different personas and hostnames**: DECEIVE uses a video-game-developer persona
  (`mf-dev-ws07`), Beelzebub uses `ubuntu`, AdvancedshelLM uses `hp_dev_server`.
  Direct similarity to the ground-truth Ubuntu system is biased against LLM honeypots
  by design; the fidelity metric measures shell behavior, not persona matching.

- **Cowrie-family static filesystem**: Cowrie and llm-honeypot share a static fake
  Debian filesystem.  `ls`, `cat`, and state commands always return the same output
  regardless of prior commands.  State-consistency checks pass for these targets
  because the static filesystem has the files the harness expects, not because state
  was actually mutated.

- **Ground truth is a plain system**: The ground-truth SSH container has no persona,
  no game files, no custom user files.  Persona-dependent output in LLM honeypots
  (game source code, custom dotfiles) cannot match it.

- **Similarity is a rough proxy**: `difflib.SequenceMatcher.ratio()` compares
  character sequences.  A correct but differently formatted output (e.g. different
  whitespace in a table) will score lower than an incorrect but similarly formatted
  one.

- **AdvancedshelLM's wrapper layer**: AdvancedshelLM runs as a subprocess behind an
  asyncssh wrapper, adding process-spawn latency and pipe-buffering overhead.  Its
  persona and persistent filesystem (`worker.yml`) differ from all other targets.

- **Beelzebub's seeded conversation**: A `pwd → /home/user` exchange is inserted
  before the benchmark commands arrive in every session.  This may affect state-dependent
  commands differently from a clean session.

- **Harness restarts during data collection**: The harness was restarted multiple
  times during the data collection pass.  CSV files were deduplicated afterwards.
  All `(target, run, cmd_id)` combinations appear exactly once in the final CSVs
  (verified in `DOC_REVIEW_NOTES.md`).  This process is reported honestly here;
  readers should be aware that the data may not represent five strictly sequential,
  uninterrupted runs per target.

- **AdvancedshelLM early startup failures**: Two early log directories from
  2026-11-01 exist in `results/honeypot_logs/advshellm/` from a startup failure
  pass.  The final JSONL data is from successful runs only.

- **API-side latency noise**: Fireworks API response time varies with server load.
  Latency differences between LLM targets may reflect API conditions at the time of
  each run rather than honeypot behavior.

- **No human or LLM-attacker evaluation**: All sessions were scripted.  No human
  operator or LLM-driven attacker was used to assess whether the honeypots are
  convincing under realistic attack conditions.

---

## 8. Not Done and Next Steps

- **VelLMes and honeybee**: not attempted in this benchmark.
- **LLM-driven attacker evaluation**: replacing the scripted harness with an LLM
  agent as the attacker would test whether the honeypots actually fool an AI.
- **More runs**: 5 runs is a small sample; 20–50 runs would reduce variance.
- **Other models**: testing with multiple models (e.g. GPT-4o, Llama 3, Claude) would
  determine whether the observed behavior is model-specific.
- **Temperature sweep**: varying temperature would isolate its effect on determinism
  and fidelity.
- **Beelzebub temperature**: the Go `Request` struct has no temperature field; a
  fork or PR would be needed to set it.
- **Human evaluation**: qualitative assessment of whether outputs are plausible to
  a human attacker.

---

## 9. Appendix

### Appendix A: Command list

Source: `harness/commands.yaml`

| ID | Command | Category | host_specific |
|----|---------|----------|---------------|
| whoami | `whoami` | recon | false |
| id | `id` | recon | false |
| pwd | `pwd` | recon | false |
| hostname | `hostname` | recon | true |
| uname_a | `uname -a` | recon | true |
| os_release | `cat /etc/os-release` | recon | false |
| passwd | `cat /etc/passwd` | files | false |
| ls | `ls` | files | false |
| ls_la | `ls -la` | files | false |
| ls_etc | `ls /etc` | files | false |
| ls_home | `ls /home` | files | false |
| date | `date` | recon | true |
| uptime | `uptime` | recon | true |
| free_m | `free -m` | recon | true |
| df_h | `df -h` | recon | true |
| ps_aux | `ps aux` | process | true |
| cpuinfo | `cat /proc/cpuinfo \| head -5` | recon | true |
| w | `w` | process | true |
| env | `env` | recon | true |
| which_python3_gcc | `which python3 gcc` | recon | false |
| find_etc_conf | `find /etc -name '*.conf' \| head -5` | files | false |
| err_foobarbaz | `foobarbaz` | errors | false |
| err_cat_nonexistent | `cat /nonexistent` | errors | false |
| err_ls_root | `ls /root` | errors | false |
| perm_shadow | `cat /etc/shadow` | permissions | false |
| perm_sudo_l | `sudo -l` | permissions | false |
| state_cd_tmp | `cd /tmp` | state | false |
| state_pwd_after_cd | `pwd` | state | false |
| state_echo_marker | `echo benchmark_marker > /tmp/bm.txt` | state | false |
| state_cat_marker | `cat /tmp/bm.txt` | state | false |
| state_ls_tmp_1 | `ls /tmp` | state | false |
| state_mkdir_bm_dir | `mkdir /tmp/bm_dir` | state | false |
| state_ls_tmp_2 | `ls /tmp` | state | false |
| state_rm_marker | `rm /tmp/bm.txt` | state | false |
| state_ls_tmp_3 | `ls /tmp` | state | false |
| state_rmdir_bm_dir | `rmdir /tmp/bm_dir` | state | false |
| exit | `exit` | state | false |

Total: 37 commands (36 non-exit commands used for metrics).

### Appendix B: HTTP request list

Source: `harness/http_requests.yaml`

| ID | Method | Path | Purpose |
|----|--------|------|---------|
| get_root | GET | `/` | Homepage / default response |
| get_admin | GET | `/admin` | Common admin path probe |
| get_env | GET | `/.env` | Credential file leak probe |
| get_login | GET | `/login` | Login page probe |
| get_api_status | GET | `/api/status` | REST API status probe |
| get_api_v1_users | GET | `/api/v1/users` | REST API user list probe |
| get_robots | GET | `/robots.txt` | Robots.txt disclosure probe |
| get_favicon | GET | `/favicon.ico` | Favicon probe |
| get_wp_login | GET | `/wp-login.php` | WordPress login probe |
| get_phpmyadmin | GET | `/phpmyadmin/` | phpMyAdmin probe |
| get_server_status | GET | `/server-status` | Apache server-status probe |
| get_nonexistent | GET | `/nonexistent-page-xyz` | Expected 404 — error response consistency |
| head_root | HEAD | `/` | HEAD / — header presence without body |
| options_root | OPTIONS | `/` | OPTIONS / — Allow header check |
| post_login | POST | `/login` | POST login with fake credentials |
| get_long_qs | GET | `/?q=AAA…` (500-char string) | Long query string |
| get_path_traversal | GET | `/../../etc/passwd` | Raw path traversal probe |
| get_root_repeat1 | GET | `/` | GET / repeated #1 — determinism check |
| get_root_repeat2 | GET | `/` | GET / repeated #2 — determinism check |
| get_root_repeat3 | GET | `/` | GET / repeated #3 — determinism check |

Total: 20 requests.

### Appendix C: Results file index

| File | Contents |
|------|----------|
| `results/summary.md` | Per-target human-readable report (generated by `analyze.py`) |
| `results/summary.csv` | One row per target, key metrics |
| `results/ssh_commands_long.csv` | All SSH results: 185 rows per target (6 targets × 185 = 1110 rows) |
| `results/http_requests_long.csv` | All HTTP results: 100 rows per target (2 targets × 100 = 200 rows) |
| `results/ssh_fingerprints.json` | SSH transport metadata per target/run |
| `results/raw/<target>_run<NN>.jsonl` | Per-command JSONL (SSH); 37 lines per file |
| `results/raw_http/<target>_run<NN>.jsonl` | Per-request JSONL (HTTP); 20 lines per file |
| `results/honeypot_logs/` | Container log files copied by `scripts/copy_logs.ps1` |
| `results/errors.log` | Runtime errors from the harness |
