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
| `--cost-cap C` | 6.0 | Safety stop if estimated cost exceeds C USD |
| `--targets-yaml P` | harness/targets.yaml | Targets YAML path |
| `--commands-yaml P` | harness/commands.yaml | Commands YAML path |
| `--requests-yaml P` | harness/http_requests.yaml | HTTP requests YAML |

---

## 3. How to resume after a crash or sleep

Re-run the **same command**. The driver:

1. Reads `status.json` from `--out`.
2. For each **mode** of each slot (a slot in runs 1-2 can have both `prompt`
   and `quiet`), checks that its JSONL has 37 lines (SSH) or 20 lines (HTTP)
   **and** that `status[<target>:runNN:<mode>]` is `"complete"`.
3. Skips a mode that passes both checks; a slot is skipped only when every one
   of its modes is complete. A resumed slot re-runs only the missing modes
   (recorded in the manifest as `modes_run` with `"resumed": true`).
4. If the JSONL exists but has fewer than the expected number of lines
   (partial write), renames it to `.partial.bak` and reruns that mode.

Each mode has its own file: `raw/` for prompt (and non-LLM) sessions,
`raw_quiet/` for quiet-check sessions, `raw_http/` for HTTP targets. This is
required because `run_ssh.py --force` copies the existing file to `.bak` and
rewrites the canonical name; sharing one name made the quiet session overwrite
the prompt rows (they survived only as `.jsonl.bak`).

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
  raw_quiet/                quiet-check SSH JSONL files (runs 1-2)
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
| `modes` | list[str] | Modes planned for this slot ("prompt", optionally "quiet") |
| `modes_run` | list[str] | Modes actually executed in this invocation (differs from `modes` after a resume) |
| `resumed` | bool | True when `modes_run != modes` |
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
| Cumulative estimated cost | > `--cost-cap` USD | `--cost-cap` (default $6) |
| Unexpected model string in proxy log | any model ≠ `glm-5p3-flash` | hardcoded |
| Per-slot provider call count | > 80 single-mode / > 100 two-mode (LLM SSH), > 45 (galah) | hardcoded |

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

**Verification:** galah creates `cache.db` (with its schema) at startup, so a
fresh DB is ~12 KB and its size cannot show whether the cache holds entries.
After the container starts the driver instead compares the volume's
`docker volume inspect galah_galah_logs --format '{{.CreatedAt}}'` timestamp
with the slot start: a volume created at/after the slot start proves the
`down --volumes` above removed the old one. The `cache.db` size is still
logged, as information only. Both values are written to `driver.log`
(`galah cache check: ... fresh=True ...`).

**Second check:** galah made exactly 20 upstream calls to the proxy for the 20
HTTP requests in the smoke slot, i.e. no request was served from cache.

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
takes effect. The driver passes `--force-recreate` to `docker compose up`
(without `--no-build`, so an image that was never built - galah, llmhoneypot -
is built on first use instead of failing the slot).

---

## 10. Quiet-check output naming

When `--quiet-check-runs N` causes a run to execute both prompt and quiet
modes, the driver runs them **sequentially in the same slot** (prompt first,
then quiet), but writes them to **different directories**:
`raw/{target}_run{N:02d}.jsonl` for prompt and
`raw_quiet/{target}_run{N:02d}.jsonl` for quiet. A separate slot-boundary
marker is written to the proxy log for each mode, and each mode has its own
`status.json` key.

`analyze_stage4.py` loads `raw_quiet/` separately, excludes those rows from
the prompt-mode statistics, and uses them only for the prompt-vs-quiet
comparison (`s4_timing_mode` also remains in every row).

---

## 11. Bugs found after the first 20-run attempt (2026-11-22)

The first 20-run pass (2026-11-21T20:55Z .. 2026-11-22T03:12Z) was aborted by
the cost cap after 6.3 runs. Two driver bugs produced its numbers.

### 11.1 Run multiplier (extra calls)

