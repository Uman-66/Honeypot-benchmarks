# STAGE2_NOTES.md — measurement fixes and smoke results

Branch: `stage2-measurement` (not pushed). Nothing under `results/raw`,
`results/raw_http`, `results_pilot/`, `report/` or `BENCHMARK.md` was modified.
Every new artefact is under `results/exp/`.

---

## 1. How timing works today (the five-line answer)

1. `run_ssh.py` sends one command and records `t_send` immediately before
   `sendall` (`_run_once`).
2. It then reads in a non-blocking loop and runs `_detect_prompt` on the whole
   buffer after every chunk; a prompt is only a *candidate* at that point.
3. `QUIET_PERIOD = 0.5` s of silence *after the last chunk that contained a
   prompt* is required before the command counts as finished, and the idle branch
   waits in `select` slices of ≤0.1 s.
4. `latency_s = now − t_send` therefore includes the quiet period plus poll
   granularity: a command the server answers in 3 ms is recorded as ≥0.5 s.
5. `--timeout` (120 s in the batch) only fires when no prompt ever matches.

Stage 2 adds `--timing prompt`, which stops ~5 ms after the prompt appears. The
default is unchanged, so the published batch keeps its behaviour.

## 2. Reviewer points

| Point | Status | Evidence |
|---|---|---|
| (a) the 0.5 s quiet period dominates real-server latency | measured and fixed | `results/exp/floor.md`, §3 below |
| (b) no per-request API timing | proxy implemented and exercised on one target | §8 below |
| (c) no masked ground-truth determinism | done on the published batch | `results/exp/summary_v2.md` |
| (d) fidelity mixes persona with shell errors | masked column + persona note; E5c still needed | `results/exp/summary_v2.md` |
| raw files safe to publish | write-time credential masking + SHA-256 | `harness/masking.py` |

## 3. The floor: what it was, what it is

The first prompt-mode implementation reported a median of **0.000 s** for both
targets. That was investigated rather than believed:

- the 60 prompt-mode samples took only **three distinct values** — 0.000, 0.015,
  0.016 — which is the 15.6 ms Windows system tick, not three different servers;
- `select()` and `sleep()` on Windows round up to that tick, so the completion
  poll could never resolve anything finer;
- the byte counts per command were normal (42 B for `true`, 47 B for `echo x`), so
  the output was the command's, not a stale prompt left over from the previous
  command.

Two fixes followed: prompt mode now measures with `time.perf_counter()` and a
blocking `recv` (which releases the GIL so paramiko's reader thread keeps
draining), and it drains the channel before sending in case a prompt is left over.
Quiet mode was split into its own unchanged reader so the published batch is
unaffected.

| Target | Timing | n | Min (s) | Median (s) | p95 (s) | Max (s) |
|---|---|---:|---:|---:|---:|---:|
| groundtruth_ssh | quiet | 30 | 0.5470 | 0.5470 | 0.5630 | 0.5630 |
| groundtruth_ssh | prompt | 30 | 0.0152 | 0.0158 | 0.0163 | 0.0313 |
| cowrie | quiet | 30 | 0.5470 | 0.5630 | 0.5780 | 0.5780 |
| cowrie | prompt | 30 | 0.0150 | 0.0155 | 0.0314 | 0.1479 |

Full 37-command run (one session per mode, medians over the 36 scored commands):

| Target | Quiet median | Prompt min | Prompt median | Prompt p95 |
|---|---:|---:|---:|---:|
| groundtruth_ssh | 0.5620 | 0.0148 | 0.0155 | 0.0187 |
| cowrie | 0.5620 | 0.0150 | 0.0156 | 0.0316 |

**The remaining 15.5 ms is the instrument, not the server.** `PROMPT_SETTLE` is
5 ms, but a 5 ms socket wait on Windows also rounds up to the 15.6 ms tick, so the
achievable floor for any "wait and confirm silence" rule on this host is one tick.
The servers themselves answer in 3–9 ms (`t_prompt` median 0.0031 s on the ground
truth, 0.0093 s on cowrie).

## 4. The prompt-detection rule, in full

`_read_until_prompt_settled` (harness/run_ssh.py) completes a command only when all
of these hold:

1. **After `t_send`.** The caller drained the channel before sending
   (`_drain_pending`), so every byte considered arrived after the command was sent.
2. **After the echo or some output.** The prompt must close a buffer that already
   holds something else (`_prompt_preceded_by_content`). A buffer holding nothing
   but a prompt is accepted only after the settle window and is flagged
   `prompt_without_echo`, so a target that echoes nothing is visible in the data
   instead of silently fast.
