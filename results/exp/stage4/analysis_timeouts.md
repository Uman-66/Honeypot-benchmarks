# Stage 4: timeout attribution, max-tokens enforcement, container-lifetime control

Read-only analysis of the existing Stage 4 data plus one small control experiment.
No target was re-run for Part A; Part B adds new data under
`results/exp/lifetime_control/` only.

Data used:

| Set | Rows | Proxy log |
|---|---|---|
| Stage 4 `raw/` (prompt timing, 7 SSH targets x 20 runs) | 140 files | `results/exp/stage4/api_proxy_log.jsonl` |
| Stage 4 `raw_quiet/` (quiet timing, 4 LLM targets x 2 runs) | 8 files | same |
| Stage 2 validation passes (A quiet / B prompt / C quiet) | 12 files | `results/exp/validation/api_proxy_log.jsonl` |

All numbers below come from `results/exp/stage4/attrib_timeouts.py` (read-only,
prints to stdout).

## Method: how a request is attributed to a slot

The proxy stamps `ts` **before** forwarding the request and writes the log line
**after** the response completes (`harness/api_proxy.py:188-261`). File order is
therefore completion order, not start order: a 250 s generation is written long
after the *next* slot's `slot_start` marker.

Attribution used here:

* a request belongs to the slot whose `slot_start` marker has the latest `ts`
  (= request start) that is `<=` the request's own `ts`;
* inside a slot, every proxy entry is assigned at most once, to the command with
  the latest `t_send <=` request `ts`;
* Stage 2's validation proxy log has no markers, so the window for each pass
  file is built from that file's own command timestamps.

Class definitions:

* **api** - the matched request ran `>= 120 s`, or started so late that an
  on-time reply was impossible;
* **target** - the proxy replied well before the timeout (API duration reported)
  but the harness never saw the prompt;
* **unmatched** - no proxy request was assigned to the command.

The earlier slot-level analysis (`verify_s4.py`) segments the proxy log by file
order. That is fine for call counts, but it misassigns long generations; the
consequence is quantified at the end of Part A.

## Part A.1 - Timeout attribution

### Stage 4 (`raw/` + `raw_quiet/`)

86 timed-out SSH rows (exit rows excluded).

| Class | n | meaning |
|---|---:|---|
| api-side | 9 | request ran 241.6-291.4 s; harness gave up at 120 s |
| target-side | 66 | API answered in 1.5-28.1 s, harness saw no prompt |
| unmatched | 11 | no proxy request for the command |

Per target and mode:

| Target | Mode | api | target | unmatched |
|---|---|---:|---:|---:|
| beelzebub | prompt | 2 | 0 | 2 |
| beelzebub | quiet | 1 | 0 | 1 |
| deceive | prompt | 6 | 15 | 8 |
| vellmes | prompt | 0 | 45 | 0 |
| vellmes | quiet | 0 | 6 | 0 |

API duration per class:

| Class | n | min | p50 | p90 | max |
|---|---:|---:|---:|---:|---:|
| api-side | 9 | 241.6 s | 264.1 s | 276.7 s | 291.4 s |
| target-side | 66 | 1.5 s | 5.4 s | 6.8 s | 28.1 s |

Per command (timed-out rows only):

| Target | Command | api | target | unmatched |
|---|---|---:|---:|---:|
| beelzebub | env | 2 | 0 | 0 |
| beelzebub | ls | 1 | 0 | 0 |
| beelzebub | ls_la | 0 | 0 | 1 |
| beelzebub | which_python3_gcc | 0 | 0 | 2 |
| deceive | ps_aux | 6 | 0 | 0 |
| deceive | cpuinfo | 0 | 0 | 6 |
| deceive | hostname / id / pwd / whoami | 0 | 8 | 0 |
| deceive | perm_sudo_l | 0 | 4 | 0 |
| deceive | state_cd_tmp | 0 | 2 | 0 |
| deceive | state_pwd_after_cd | 0 | 1 | 0 |
| deceive | id / whoami (run 20) | 0 | 0 | 2 |
| vellmes | ps_aux | 0 | 21 | 0 |
| vellmes | env | 0 | 19 | 0 |
| vellmes | perm_sudo_l | 0 | 4 | 0 |
| vellmes | whoami | 0 | 3 | 0 |
| vellmes | ls_etc | 0 | 2 | 0 |
| vellmes | state_cd_tmp | 0 | 2 | 0 |

Reading the two classes:

* **api-side (9).** Every one is a 65,536-token generation that ran 242-291 s,
  started within 0.1 s of the command, and made the harness time out. They are
  the only timed-out rows in this dataset that hit the model ceiling.
