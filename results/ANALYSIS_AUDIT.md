# Analysis audit

All counts below were computed from UTF-8 JSONL/CSV inputs; no result input was modified.

| Target | Raw JSONL rows | CSV rows | Analyzer n_used | n_expected | Exclusions |
|---|---:|---:|---:|---:|---|
| advshellm | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| beelzebub | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| cowrie | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| deceive | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| groundtruth_ssh | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| llmhoneypot | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |
| vellmes | 185 | 185 | 180 | 180 | 5 exit control rows; 0 malformed/unknown cmd_id rows; 0 expected rows absent from raw JSONL |

## Where rows are dropped

* `harness/analyze.py:65-75` loads every non-empty JSONL line and silently skips only invalid JSON.
* The command filter in `_analyze_ssh_target` (`harness/analyze.py:162-178`) keeps known command IDs and excludes `exit`; connection-error rows have an empty `cmd_id` and are therefore excluded as malformed.
* There is no analyzer deduplication and no category-based row drop; categories are only grouping labels (`harness/analyze.py:185-195`).
* `harness/run_ssh.py:655-680` appends CSV rows independently, so CSV counts can exceed JSONL counts after reruns or when a run is partially written.
