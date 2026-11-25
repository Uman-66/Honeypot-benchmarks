# NEXT_EXPERIMENT.md — runbook for the next round

Status: **planning document.** Nothing in here has been executed. Every command is written to be
copied verbatim from the repository root in **PowerShell** on Windows.

Read this whole file once before running anything. Phase 1 (pre-flight) and Phase 2 (baseline
verification) are not optional; the rest of the document assumes both passed.

---

## Stage 2 status (branch `stage2-measurement`; merged into `main`)

Stage 2 fixed the measurement layer before any more API calls are spent. Read this
section first: two of the rules below have changed.

| Reviewer point | Status after Stage 2 |
|---|---|
| (a) the 0.5 s quiet period dominates real-server latency | **measured.** `groundtruth_ssh` quiet median 0.547 s / p95 0.563 s; cowrie 0.563 s / 0.578 s. Under `--timing prompt` both fall to 0.0155 s median (min 0.0148, p95 0.0187 / 0.0316), which is the 5 ms settle window rounded up to the 15.6 ms Windows timer tick. The published 0.56 s is the harness. See `results/exp/floor.md`. |
| (b) no per-request API timing | **verified on one target.** `harness/api_proxy.py` logs one JSONL row per request (duration, status, size, token usage, request SHA-256; never headers or bodies). A 10-request AdvancedshelLM smoke run matched every command to exactly one request with a 0.045 s median non-API gap. Wiring for the other five targets is in `docs/STAGE2_NOTES.md` and is still untested. |
| (c) ground-truth determinism never reported after masking | **done on the existing batch.** `results/exp/summary_v2.md` reports determinism for `groundtruth_ssh` and every target, raw text and masked, side by side. `groundtruth_ssh` = 0.9746 raw / 0.9841 masked; cowrie 0.9874 / 0.9957. |
| (d) fidelity mixes persona with shell errors | **partly addressed.** A masked fidelity column and an explicit persona note were added; separating the two still needs E5c. |

Other changes that affect the phases below:

- **Phase 3 Step 3.0 is out of date.** `harness/analyze.py` now accepts
  `--masked-report DIR`, which writes `summary_v2.md` / `summary_v2.csv` /
  `determinism_v2.csv` into `DIR` and touches nothing under `results/`. With no
  argument it still writes `results/summary.md` exactly as before.
- **"Do not touch `harness/*.py`" no longer applies on this branch.** `run_ssh.py`
  gained `--timing prompt` and `--no-mask-credentials`; `run_http.py` gained
  `--no-mask-credentials`; `analyze.py` gained masking and the flag above. Defaults
  are unchanged, so the published batch stays reproducible.
- **Latency comparisons must subtract the floor.** Any new cell run in the default
  timing mode carries ~0.55 s of harness wait. Run E12c and the mechanism cells with
  `--timing prompt` (~15.5 ms floor after the Stage 2 fix), or report both modes.
- **Prompt mode is validated.** A full 37-command quiet-vs-prompt audit on
  `groundtruth_ssh` and cowrie found no command losing output (same byte length in both
  modes); the only differences are volatile fields such as free memory and PIDs.
  `harness/timing_audit.py` reproduces that check.

## 0. What this round is for

The current report is a descriptive snapshot. Determinism spans 0.4664–0.8364 against a Cowrie
baseline of 0.9874, Beelzebub times out 16 times, galah returns 5xx on 11/100 requests — but the
report says "cause UNVERIFIED" about a dozen times. Each experiment below removes exactly one of
those unknowns.

| ID | Question it answers | Type | Status |
|---|---|---|---|
| E0 | Do the headline numbers survive my own analysis parameters? | robustness check | ready, no API |
| E12c | Are timeouts an artifact of run order / API load? | confound fix | ready |
| E7 | Can a model that did not generate the output tell it apart from real Ubuntu? | face-validity check | **gated** |
| E1 | Is determinism a function of temperature? | mechanism | ready |
| E5a | Are VelLMes timeouts caused by prompt verbosity vs `MAX_TOKENS`? | mechanism | ready |
| E5c | Is the fidelity gap capability or persona? | confound fix | ready |

Only **E12c and E5c** fix confounds. E0 is a robustness check and must not be described as a
confound fix in the write-up. E1, E5a and E5c are mechanism tests at n = 5: they are direction
checks, not hypothesis tests. Do not attach p-values to them.

Parked deliberately, because they are too large to finish well in this round: adaptive attacker,
timing side channel, session memory, HTTP and generator tracks, canned static baseline, a second
endpoint.

---

## 1. Five ground rules (violate these and you lose data)

1. **Nothing new is written into `results/raw` or `results/raw_http`.** Every new cell writes to
   `results/exp/raw`. The published batch stays byte-identical so it can always be defended.
2. **`harness/analyze.py` is never run casually.** It has no CLI arguments and writes
   `results/summary.md`, `results/summary.csv`, `results/summary_by_run.csv` and
   `results/ANALYSIS_AUDIT.md` in place (`analyze.py:39-40` and `main()` at `:1237`). It is run
   exactly twice in this runbook — once in Phase 2 on purpose, after a snapshot, and once at the
   very end if you want the published summary regenerated.
3. **`results/ssh_commands_long.csv` is stashed before every batch.** `run_ssh.py:798` hardcodes
   `csv_path = Path("results") / "ssh_commands_long.csv"`, ignoring `--out`, so it accumulates
   across batches no matter where the JSONL goes. Analyze JSONL only.
4. **Every variant target is registered in `harness/targets.yaml` with `kind: llm` before it runs.**
   Unregistered names get `kind = "unknown"` and silently produce no determinism row
   (`analyze.py:1276-1277`, gate at `:447`).
5. **`.env` has no `MODEL`.** `api_probe.py` requires `OPENAI_API_KEY`, `OPENAI_BASE_URL` *and*
   `MODEL`, and exits 2 if any is missing. Export `MODEL` in every shell that runs a probe.