* **target-side (66).** 51 of them are VelLMes: the API returned in 4.5-7.8 s
  with exactly 800 completion tokens (its cap), and the target never wrote the
  reply to the terminal. The rest are DECEIVE rows whose reply arrived in
  1.5-28.1 s.
* **unmatched (11).** 9 of the 11 were issued while a `>= 120 s` request from the
  same run was still in flight (the target was blocked and never issued a second
  request); the other 2 are DECEIVE run 20 `whoami`/`id`, where no request was
  logged at all and the first successful command (`pwd`) then took 20.9 s - a
  cold start, not an API timeout.

Timed-out rows whose matched API `completion_tokens` is at or near 65,536: **9**
(all of the api-side class).

### Stage 2 validation passes

12 timed-out rows over 444 rows.

| Class | n | API duration |
|---|---:|---|
| api-side | 0 | - |
| target-side | 9 | 2.2-6.5 s (p50 4.4 s) |
| unmatched | 3 | - |

Per target and command: deceive quiet `ls_etc` 1 unmatched, `perm_sudo_l` 3
target; vellmes prompt `perm_sudo_l` 1 target, `ps_aux` 1 unmatched; vellmes
quiet `env` 1, `ls_etc` 1, `perm_sudo_l` 2, `ps_aux` 1 target + 1 unmatched,
`state_cd_tmp` 1. No Stage 2 timeout is API-side and none is near the token
ceiling; all matched timeouts are the VelLMes/DECEIVE "reply produced, never
surfaced" pattern.

## Part A.2 - Max-tokens enforcement

Distribution of `completion_tokens` over the requests attributed to each target
in Stage 4 (`raw/` + `raw_quiet/`; HTTP targets from their own windows):

| Target | n | p50 | p95 | max | documented cap | over cap | max reasoning tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| AdvancedshelLM | 792 | 51 | 533 | 4,096 | 4,096 | 0 | 1,415 |
| VelLMes | 814 | 56.5 | 800 | 800 | 800 | 0 | 800 |
| DECEIVE | 806 | 73 | 1,221.2 | 65,536 | none | n/a | 15,373 |
| Beelzebub | 789 | 55 | 681.8 | 65,536 | none / unknown | n/a | 577 |
| galah | 400 | 388 | 3,232.2 | 65,536 | not recorded | n/a | 65,536 |
| cowrie, llm-honeypot, ground-truth SSH/HTTP | - | - | - | - | no LLM call | - | - |

Both documented caps are respected exactly: AdvancedshelLM peaks at 4,096 and
VelLMes peaks at 800, with no request above either cap. The three targets that
reach 65,536 are the ones with no documented cap. For galah all 8 ceiling
responses report `reasoning_tokens = 65,536`, i.e. the provider's ceiling was
spent entirely on reasoning; DECEIVE's are near-zero reasoning (visible text),
which matches its documented "no output cap".

### Where `max_tokens` is set for AdvancedshelLM

The wrapper runs `codebase/advancedShellm.py --provider openai` as a child
(`docker/advshellm_ssh_wrapper.py:117-133`), and the child inherits the
container environment.

* Worker calls: `shelLM/AdvancedshelLM/codebase/LLM_Plugins/api_clients/openai_client.py:155`
  reads `_max_tokens = int(os.environ.get("MAX_TOKENS", "4096"))` and puts it in
  the request body at `:160` (`"max_tokens": _max_tokens`). Every worker reply
  goes through `send_chat` -> `_send_chat_completions` (`:135-139`), so every
  worker call passes the cap. `docker/advshellm.compose.yaml:61` sets
  `MAX_TOKENS: "4096"` for the container.
* Two code paths do **not** pass 4,096, and neither is reachable in this
  configuration:
  * `_send_responses_api` (`:213-262`) sends only `model`/`instructions`/`input`
    - no token field at all. It is selected only when the model name is in
    `RESPONSES_API_MODELS` or contains `codex` (`:40-42`); the benchmark model is
    `accounts/fireworks/models/glm-5p3-flash`.
  * `EinfraClient` hardcodes `"max_tokens": 16384`
    (`LLM_Plugins/api_clients/einfra_client.py:75`). It is instantiated only for
    `--provider einfra` or for the manager when `--manager_config` is passed
    (`advancedShellm.py:899-911`). The wrapper always passes
    `--provider openai` and never passes `--manager_config`.
* The manager path is off: `SUPERVISE: "0"` in compose, and when it is on the
  manager also uses `OpenAIClient`, i.e. the same 4,096 cap
  (`advancedShellm.py:911`, `:881`).
* `shelLM/LinuxSSHbot.py:53` (hardcoded `max_tokens = 800`, `gpt-3.5-turbo-16k`)
  is a separate legacy entry point that the wrapper does not run.

Conclusion: in this benchmark every AdvancedshelLM API call passes
`max_tokens = 4096`, and the data agrees (792 requests, max 4,096, none above).

