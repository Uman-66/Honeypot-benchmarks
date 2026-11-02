# scripts/copy_logs.ps1
# Copy logs from running containers into results/honeypot_logs/<name>/.
# Usage (from repo root):
#   .\scripts\copy_logs.ps1
#
# NOTE: The pattern
#   docker cp "$(docker compose … ps -q <svc>):<path>" <dest>
# does NOT work in Windows PowerShell because PowerShell does not expand
# $(...) inside double-quoted strings passed to external commands.
# Instead we capture the container ID into a variable first, then use it.

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # warn on failures, keep going

$root    = Split-Path -Parent $PSScriptRoot
$logBase = Join-Path $root "results\honeypot_logs"

function Copy-ContainerLog {
    param(
        [string]$ComposeFile,   # relative to repo root
        [string]$ServiceName,   # docker compose service name
        [string]$ContainerPath, # path inside the container to copy
        [string]$DestName       # subdirectory name under results/honeypot_logs/
    )

    $absCompose = Join-Path $root $ComposeFile
    $dest       = Join-Path $logBase $DestName
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    Write-Host "[$DestName] Getting container ID for service '$ServiceName' ..." -NoNewline

    # Capture the container ID into a variable — avoids the subshell problem.
    $id = docker compose -f $absCompose ps -a -q $ServiceName 2>$null
    $id = ($id | Select-Object -First 1).Trim()

    if (-not $id) {
        Write-Host " NOT FOUND (container not running?)" -ForegroundColor Yellow
        return
    }
    Write-Host " $id"

    Write-Host "  Copying $ContainerPath -> $dest"
    docker cp "${id}:${ContainerPath}" $dest
    if ($?) {
        Write-Host "  OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED" -ForegroundColor Red
    }
}

# ── DECEIVE ──────────────────────────────────────────────────────────────────
# Service: deceive  (docker/deceive.compose.yaml)
# Log:     /app/SSH/ssh_log.log
Copy-ContainerLog `
    -ComposeFile  "docker/deceive.compose.yaml" `
    -ServiceName  "deceive" `
    -ContainerPath "/app/SSH/ssh_log.log" `
    -DestName     "deceive"

# ── Beelzebub ─────────────────────────────────────────────────────────────────
# Service: beelzebub-ssh  (docker/beelzebub.compose.yaml)
# Log:     /logs/beelzebub.log
Copy-ContainerLog `
    -ComposeFile  "docker/beelzebub.compose.yaml" `
    -ServiceName  "beelzebub-ssh" `
    -ContainerPath "/logs/beelzebub.log" `
    -DestName     "beelzebub"

# ── Cowrie ────────────────────────────────────────────────────────────────────
# Service: cowrie  (docker/cowrie.compose.yaml)
# Log:     /cowrie/cowrie-git/var/log/cowrie/cowrie.json
Copy-ContainerLog `
    -ComposeFile  "docker/cowrie.compose.yaml" `
    -ServiceName  "cowrie" `
    -ContainerPath "/cowrie/cowrie-git/var/log/cowrie/cowrie.json" `
    -DestName     "cowrie"

# ── AdvancedshelLM ────────────────────────────────────────────────────────────
# Service: advshellm  (docker/advshellm.compose.yaml)
# Log:     /app/codebase/logs  (directory with timestamped subdirectories)
Copy-ContainerLog `
    -ComposeFile  "docker/advshellm.compose.yaml" `
    -ServiceName  "advshellm" `
    -ContainerPath "/app/codebase/logs" `
    -DestName     "advshellm"

# ── galah ─────────────────────────────────────────────────────────────────────
# Service: galah  (docker/galah.compose.yaml)
# Log:     /galah/logs/galah.json
Copy-ContainerLog `
    -ComposeFile  "docker/galah.compose.yaml" `
    -ServiceName  "galah" `
    -ContainerPath "/galah/logs/galah.json" `
    -DestName     "galah"

# ── llm-honeypot ──────────────────────────────────────────────────────────────
# Service: llmhoneypot  (docker/llmhoneypot.compose.yaml)
# Log:     /home/cowrie/cowrie/var/log/cowrie/cowrie.json
Copy-ContainerLog `
    -ComposeFile  "docker/llmhoneypot.compose.yaml" `
    -ServiceName  "llmhoneypot" `
    -ContainerPath "/home/cowrie/cowrie/var/log/cowrie/cowrie.json" `
    -DestName     "llmhoneypot"

Write-Host ""
Write-Host "Log copy complete.  Files are in: $logBase" -ForegroundColor Cyan