`_run_ssh_slot` / `_run_http_slot` passed `--runs <run index>` to
`run_ssh.py` / `run_http.py`, and those runners loop `range(1, runs+1)`.
Run n therefore executed the whole command list n times inside one slot,
writing `{target}_run01..runNN.jsonl`; the driver kept only the last file and
`--force` overwrote the rest. Slot call counts scaled linearly with the run
index (vellmes 38, 76, 114, 152, 190; galah 20, 40, 60, 79, 99), and the
beelzebub container log shows 1/2/3/5/6 SSH sessions per prompt slot.

**Fix:** `run_ssh.py` and `run_http.py` take `--run-index N` (requires
`--runs 1`), which sets only the output-file suffix and the `run` field. The
driver now calls `--runs 1 --run-index <run>`, so one slot is one execution
and one session. Without `--run-index` the runners behave exactly as before
(covered by a byte-comparison test).

**Discarded data:** the contaminated batch was moved to
`results/exp/stage4_discarded_multiplier_bug/` (with a README.txt) and must
not be used for analysis. Nothing was deleted. `results/exp/stage4/` does not
exist; the driver creates it.

### 11.2 Cost overestimate (cached tokens)

`_estimate_cost_from_proxy_log` billed every prompt token at $0.15/M, but
46,645,388 of that batch's 48,801,496 prompt tokens (95.6%) were cache hits.
The corrected model:

| Component | Price |
|---|---|
| uncached prompt (`prompt_tokens - cached_tokens`) | $0.15/M |
| cached prompt (`usage.prompt_tokens_details.cached_tokens`) | $0.03/M |
| completion (`completion_tokens`, includes reasoning tokens) | $0.50/M |
| row without a cached breakdown | whole prompt at $0.15/M (conservative) |

For the discarded batch that gives $2.74 instead of $8.34, which matches the
billing page (~$3 including earlier runs). The default cap is now $6. The
cumulative estimate is logged at slot start (`slot start: calls=...
est_cost=...`) and on the per-slot progress line.

### 11.3 Per-slot call guard

After each slot the driver counts proxy requests since the slot started and
stops with exit 3 and `slot_call_anomaly: <target> <n> calls` when an LLM SSH
slot exceeds 80 calls (100 when the slot runs both prompt and quiet) or a galah
slot exceeds 45. The count spans the **whole slot**: `calls_before_slot` is
taken before the mode loop, so runs 1-2 sum both modes (38+38 vellmes,
36+36 beelzebub, 37+37 advshellm, 39+39 deceive). Targets that never call the model
(cowrie, llmhoneypot, groundtruth_*) are not guarded. This would have stopped
the multiplier bug at run 2 (152 calls in one prompt+quiet slot).

### 11.4 Live fix check

`results/exp/stage4_fixcheck/` (untracked evidence, 2026-11-22): vellmes run 3
in prompt mode made 38 calls (was 114), wrote `raw/vellmes_run03.jsonl` with
37 rows and `run=3`, and exited 0; cowrie run 4 wrote `raw/cowrie_run04.jsonl`
with 37 rows and `run=4`; the estimator matched the token arithmetic to the
cent.

---

## 12. UNVERIFIED items

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

7. **Graceful Ctrl+C teardown.** The SIGINT handler sets `_interrupted` and
   the `finally` block stops the proxy and the last container, but that path
   has not been exercised live since the fixes.

8. **Live error-rate / unexpected-model / disk stops.** All three are unit
   tested; only the cost stop and the slot call guard have been observed
   live.

9. **`--start-run` extension to 30 runs.** Runs 1..N are skipped through
   `status.json`; extending a finished pass
   (`--runs 30 --start-run 21`) has not been run end-to-end.

## 13. DECEIVE output-cap evidence

Recorded for the max-token check (read-only, no code change):

- `DECEIVE/SSH/config.ini` line 61 `temperature = 0.2`; line 67
  `trimmer_max_tokens = 64000` (history trimmer only, not an output cap).
- `DECEIVE/SSH/ssh_server.py` line 429 `ChatOpenAI(**kwargs)` with no
  `max_tokens` argument (kwargs built at lines 421-428).