6. **One flag name everywhere: `--target`.** `--help` (Step 1.10) documents `--target` as
   "Comma-separated target names (default: all SSH targets)", so one cell and a batch of cells use
   the identical flag. `--targets` also exists, but it doubles as "path to a different YAML file";
   use it only for that, never for naming cells.

---

## 2. Where data lives

```
results/                     published batch (35 SSH JSONL + 10 HTTP + summaries) — READ ONLY
results/raw/                 published SSH JSONL       <target>_runNN.jsonl
results/raw_http/            published HTTP JSONL
results/ssh_commands_long.csv, http_requests_long.csv   append-only, batch-mixed — do not analyze
results/api_probe.csv        API weather; does not currently exist
results/summary.md|csv, summary_by_run.csv, ANALYSIS_AUDIT.md   analyzer output — regenerable
results/exp/                 EVERYTHING NEW GOES HERE (created in Phase 4)
```

Filename pattern is confirmed at `run_ssh.py:811,826`: `{target}_run{run:02d}.jsonl`, e.g.
`vellmes_run03.jsonl`. The analyzer derives the target from the filename (`analyze.py:88-90`), so
**the filename is the identity of the run** — never rename these files.

---

## 3. Files this round creates or edits

| File | Action | Why |
|---|---|---|
| `harness/targets.yaml` | **edit** (append 7 entries) | register variant targets |
| `docker/vellmes.t00.yaml` | create | E1 overlay: `TEMPERATURE: "0.0"` only, no `volumes:` |
| `docker/vellmes.sp2000.yaml` | create | E5a overlay: `MAX_TOKENS: "2000"` only, **no `volumes:`** — the sentence must stay present |
| `docker/vellmes.nosize.yaml` | create | E5a overlay: `MAX_TOKENS` + bind the sentence-deleted prompt |
| `docker/vellmes.persona.yaml` | create | E5c overlay: bind the persona prompt |
| `docker/vellmes_configSSH_nosize.yml` | create | prompt with the "as big as possible" clause removed |
| `docker/vellmes_configSSH_persona.yml` | create | persona-matched prompt |
| `docker/galah.cell.yaml` | create | override `LLM_TEMPERATURE` |
| `docker/deceive.persona.yaml` | create | bind persona `config.ini` + `prompt.txt` |
| `DECEIVE/SSH/config_persona.ini` | create | DECEIVE persona with password auth |
| `DECEIVE/SSH/prompt_persona.txt` | create | DECEIVE persona prompt |
| `docker/vellmes_ssh_wrapper.py` | **edit** (2 lines) | credentials from env — E5c only |
| `docs/PATCH_NOTES.md` | **edit** | it is factually wrong, see Phase 0 |
| `BENCHMARK.md` | **edit** (table only) | DECEIVE temperature/cap are wrong, see Phase 0 |
| `%TEMP%\e0\*.py` | create, outside repo | E0 analyses |
| `%TEMP%\e7\*.py` | create, outside repo | E7 judge |

Compose files are always used as `-f base -f overlay`, so the shipped files stay unmodified and
every cell is one command you can re-run.

**Do not touch:** `harness/run_ssh.py`, `harness/run_http.py`, `harness/analyze.py`,
`harness/api_probe.py`, any Dockerfile, `.env`, or anything under `results/`.

> Stage 2 exception (branch `stage2-measurement`): `run_ssh.py`, `run_http.py` and
> `analyze.py` were deliberately changed there to add prompt timing, write-time
> credential masking and the masked comparison. Their default behaviour is unchanged.

---

## PHASE 0 — Fix the documentation first (≈1.5 h, no compute)

A reviewer who finds a wrong "not recorded" beside a real number discounts the real number. Fix
these before the professor sees either document.

**Step 0.1 — `docs/PATCH_NOTES.md`.** Its opening claim that no `patches/` directory exists is
false: `patches/vellmes.patch` (181 lines), `patches/honeybee.patch` (737),
`patches/honeybee_before_fixes.patch` (632), and `README.md:62-64` tells the reader to `git apply`
them. The file also has **no VelLMes section and no HoneyBee section at all**, so setup is not
reproducible from it.

Check what the patches actually do before writing the sections:

```powershell
Get-Content patches\vellmes.patch -TotalCount 40
Get-Content patches\honeybee.patch -TotalCount 40
git -C VelLMes-AI-Deception-Framework status --short
git -C honeybee status --short
```

Record in PATCH_NOTES, per patch: which repository, whether it is already applied in the working
tree, and what breaks if it is not applied.

**Step 0.2 — `BENCHMARK.md` configuration table.** Two entries need correcting:

- DECEIVE temperature "not recorded" → it **is** 0.2, in `DECEIVE/SSH/config.ini` `[llm]`.
- DECEIVE max tokens "not recorded" → there **is no output cap** (`ssh_server.py:421-429` builds
  `ChatOpenAI` with no `max_tokens`; the only `max_tokens` is a history trimmer at `:588`). This
  is what produces the 135,108-character maximum output; say so instead of leaving it unexplained.
- Beelzebub "not recorded" is correct, but reword to "not exposed by the plugin configuration
  (plugin source is not in this repository)".

**Verify:** `Select-String -Path BENCHMARK.md -Pattern "not recorded"` should now return only the
Beelzebub line.

---

## PHASE 1 — Pre-flight (≈1 h, do not skip)

**Step 1.1 — Container inventory.**

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
Expect the eight services started by `scripts/up_all.ps1`, plus `vellmes` and `honeybee` started
separately (`README.md:99-103`). Anything not `Up` is a stop.

**Step 1.2 — Port reachability.** Expected listeners: 8022 (deceive), 2222 (beelzebub), 2223
(cowrie), 2224 (advshellm), 2225 (groundtruth_ssh), 2226 (groundtruth_http), 2227 (llmhoneypot),
2228 (vellmes), 8088 (galah).

