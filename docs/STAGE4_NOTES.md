# STAGE4_NOTES.md — Stage 4 driver design and schema

Branch: `stage4-driver` (from `stage2-measurement`). All output goes under
`results/exp/stage4/` (or `--out`). Nothing under `results/raw`,
`results/raw_http`, `results_pilot/`, or `report/` is modified.

---

## 1. How to run

### Full 20-run pass (do NOT start until smoke run passes)

```powershell
# From repo root, using the .venv-hb interpreter
.venv-hb\Scripts\python.exe harness\run_stage4.py `
    --runs 20 --timing prompt --seed 2026
```

### Smoke run (1 run, all 9 targets; run this first)

```powershell
.venv-hb\Scripts\python.exe harness\run_stage4.py `
    --runs 1 --timing prompt --seed 2026 `
    --quiet-check-runs 1 `
    --out results/exp/stage4_smoke
```

### Dry run (print plan without connecting)

```powershell
.venv-hb\Scripts\python.exe harness\run_stage4.py `
    --runs 20 --timing prompt --seed 2026 --dry-run
```

### Preflight check only

```powershell
.venv-hb\Scripts\python.exe harness\run_stage4.py --preflight
```

### Analyze stage4 output

```powershell
.venv-hb\Scripts\python.exe harness\analyze_stage4.py
# or for the smoke run:
.venv-hb\Scripts\python.exe harness\analyze_stage4.py `
    --stage4-dir results/exp/stage4_smoke
```

---

## 2. CLI flags (run_stage4.py)

| Flag | Default | Meaning |
|---|---|---|
| `--runs N` | 20 | Total number of runs |
| `--start-run K` | 1 | First run number (use >1 to extend) |
| `--timing MODE` | prompt | SSH timing mode (prompt or quiet) |
| `--seed S` | 2026 | Shuffle seed |
| `--targets T,...` | all 9 | Comma-separated target list |
| `--out DIR` | results/exp/stage4 | Output root directory |
| `--quiet-check-runs N` | 2 | Also run LLM SSH targets in quiet mode for runs 1..N |
| `--dry-run` | false | Print plan and exit |
| `--preflight` | false | Run preflight checks and exit |
| `--timeout S` | 120 | Per-command SSH timeout (seconds) |
| `--http-timeout S` | 30 | Per-request HTTP timeout (seconds) |
| `--cost-cap C` | 8.0 | Safety stop if estimated cost exceeds C USD |
| `--targets-yaml P` | harness/targets.yaml | Targets YAML path |
| `--commands-yaml P` | harness/commands.yaml | Commands YAML path |
| `--requests-yaml P` | harness/http_requests.yaml | HTTP requests YAML |

---

## 3. How to resume after a crash or sleep

Re-run the **same command**. The driver:

1. Reads `status.json` from `--out`.
2. For each slot, checks whether the JSONL file has 37 lines (SSH) or 20 lines
   (HTTP) **and** whether `status[slot_key]` is `"complete"`.
3. Skips any slot that passes both checks.
4. If the JSONL exists but has fewer than the expected number of lines
   (partial write), renames it to `.partial.bak` and reruns the slot.

The proxy is restarted with each invocation. It appends to the same
`api_proxy_log.jsonl`, so the cumulative log is preserved.

**After a sleep/hibernate**, Docker containers may have been killed.
The driver tears down and restarts the target container for each slot
regardless, so stale containers are not an issue.

---

## 4. How to extend to 30 runs

```powershell
.venv-hb\Scripts\python.exe harness\run_stage4.py `
    --runs 30 --timing prompt --seed 2026 `
    --start-run 21
```

The `--start-run 21` flag tells the driver to begin numbering from run 21.
Runs 1–20 in `status.json` are not re-checked (they are in `results/exp/stage4/`
and their JSONL files already count as complete). The manifest and proxy log
are appended to, not overwritten.

---

## 5. Output layout