### Are the 65,536-token completions attributed to AdvancedshelLM a different call type?

No - they are **not AdvancedshelLM calls at all**. With request-start attribution
all 17 requests with `>= 60,000` completion tokens belong to galah (8), DECEIVE
(6) and Beelzebub (3). The slot-level (file-order) segmentation in
`verify_s4.py` blamed AdvancedshelLM and VelLMes for several of them only because
their log lines were written after the next slot's marker; e.g.

| request start | duration | owner (request start) | owner (file order) |
|---|---:|---|---|
| 08:10:46 | 258 s | galah | AdvancedshelLM |
| 09:33:42 | 253 s | galah | VelLMes |
| 12:06:03 | 254 s | galah | Beelzebub |
| 12:18:59 | 280 s | galah | VelLMes |
| 12:40:33 | 277 s | galah | DECEIVE |
| 13:00:48 | 289 s | galah | VelLMes |

Because AdvancedshelLM's peak is exactly 4,096 and VelLMes' is exactly 800, no
different call type is needed to explain the ceiling rows: they come from the
uncapped targets. The question is settled by the data, so nothing is left
UNVERIFIED here for AdvancedshelLM.

## Part A.3 - Statements in the repo vs the data

Files checked: `BENCHMARK.md` (config table, lines 182-183) and
`report/honeypot_report_v2.tex` (`tab:config`, lines 136-137). Neither was
edited.

| Statement | Data | Verdict |
|---|---|---|
| AdvancedshelLM max tokens 4096 (`BENCHMARK.md:182`, `.tex:136`) | max 4,096 over 792 requests, 0 above | not contradicted |
| VelLMes max tokens 800 (`BENCHMARK.md:183`, `.tex:137`) | max 800 over 814 requests, 0 above | not contradicted |
| DECEIVE has no output-token cap (`BENCHMARK.md:193-197`) | ceiling responses with ~0 reasoning and full visible text | consistent |
| Beelzebub and galah caps "not exposed" / "not recorded" | both reach 65,536 | consistent with "unknown" |
| "DECEIVE produced 2 oversized outputs, maximum 135,108 characters" (`BENCHMARK.md:196-197`) | published batch: 2 oversized, 135,108 chars (confirmed); Stage 4: 6 oversized, 142,810 chars | batch-specific number, not a cap statement; not a contradiction, but it does not hold for Stage 4 |
| "AdvancedshelLM ... MAX_TOKENS 4096" implied to be violated by 65,536-token rows (earlier reading of the Stage 4 proxy log) | those rows belong to galah/DECEIVE/Beelzebub | resolved: misattribution, no contradiction |

No statement about the two documented caps is contradicted by the data.

## Part B - Container-lifetime control (new data)

Question: does the monotone latency rise and the 16/180 timeouts of the
published batch come from reusing **one long-lived container**? Stage 4 recreates
the container every slot and is flat; the published batch kept one container for
all five runs.

### Setup

`harness/run_lifetime_control.py` starts Beelzebub once (proxy overlay as in
Stage 4), then runs 10 consecutive sessions against the same container:
`run_ssh.py --runs 1 --run-index k --timing prompt`, 120 s timeout, masking on,
36 commands per session. No container recreate, restart or `docker down` between
runs. Output only under `results/exp/lifetime_control/beelzebub_persistent/`.

| Item | Value |
|---|---|
| container id | `e85c64992b2c4723362a36ff38449fdcb4c101c89169002b7b4ac9fafdf7f155` |
| `State.StartedAt` | `2026-11-22T19:07:05.078776169Z` |
| image | `sha256:f54cfa99d5cbe8e5386c1f974d2f630311b371628b81d62d41d78eb2e15c53e6` |
| container state before/after every run | identical id and StartedAt (`container_unchanged=True` x10) |
| container state at end | identical to the start (`container_never_recreated=True`) |
| proxy calls | 360 (36 per run; guard 45 never tripped) |
| cost | $0.8210 (cap $1.50) |
| teardown | proxy stopped, `docker ps -q` empty (0 containers) |
| safety stops | none |

Container identity is constant across all ten sessions: the same id and the same
`StartedAt` were recorded before run 1, after every run, and at the end, so no
recreate happened between runs.

### Per-run series (persistent container)

