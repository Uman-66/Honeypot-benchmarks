# Stage 2 smoke - advshellm

Quiet: n=5 min=2.7030s median=3.1400s max=4.8910s timeouts=0
Prompt: n=5 min=3.6360s median=3.9360s max=6.7880s timeouts=0
Proxy requests logged: 12

| Command | Quiet harness (s) | Prompt harness (s) | Proxy requests | Proxy total (s) | Gap: harness minus proxy (s) | Max status | Total tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| whoami | 4.25 | 3.8090 | 1 | 3.7340 | 0.0750 | 200 | 1350 |
| id | 3.016 | 3.9360 | 1 | 3.8910 | 0.0450 | 200 | 1398 |
| pwd | 3.14 | 6.7880 | 1 | 6.7340 | 0.0540 | 200 | 1405 |
| uname_a | 2.703 | 5.0840 | 1 | 5.0470 | 0.0370 | 200 | 1501 |
| ls | 4.891 | 3.6360 | 1 | 3.6100 | 0.0260 | 200 | 1702 |

## Harness overhead around the API call (prompt mode)

- commands matched to exactly one API request: 5/5
- gap median: 0.0450 s
- gap min/max: 0.0260 / 0.0750 s

The gap is SSH transport, wrapper process I/O and harness bookkeeping
around the API call. It is the part of a command's latency that is not the
model, and it is now measurable instead of being buried in a 0.5 s quiet
period.

## Redaction checks on the proxy log

| Check | Result |
|---|---|
| api_key_absent | PASS |
| authorization_header_absent | PASS |
| bearer_absent | PASS |
| sk_prefix_absent | PASS |
| prompt_text_absent | PASS |

## Proxy log shape

- requests: 12
- attributed to a command (both modes): 10; unattributed (session/banner): 2
- statuses: {'200': 12}
- duration_ms median: 3710.5
- usage present on: 12 requests
- keys logged: completion_tokens, duration_ms, error, method, model_reported, model_requested, path, prompt_tokens, request_bytes, request_sha256, response_bytes, status, stream, total_tokens, ts, upstream_path, usage