```powershell
"8022","2222","2223","2224","2225","2226","2227","2228","8088" | ForEach-Object {
  $r = Test-NetConnection -ComputerName 127.0.0.1 -Port $_ -WarningAction SilentlyContinue
  "{0} {1}" -f $_, $r.TcpTestSucceeded
}
```

**Step 1.3 — Establish the batch timeout.** The harness default is 90 s (`run_ssh.py:740`), and
the VelLMes wrapper has its own soft deadline `EXEC_TIMEOUT` defaulting to **90 s**. Whatever the
published batch used must be what E12c uses, or the timeout comparison is confounded.

```powershell
Select-String -Path README.md,BENCHMARK.md,docs\*.md -Pattern "timeout" | Select-Object -First 20
```
Write the answer down here before continuing: batch timeout = ______ s.

**Step 1.4 — Snapshot the published batch.**

```powershell
Copy-Item results results_pre_next_round -Recurse
(Get-ChildItem results\raw\*.jsonl).Count          # expect 35
(Get-ChildItem results\raw_http\*.jsonl).Count     # expect 10
Get-FileHash results\summary.md, results\summary.csv, results\summary_by_run.csv | Format-Table
```
Record those three hashes. They are how you prove at the end that the published batch was never
altered.

**Step 1.5 — Stash the append-only CSVs.**

```powershell
New-Item -ItemType Directory results\exp -Force | Out-Null
Copy-Item results\ssh_commands_long.csv     results\exp\batch1_ssh_commands_long.csv
Copy-Item results\http_requests_long.csv    results\exp\batch1_http_requests_long.csv
```

**Step 1.6 — Confirm the probe file is absent.** It does not currently exist; make sure nothing
left a stop sentinel behind either.

```powershell
Test-Path results\api_probe.csv    # expect False
Test-Path results\STOP_PROBE       # expect False
Remove-Item results\STOP_PROBE -ErrorAction SilentlyContinue
```

**Step 1.7 — Export `MODEL`.** Required by `api_probe.py`, absent from `.env`.

```powershell
$env:MODEL = "accounts/fireworks/models/glm-5p3-flash"
```

**Step 1.8 — The E7 gate.** Confirm a usable judge model that is **not** `glm-5p3-flash` exists
(check the Fireworks dashboard, or a models-list call you make yourself). Self-preference bias
makes a model judging its own output worthless. If no second model is available, write "E7
blocked on second-model access" and skip Phase 5 entirely — do not substitute the generator model.

Gate status: [ ] second model confirmed: ____________________  [ ] blocked

**Step 1.9 — Record the environment.** Version drift is the most likely explanation for any
difference you find later.

```powershell
docker --version; docker compose version; python --version
docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedSince}}" | Select-String honeypot
```

**Step 1.10 — Reconcile the interpreter and the CLI flags (run before Phase 2).**

`run_ssh.py` imports `paramiko` at module scope (`run_ssh.py:38`), so a missing dependency makes
`--help` itself fail. Check the interpreter you intend to use:

```powershell
python -c "import paramiko, yaml; print('ok', paramiko.__version__, yaml.__version__)"
```

If that fails, install the harness's own declared requirements into a venv and use that interpreter
for every command in this runbook:

```powershell
python -m venv .venv-harness
.venv-harness\Scripts\python.exe -m pip install -r harness\requirements.txt
.venv-harness\Scripts\python.exe harness\run_ssh.py --help
```

Use a **separate** venv from any environment that has `pyhoneybee` installed: `harness/requirements.txt`
pins `PyYAML==6.0.1` while `pyhoneybee` requires `PyYAML==6.0.2`, so installing the harness deps into
the honeybee environment produces a resolver conflict. Pinning `PyYAML==6.0.2` inside the harness
venv is harmless — the harness only needs a working YAML parser.

Then confirm the flags actually accepted by both tools, because a flag name that does not exist
fails at the worst moment — mid-batch:

```powershell
python harness\run_ssh.py  --help
python harness\run_http.py --help
```

Verified signature at time of writing:

| Flag | `run_ssh.py` | `run_http.py` |
|---|---|---|
| `--target` | comma-separated target names, default all SSH targets | same, default all HTTP targets |
| `--targets` | config path **or** comma-separated names | same |
| `--commands` / `--requests` | `harness/commands.yaml` | `harness/http_requests.yaml` |
| `--runs` | default 5 | default 5 |
| `--out` | default `results/raw` | default `results/raw_http` |
| `--timeout` | default **90.0** | default **30.0** |
| `--dry-run`, `--force` | both present | both present |

Every command in this runbook uses `--target`; none of them relies on a flag that is absent. If a
future edit changes the CLI, this step is where you find out.

---

## PHASE 2 — Baseline verification (≈1.5 h, no API calls)

Purpose: prove the pipeline reproduces the published numbers *before* you add new data to it. If
this phase fails, nothing downstream is trustworthy.

**Step 2.1 — Run the analyzer once, on purpose.**

```powershell
python harness\analyze.py
Get-FileHash results\summary.md, results\summary.csv, results\summary_by_run.csv | Format-Table
```

**Step 2.2 — Compare against the Phase 1.4 hashes.** Two outcomes:

- *Identical* → the analyzer is deterministic on this data and the published summaries are exactly
  what the data produces. Best case; continue.
- *Different* → do not panic and do not proceed blindly. Restore and investigate:

```powershell
Copy-Item results_pre_next_round\summary.md, results_pre_next_round\summary.csv, `
          results_pre_next_round\summary_by_run.csv, results_pre_next_round\ANALYSIS_AUDIT.md results\ -Force
