# API duration per target, joined from the validation proxy log (results/exp/api_duration_validation.md)

Source: `results/exp/validation/api_proxy_log.jsonl` joined to
`results/exp/validation/{target}_pass{A,B,C}.jsonl` on the strict condition
`t_send <= request ts <= t_send + latency_s`, first unused entry wins, so each proxy entry
is used at most once. Passes A (quiet), B (prompt) and C (quiet) are **pooled** per target;
the per-pass split is in `api_duration_validation_passes.csv`.

Proxy entries in the log: 452; matched to a command row: 432; unmatched: 20 (session/banner calls and requests that fell outside every command window, e.g. after a timeout).

| Target | Command rows | Matched | Matched, status 200 | Unmatched rows | Median API (s) | p95 API (s) | Median harness (s) | Median non-API gap (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deceive | 108 | 108 | 108 | 0 | 2.023 | 7.974 | 2.476 | 0.586 |
| beelzebub | 108 | 108 | 108 | 0 | 1.586 | 4.099 | 1.977 | 0.563 |
| vellmes | 108 | 108 | 108 | 0 | 1.735 | 4.836 | 2.25 | 0.577 |
| advshellm | 108 | 108 | 108 | 0 | 1.609 | 3.536 | 2.117 | 0.578 |

Per pass, so the quiet and prompt rules are visible separately (all four tables show the
same API column; only the harness side changes with the timing rule):

| Target | Pass | n | Median API (s) | p95 API (s) | Median harness (s) | Median non-API gap (s) |
|---|---|---:|---:|---:|---:|---:|
| deceive | passA_quiet | 36 | 2.179 | 5.82 | 2.743 | 0.594 |
| deceive | passB_prompt | 36 | 2.008 | 11.656 | 2.067 | 0.06 |
| deceive | passC_quiet | 36 | 1.953 | 7.141 | 2.571 | 0.601 |
| beelzebub | passA_quiet | 36 | 1.531 | 3.938 | 2.109 | 0.579 |
| beelzebub | passB_prompt | 36 | 1.656 | 4.399 | 1.697 | 0.044 |
| beelzebub | passC_quiet | 36 | 1.484 | 3.359 | 2.039 | 0.578 |
| vellmes | passA_quiet | 36 | 1.601 | 4.539 | 2.172 | 0.579 |
| vellmes | passB_prompt | 36 | 1.914 | 5.742 | 1.958 | 0.045 |
| vellmes | passC_quiet | 36 | 1.789 | 4.34 | 2.375 | 0.578 |
| advshellm | passA_quiet | 36 | 1.624 | 3.871 | 2.203 | 0.578 |
| advshellm | passB_prompt | 36 | 1.648 | 3.824 | 1.692 | 0.049 |
| advshellm | passC_quiet | 36 | 1.578 | 2.984 | 2.172 | 0.593 |

The pooled gap above is dominated by the two quiet passes, whose 0.5 s quiet period sits
inside it; the prompt pass is the informative one for transport overhead.

Status-200 requests only (the completed generations):

| Target | n (200) | Median API (s) | p95 API (s) | Median non-API gap (s) |
|---|---:|---:|---:|---:|
| deceive | 108 | 2.023 | 7.974 | 0.586 |
| beelzebub | 108 | 1.586 | 4.099 | 0.563 |
| vellmes | 108 | 1.735 | 4.836 | 0.577 |
| advshellm | 108 | 1.609 | 3.536 | 0.578 |

## Limits

- **One session per pass.** Each target has a single A, a single B and a single C pass, so
  these are not distributions over sessions; a different session could shift the medians.
- **One pass of each mode per target**: 36 scored commands per pass (`exit` excluded), so
  108 command rows per target. Not every row issues an API call the proxy can see: a command
  answered from a cached or non-LLM path has no request, and a timed-out row may have none
  that closed inside its window. The `Unmatched rows` column is that remainder.
- **One shared endpoint.** All four targets used the same remote model endpoint, so the API
  durations are not independent of each other and say nothing about the honeypot code.
- **Passes pooled.** Quiet and prompt passes are pooled above because the API call is the
  same call in both; the prompt-mode rule changes only when the harness stops reading.
- `median non-API gap` = harness latency minus API duration for the same matched command.
  It contains SSH transport, the honeypot wrapper process, and harness bookkeeping; it
  cannot be split further from this log.
- Requests that never returned before `--timeout` are matched only if their timestamp fell
  inside the command window; otherwise they count as unmatched, so a slow model can
  under-count duration on timeout rows.

No cause is assigned to any difference.