```
results/exp/stage4/
  raw/                      SSH JSONL files:  {target}_run{N:02d}.jsonl
  raw_http/                 HTTP JSONL files: {target}_run{N:02d}.jsonl
  manifest.jsonl            one line per slot (see §6)
  status.json               slot status map  {slot_key: "complete"|"..."}
  driver.log                human-readable progress log
  api_proxy_log.jsonl       proxy request log + slot-boundary markers
  containers.json           per-slot image IDs and container names
  analysis.md               (written by analyze_stage4.py)
  latency.csv               (written by analyze_stage4.py)
  determinism.csv           (written by analyze_stage4.py)
  drift.csv                 (written by analyze_stage4.py)
  extra_vs_gt.csv           (written by analyze_stage4.py)
  proxy_join.csv            (written by analyze_stage4.py)
```

---

## 6. Schema

### JSONL row schema (SSH: results/exp/stage4/raw/{target}_run{N:02d}.jsonl)

All fields from `run_ssh.py` (see §3 of STAGE2_NOTES.md) plus:

| Field | Type | Meaning |
|---|---|---|
| `s4_run` | int | Run number (1–20) |
| `s4_position` | int | Position-in-run (1–9) for the slot this row belongs to |
| `s4_order_seed` | int | The shuffle seed used (always 2026 in the standard pass) |
| `s4_timing_mode` | str | "prompt" or "quiet" (the mode this session used) |
| `s4_wall_start` | str | UTC ISO-8601 timestamp when the slot started |
| `s4_harness_ver` | str | Short git commit hash (7 chars) of HEAD at driver start |

### manifest.jsonl schema

One line per slot:

| Field | Type | Meaning |
|---|---|---|
| `run` | int | Run number |
| `position` | int | Position-in-run (1-indexed) |
| `target` | str | Target name |
| `modes` | list[str] | Modes run in this slot ("prompt", optionally "quiet") |
| `order_seed` | int | Shuffle seed |
| `planned_start_utc` | str | UTC ISO-8601 timestamp when the slot was planned to start |

### api_proxy_log.jsonl schema

Real request rows (from api_proxy.py) plus slot-boundary markers:

**Slot-boundary marker** (not a real request):

| Field | Value | Meaning |
|---|---|---|
| `event` | "slot_start" | Marks the beginning of a slot |
| `run` | int | Run number |
| `position` | int | Position-in-run |
| `target` | str | Target name |
| `mode` | str | Mode being run |
| `ts` | str | UTC ISO timestamp |

**Real proxy request row** (all fields from api_proxy.py):
`ts, method, path, upstream_path, status, duration_ms, request_bytes,
request_sha256, response_bytes, model_requested, model_reported, stream,
usage, prompt_tokens, completion_tokens, total_tokens, error`

### containers.json schema

JSON array; one entry per slot:

| Field | Type | Meaning |
|---|---|---|
| `run` | int | Run number |
| `position` | int | Position-in-run |
| `target` | str | Target name |
| `image_id` | str | Docker image SHA256 |
| `container_name` | str | Docker container name |
| `started_utc` | str | UTC ISO timestamp |

---

## 7. Safety stops

The driver exits with code 3 and writes `status["safety_stop"]` to
`status.json` if any of these conditions is met:

| Condition | Threshold | Configured by |
|---|---|---|
| Proxy not reachable at slot start | — | hardcoded |
| Fireworks HTTP error rate | > 20% over last 50 requests | hardcoded |
| Consecutive LLM SSH timeout slots | ≥ 3 above 50% timeout rate | hardcoded |
| Free disk below | 5 GB | hardcoded |
| Cumulative estimated cost | > `--cost-cap` USD | `--cost-cap` (default $8) |
| Unexpected model string in proxy log | any model ≠ `glm-5p3-flash` | hardcoded |

To resume after a safety stop, fix the underlying issue, then re-run.
The status file keeps `"safety_stop"` until you manually remove it
(or delete the key in `status.json`) — this is intentional so you don't
accidentally start a new pass over a broken run.

---

## 8. galah cache clearing and proxy

**Cache location:** galah stores its SQLite cache at
`/galah/logs/cache.db` inside the named volume `galah_logs`.