```
  Then find what moved. The usual culprits are a stale `ssh_commands_long.csv` feeding a
  different command set, or a target present in `results/raw` but absent from `targets.yaml`.

**Step 2.3 — Check the headline numbers by eye.** All of these must appear:

| Quantity | Expected |
|---|---|
| determinism deceive / beelzebub / advshellm / vellmes / cowrie | 0.4664 / 0.6800 / 0.7836 / 0.8364 / 0.9874 |
| fidelity (CSV columns) deceive / beelzebub | 0.4738 / 0.3785 |
| fidelity (report) deceive / beelzebub | 0.4731 / 0.3737 |
| vellmes fidelity | 0.6070 |
| timeouts beelzebub / vellmes / deceive | 16 / 9 / 5 |
| galah 5xx / status agreement / repeat similarity | 11/100 / 25/94 / 0.2364 |
| DECEIVE oversized, max chars | 2, 135,108 |
| beelzebub oversized, max chars, leakage | 9, 239,959, 14/180 |

The two fidelity rows differ because they are different aggregation columns; that divergence is
already documented. If you are trying to reproduce 0.3737, use `fidelity_shared`, not
`fidelity_comparable_mean_sim`.

**Step 2.4 — Smoke test the harness without API calls or containers.**

```powershell
python harness\run_ssh.py --target cowrie --runs 5 --dry-run --out scratch\smoke
```
This validates YAML parsing and target resolution. If it fails, fix `targets.yaml` now — before
editing it in Phase 6.

---

## PHASE 3 — E0: robustness re-analysis (0 API calls, ~1 h compute + ~2–3 h writing scripts)

**Question.** Do the headline numbers survive the analyzer's own parameter choices?
**Falsifier.** Per-command fidelity ranking is unchanged at similarity caps 1k/2k/4k/8k, and no
single dropped command changes any target's rank → metric choices are not load-bearing.

**Why this is first.** It is free, it needs no containers, and if the ranking is fragile you would
rather learn that before spending 1,500 API calls.

**Step 3.0 — Learn the analyzer's API before writing anything.** Its paths are module-level
constants relative to the current directory (`analyze.py:37-40`), and the similarity cap is read
at call time from the module global (`:62` applied at `:139`). So both are patchable, and the
script must run from the repo root.

```powershell
Select-String -Path harness\analyze.py -Pattern "^def |^    def " | Select-Object -First 40
Select-String -Path harness\analyze.py -Pattern "SIMILARITY_TEXT_LIMIT|_similarity|fidelity_shared|determinism"
```

**Step 3.1 — Cap sensitivity (`%TEMP%\e0\cap_sensitivity.py`).** Skeleton:

```python
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("harness").resolve()))
import analyze

def run(cap):
    analyze.SIMILARITY_TEXT_LIMIT = cap          # read at call time, :139
    # call the same internals main() uses: per-target analysis over analyze.RAW_SSH_DIR
    # do NOT call analyze.main() — it would overwrite results/summary.*
    ...

if __name__ == "__main__":
    for cap in (1000, 2000, 4000, 8000):
        print(json.dumps({"cap": cap, "result": run(cap)}))
```

The one hard rule: **never call `analyze.main()`** from these scripts. Import the functions, keep
every write inside `%TEMP%\e0\`.

**Step 3.2 — Leave-one-command-out (`loo.py`).** For each of the 36 scored commands, drop it and
recompute fidelity per target using the **same shared intersection** (`analyze.py:641-661`). Report
the max absolute shift and whether any target changes rank. Dropping a command must also drop it
from every target's intersection, or you are measuring different command sets.

**Step 3.3 — Per-command determinism (`per_command_determinism.py`).** Read
`determinism.per_command` from a normal analysis and rank commands by instability, per target.
This is what tells you whether Beelzebub's 0.6800 is uniform noise or three catastrophic commands.

**Step 3.4 — Timeout-as-failure (`state_timeout_as_failure.py`).** Re-score state-check commands
counting VelLMes' 9 and DECEIVE's 5 timeouts as failures rather than as unavailable. Report both
the strict and permissive numbers so the report can quote whichever it defends.

**How to run.**

```powershell
New-Item -ItemType Directory $env:TEMP\e0 -Force | Out-Null
python $env:TEMP\e0\cap_sensitivity.py --caps 1000,2000,4000,8000
python $env:TEMP\e0\loo.py --raw results\raw
python $env:TEMP\e0\per_command_determinism.py --raw results\raw
python $env:TEMP\e0\state_timeout_as_failure.py --raw results\raw
```

**Verify.** `Get-ChildItem $env:TEMP\e0` contains only your outputs, and
`git status --short results/` is empty. If `results/summary.md` changed, you called `main()` by
accident — restore from `results_pre_next_round`.

**Record.** One line per analysis: did the ranking hold, and what was the largest shift.

---

## PHASE 4 — E12c: order randomization with drift controls (555 API calls, ≈1.75 h)

**Question.** Are the timeout counts (Beelzebub 16, VelLMes 9, DECEIVE 5) a function of target
order and API load rather than target behaviour?
**Falsifier.** The randomized batch reproduces 16/9/5 and both controls are unchanged → order is
not a confound and the ordered batch stays primary.

**Scope.** Beelzebub, VelLMes, DECEIVE re-run; Cowrie and `groundtruth_ssh` as drift controls;
HTTP dropped (galah and GT HTTP keep ordered-batch values — state this as a limitation).

**Why this version is safer than the obvious one.** `run_ssh.py` honours `--out` for JSONL
(`:797,811,826`) but hardcodes the CSV to `results/ssh_commands_long.csv` (`:798`). Writing to
`results/exp/raw` therefore leaves every published JSONL untouched, **and** the duplicate guard
(`:808-815`) never fires because that directory starts empty — so **no `--force` is needed and no
`.bak` files are created.**

**Step 4.1 — Start the API weather probe in a separate window.** Leave it running for the whole
batch; it writes one row every ~30 s (`api_probe.py` sleeps 30×1 s between probes).

```powershell
$env:MODEL = "accounts/fireworks/models/glm-5p3-flash"
python harness\api_probe.py
```
Check it is alive and not erroring:

```powershell
Start-Sleep 60; Get-Content results\api_probe.csv -Tail 3
```
If `http_status` is empty and `error_type` is set on every row, stop and fix the key/base URL
before spending calls.

**Step 4.2 — Run the shuffled batch.** Use the timeout you established in Step 1.3.

```powershell
$timeout = 120   # <-- replace with the value from Step 1.3
$batch = "beelzebub","vellmes","deceive","cowrie","groundtruth_ssh"
for ($r = 1; $r -le 5; $r++) {
  $order = $batch | Get-Random -Count $batch.Count
  $order | Out-File "results\exp\order_run0$r.txt"
  foreach ($t in $order) {
    Write-Host "run $r : $t"
    python harness\run_ssh.py --target $t --runs $r --timeout $timeout --out results\exp\raw
    if ($LASTEXITCODE -ne 0) { Write-Error "failed on $t run $r"; break }
  }
}
```

**Expected output.** `results\exp\raw` gains 25 JSONL files (5 targets × 5 runs) and
`results\exp\order_run01..05.txt` record each order. `results\raw` must still contain exactly 35
files — check it:

```powershell
(Get-ChildItem results\exp\raw\*.jsonl).Count   # 25
(Get-ChildItem results\raw\*.jsonl).Count       # still 35
Get-Content results\exp\order_run01.txt
```

**Step 4.3 — Stop the probe.**

```powershell
New-Item results\STOP_PROBE -ItemType File | Out-Null
Start-Sleep 35
Remove-Item results\STOP_PROBE
Copy-Item results\api_probe.csv results\exp\api_probe_batch2.csv
Remove-Item results\api_probe.csv
```

**Step 4.4 — Compare.** Join `api_probe_batch2.csv` to per-command latency by timestamp so a
moving timeout count has an explanation instead of a shrug. Produce, per target: timeout count in
the ordered batch vs the randomized batch, and the median latency in each.

**Null result means.** Order is not load-bearing; ordered batch stays primary and this becomes a
sensitivity check. **If timeouts move materially**, the randomized batch becomes primary and the
timeout section of the report has to be rewritten — know this *before* emailing the professor.

**Traps.** `exit` may appear as an extra row in Beelzebub run 1; keep scoring it out. Never point
these runs at `results/raw` — the guard would see complete pairs and skip, and `--force` would
overwrite your published data.

---

## PHASE 5 — E7: blind judge (GATED, ≈640 calls, 20–30 min)

**Do not start unless Step 1.8 passed.** Judging outputs with the model that generated them
measures self-preference, not detectability.

**Step 5.1 — Calibration first, ~40 samples, before the real run.**

- Ground truth vs ground truth → the judge should say "real" essentially always.
- Cowrie vs ground truth → the judge must beat chance.

**Stop condition:** if the judge cannot separate Cowrie from real Ubuntu, the experiment cannot
tell you anything about the LLM honeypots. Stop, report a null about the judge, and say so plainly.

**Step 5.2 — Main run.** ~100 (command, output) pairs per target, ground truth included in the
same shuffled pool, judge returning real/emulated + confidence + a one-sentence reason.

```powershell
New-Item -ItemType Directory $env:TEMP\e7 -Force | Out-Null
python $env:TEMP\e7\calibrate.py
python $env:TEMP\e7\judge.py --samples 100 --targets deceive,vellmes,advshellm,beelzebub,cowrie `
       --judge <second-model-id>
```