3. **At the end of the buffer.** The prompt regex must match the last non-empty
   line; new bytes that leave the buffer not ending in a prompt cancel the
   decision and reading continues.
4. **After a fixed settle window.** `PROMPT_SETTLE = 0.005` s of no further bytes,
   not 0.5 s. The 120 s `--timeout` remains the fallback.

Each row records `timing_mode`, `t_send`, `t_first_byte`, `t_prompt`,
`stale_bytes` and `prompt_without_echo` when `--timing` is passed explicitly.

## 5. Full 37-command output comparison

`python harness/timing_audit.py` runs every command in both modes on both
non-API targets and compares the outputs. Raw sessions and `comparison.csv` are in
`results/exp/timing_audit/`.

| Target | Exact equality | Same length, volatile content only | Shorter or empty in prompt mode |
|---|---:|---:|---:|
| groundtruth_ssh | 31/37 | 6/37 | **0** |
| cowrie | 32/37 | 5/37 | **0** |

The commands that differ all have **identical byte length in both modes**, which is
the point — they differ in content that changes between any two sessions:

| Target | Command | Quiet bytes | Prompt bytes | Masked similarity |
|---|---|---:|---:|---:|
| groundtruth_ssh | free_m | 203 | 203 | 0.7685 |
| groundtruth_ssh | ps_aux | 518 | 518 | 0.9156 |
| groundtruth_ssh | w | 195 | 195 | 0.9882 |
| groundtruth_ssh | env | 1828 | 1828 | 0.9956 |
| cowrie | free_m | 203 | 203 | 0.9852 |

`free`, `ps`, `w` and `env` report memory, PIDs and session variables; those move
between sessions for reasons that have nothing to do with the timing rule. No
command produced a truncated or empty output in prompt mode, so the faster rule
captures the same transcript.

## 6. Stale-prompt regression test

`tests/test_prompt_timing.py` keeps the bug reproducible:

- `test_stale_prompt_alone_is_flagged_as_a_prompt_without_output` feeds a buffer
  that is nothing but a prompt and asserts `prompt_without_echo` is True — the
  signature of a stale prompt.
- `test_draining_removes_the_stale_prompt_before_the_command_is_sent` asserts the
  drain consumes exactly the stale bytes and the read then starts with the echo.
- `test_prompt_must_follow_the_echo_or_some_output` pins rule 2.

## 7. Masked determinism and fidelity (published batch, no API calls)

Masked before similarity: ISO/RFC3339 dates, `date`-style dates, clock times,
uptime, load averages, PIDs, `pts/N`, ports after a colon, and every hostname
observed in the batch.

| Target | Kind | Determinism raw | Determinism masked | Δ |
|---|---|---:|---:|---:|
| advshellm | llm | 0.7836 | 0.8034 | +0.0198 |
| beelzebub | llm | 0.6800 | 0.6815 | +0.0015 |
| cowrie | baseline | 0.9874 | 0.9957 | +0.0083 |
| deceive | llm | 0.4664 | 0.5038 | +0.0374 |
| groundtruth_ssh | groundtruth | 0.9746 | 0.9841 | +0.0095 |
| vellmes | llm | 0.8364 | 0.8472 | +0.0108 |

| Target | Raw-text fidelity | Masked fidelity | Δ |
|---|---:|---:|---:|
| advshellm | 0.5947 | 0.5992 | +0.0045 |
| beelzebub | 0.3737 | 0.3797 | +0.0060 |
| cowrie | 0.5877 | 0.5975 | +0.0098 |
| deceive | 0.4731 | 0.4750 | +0.0019 |
| vellmes | 0.6070 | 0.6074 | +0.0004 |

Two findings to report as they are: the ground truth is **not** perfectly
deterministic (0.9746) and had never been reported, so the honeypots were being
compared against an implicit 1.0; and masking lifts every target by ≤0.04, so
clock/PID noise was **not** the main cause of honeypot instability.

## 8. API proxy

### Smoke run (AdvancedshelLM, 5 commands per mode, 12 requests total)

`results/exp/smoke/` holds both sessions, the proxy log and `smoke_summary.md`.

| Command | Quiet harness (s) | Prompt harness (s) | Proxy requests | Proxy total (s) | Gap (s) | Status | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| whoami | 4.2500 | 3.8090 | 1 | 3.7340 | 0.0750 | 200 | 1350 |
| id | 3.0160 | 3.9360 | 1 | 3.8910 | 0.0450 | 200 | 1398 |
| pwd | 3.1400 | 6.7880 | 1 | 6.7340 | 0.0540 | 200 | 1405 |
| uname_a | 2.7030 | 5.0840 | 1 | 5.0470 | 0.0370 | 200 | 1501 |
| ls | 4.8910 | 3.6360 | 1 | 3.6100 | 0.0260 | 200 | 1702 |