**Clearing strategy:** the driver runs
`docker compose -f docker/galah.compose.yaml down --volumes --remove-orphans`
before each galah slot. This removes the `galah_logs` named volume, which
contains both the event log and the cache DB. On the subsequent `docker up`
the volume is recreated empty.

**Verification:** after the container starts, the driver executes
`docker exec <cid> stat -c%s /galah/logs/cache.db`; a size < 4096 bytes
(zero or fresh SQLite header only) is considered empty. This is logged to
`driver.log`.

**Proxy feasibility for galah:**
galah reads `LLM_SERVER_URL` via `docker/galah-entrypoint.sh` (which maps
`OPENAI_BASE_URL → LLM_SERVER_URL` at startup). The proxy overlay
`docker/galah.proxy.yaml` sets `OPENAI_BASE_URL` to
`http://host.docker.internal:11435/inference/v1`. Since galah reads this at
startup, `--force-recreate` (which the driver always uses) is sufficient.

**Caveat (UNVERIFIED):** galah uses a cache DB; a repeated identical request
in the same slot will be served from cache without an upstream call. The
proxy log is therefore a lower bound on actual API usage for galah. The
driver clears the volume before each slot to minimize this effect, but it
cannot prevent caching of requests that are identical within a single slot.

---

## 9. AdvancedshelLM recreate requirement

AdvancedshelLM reads `OPENAI_BASE_URL` at Python import time in
`shelLM/.../openai_client.py`. Restarting the container is insufficient;
the container must be recreated (`--force-recreate`) so the new environment
takes effect. The driver always passes `--force-recreate --no-build` to
`docker compose up`.

---

## 10. Quiet-check output naming

When `--quiet-check-runs N` causes a run to execute both prompt and quiet
modes, the driver runs them **sequentially in the same slot** (prompt first,
then quiet). Both sessions write to the same output file
(`{target}_run{N:02d}.jsonl` in `raw/`), because the second `run_ssh.main()`
call uses `--force`, which overwrites the first. The `s4_timing_mode` field
in each JSONL row distinguishes them. This design means the quiet-check rows
are **appended** to the same file, not stored separately.

For analysis, `analyze_stage4.py` splits the rows by `s4_timing_mode` to
perform the prompt-vs-quiet comparison.

---

## 11. UNVERIFIED items

The following have NOT been tested in Stage 4 and may need investigation:

1. **State leaks between runs without container restarts.** The driver
   restarts containers per slot (not per run). If the previous run left
   state in a named volume (e.g., VelLMes conversation history), the next
   run may inherit it. Currently, named volumes are NOT cleared between
   slots (only galah's cache volume is cleared). Whether this affects
   output determinism is UNVERIFIED.

2. **Prompt mode on galah.** galah returns HTTP responses, not SSH shells.
   The timing mode flag does not apply to galah (it uses `--http-timeout`).
   Whether the proxy correctly sits in front of galah has been verified
   architecturally but NOT tested end-to-end with the driver.

3. **llmhoneypot trap markers in prompt mode.** The llmhoneypot target is
   a detector that injects ANSI-hidden trap markers. Whether prompt mode
   captures these markers correctly (vs. quiet mode's 0.5s settle window)
   is UNVERIFIED.

4. **Consecutive-timeout stop after SIGINT resume.** The
   `_consec_timeout_*` counter in `status.json` persists across restarts.
   After a SIGINT, a target that was already at count 2 would stop after
   just one more bad slot on resume. This is conservative (safe) but may
   be surprising. UNVERIFIED whether this is the right behaviour.

5. **Laptop sleep on Windows.** The preflight check prints the `powercfg`
   commands to disable sleep/hibernate but does NOT run them. If the
   machine sleeps mid-run, Docker containers may be killed and ports may
   be in an indeterminate state. The resume logic handles this gracefully
   (each slot is backed up and restarted), but the SIGINT handler cannot
   fire during a sleep event.

6. **galah proxy correctness.** The entrypoint mapping
   `OPENAI_BASE_URL → LLM_SERVER_URL` was verified by reading source; it
   has not been exercised end-to-end with the stage4 driver.
