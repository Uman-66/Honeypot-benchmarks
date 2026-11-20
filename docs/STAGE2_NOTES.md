# STAGE2_NOTES.md — measurement fixes

Branch: `stage2-measurement` (not pushed). Nothing under `results/raw`,
`results/raw_http`, `results_pilot/`, `report/` or `BENCHMARK.md` was modified;
every new output is under `results/exp/`.

---

## 1. How timing works today (the five-line answer)

1. `run_ssh.py` sends one command, then records `t_send = time.monotonic()` immediately
   before `sendall` (`harness/run_ssh.py`, `_run_once`).
2. It then reads in a non-blocking loop and runs `_detect_prompt` on the accumulated
   buffer after every chunk; a prompt is only a *candidate* at that point.
3. `QUIET_PERIOD = 0.5` s of silence *after the last chunk that contained a prompt* is
   required before the command is considered finished, and the idle branch polls with
   `select` in ≤0.1 s slices, so completion is quantised to roughly 0.5–0.6 s.
4. `latency_s = time.monotonic() - t_send` is therefore server time **plus** the quiet
   period **plus** poll granularity — for a 3 ms command that is ≥0.5 s.
5. The 120 s ceiling is `--timeout`, which only fires when no prompt ever matches.

That is why the published ground-truth median is 0.562 s on a command the server
answers instantly. Stage 2 adds `--timing prompt`, which stops the moment the prompt
regex matches the end of the buffer. The default is unchanged.

## 2. Reviewer points

| Point | What changed | Evidence |
|---|---|---|
| (a) 0.5 s quiet period dominates real-server latency | `harness/calibrate_floor.py`, `--timing prompt` | `results/exp/floor.md` |
| (b) no per-request API timing | `harness/api_proxy.py` | `harness/api_proxy.py`, `tests/test_api_proxy.py` |
| (c) no masked ground-truth determinism | masking in `harness/analyze.py`, `--masked-report` | `results/exp/summary_v2.md` |
| (d) fidelity mixes persona with shell errors | masked fidelity column + persona note | `results/exp/summary_v2.md` |
| publish-safety of raw files | write-time credential masking + SHA-256 | `harness/masking.py`, `tests/test_masking.py` |

## 3. Measured floor

30 trivial commands (`true` / `echo x`) per target per mode, the two non-API
containers only. Full data: `results/exp/floor_raw.csv`, `floor.json`.

| Target | Timing | Median (s) | p95 (s) | Median first byte (s) |
|---|---|---:|---:|---:|
| groundtruth_ssh | quiet | 0.547 | 0.563 | 0.000 |
| groundtruth_ssh | prompt | 0.000 | 0.0155 | 0.000 |
| cowrie | quiet | 0.563 | 0.5872 | 0.0155 |
| cowrie | prompt | 0.000 | 0.0155 | 0.000 |

**Reading it:** in the published mode the harness adds ~0.55 s to every command and the
spread (p95 − median = 16–24 ms) is poll granularity, not server variance. In prompt
mode both servers answer in under a millisecond and the p95 of 16 ms is the only real
jitter. Any latency claim about a target heavier than these two must therefore be
reported in prompt mode, or with the floor subtracted explicitly.

Caveat: this is one idle desktop, 30 samples per cell, and `true`/`echo x` do not
exercise the LLM path. The floor is a harness property, so it transfers; the server
numbers are not a benchmark.

## 4. Masked determinism and fidelity (existing batch, no API calls)

`python harness/analyze.py --masked-report results/exp`

Masked before similarity: ISO/RFC3339 dates, `date`-style dates, clock times, uptime,
load averages, PIDs, `pts/N` handles, ports after a colon, and every hostname observed
in the batch (9 of them, listed in `results/exp/summary_v2.md`).