| Run | median s | p95 s | timeouts | calls | mem | container log | oversized |
|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 3.8805 | 8.92 | 0 | 36 | 11.14 MiB | 38,143 B | 0 |
| 2 | 3.9535 | 7.33 | 0 | 36 | 11.68 MiB | 75,192 B | 0 |
| 3 | 4.0860 | 8.70 | 0 | 36 | 12.22 MiB | 112,429 B | 0 |
| 4 | 3.8330 | 8.83 | 0 | 36 | 12.82 MiB | 149,977 B | 0 |
| 5 | 4.1345 | 7.24 | 0 | 36 | 13.14 MiB | 187,710 B | 0 |
| 6 | 5.1180 | 9.17 | 0 | 36 | 12.57 MiB | 226,510 B | 0 |
| 7 | 4.3275 | 9.29 | 2 | 36 | 14.35 MiB | 436,216 B | 1 |
| 8 | 5.4275 | 13.81 | 0 | 36 | 15.96 MiB | 497,396 B | 0 |
| 9 | 5.4390 | 10.34 | 2 | 36 | 16.91 MiB | 702,531 B | 1 |
| 10 | 5.9460 | 13.97 | 2 | 36 | 20.35 MiB | 906,557 B | 1 |

Spearman rank correlation against run index (permutation test, 20,000 draws,
seed 20261122):

| Series | rho | p (two-sided) |
|---|---:|---:|
| median latency vs run | **0.915** | **0.0006** |
| timeouts vs run | 0.722 | 0.035 |

First-half median 3.95 s, second half 5.43 s (+37%); per-run median rises from
3.83 s (run 4) to 5.95 s (run 10). Memory and container log size also grow
monotonically (11.1 -> 20.4 MiB, 38 kB -> 907 kB).

All six timeouts fall in the three runs that produced a ceiling response: the
proxy logged three 65,536-token generations (315 s, 298 s, 287 s) in runs 7, 9 and
10, and each of those runs has exactly 2 timed-out commands. The other seven runs
have none.

### Stage 4 fresh-container series (Beelzebub, 20 runs)

| Run | median s | timeouts | | Run | median s | timeouts |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 2.273 | 0 | | 11 | 2.194 | 0 |
| 2 | 2.063 | 0 | | 12 | 2.010 | 0 |
| 3 | 2.450 | 0 | | 13 | 1.871 | 0 |
| 4 | 2.694 | 2 | | 14 | 2.288 | 0 |
| 5 | 1.983 | 0 | | 15 | 2.417 | 0 |
| 6 | 2.136 | 0 | | 16 | 2.227 | 0 |
| 7 | 1.707 | 0 | | 17 | 2.344 | 0 |
| 8 | 2.196 | 0 | | 18 | 2.988 | 0 |
| 9 | 3.827 | 2 | | 19 | 2.958 | 0 |
| 10 | 2.243 | 0 | | 20 | 3.114 | 0 |

| Series | rho | p (two-sided) |
|---|---:|---:|
| median latency vs run | 0.373 | 0.108 |
| timeouts vs run | -0.231 | 0.380 |

No significant drift; the two timeout runs (4 and 9) are the two ceiling runs.

### Side by side

| | persistent (this control) | fresh per slot (Stage 4) |
|---|---|---|
| runs | 10 | 20 |
| median-of-medians | 4.231 s | 2.258 s |
| median range | 3.833 - 5.946 s | 1.707 - 3.827 s |
| first half -> second half | 3.95 -> 5.43 s | 2.26 -> 2.42 s |
| rho (median vs run), p | 0.915, p=0.0006 | 0.373, p=0.108 |
| timeouts | 6/360 (1.7%) | 4/720 (0.6%) |
| rho (timeouts vs run), p | 0.722, p=0.035 | -0.231, p=0.380 |

What this supports: the persistent series is **not** flat like the fresh series.
It shows a statistically significant upward drift in median latency and more
timeouts than the fresh series, so the hypothesis "container reuse is harmless
for Beelzebub" is not supported by this control.

What stays UNVERIFIED:

* **causality.** The two series differ in time of day, machine load and the
  number of ceiling responses, and 3 of 10 persistent runs hit a 65,536-token
  generation versus 2 of 20 fresh runs. The timeouts are produced by those
  ceiling responses (each affected run has exactly 2), not demonstrably by
  container age.
* whether the latency drift would continue past 10 sessions or saturate;
* whether the memory/log growth (11.1 -> 20.4 MiB, 38 -> 907 kB) affects
  latency. No causal link is claimed.
* 10 runs is a small sample; the timeout correlation (p=0.035) is weaker than
  the latency correlation (p=0.0006).

The published batch's 16/180 timeouts and 2.16 -> 7.09 s rise are consistent in
direction with this control, but the control does not reproduce their magnitude
and cannot single out container lifetime as the cause.

## Reproduce

```
.venv-hb\Scripts\python.exe results/exp/stage4/attrib_timeouts.py
.venv-hb\Scripts\python.exe harness/run_lifetime_control.py --runs 10 \
    --out results/exp/lifetime_control/beelzebub_persistent \
    --timeout 120 --call-limit 45 --cost-cap 1.5
.venv-hb\Scripts\python.exe -m pytest tests -q
```
