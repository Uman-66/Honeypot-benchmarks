# honeypot-benchmark

A reproducible scripted benchmark of LLM-based SSH/HTTP honeypots, a Cowrie
baseline, ground-truth services, and the HoneyBee environment generator.
See [BENCHMARK.md](BENCHMARK.md) for the final results and methodology.

## What this is

The harness sends 37 scripted SSH commands (36 scored plus `exit`) and 20 HTTP
requests over five runs. Targets run locally on loopback ports. HoneyBee is
evaluated separately as a generator, not as a honeypot; its one-click deploy
path is disabled and generated artifacts must never be executed.

## Results at a glance

See [BENCHMARK.md](BENCHMARK.md) and [results/summary.md](results/summary.md).

- Cowrie's determinism was 0.9874; LLM SSH targets ranged from 0.4664 to
  0.8364.
- Galah returned 11 HTTP 5xx responses out of 100, six `Server` header values,
  and 25/94 status agreements with nginx.
- Beelzebub had 16 scored timeouts, 14/180 transcript-leakage outputs, and nine
  outputs over 20,000 characters; the largest was 239,959 characters.
- The final batch contains five runs per target; latency medians and p95 values
  use completed commands only, so they understate latency for targets with
  timeouts. No ranking or causal explanation is inferred from these data.

## Tool inventory