Run this on **post-E12c** data. Read `.env` inside the script; never print the key.

**Step 5.3 — Report.** Per target: share judged "real", with a run-level interval (not the
command-level bootstrap the analyzer uses). Build a taxonomy of the tells the judge cites —
invented files, uid/hostname mismatch, ANSI in the wrong position, prompt shape, markdown fences.

**Traps.** Randomize presentation order. Strip the trailing prompt identically for every target or
the judge learns prompt shape rather than content. Keep `exit` out of the pool. VelLMes spoofs the
SSH banner (`SERVER_VERSION` in `docker/vellmes_ssh_wrapper.py`), DECEIVE does not — if your
samples include the banner, that is a free tell and the judge is measuring the banner.

---

## PHASE 6 — Target registration (do this before E1, E5a, E5c)

**Step 6.1 — Append to `harness/targets.yaml`.** Seven entries, same shape as the existing ones
(`name`, `kind`, `track`, `host`, `port`, `username`, `password`). Ports are shared with the
shipped targets because cells run one at a time.

```yaml
  # ── Experiment cells (NEXT_EXPERIMENT.md) ──────────────────────────────────
  # Sequential only: these reuse the shipped ports, so exactly one container of a
  # given family may be up at a time. Do NOT put two same-port targets in one
  # --target list.

  - name: vellmes_t00            # E1: temperature 0.0
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 2228
    username: user
    password: user123

  - name: galah_t00              # E1: temperature 0.0 (HTTP)
    kind: llm
    track: http
    host: "127.0.0.1"
    port: 8088

  - name: vellmes_sd_t800        # E5a: sentence deleted, MAX_TOKENS 800
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 2228
    username: user
    password: user123

  - name: vellmes_sd_t2000       # E5a: sentence deleted, MAX_TOKENS 2000
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 2228
    username: user
    password: user123

  - name: vellmes_sp_t2000       # E5a: sentence present, MAX_TOKENS 2000
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 2228
    username: user
    password: user123

  - name: vellmes_persona        # E5c
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 2228
    username: guest
    password: guest

  - name: deceive_persona        # E5c
    kind: llm
    track: ssh
    host: "127.0.0.1"
    port: 8022
    username: guest
    password: guest
```

**Step 6.2 — Validate without running.**

```powershell
python harness\run_ssh.py --target "vellmes_t00,galah_t00,vellmes_sd_t800" --dry-run --out scratch\verify
```
A clean exit means the YAML parses and the names resolve. A `kind: unknown` row later means you
skipped this step.

---

## PHASE 7 — E1: temperature 0.0 vs 0.2 (470 calls, ≈35 min + recreates)

