# honeypot-benchmark

A reproducible scripted benchmark comparing five LLM-based SSH/HTTP honeypots from the
*awesome-genai-cyberhub* list against a Cowrie baseline and ground-truth servers.
See [BENCHMARK.md](BENCHMARK.md) for full results and methodology.

**Author**: Muhammad Rumman Aslam

---

## What this is

This repository contains the harness code, Docker deployment configurations, result data,
and documentation for a local benchmark of LLM-powered honeypots.  Six targets were
deployed as isolated Docker containers (loopback ports only, no external exposure),
subjected to 37 scripted SSH commands and 20 HTTP requests over 5 runs each, and
compared with ground-truth servers (real Ubuntu 20.04 OpenSSH 8.2 and real nginx 1.18).
The four LLM-based SSH honeypots and the one LLM-based HTTP honeypot all used the same
model on Fireworks AI (`accounts/fireworks/models/glm-5p3-flash` via an
OpenAI-compatible endpoint).

---

## Tool inventory

| Tool | Status | Protocol | LLM-based | Host port | Notes |
|------|--------|----------|-----------|-----------|-------|
| [DECEIVE](https://github.com/coverflex-tech/DECEIVE) | ✅ Done | SSH | Yes | 8022 | LangChain-based; video-game dev persona |
| [Beelzebub](https://github.com/mariocandela/beelzebub) | ✅ Done | SSH | Yes | 2222 | Go-based; seeded pwd/home exchange |
| [shelLM / AdvancedshelLM](https://github.com/stratosphereips/AdvancedShelLM) | ✅ Done | SSH | Yes | 2224 | Subprocess wrapper; `admin@hp_dev_server` persona |
| [galah](https://github.com/0x4D31/galah) | ✅ Done | HTTP | Yes | 8088 | LLM generates HTTP responses as JSON |
| [llm-honeypot](https://github.com/PalisadeResearch/llm-honeypot) | ✅ Done (detector only) | SSH | No | 2227 | ANSI-hidden prompt injection; detector — not a fidelity target |
| [Cowrie](https://github.com/cowrie/cowrie) | ✅ Baseline added | SSH | No | 2223 | Static emulation baseline |
| [VelLMes](https://github.com/stratosphereips/VelLMes-LLM-Honeypot) | ❌ Not attempted | SSH | Yes | — | — |
| [honeybee](https://github.com/jaredfolkins/honeybee) | ❌ Not attempted | SSH | Yes | — | — |
| Ground truth SSH | ✅ Added | SSH | No | 2225 | Ubuntu 20.04 + OpenSSH 8.2p1 |
| Ground truth HTTP | ✅ Added | HTTP | No | 2226 | Ubuntu 20.04 + nginx 1.18.0 |

---

## Repository layout

```
honeypot-benchmark/
├── docker/               Dockerfiles and Docker Compose files for each target
│   ├── deceive.compose.yaml / deceive.slim.Dockerfile
│   ├── beelzebub.compose.yaml / beelzebub-ssh.yaml / beelzebub-core.yaml
│   ├── cowrie.compose.yaml / cowrie/
│   ├── advshellm.compose.yaml / advshellm.Dockerfile / advshellm_ssh_wrapper.py
│   ├── llmhoneypot.compose.yaml / llmhoneypot.Dockerfile / llmhoneypot.cowrie.cfg
│   ├── galah.compose.yaml / galah.Dockerfile / galah-config.yaml / galah-entrypoint.sh
│   ├── groundtruth_ssh.compose.yaml / groundtruth_ssh.Dockerfile
│   └── groundtruth_http.compose.yaml / groundtruth_http.Dockerfile
├── harness/              Benchmark scripts and configuration
│   ├── run_ssh.py        SSH attacker harness
│   ├── run_http.py       HTTP attacker harness
│   ├── analyze.py        Result analyser — writes results/summary.md and .csv
│   ├── commands.yaml     37-command SSH test list with categories
│   ├── http_requests.yaml 20-request HTTP test list
│   ├── targets.yaml      Target definitions (ports, credentials)
│   ├── requirements.txt  Python dependencies
│   └── README.md         Detailed usage guide
├── scripts/              PowerShell management scripts
│   ├── up_all.ps1        Start all 8 containers and wait for port readiness
│   ├── down_all.ps1      Stop all containers (preserves volumes)
│   └── copy_logs.ps1     Copy container logs to results/honeypot_logs/
├── results/              All benchmark output (tracked in git)
│   ├── summary.md        Human-readable summary report
│   ├── summary.csv       One row per target, key metrics
│   ├── ssh_commands_long.csv  Flat CSV of all SSH results
│   ├── http_requests_long.csv Flat CSV of all HTTP results
│   ├── ssh_fingerprints.json  SSH transport metadata per target/run
│   ├── raw/              Per-run JSONL files (SSH)
│   ├── raw_http/         Per-run JSONL files (HTTP)
│   └── honeypot_logs/    Copied container logs
├── docs/
│   └── PATCH_NOTES.md    All source edits made to third-party repos
├── Changes/              Detailed per-task design and change notes
├── BENCHMARK.md          Technical report with full results
├── DOC_REVIEW_NOTES.md   Data check, secret scan, UNVERIFIED items
└── .env                  API key file — NOT committed; create from template below
```

---

## Prerequisites

| Requirement | Minimum version |
|-------------|----------------|
| Windows | 10 or 11 (x64) |
| Docker Desktop | Latest stable with WSL 2 backend enabled |
| Python | 3.10+ (available as `python` or `python3` in PATH) |
| git | Any recent version |
| Fireworks AI API key | Account at [fireworks.ai](https://fireworks.ai) |
| PowerShell | 5.1+ (built into Windows 10/11) |

---

## Reproduction steps

### Step 0 — Rotate the API key

> ⚠️ **Security notice**: A Fireworks API key was present in the `.env` file at
> time of writing.  That key must be revoked and replaced before any further use.
> Never commit `.env` to git.

### Step 1 — Create `.env`

Create a file named `.env` at the repository root with the following content
(replace the placeholder with your actual Fireworks API key):

```ini
OPENAI_API_KEY=<FIREWORKS_API_KEY>
OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1
```

This file is listed in `.gitignore` and will not be committed.

### Step 2 — Re-clone the third-party repositories

The cloned source directories have been deleted from this repository to keep it small.
Clone each one into the exact directory name the Dockerfiles expect:

| Repository | Clone into | Known version |
|-----------|-----------|---------------|
| `https://github.com/coverflex-tech/DECEIVE` | `DECEIVE/` | UNVERIFIED — cloned Oct 31 – Nov 2, 2026 |
| `https://github.com/mariocandela/beelzebub` | `beelzebub/` | UNVERIFIED — cloned Oct 31 – Nov 2, 2026 |
| `https://github.com/stratosphereips/AdvancedShelLM` | `shelLM/` | UNVERIFIED — cloned Oct 31 – Nov 2, 2026 |
| `https://github.com/0x4D31/galah` | `galah/` | UNVERIFIED — cloned Oct 31 – Nov 2, 2026 |
| `https://github.com/PalisadeResearch/llm-honeypot` | `llm-honeypot/` | UNVERIFIED — cloned Oct 31 – Nov 2, 2026 |
| `https://github.com/cowrie/cowrie` (tag `v2.6.1`) | `cowrie-base/` | **Pinned: v2.6.1** |

```powershell
# From repo root
git clone https://github.com/coverflex-tech/DECEIVE DECEIVE
git clone https://github.com/mariocandela/beelzebub beelzebub
git clone https://github.com/stratosphereips/AdvancedShelLM shelLM
git clone https://github.com/0x4D31/galah galah
git clone https://github.com/PalisadeResearch/llm-honeypot llm-honeypot
git clone --branch v2.6.1 https://github.com/cowrie/cowrie cowrie-base
```

### Step 3 — Apply source patches

No `patches/` directory is present.  Apply every edit listed in
[docs/PATCH_NOTES.md](docs/PATCH_NOTES.md) manually to the cloned repositories.
The detailed rationale for each edit is in the corresponding file under `Changes/`.

Key edits required:

- **DECEIVE** (`DECEIVE/SSH/ssh_server.py`, `DECEIVE/SSH/config.ini`): lazy provider
  imports, `strip_llm_output` helper, Fireworks API key/base URL handling,
  `tiktoken_model_name` fix, exit sentinel `.strip()` fix, model name in config.
- **Beelzebub** (`beelzebub/internal/plugins/llm-integration.go`): `OPENAI_API_KEY`
  env var fallback, `OPENAI_BASE_URL`-derived host.
- **AdvancedshelLM** (`shelLM/AdvancedshelLM/codebase/advancedShellm.py`,
  `shelLM/AdvancedshelLM/codebase/LLM_Plugins/api_clients/openai_client.py`):
  non-fatal `.env` load, API key env var fallback, `OPENAI_BASE_URL` base URL,
  `MAX_TOKENS` env var, `BackendHTTPError` wrapping, exit `break` fix.
- **galah** (`galah/pkg/llm/llm.go`): `cleanResponse` `<think>` stripping.
- **llm-honeypot + cowrie-base**: use `cowrie-base/` source (v2.6.1) and overlay
  `llm-honeypot/configs/` command files per `docs/PATCH_NOTES.md` section 5.

### Step 4 — Recreate config files

Some configuration files referenced by the Dockerfiles are already in this repo
under `docker/`.  No additional config recreation is required beyond the `.env` file.

### Step 5 — Create required host directories

Beelzebub uses a bind mount for logs:

```powershell
New-Item -ItemType Directory -Force docker/logs/beelzebub
```

### Step 6 — Start all containers

```powershell
# From repo root
.\scripts\up_all.ps1
```

This builds images and starts all 8 containers.  The first build will take several
minutes.  The script waits up to 120 s per port for TCP readiness and reports which
targets are ready.

**SSH host-key note**: If you rebuild images after a previous run, SSH may reject the
new host key.  Clear stale entries with:

```powershell
ssh-keygen -R "[127.0.0.1]:8022"   # DECEIVE
ssh-keygen -R "[127.0.0.1]:2222"   # Beelzebub
ssh-keygen -R "[127.0.0.1]:2223"   # Cowrie
ssh-keygen -R "[127.0.0.1]:2224"   # AdvancedshelLM
ssh-keygen -R "[127.0.0.1]:2225"   # Ground truth SSH
ssh-keygen -R "[127.0.0.1]:2227"   # llm-honeypot
```

### Step 7 — Set up the Python harness

```powershell
# From repo root
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r harness/requirements.txt
```

### Step 8 — Delete old result files (before a full rerun)

> ⚠️ The harness **appends** to existing CSVs and JSONL files.  Running it again
> without deleting the old files will produce duplicate data.  The CSVs were
> deduplicated for this benchmark, but a fresh run needs a clean slate:

```powershell
Remove-Item results/raw/*.jsonl -ErrorAction SilentlyContinue
Remove-Item results/raw_http/*.jsonl -ErrorAction SilentlyContinue
Remove-Item results/ssh_commands_long.csv -ErrorAction SilentlyContinue
Remove-Item results/http_requests_long.csv -ErrorAction SilentlyContinue
```

### Step 9 — Run the harness

```powershell
# SSH benchmark (all targets, 5 runs each)
python harness/run_ssh.py --runs 5

# HTTP benchmark (all targets, 5 runs each)
python harness/run_http.py --runs 5
```

Increase `--timeout` to 120 if AdvancedshelLM or DECEIVE show early timeouts
(the first LLM call can take 10+ seconds at Fireworks API load).

### Step 10 — Copy container logs

```powershell
.\scripts\copy_logs.ps1
```

Copies logs from running containers into `results/honeypot_logs/<name>/`.

### Step 11 — Run the analyser

```powershell
python harness/analyze.py
```

Writes `results/summary.md` and `results/summary.csv`.

### Step 12 — Stop containers

```powershell
.\scripts\down_all.ps1
```

Named Docker volumes (SSH host keys, honeypot logs) are preserved.
To remove them: `docker volume prune`.

---

## Port table

| Target | Host port | Protocol | Kind |
|--------|-----------|----------|------|
| DECEIVE | 8022 | SSH | LLM honeypot |
| Beelzebub | 2222 | SSH | LLM honeypot |
| Cowrie | 2223 | SSH | Baseline honeypot |
| AdvancedshelLM | 2224 | SSH | LLM honeypot |
| Ground truth SSH | 2225 | SSH | Ground truth |
| Ground truth HTTP | 2226 | HTTP | Ground truth |
| llm-honeypot | 2227 | SSH | Detector (not fidelity target) |
| galah | 8088 | HTTP | LLM honeypot |

All ports are bound to `127.0.0.1` only — no external exposure.

---

## Known issues and tips

- **Never enable `--trace` on AdvancedshelLM**: the trace log writes the Bearer
  token (API key) to `trace_log.txt` on disk.  The wrapper does not pass `--trace`
  by default.
- **Never include URLs or IP addresses in test commands**: Cowrie-family honeypots
  (Cowrie, llm-honeypot) emulate `wget`/`curl` and may attempt real outbound TCP
  connections to raw IP addresses even with DNS blocked.  The benchmark command list
  was designed to avoid this.
- **The harness has no resume**: it appends to existing CSV/JSONL files.  Delete old
  output before a full rerun (see Step 8).
- **AdvancedshelLM had startup failures in early passes**: the final data in
  `results/raw/` is from successful runs; early failures are recorded in
  `results/honeypot_logs/advshellm/`.
- **SSH host keys regenerate on rebuild**: clear `~/.ssh/known_hosts` entries with
  `ssh-keygen -R "[127.0.0.1]:<port>"` after rebuilding images.
- **Named volumes instead of bind mounts**: all honeypots use Docker named volumes
  for logs because Docker Desktop on Windows (NTFS/WSL2) does not give non-root
  container users write access to bind-mounted host directories.
- **PowerShell `docker cp` variable pattern**: `copy_logs.ps1` captures the container
  ID into a variable before calling `docker cp`.  The pattern
  `docker cp "$(docker compose ... ps -q svc):..."` does not work in Windows
  PowerShell because PowerShell does not expand `$(...)` inside double-quoted strings
  passed to external commands.
- **Harness was restarted during data collection**: the CSV files were deduplicated
  afterwards.  All `(target, run, cmd_id)` combinations appear exactly once in the
  final CSVs.

---

## Safety and ethics

- All traffic stays on the loopback interface (`127.0.0.1`).  No real attackers,
  no external network exposure, no malware.
- Commands sent by the harness are benign scripted Unix reconnaissance commands.
  No destructive, escalation, or network commands are used.
- The ground-truth SSH container executes real commands, but the command list is
  read-only (reconnaissance only) except for `/tmp` writes that are cleaned up
  within the same session.
- The Fireworks AI API key in `.env` must never be committed to git.  Rotate it
  after any accidental exposure.
- `llm-honeypot` output contains ANSI-concealed prompt-injection text.  The harness
  records but never acts on this text.  Treat all content in `results/raw/` as
  untrusted data when processing programmatically.
- No LLM-generated output is interpreted as instructions by the harness.

---

## License and third-party notices

**This repository**: license TBD by the author.

**Third-party tools** (cloned separately; not included here):

| Tool | Upstream license |
|------|-----------------|
| DECEIVE | UNVERIFIED — check `DECEIVE/LICENSE` after cloning |
| Beelzebub | UNVERIFIED — check `beelzebub/LICENSE` after cloning |
| shelLM / AdvancedshelLM | UNVERIFIED — check `shelLM/LICENSE` after cloning |
| galah | UNVERIFIED — check `galah/LICENSE` after cloning |
| llm-honeypot | UNVERIFIED — check `llm-honeypot/LICENSE` after cloning |
| Cowrie | UNVERIFIED — check `cowrie-base/LICENSE` after cloning |

---

## See also

- [BENCHMARK.md](BENCHMARK.md) — technical report with full results
- [docs/PATCH_NOTES.md](docs/PATCH_NOTES.md) — all source edits applied to third-party repos
- [DOC_REVIEW_NOTES.md](DOC_REVIEW_NOTES.md) — data check, secret scan, UNVERIFIED items
- [Changes/](Changes/) — detailed design and change notes per task
- [harness/README.md](harness/README.md) — harness usage reference
