# Harness latency floor (results/exp/floor.md)

Sent only trivial commands (`true` / `echo x`) to the two non-API targets.
No LLM was contacted.

Commands per target and mode: 30

| Target | Timing | n | Median (s) | p95 (s) | min | max | Median first byte (s) | Median prompt (s) | Timeouts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| groundtruth_ssh | quiet | 30 | 0.547 | 0.563 | 0.546 | 0.578 | 0.0 | 0.0 | 0 |
| groundtruth_ssh | prompt | 30 | 0.0158 | 0.0163 | 0.015 | 0.0163 | 0.0031 | 0.0031 | 0 |
| cowrie | quiet | 30 | 0.563 | 0.578 | 0.547 | 0.579 | 0.0155 | 0.016 | 0 |
| cowrie | prompt | 30 | 0.0155 | 0.0314 | 0.015 | 0.0319 | 0.0081 | 0.0093 | 0 |

**Reading the table.** `quiet` is the published-batch rule and cannot go
below `QUIET_PERIOD` (0.5 s); its median minus the server's own
`median_prompt_s` is the harness floor. `prompt` is the opt-in rule added in
Stage 2 and tracks the server.