**Question.** Is VelLMes determinism 0.8364 a sampling effect?
**Falsifier.** Determinism at T = 0.0 equals 0.8364 within run-level noise → temperature is not the
driver.

T = 0.2 already exists; T = 1.0 is dropped (nobody deploys it). **Exclude AdvancedshelLM** unless
you first patch `shelLM/.../openai_client.py:159`, because its temperature is hardcoded and an env
var is inert — a sweep there would publish a null from a no-op.

**Step 7.1 — Create `docker/vellmes.t00.yaml`.** The shipped compose sets these as **literals**
inside `environment:`, which beat both `env_file` and your shell. Exporting `$env:TEMPERATURE` and
recreating does nothing — this is the trap that silently produces a duplicate 0.2 cell.

```yaml
services:
  vellmes:
    environment:
      TEMPERATURE: "0.0"
```

**Step 7.2 — Recreate and run.**

```powershell
docker compose -f docker\vellmes.compose.yaml -f docker\vellmes.t00.yaml up -d --force-recreate
docker compose -f docker\vellmes.compose.yaml -f docker\vellmes.t00.yaml logs --tail 20 vellmes
python harness\run_ssh.py --target vellmes_t00 --runs 5 --timeout 120 --out results\exp\raw
```
**Verify the cell is really at 0.0** before trusting the data — the wrapper logs its parameters at
startup ("model=… temperature=… max_tokens=…"). If that line says 0.2, stop: the overlay did not
apply.

**Step 7.3 — galah.** Same pattern; note galah reads `LLM_TEMPERATURE`, not `TEMPERATURE`.

```yaml
# docker/galah.cell.yaml
services:
  galah:
    environment:
      LLM_TEMPERATURE: "0.0"
```
```powershell
docker compose -f docker\galah.compose.yaml -f docker\galah.cell.yaml up -d --force-recreate
python harness\run_http.py --target galah_t00 --runs 5 --out results\exp\raw_http
```

**Step 7.4 — Restore the shipped containers.** Do not leave T = 0.0 running; Phase 8 assumes the
shipped configuration.

```powershell
docker compose -f docker\vellmes.compose.yaml up -d --force-recreate
docker compose -f docker\galah.compose.yaml up -d --force-recreate
```

**Null result means.** Determinism between 0.0 and 0.2 is not temperature-driven; look at session
context, prompt, and API nondeterminism instead.

---

## PHASE 8 — E5a: VelLMes prompt × MAX_TOKENS (555 calls, ≈70 min)

**Question.** Are the `ps_aux` 5/5 and `env` 4/5 timeouts caused by "make them as big as possible"
(`docker/vellmes_configSSH.yml:26`) combined with `MAX_TOKENS=800`?
**Falsifier.** Timeouts persist at 2000 tokens with the sentence deleted → output length is not the
cause.

**Design (2×2, 5 runs per cell).** Only three cells are new: the shipped configuration already
*is* the (sentence present, 800) cell.

| Cell | Prompt | `MAX_TOKENS` | Overlay | Target |
|---|---|---|---|---|
| baseline | sentence present | 800 | none (shipped config) | existing `vellmes` data — **reuse, do not re-run** |
| `vellmes_sp_t2000` | sentence present | 2000 | `vellmes.sp2000.yaml` — **no `volumes:`** | new |
| `vellmes_sd_t800` | sentence deleted | 800 | `vellmes.nosize.yaml` | new |
| `vellmes_sd_t2000` | sentence deleted | 2000 | `vellmes.nosize.yaml` | new |

Each row names exactly one overlay. A cell that inherits another cell's `volumes:` block is no
longer the cell you think it is — `vellmes_sp_t2000` mounted the deleted-prompt file would be a
duplicate of `vellmes_sd_t2000` and the whole 2×2 collapses to a 1×2.

**Step 8.1 — Create the prompt variant.** The config is `COPY`ed into the image
(`vellmes.Dockerfile`: `COPY docker/vellmes_configSSH.yml /app/vellmes/configSSH_bench.yml`) and is
**not** bind-mounted, so editing the original means rebuilding. Instead copy it and bind-mount over
that path, which needs no rebuild and leaves the shipped file intact.

```powershell
Copy-Item docker\vellmes_configSSH.yml docker\vellmes_configSSH_nosize.yml
```
In the copy, delete only the clause "make them as big as possible and", keeping "Be very detailed"
and "think step by step" so the cell changes exactly one thing.

```powershell
Select-String -Path docker\vellmes_configSSH_nosize.yml -Pattern "detailed|step by step|as big"
```

**Step 8.2 — Create two overlays, not one.** This is the bug that silently turns the 2×2 into a
1×2: if the sentence-present cell uses the overlay that bind-mounts the deleted-prompt file, that
cell runs with the sentence deleted and becomes a duplicate of `vellmes_sd_t2000`.

`docker/vellmes.sp2000.yaml` — sentence **present**, only the cap changes. Note the deliberate
absence of any `volumes:` block:

```yaml
services:
  vellmes:
    environment:
      MAX_TOKENS: "2000"
```

`docker/vellmes.nosize.yaml` — sentence **deleted**, cap set per cell. Copy this file and edit the
one line for the 800-token cell:

```yaml
services:
  vellmes:
    environment:
      MAX_TOKENS: "2000"        # set to "800" for vellmes_sd_t800
    volumes:
      - type: bind
        source: ./vellmes_configSSH_nosize.yml
        target: /app/vellmes/configSSH_bench.yml
        read_only: true
```

Compose merges `environment` per key (overlay wins) and appends `volumes`, so an overlay with no
`volumes:` key leaves the shipped prompt untouched — and an overlay **with** one shadows it.

**Step 8.3 — Run each cell with its own overlay, one at a time.** Never put two same-port targets
in one `--target` list; each cell needs its own recreate, and the overlay must match the cell.