| Target | Kind | Determinism raw | Determinism masked | Δ |
|---|---|---:|---:|---:|
| advshellm | llm | 0.7836 | 0.8034 | +0.0198 |
| beelzebub | llm | 0.6800 | 0.6815 | +0.0015 |
| cowrie | baseline | 0.9874 | 0.9957 | +0.0083 |
| deceive | llm | 0.4664 | 0.5038 | +0.0374 |
| **groundtruth_ssh** | groundtruth | **0.9746** | **0.9841** | +0.0095 |
| vellmes | llm | 0.8364 | 0.8472 | +0.0108 |

| Target | Raw-text fidelity | Masked fidelity | Δ |
|---|---:|---:|---:|
| advshellm | 0.5947 | 0.5992 | +0.0045 |
| beelzebub | 0.3737 | 0.3797 | +0.0060 |
| cowrie | 0.5877 | 0.5975 | +0.0098 |
| deceive | 0.4731 | 0.4750 | +0.0019 |
| vellmes | 0.6070 | 0.6074 | +0.0004 |

Two things worth saying plainly:

- **The ground truth is not perfectly deterministic either** (0.9746 raw). It was never
  reported, so the honeypots were being compared against an implicit 1.0. After masking
  it is 0.9841, still below cowrie's 0.9957 — an honest Ubuntu container still varies in
  ways masking does not remove (file sizes, inode order, tool versions).
- **Masking moves every target up by ≤0.04**, so the ranking is unchanged and clock/PID
  noise was never the main cause of the honeypot instability. This *weakens*, rather
  than supports, the original "instrumentation noise" explanation — say so rather than
  presenting masking as a rescue.

`groundtruth_ssh` has no fidelity row by construction; it is the reference.

## 5. API proxy

```bash
python harness/api_proxy.py --port 11435            # host clients
python harness/api_proxy.py --port 11435 --bind 0.0.0.0 --allow-remote-bind   # containers
```

One JSONL row per request in `results/exp/api_proxy_log.jsonl`: `ts`, `method`, `path`,
`upstream_path`, `status`, `duration_ms`, `request_bytes`, `request_sha256`,
`response_bytes`, `model_requested`, `model_reported`, `stream`, `usage`,
`prompt_tokens`, `completion_tokens`, `total_tokens`, `error`.

Redaction guarantee: headers are never copied into the record and bodies are never
logged; the only body-derived value is its SHA-256. `tests/test_api_proxy.py` asserts a
request carrying `Bearer sk_live_…` produces a log containing neither the token, nor
`sk_live_`, nor `Authorization`, nor `Bearer`.

### How each target is pointed at it

| Target | Mechanism | Works? |
|---|---|---|
| DECEIVE | `DECEIVE/SSH/ssh_server.py:412-428` — `os.environ.get("OPENAI_BASE_URL")` first, then `config['llm'].base_url` | yes, via `.env` |
| Beelzebub | `docker/beelzebub-ssh.yaml:38-44` — `host: ""` forces the `OPENAI_BASE_URL` path, `/chat/completions` appended by the plugin | yes |
| VelLMes | `VelLMes-AI-Deception-Framework/VelLMes.py:88-91` — `base_url = os.environ.get("OPENAI_BASE_URL")`; wrapper forwards the env | yes |
| AdvancedshelLM | `shelLM/.../LLM_Plugins/api_clients/openai_client.py:27` — `_BASE_URL` read **at import time** | yes, but the container must be recreated, not just re-env'd |
| HoneyBee | `honeybee/honeybee/src/client_provider.py:12-13` — `base_url = os.getenv("OPENAI_BASE_URL")` | yes |
| galah | `docker/galah-entrypoint.sh:22-24` maps `OPENAI_BASE_URL → LLM_SERVER_URL`; `galah/internal/app/args.go:6`, `galah/pkg/llm/openai.go:17` (`openai.WithBaseURL`) | yes |
| llmhoneypot | detector, no LLM call | not applicable |

Setup per container: set `OPENAI_BASE_URL=http://host.docker.internal:11435/inference/v1`
in `.env` (the proxy keeps the `/inference/v1` prefix whether or not the client includes
it) and start the proxy with `--bind 0.0.0.0 --allow-remote-bind`.