- Stage 4 data consistent with an uncapped target: 6 oversized outputs
  (max 142,810 characters) and six requests at the 65,536-token ceiling
  (`analysis.md`, `analysis_timeouts.md`).

## 14. Final UNVERIFIED list (Stage 4 scope)

1. State carried between runs in named volumes (only galah's cache volume is
   cleared per slot); effect on determinism not measured.
2. galah end-to-end proxy correctness was exercised in Stage 4 (17-20 calls per
   slot, all logged), but whether identical in-slot requests are served from
   `cache.db` instead of the API is unknown; the proxy log is a lower bound.
3. llmhoneypot trap markers in prompt mode: markers were visible after ANSI
   stripping in Stage 4, but a marker-level comparison against quiet mode was
   not run.
4. Cause of the Beelzebub baseline-vs-Stage-4 difference; the
   container-lifetime control covers one of the three protocol changes only.
5. Why prompt mode returned shorter output for 32 of 288 quiet-check pairs.
6. Whether VelLMes target-side replies are held or dropped inside the target
   (no container-side log for those slots).
7. The exact Beelzebub binary identity for the published batch (YAML identical,
   image digest not recorded).

## 15. v2.1 re-analysis (added 2026-11-25)

A reviewer re-analysed the same raw files and reported four differences from
v2. This section records how to reproduce the v2.1 answers. The analyzer is
read-only over `results/exp/stage4/raw*`: it writes new files and never
overwrites a v2 output.

### One command

```powershell
.venv-hb\Scripts\python.exe harness\analyze_stage4_v21.py
```

The determinism section is the slow one (difflib is quadratic; about 2.5
minutes on this machine, 105 s of it DECEIVE). `--skip-determinism` runs only
T2-T4 in a few seconds.

### Outputs (all new files, none of them a v2 filename)

| File | Contents |
|---|---|
| `results/exp/stage4/v21_reanalysis.md` | all four tables in one page |
| `results/exp/stage4/determinism_variants_v21.csv` | T1: per target x variant determinism |
| `results/exp/stage4/narration_hits_v21.csv` | T2: every hit, run, command id, first 200 chars |
| `results/exp/stage4/narration_by_target_v21.csv` | T2: outputs and sessions per target |
| `results/exp/stage4/state_checks_v21.csv` | T3: one row per run x check, with failure cause |
| `results/exp/stage4/state_by_target_v21.csv` | T3: per target, per check totals |
| `results/exp/stage4/literal_ansi_hits_v21.csv` | T4: every match with context |
| `results/exp/stage4/literal_ansi_by_target_v21.csv` | T4: counts per target and form |

### T1 DECEIVE determinism: the 0.509 / 0.522 difference

V0 reproduces `determinism.csv` exactly (all six targets). Two variants land
near the reviewer's 0.522 and neither is confirmed:

- **V12, the `exit` control row kept as a 37th command** gives 0.5219, which
  rounds to his 0.522. The `exit` row is perfectly stable for every target
  (mean pairwise 1.0000), so a 36-command mean of 0.5086 becomes
  `(36 x 0.5086 + 1.0000) / 37 = 0.5219`. But it also moves Beelzebub by
  0.011, so it does not match his statement that the other targets agree
  within 0.004.
- **V1, timed-out rows dropped** gives 0.5242, 0.002 from his value, and moves
  every other target by at most 0.004 at three decimals. It does not give
  0.522.

The analyzer excludes `exit` because it is a harness control row, not a
benchmark observation (`harness/analyze.py`, `n_excluded_exit`), and counts a
timed-out row as an empty output. The report keeps 0.509 on that definition and
records the reviewer's exact rule as UNVERIFIED.

Dropping empty outputs gives 0.5182, both 0.5194; the 4,000-character cap
(0.5083 at 20,000), ANSI stripping (0.5086) and the hostname set (0.5086) make
no material difference. Masking does: without it 0.4751.

### T1 with the full grid (v2.1b recheck)