| Tool | Status | Protocol | LLM-based | Host port | Notes |
|---|---|---:|:---:|---:|---|
| [DECEIVE](https://github.com/coverflex-tech/DECEIVE) | Done | SSH | Yes | 8022 | LangChain-based |
| [Beelzebub](https://github.com/mariocandela/beelzebub) | Done | SSH | Yes | 2222 | Go-based |
| [shelLM / AdvancedshelLM](https://github.com/stratosphereips/AdvancedShelLM) | Done | SSH | Yes | 2224 | Subprocess wrapper |
| [VelLMes](https://github.com/stratosphereips/VelLMes-AI-Deception-Framework) | Done | SSH | Yes | 2228 | Commit `192fa5084df84b38a16f6581939fd3143c350181` |
| [galah](https://github.com/0x4D31/galah) | Done | HTTP | Yes | 8088 | LLM-generated HTTP responses |
| [llm-honeypot](https://github.com/PalisadeResearch/llm-honeypot) | Detector only | SSH | No | 2227 | ANSI-hidden marker detector |
| [Cowrie](https://github.com/cowrie/cowrie) | Baseline | SSH | No | 2223 | Static emulation |
| [honeybee](https://github.com/yaaras/honeybee) | Evaluated | N/A | Yes | 2229 | Not a honeypot: LLM generator of misconfigured environments; evaluated on output quality only; one-click deploy disabled |
| Ground truth SSH | Added | SSH | No | 2225 | Ubuntu 20.04/OpenSSH |
| Ground truth HTTP | Added | HTTP | No | 2226 | Ubuntu 20.04/nginx |

## Repository layout

```text
docker/       Dockerfiles and compose files
harness/      SSH/HTTP runners, analyzer, API probe, generator evaluator
scripts/      Container lifecycle and log-copy scripts
patches/      Reproducible third-party patches
tests/        Pytest coverage
docs/         Patch notes
results/      Final summaries and local benchmark data
BENCHMARK.md  Technical report
HONEYBEE_CHANGES.md / VELLMES_CHANGES.md  Integration notes
```

`results/honeybee/UI_TESTS.md` is not present. UI observations are documented
in the benchmark report and HoneyBee notes. `results/honeybee_max16384/` is
also absent; the 16,384-token comparison is TODO.

## Prerequisites

- Windows 10/11, Python 3.10+ (tested with Python 3.12), Git, and Docker
  Desktop with WSL 2.
- A Fireworks-compatible API key for reproducing LLM targets. Never commit
  `.env`; generated artifacts must not be executed.

## Reproduction

### 1. Rotate the API key and create `.env`

Revoke any previously exposed key before use. Create a UTF-8 `.env` in the
repository root:

```ini
OPENAI_API_KEY=<FIREWORKS_API_KEY>
OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1
```

### 2. Clone dependencies

```powershell
git clone https://github.com/coverflex-tech/DECEIVE DECEIVE
git clone https://github.com/mariocandela/beelzebub beelzebub
git clone https://github.com/stratosphereips/AdvancedShelLM shelLM
git clone https://github.com/0x4D31/galah galah
git clone https://github.com/PalisadeResearch/llm-honeypot llm-honeypot
git clone --branch v2.6.1 https://github.com/cowrie/cowrie cowrie-base
git clone https://github.com/stratosphereips/VelLMes-AI-Deception-Framework VelLMes-AI-Deception-Framework
git clone https://github.com/yaaras/honeybee honeybee
```

### 3. Apply patches

```powershell
git -C honeybee apply ..\patches\honeybee.patch
git -C VelLMes-AI-Deception-Framework apply ..\patches\vellmes.patch
```

Apply the remaining edits listed in [docs/PATCH_NOTES.md](docs/PATCH_NOTES.md).

### 4. Set up and test the harness

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r harness\requirements.txt
python -m pytest -q tests
```

### 5. Start benchmark containers

The core script starts these existing compose files:

```text
docker/deceive.compose.yaml
docker/beelzebub.compose.yaml
docker/cowrie.compose.yaml
docker/advshellm.compose.yaml
docker/llmhoneypot.compose.yaml
docker/galah.compose.yaml
docker/groundtruth_ssh.compose.yaml
docker/groundtruth_http.compose.yaml
```

```powershell
.\scripts\up_all.ps1
docker compose -f docker\vellmes.compose.yaml up -d --build
docker compose -f docker\honeybee.compose.yaml up -d --build
```

HoneyBee deployment is disabled for this benchmark; do not execute generated
HoneyBee artifacts.

### 6. Preflight checks

```powershell
8022,2222,2223,2224,2225,2227,2228 | % {
  $c = New-Object Net.Sockets.TcpClient
  try { $c.Connect("127.0.0.1", $_); $r = New-Object IO.StreamReader($c.GetStream()); Write-Host "$_: $($r.ReadLine())" }
  finally { $c.Close() }
}
2226,8088 | % {
  $c = New-Object Net.Sockets.TcpClient
  try { $c.Connect("127.0.0.1", $_); Write-Host "$_: TCP OK" }
  finally { $c.Close() }
}
```

### 7. Run the final batches

The recorded batch was collected in two SSH passes per run, with HTTP collected
after the first SSH pass. The duplicate guard skips complete `(target, run)`
pairs. Stop immediately on any non-zero exit code:

```powershell
$ssh = "advshellm","beelzebub","cowrie","deceive","groundtruth_ssh","llmhoneypot","vellmes"
for ($r=1; $r -le 5; $r++) {
  foreach ($t in $ssh) {
    python harness\run_ssh.py --target $t --runs $r --timeout 120
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
}
$http = "galah","groundtruth_http"
for ($r=1; $r -le 5; $r++) {
  foreach ($t in $http) {
    python harness\run_http.py --target $t --runs $r --timeout 120
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
}
```

Copy logs and analyze after the run:

```powershell
.\scripts\copy_logs.ps1
python harness\analyze.py
```

For a clean-slate rerun only, remove the generated raw files and summaries
after preserving any evidence:

```powershell
Remove-Item results\raw\*.jsonl,results\raw_http\*.jsonl -ErrorAction SilentlyContinue
Remove-Item results\summary.md,results\summary.csv,results\summary_by_run.csv -ErrorAction SilentlyContinue
```

The duplicate guard is preferred for normal reruns; `--force` intentionally
backs up and reruns an existing pair. Do not run `down -v` before copying logs.

## Known issues and handling constraints

- Use UTF-8 explicitly on Windows; the default code page can cause decoding
  errors.
- The CSV field-size limit is raised because LLM outputs can exceed 131,072
  characters.
- Similarity compares ANSI-stripped prefixes capped at 4,000 characters.
- All LLM targets share one model/API key, so timeout patterns can reflect API
  load; containers were freshly started before the batch.
- Latencies at the timeout are censored observations, not measured completion
  times; reported latency medians and p95 values use completed commands only.
- HoneyBee one-click deployment is disabled. Never execute generated files.
- License: TBD.
