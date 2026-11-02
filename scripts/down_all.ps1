# scripts/down_all.ps1
# Bring down all honeypot containers and ground-truth services.
# Usage (from repo root):
#   .\scripts\down_all.ps1
#
# Volumes are NOT removed (no --volumes flag) so that named-volume data
# (logs, SSH host keys) is preserved between sessions.

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

$composeFiles = @(
    "docker/deceive.compose.yaml",
    "docker/beelzebub.compose.yaml",
    "docker/cowrie.compose.yaml",
    "docker/advshellm.compose.yaml",
    "docker/llmhoneypot.compose.yaml",
    "docker/galah.compose.yaml",
    "docker/groundtruth_ssh.compose.yaml",
    "docker/groundtruth_http.compose.yaml"
)

foreach ($file in $composeFiles) {
    $composeFile = Join-Path $root $file
    Write-Host "Stopping $file ..." -ForegroundColor Cyan
    docker compose -f $composeFile down
    if (-not $?) {
        Write-Warning "docker compose down failed for $file"
    }
}

Write-Host ""
Write-Host "All services stopped." -ForegroundColor Green
Write-Host "Named volumes are preserved.  To remove them, run:"
Write-Host "  docker volume prune"