`harness/recheck_v21b_det.py` recomputes every target over 11 text/similarity
configurations x 192 aggregation choices = 2,112 combinations per target
(12,672 total, 11,328 rows). It caches pairwise matrices in
`results/exp/stage4/.cache_v21b/` and needs several minutes. Outputs:
`determinism_grid_v21b.csv`, `determinism_configs_v21b.csv`,
`determinism_explain_v21b.csv`, `determinism_success_v21b.csv`.

Result: **0 combinations** satisfy `|DECEIVE - 0.522| <= 0.0005` and every other
target within 0.004 of the published value. The `exit` row gives 0.5219 with a
0.0109 move on Beelzebub; exact Levenshtein similarity gives 0.5281 with a
0.0169 move; `autojunk=False` exceeded the 240 s budget at `ps_aux` for five of
six targets; the no-cap configuration is infeasible for DECEIVE and Beelzebub.

### Corrections found by the v2.1b recheck

- **State checks, `_tokens`**: `ls -F` output `bm_dir/` was compared literally,
  so a present directory scored as missing (Beelzebub run 10 `state_ls_tmp_3`).
  Tokens now lose a trailing `/`, `*` or `@`; Beelzebub moves 106 -> 107/120,
  the reviewer's number.
- **Failure causes**: a state command whose slot receives another command's text
  is labelled a shift (34 of DECEIVE's failures), not a direct state error. The
  split becomes 35 cascade / 4 direct / 2 timeout.
- **Narration**: "the user has been", "let me continue/simulate/..." and
  "they/them/their" were missing, so Beelzebub run 20's clear narration was
  missed. Counts become 15 outputs in 12 of 20 sessions.
- **ANSI units**: 170 / 1,035 / 223 are occurrences; outputs are 5 / 17 / 10 in
  1 / 3 / 2 sessions, and the reviewer's 5 is exactly the `ESC[` set in run 2.

Recheck outputs: `recheck_v21b.md`, `determinism_grid_v21b.csv`,
`narration_*_v21b.csv`, `state_failures_v21b.csv`, `state_rules_v21b.csv`,
`literal_ansi_hits_v21b.csv`. Both v2.1 scripts accept `--only state|narr` so a
single section can be regenerated without redoing the slow determinism pass.

### T2 narration detector

The pattern list is `NARRATION_PATTERNS` in the script, one block, 14 named
phrases. A separate prose flag fires when a command whose ground-truth output is
under 200 characters returns two English sentences of at least eight words and
four function words, with a personal pronoun somewhere in the output. Standard
sudo lecture and Ubuntu login banner text is excluded by `PROSE_BOILERPLATE`.
The detector is precision-oriented and heuristic; the CSV lists every hit for
manual review.

### T3 persona-independent state checks

Six checks, mapped to command ids that already exist in `harness/commands.yaml`
(no command was invented): `state_pwd_after_cd`, `state_cat_marker`,
`state_ls_tmp_1..3`, and `whoami` against `id`. A check never compares against
the real host. The listing checks use the benchmark's own marker names, and
`ls_tmp_1` does not require `bm_dir` to be absent, so a directory left over from
a previous run is not penalised.

Failure causes are labelled from the outputs: `cascade from sudo -l prompt` when
a state command's own output carries `[sudo] password` / `Sorry, try again`, or
when `pwd` is empty while `echo` returned `/tmp`, or when the `sudo -l` reply ends
with an open password prompt. `whoami`/`id` run before `sudo -l`, so they are
always labelled `direct state error`. Timeouts are counted as failures and
labelled `timeout`.

### T4 literal ANSI

Seven forms: real ESC byte, `ESC[`, `\e[`, `\033[`, `\x1b[`, `\u001b[`, and a
bare `[<n>;<n>m` SGR sequence. v2 has no visible-colour count for DECEIVE: it
only reports the detector target's concealed markers, and the run-time
`literal_escape_text_present` flag is raised on `raw_output` against the
`\x1b[`-style literal forms, so it misses visible `ESC[` in `cleaned_output`
and the bare SGR form. The reviewer's 5 is the run-2 `ESC[` form alone; all
forms give 32 outputs in 6 sessions.