```powershell
$cells = @(
  @{ name = "vellmes_sp_t2000"; overlay = "docker\vellmes.sp2000.yaml"; cap = "2000" },
  @{ name = "vellmes_sd_t800";  overlay = "docker\vellmes.nosize.yaml"; cap = "800"  },
  @{ name = "vellmes_sd_t2000"; overlay = "docker\vellmes.nosize.yaml"; cap = "2000" }
)
foreach ($c in $cells) {
  docker compose -f docker\vellmes.compose.yaml -f $c.overlay up -d --force-recreate
  $log = docker compose -f docker\vellmes.compose.yaml -f $c.overlay logs --tail 20 vellmes | Select-String "max_tokens"
  Write-Host "$($c.name): $log"
  # single line on purpose: Windows PowerShell 5.1 rejects a trailing pipe as continuation
  if (-not ($log -match $c.cap)) { Write-Error "overlay not applied for $($c.name)"; break }
  python harness\run_ssh.py --target $c.name --runs 5 --timeout 120 --out results\exp\raw
}
```
The `cap` assertion is the point of the loop: it fails loudly instead of quietly producing a cell
labelled 2000 that ran at 800. For `vellmes_sd_t800`, edit `MAX_TOKENS` in
`vellmes.nosize.yaml` to `"800"` immediately before that iteration.

**Verify the prompt really differs** between the two families before trusting the comparison:

```powershell
Select-String -Path docker\vellmes_configSSH.yml,docker\vellmes_configSSH_nosize.yml -Pattern "as big"
```
Exactly one file must match.

**Step 8.4 — Record censoring, not just timeouts.** The wrapper has a soft deadline,
`EXEC_TIMEOUT` default **90 s**, and on expiry it returns whatever it accumulated instead of
failing. So a "timeout" in the results can be either a harness-level abort or a wrapper-level
truncation. Log `EXEC_TIMEOUT` per cell and report the censored fraction per command.

**Null result means.** Length is exonerated; the next suspects are prompt-following and the
wrapper's prompt detection (`_has_prompt`). That would be a more interesting finding than the
original hypothesis.

---

## PHASE 9 — E5c: persona-matched fidelity (370 calls, ≈40 min)

**Question.** Is the fidelity gap (DECEIVE 0.4731 vs VelLMes 0.6070) capability or persona?
**Falsifier.** Two tools with the identical persona still differ by more than 0.1 → capability.

**Write this down before you run it:** if persona explains the gap, difflib fidelity was never
measuring tool quality. That explains the overlapping confidence intervals, retires fidelity as a
ranking metric, and moves the weight onto E7.

**Step 9.1 — Match the persona on both sides.** Same hostname `srv-ubuntu`, same home `/home/user`,
same Ubuntu 20.04 wording, no invented game assets.

```powershell
Copy-Item docker\vellmes_configSSH.yml docker\vellmes_configSSH_persona.yml
# edit docker\vellmes_configSSH_persona.yml: hostname, home dir, OS string — and keep the
# shipped "Be very detailed" wording, since this experiment varies persona only
```

`docker/vellmes.persona.yaml` binds it over the baked-in copy (no rebuild):

```yaml
services:
  vellmes:
    environment:
      MAX_TOKENS: "800"        # shipped value, stated explicitly so the overlay is self-contained
      # REQUIRED: targets.yaml registers vellmes_persona as guest/guest. Without these the
      # wrapper keeps its user/user123 defaults and every login in this cell fails.
      VALID_USER: "guest"
      VALID_PASSWORD: "guest"
    volumes:
      - type: bind
        source: ./vellmes_configSSH_persona.yml
        target: /app/vellmes/configSSH_bench.yml
        read_only: true
```

**Step 9.2 — Match the login surface, or document that you did not.** The wrapper hardcodes
`VALID_USER`/`VALID_PASSWORD` (`docker/vellmes_ssh_wrapper.py`, lines 71-72), and DECEIVE is
`auth: none`. Without this step, every VelLMes transcript opens with a password auth for `user`
and every DECEIVE one with no auth at all — a free discriminator that has nothing to do with output
quality.

Two-line change in the wrapper:

```python
VALID_USER     = os.environ.get("VALID_USER",     "user")
VALID_PASSWORD = os.environ.get("VALID_PASSWORD", "user123")
```

Keeping the defaults as `user`/`user123` leaves every other VelLMes cell at its shipped behaviour;
only the persona cell overrides them. That override has to come through the overlay, which is why
`docker/vellmes.persona.yaml` passes `VALID_USER` and `VALID_PASSWORD` explicitly — an overlay that
omits them authenticates as `user` while `targets.yaml` advertises `guest`, and every login in the
cell fails with an auth error that looks like a broken container.

Create `DECEIVE/SSH/config_persona.ini` as a copy of `config.ini` with `[user_accounts]` set to
require password `guest` instead of blank (blank is what makes `begin_auth` return False and grant
auth-none). **Verify the intended behaviour with one manual attempt before the batch** — if the
syntax is wrong you will either lock yourself out or leave auth-none in place:

```powershell
ssh -p 8022 guest@127.0.0.1 exit      # DECEIVE: must prompt for a password
ssh -p 2228 guest@127.0.0.1 exit      # VelLMes persona: must prompt AND accept "guest"
```

If the VelLMes attempt prompts but rejects the password, the overlay is not reaching the container.
Check the resolved configuration rather than guessing:

```powershell
docker compose -f docker\vellmes.compose.yaml -f docker\vellmes.persona.yaml config | Select-String "VALID_"
```

**Step 9.3 — Create `docker/deceive.persona.yaml`** (mirrors how the slim Dockerfile bakes the
files in, but shadows them without a rebuild):

```yaml
services:
  deceive:
    volumes:
      - type: bind
        source: ./DECEIVE/SSH/config_persona.ini
        target: /app/SSH/config.ini
        read_only: true
      - type: bind
        source: ./DECEIVE/SSH/prompt_persona.txt
        target: /app/SSH/prompt.txt
        read_only: true
```
Confirm the service name and the compose file that defines it first:
`Select-String -Path docker\*.yaml -Pattern "deceive"`.

