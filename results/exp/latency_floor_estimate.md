# Floor estimate from the published batch (results/exp/latency_floor_estimate.md)

**ESTIMATE: published latency minus measured quiet floor; polling granularity not removed.**

Derived only from `results/raw/*.jsonl` (published final batch, 5 runs per target, `exit`
and timed-out rows excluded) and the floor measured in `results/exp/floor.md`
(groundtruth quiet median 0.547 s, max 0.563 s).
Nothing under `results/` outside `results/exp/` was written and no run was repeated.

| Target | Kind | Completed | Median (s) | p95 (s) | ESTIMATE median (s) | ESTIMATE p95 (s) | Ratio (median) | Ratio (p95) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| groundtruth_ssh | groundtruth | 180 | 0.562 | 0.579 | 0.015 | 0.032 | 1.00 (denominator) | 1.00 (denominator) |
| cowrie | baseline | 180 | 0.563 | 0.610 | 0.016 | 0.063 | 1.1 | 4.2 |
| advshellm | llm | 180 | 1.922 | 4.504 | 1.375 | 3.957 | 91.7 | 263.8 |
| vellmes | llm | 171 | 1.687 | 4.874 | 1.140 | 4.327 | 76.0 | 288.5 |
| deceive | llm | 175 | 1.984 | 10.361 | 1.437 | 9.814 | 95.8 | 654.3 |
| beelzebub | llm | 164 | 5.023 | 31.656 | 4.476 | 31.109 | 298.4 | 2073.9 |

Ratio denominator: groundtruth published median 0.562 s minus 0.547 s = 0.015 s.

## Why the ratios must not be quoted as point values

- The Cowrie and groundtruth estimates are 0.016 s and 0.015 s, i.e. about 0.0-0.02 s.
- The denominator is therefore ~0.015 s, one quarter of a single 15.6 ms Windows timer tick.
- Using the floor maximum (0.563 s) instead of the median makes the denominator -0.001 s, so every ratio flips sign or becomes undefined. The floor was measured on one host in one session; its own p95 is 0.563 s.
- Polling granularity is not removed: quiet mode resolves completion in `select` slices of up to 0.1 s, so each published latency carries up to one slice of quantisation that this subtraction cannot remove.
- With floor 0.563 s the per-target estimates become: groundtruth_ssh -0.001, cowrie 0.000, advshellm 1.359, vellmes 1.124, deceive 1.421, beelzebub 4.460 s.

**Read this table as an order-of-magnitude sensitivity check, not as floor-corrected
latency.** No cause is assigned to any difference.
