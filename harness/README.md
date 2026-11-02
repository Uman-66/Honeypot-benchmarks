# Benchmark Harness — README

## Prerequisites

- Windows 10/11, PowerShell 5.1+
- Docker Desktop with WSL 2 backend enabled
- Python 3.11+ (available in PATH as `python` or `python3`)
- A `.env` file at the repo root containing `OPENAI_API_KEY` and
  `OPENAI_BASE_URL` (required by DECEIVE, Beelzebub, AdvancedshelLM, galah)

---

## 1 — Start all containers

```powershell
# From repo root
.\scripts\up_all.ps1
```

This builds and starts all eight services and waits up to 120 s per port for
TCP readiness.  Expect the first build to take several minutes.

---

## 2 — Create a Python virtual environment and install dependencies

```powershell
# From repo root
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r harness/requirements.txt
```

---

## 3 — Dry run (validate YAML, no network connections)

```powershell
python harness/run_ssh.py  --dry-run
python harness/run_http.py --dry-run
```

Both commands should print `Dry-run: YAML validated OK` and exit with code 0.

---

## 4 — Smoke test (1 run against one target)

```powershell
# SSH smoke test against the Cowrie baseline (fastest, no LLM calls)
python harness/run_ssh.py --target cowrie --runs 1

# HTTP smoke test against the nginx ground truth
python harness/run_http.py --target groundtruth_http --runs 1
```

Check that `results/raw/cowrie_run01.jsonl` and
`results/raw_http/groundtruth_http_run01.jsonl` exist and contain valid JSON
lines.

---

## 5 — Full benchmark run

```powershell
# SSH: all targets, 5 runs each (default)
python harness/run_ssh.py --runs 5

# HTTP: all targets, 5 runs each
python harness/run_http.py --runs 5
```

Output files:
- `results/raw/<target>_run<NN>.jsonl`      — per-command JSONL (SSH)
- `results/raw_http/<target>_run<NN>.jsonl` — per-request JSONL (HTTP)
- `results/ssh_commands_long.csv`           — flat CSV of all SSH results
- `results/ssh_fingerprints.json`           — transport metadata per target/run
- `results/http_requests_long.csv`          — flat CSV of all HTTP results

**Timeouts**: the default per-command SSH timeout is 90 s; AdvancedshelLM's
first banner can take 10+ s (one LLM call before the first prompt).  Increase
with `--timeout 120` if you see early timeouts.

---

## 6 — Analysis

```powershell
python harness/analyze.py
```

Reads all `results/raw/*.jsonl` and `results/raw_http/*.jsonl` files and
writes:
- `results/summary.md`  — human-readable Markdown report
- `results/summary.csv` — one row per target, key metrics

The analyzer requires only the standard library and PyYAML; no pandas or
matplotlib.

---

## 7 — Copy container logs

```powershell
.\scripts\copy_logs.ps1
```

Copies log files from running containers into `results/honeypot_logs/<name>/`.

---

## 8 — Stop all containers

```powershell
.\scripts\down_all.ps1
```

Named volumes (logs, SSH host keys) are preserved.

---

## Options reference

### run_ssh.py

| Option | Default | Description |
|--------|---------|-------------|
| `--targets`  | `harness/targets.yaml`   | Path to targets YAML |
| `--commands` | `harness/commands.yaml`  | Path to commands YAML |
| `--runs`     | `5`                      | Runs per target |
| `--out`      | `results/raw`            | JSONL output directory |
| `--timeout`  | `90`                     | Per-command timeout (s) |
| `--dry-run`  | off                      | Validate YAML only |
| `--target`   | all SSH targets          | Comma-separated target names |

### run_http.py

| Option | Default | Description |
|--------|---------|-------------|
| `--targets`  | `harness/targets.yaml`        | Path to targets YAML |
| `--requests` | `harness/http_requests.yaml`  | Path to requests YAML |
| `--runs`     | `5`                           | Runs per target |
| `--out`      | `results/raw_http`            | JSONL output directory |
| `--timeout`  | `30`                          | Per-request timeout (s) |
| `--dry-run`  | off                           | Validate YAML only |
| `--target`   | all HTTP targets              | Comma-separated target names |

---

## Safety notes

- Every container port is bound to `127.0.0.1` only — no external exposure.
- The harness never sends `wget`, `curl`, `ping`, `nc`, `ssh`, or `telnet`
  commands, and never sends URLs or IP addresses to any container.
- All writes in the ground-truth SSH container go under `/tmp` only.
- The harness refuses to send the llm-honeypot recovery commands
  (`fsck-repair`, `sysctl-recovery`, `server-init`, `id-service`,
  `disk-recover`, `cat8193`) even if they appear in `commands.yaml`.
- Passwords are never logged.

---

## Known limitations / UNVERIFIED items

See `HARNESS_CHANGES.md` for the full list of UNVERIFIED items and known
failure modes.