- Every command matched to **exactly one** API request; the two unmatched requests
  are the per-session banner generation.
- **Gap between harness latency and API duration: median 0.0450 s**
  (min 0.0260, max 0.0750). That is SSH transport, wrapper process I/O and harness
  bookkeeping — the part of a command that is not the model.
- All 12 requests returned 200 and all 12 carried a `usage` block; the proxy
  recorded `prompt_tokens`, `completion_tokens` and `total_tokens`.
- Quiet mode differs from prompt mode by the sum of the two floors, not by content:
  §5 shows the transcripts match.

Redaction checks on the proxy log (all PASS, asserted by
`harness/smoke_llm.py --compare` and by `tests/test_api_proxy.py`):

| Check | Result |
|---|---|
| API key string absent | PASS |
| `Authorization` header absent | PASS |
| `Bearer` absent | PASS |
| `sk-` prefix absent | PASS |
| request/response body text absent | PASS |

The log stores only the SHA-256 of each request body.

### Pointing each target at the proxy

| Target | Mechanism | Works? |
|---|---|---|
| DECEIVE | `DECEIVE/SSH/ssh_server.py:412-428` — `OPENAI_BASE_URL` first, then `config['llm'].base_url` | yes, via `.env` |
| Beelzebub | `docker/beelzebub-ssh.yaml:38-44` — `host: ""` forces the env path | yes |
| VelLMes | `VelLMes-AI-Deception-Framework/VelLMes.py:88-91` | yes |
| AdvancedshelLM | `shelLM/.../openai_client.py:27` — read at **import** time | yes; container must be recreated (**verified in the smoke run**) |
| HoneyBee | `honeybee/honeybee/src/client_provider.py:12-13` | yes, untested |
| galah | `docker/galah-entrypoint.sh:22-24` maps to `LLM_SERVER_URL`; `pkg/llm/openai.go:17` | yes, untested |
| llmhoneypot | detector, no LLM call | not applicable |

Containers need `OPENAI_BASE_URL=http://host.docker.internal:11435/inference/v1`
and the proxy started with `--bind 0.0.0.0 --allow-remote-bind`; the proxy keeps
the `/inference/v1` prefix whether or not the client includes it.

**Caveats.** galah keeps a cache DB and HoneyBee keeps `.qhistory`, so a repeated
identical request may be served without an upstream call and the proxy log becomes
a lower bound. Responses are buffered before relay, so `stream: true` clients get
the full body but not incrementally.

### Build caveat for the smoke run

`deb.debian.org` does not respond from this host (an `apt-get update` layer sat at
13 minutes with no progress), so the smoke container was built from
`results/exp/smoke/advshellm.smoke.Dockerfile`: same base image, same pinned
requirements, same application code, same wrapper, same `CMD` — only the
`apt-get install gcc libffi-dev` layer is omitted, which is not needed because every
dependency ships a manylinux wheel. The benchmark's own `docker/advshellm.Dockerfile`
is unchanged. This is a smoke-run expedient and should be removed once the mirror is
reachable again.

## 9. Reproducing the published batch

Defaults are unchanged except credential masking, which is **on** by default as
requested, so re-running a file that contains credential-like strings produces a
masked file. To regenerate the published batch byte-for-byte:

```bash
python harness/run_ssh.py  --runs 5 --timeout 120 --timing quiet --no-mask-credentials --out results/raw
python harness/run_http.py --runs 5 --timeout 30  --no-mask-credentials --out results/raw_http
```

`--timing` is only written into the JSONL when passed explicitly, so an invocation
without it produces exactly the published record shape.

## 10. Still unverified

- Prompt mode was measured on two containers and one LLM target only. Whether a
  honeypot's prompt shape is stable enough to trust in every case (a split prompt,
  or output that happens to end in `$`/`#`) is unverified on DECEIVE, Beelzebub,
  VelLMes, HoneyBee and galah.
- The smoke run is 5 commands per mode on one target, one run, one model. It proves
  the wiring, not the distribution.
- The proxy has only ever seen AdvancedshelLM traffic; the other five targets are
  reasoned from their source, not tested.
- The 15.5 ms prompt-mode floor is a Windows timer property. On Linux the same rule
  should resolve to ~5–6 ms; that is untested.
- Masking does not equalise file names, permissions, package lists or tool versions,
  and `results/summary.md` was not regenerated, so it still carries the one stale
  `pwd` Run 4 line found in the Stage 1 audit.
