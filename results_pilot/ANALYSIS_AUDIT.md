# Analysis audit

All counts below were computed from UTF-8 JSONL/CSV inputs; no result input was modified.

| Target | Raw JSONL rows | CSV rows | Analyzer n_used | n_expected | Exclusions |
|---|---:|---:|---:|---:|---|
| advshellm | 149 | 185 | 144 | 180 | 4 exit control rows; 1 malformed/unknown cmd_id rows; 36 expected rows absent from raw JSONL |
| beelzebub | 185 | 222 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| cowrie | 185 | 222 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| deceive | 149 | 185 | 144 | 180 | 4 exit control rows; 1 malformed/unknown cmd_id rows; 36 expected rows absent from raw JSONL |
| groundtruth_ssh | 185 | 222 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| llmhoneypot | 185 | 222 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |

## Where rows are dropped

* `harness/analyze.py:65-75` loads every non-empty JSONL line and silently skips only invalid JSON.
* The command filter in `_analyze_ssh_target` (`harness/analyze.py:162-178`) keeps known command IDs and excludes `exit`; connection-error rows have an empty `cmd_id` and are therefore excluded as malformed.
* There is no analyzer deduplication and no category-based row drop; categories are only grouping labels (`harness/analyze.py:185-195`).
* `harness/run_ssh.py:655-680` appends CSV rows independently, so CSV counts can exceed JSONL counts after reruns or when a run is partially written.

## DECEIVE

The CSV has timeout counts per run of 3, 11, 3, 0, 0 (runs 1-5), matching the requested comparison. The current raw JSONL has no complete run 1 and reports 10, 3, 0, 0 for runs 2-5; this is an input/accounting discrepancy, not a reconstructed result.

Search of `results/honeypot_logs/deceive/` found no `finish_reason`, `reasoning`, `reasoning_content`, or model-response payloads, and no evidence of a reasoning-only reply. The only log records are one connection received and one connection-lost error. UNVERIFIED: empty LLM replies or finish_reason=`length` cannot be established from the available logs.