**Where it does not work cleanly**

- **galah caches.** It keeps a cache DB in its `galah_logs` volume, so a repeated
  identical request may be answered without any upstream call. The proxy log is then a
  lower bound on requests actually served. Clear the volume, or note the gap.
- **HoneyBee keeps `.qhistory`.** Same caveat for repeated queries.
- **Nothing can be proxied if `OPENAI_BASE_URL` is overridden as a compose literal.**
  In this repo it comes from `.env`, so that is fine; check any new cell overlay.
- Responses are buffered before relay, so `stream: true` clients get the full body but
  not incrementally; `duration_ms` still covers the whole generation.

No API call was made in Stage 2, so none of this is verified against Fireworks yet.

## 6. Reproducing the published batch

Defaults are unchanged, with one exception: credential masking is **on** by default, as
requested. Re-running a file that contains credential-like strings therefore produces a
masked file. To regenerate the published batch byte-for-byte:

```bash
python harness/run_ssh.py  --runs 5 --timeout 120 --timing quiet --no-mask-credentials --out results/raw
python harness/run_http.py --runs 5 --timeout 30  --no-mask-credentials --out results/raw_http
```

`--timing` is only recorded in the JSONL when it is passed explicitly, so an invocation
without it writes exactly the published record shape. Masking adds `credential_masks`
only to rows that actually contained a credential, so clean rows are unchanged.

## 7. Masking semantics

`harness/masking.py` replaces a token with `<MASKED:<pattern>:<first-12-of-sha256>>` and
records `{"pattern", "sha256", "length", "field"}` in `credential_masks`. Patterns:
Stripe `sk_live_` / `sk_prod_` / `sk_test_` / `pk_live_` / `pk_test_` / `rk_live_`, AWS
`AKIA`/`ASIA`, GitHub `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`/`github_pat_`, Slack `xox[baprs]-`,
`sk-…`, JWT (`eyJ…`), `Bearer <token>` (scheme kept), and a generic ≥40-character
mixed-case-with-digit token. Masking is idempotent; `<MASKED:…>` is never re-matched.

Known false-positive risk: the generic long-token rule can mask a legitimate 40-character
identifier. It is off only if you edit the pattern table; no published file is affected
because masked output is only produced for new runs.

## 8. Tests

```
.venv-hb/Scripts/python.exe -m pytest tests/ -q
```

`tests/test_masking.py` (11), `tests/test_prompt_timing.py` (7),
`tests/test_api_proxy.py` (6) are new. The pre-existing analyzer, honeybee and HTTP
tests are unchanged and still pass. `test_prompt_timing.py` asserts both halves of the
floor: prompt mode finishes in less than `QUIET_PERIOD`, quiet mode does not.

## 9. Still unverified / not done

- The proxy has never forwarded a real Fireworks request; duration and usage parsing are
  tested only against a local stub. Fireworks' `usage` fields are untested in practice.
- No target has been pointed at the proxy, so per-request timing for DECEIVE, Beelzebub,
  VelLMes, AdvancedshelLM, HoneyBee or galah does not exist yet.
- Prompt-mode timing has only been measured on the two non-API containers. Whether a
  honeypot's prompt shape is stable enough for `--timing prompt` (a split prompt could
  match early) is untested on the LLM targets.
- `--timing prompt` can terminate early if a *previous* command's output ends with a
  `$`/`#`-looking line that is not the real prompt. Not observed on the two containers;
  unverified elsewhere.
- The floor was measured on an idle desktop with 30 samples per cell; no confidence
  interval and no load-controlled repetition.
- Masking does not equalise file names, permissions, package lists or tool versions, so
  two honest Ubuntu images still differ. The persona-controlled cell (E5c) is still the
  only way to separate persona from shell fidelity.
- `results/summary.md` was **not** regenerated, so it still carries the one stale
  `pwd` Run 4 line found in the Stage 1 audit.