**Step 9.4 — Run both cells** (different ports, so one invocation is fine — but only after both
containers are up in their persona configuration):

```powershell
# rebuild vellmes once so the wrapper picks up the env-driven credentials from Step 9.2
docker compose -f docker\vellmes.compose.yaml -f docker\vellmes.persona.yaml up -d --build
# deceive only needs the bind mounts, no rebuild
docker compose -f docker\<deceive-compose>.yaml -f docker\deceive.persona.yaml up -d --force-recreate
python harness\run_ssh.py --target "vellmes_persona,deceive_persona" --runs 5 --timeout 120 --out results\exp\raw
```

**Step 9.5 — Compare against shipped cells, keeping both.** These cells are **not** comparable to
the shipped-config numbers, so report shipped and persona-matched side by side and never mix them
in one table without labelling which is which.

---

## PHASE 10 — Analysis and write-up (≈4–6 h)

**Step 10.1 — Analyze the new data without touching the published summary.** Two options:

- Point the analyzer at the new directory in a script (patch `analyze.RAW_SSH_DIR` before calling
  its internals — it is a plain module constant at `:37`), or
- Copy `results/exp/raw/*.jsonl` into a throwaway tree that also contains the shipped `results/`
  layout, run the analyzer there, and keep the outputs.

Either way, **never let it write into the real `results/`.**

**Step 10.2 — Use a run-level interval for cross-cell claims.** The analyzer's bootstrap resamples
commands, not runs (`:680-698`), so its intervals are too narrow to compare two cells. Resample
runs for anything of the form "cell A differs from cell B".

**Step 10.3 — Verify the published batch was never altered.**

```powershell
Get-FileHash results\summary.md, results\summary.csv, results\summary_by_run.csv | Format-Table
(Get-ChildItem results\raw\*.jsonl).Count    # must still be 35
git status --short
```
Hashes must match Step 1.4.

**Step 10.4 — Professor update, two pages.** Paragraph 1: what was measured. Paragraph 2: the
number that matters and its weakness. Paragraph 3: the anomaly now testable. Then a four-row table
(question, falsifier, cost) and exactly one question — *"should I prioritise mechanism or
generality with roughly one week of compute left?"* — and two dates. Call E0 a robustness check.

---

## Appendix A — Cost and time

| Phase | API calls | Machine time | Human time |
|---|---:|---|---|
| 0 docs | 0 | — | 1.5 h |
| 1 pre-flight | 0 | — | 1 h |
| 2 baseline | 0 | ~5 min | 1.5 h |
| 3 E0 | 0 | ~5 min | 2–3 h |
| 4 E12c | 555 | ~1 h 45 min | 1 h |
| 5 E7 | ~640 | 20–30 min | 3–5 h |
| 6 registration | 0 | — | 20 min |
| 7 E1 | 470 | ~45 min | 30 min |
| 8 E5a | 555 | ~70 min | 1 h |
| 9 E5c | 370 | ~55 min | 1 h |
| 10 analysis | 0 | — | 4–6 h |
| **total** | **~2,590** | **~6.5 h** | **~18–22 h** |

Scoping E5a to three new cells (reusing the shipped baseline) saves 185 calls and ~24 min versus
the four-cell version. Beelzebub alone is ~55 min of E12c; the rest of the batch is ~50 min.

---

## Appendix B — Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `api_probe.py` exits 2 | `MODEL` not exported | `$env:MODEL = "accounts/fireworks/models/glm-5p3-flash"` |
| Cell labelled `_t00` behaves like 0.2 | shell env does not beat compose literals | use the `-f base -f overlay` form, check the startup log line |
| `vellmes_sp_t2000` behaves identically to `vellmes_sd_t2000` | the sentence-present cell mounted the deleted-prompt overlay | use `vellmes.sp2000.yaml` (no `volumes:`), and keep the `cap` assertion in the Step 8.3 loop |
| `run_ssh.py` dies with `ModuleNotFoundError: No module named 'paramiko'` | harness deps not installed in the active interpreter | `pip install -r harness/requirements.txt` into a dedicated venv (see Step 1.10) |
| Every `vellmes_persona` login fails authentication | overlay omits `VALID_USER` / `VALID_PASSWORD`, so the wrapper keeps `user`/`user123` while `targets.yaml` says `guest` | add both under `environment:` in `vellmes.persona.yaml`, rebuild, confirm with `docker compose ... config` |
| Target produces no determinism row | not in `targets.yaml`, or missing `kind: llm` | re-run Phase 6, check `analyze.py:1276-1277` |
| `run_ssh.py` reports all pairs complete and does nothing | writing into an already-populated `--out` | use `results\exp\raw`, or `--force` on a throwaway directory only |
| Timeout counts move a lot in E12c | order/load genuinely matters, or a different `--timeout` | check Step 1.3 first; if genuinely order-dependent, rewrite the timeout section |
| `results/summary.md` changed unexpectedly | something called `analyze.main()` | restore from `results_pre_next_round` |
| galah 5xx surge | galah's own rate limiting, cache disabled | record it; it is a finding, not a bug to fix mid-run |
| DECEIVE persona cell allows login without a password | `[user_accounts]` syntax wrong in the persona INI | verify with the manual `ssh` probe in Step 9.2 |

---

## Appendix C — Still unverified

- Whether `VelLMes.py` passes `args.temperature` / `args.max_tokens` into the API call.
- Call site of `apply_args_to_config()` in `ssh_server.py`.
- Pilot DECEIVE timeout counts 14 (raw) and 17 (CSV); only 13 (summary) is verified.
- Whether `results_backup_as_found/` is identical to `results/`.
- Whether a second Fireworks model exists (blocks Phase 5).
- Beelzebub's runtime temperature (plugin source is not in the tree).
- Applied-state of `patches/*.patch` versus the working trees — check in Phase 0.1.
- Exact `[user_accounts]` semantics used to force password auth in DECEIVE (Phase 9.2).
