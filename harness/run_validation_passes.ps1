#!/usr/bin/env pwsh
# harness/run_validation_passes.ps1
# Runs A/B/C passes for all four LLM targets with fresh containers per pass.
# Saves results under results/exp/validation/
#
# Prerequisites:
#   - api_proxy.py must be running on 0.0.0.0:11435
#   - Docker Desktop running
#   - .env present with OPENAI_API_KEY and OPENAI_BASE_URL
#
# Usage:
#   cd e:\Test\honeypot-benchmark
#   .\.venv-harness\Scripts\Activate.ps1
#   .\harness\run_validation_passes.ps1

$ErrorActionPreference = "Stop"
$REPO = "e:\Test\honeypot-benchmark"
$PYTHON = "$REPO\.venv-harness\Scripts\python"
$HARNESS = "$REPO\harness\validate_prompt_timing.py"

function Start-Target {
    param([string]$ComposeFile, [string]$OverlayFile, [string]$Name)
    Write-Host "`n[setup] Starting $Name with proxy overlay ..."
    docker compose -f $ComposeFile -f $OverlayFile up -d --force-recreate 2>&1 | Out-Null
    # Wait for the container to be ready (SSH port open)
    $port = switch ($Name) {
        "deceive"   { 8022 }
        "beelzebub" { 2222 }
        "vellmes"   { 2228 }
        "advshellm" { 2224 }
    }
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try {
            $c = New-Object System.Net.Sockets.TcpClient
            $c.Connect("127.0.0.1", $port)
            $c.Close()
            Write-Host "[setup] $Name SSH port $port open"
            Start-Sleep 2  # extra settle time
            return $true
        } catch {
            Start-Sleep 1
        }
    }
    Write-Host "WARNING: $Name SSH port $port not open after 30s"
    return $false
}

function Stop-Target {
    param([string]$ComposeFile, [string]$OverlayFile, [string]$Name)
    Write-Host "[teardown] Stopping $Name ..."
    docker compose -f $ComposeFile -f $OverlayFile down 2>&1 | Out-Null
}

# Target definitions: name, compose file, overlay file
$TARGETS = @(
    @{Name="deceive";   Compose="$REPO\docker\deceive.compose.yaml";   Overlay="$REPO\docker\deceive.proxy.yaml"}
    @{Name="beelzebub"; Compose="$REPO\docker\beelzebub.compose.yaml"; Overlay="$REPO\docker\beelzebub.proxy.yaml"}
    @{Name="vellmes";   Compose="$REPO\docker\vellmes.compose.yaml";   Overlay="$REPO\docker\vellmes.proxy.yaml"}
    @{Name="advshellm"; Compose="$REPO\docker\advshellm.compose.yaml"; Overlay="$REPO\docker\advshellm.proxy.yaml"}
)

# Check API budget before starting
$BUDGET = 500

foreach ($t in $TARGETS) {
    $name = $t.Name
    Write-Host "`n==== $name ===="

    # Check budget
    $proxy_log = "$REPO\results\exp\validation\api_proxy_log.jsonl"
    $current_calls = 0
    if (Test-Path $proxy_log) {
        $current_calls = (Get-Content $proxy_log | Where-Object { $_.Trim() -ne "" }).Count
    }
    if ($current_calls -ge $BUDGET) {
        Write-Host "BUDGET STOP: $current_calls API calls logged (budget $BUDGET)"
        break
    }
    Write-Host "[budget] $current_calls/$BUDGET API calls so far"

    # Pass A: quiet
    Write-Host "`n--- Pass A (quiet) ---"
    $ok = Start-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
    if (-not $ok) {
        Write-Host "SKIP: $name failed to start for pass A"
        Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
        continue
    }
    & $PYTHON $HARNESS --target $name --pass-label passA --timing quiet
    Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name

    # Pass B: prompt
    Write-Host "`n--- Pass B (prompt) ---"
    $ok = Start-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
    if (-not $ok) {
        Write-Host "SKIP: $name failed to start for pass B"
        Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
        continue
    }
    & $PYTHON $HARNESS --target $name --pass-label passB --timing prompt
    Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name

    # Pass C: quiet (noise baseline)
    Write-Host "`n--- Pass C (quiet) ---"
    $ok = Start-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
    if (-not $ok) {
        Write-Host "SKIP: $name failed to start for pass C"
        Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
        continue
    }
    & $PYTHON $HARNESS --target $name --pass-label passC --timing quiet
    Stop-Target -ComposeFile $t.Compose -OverlayFile $t.Overlay -Name $name
}

Write-Host "`n==== All passes complete ===="
Write-Host "Running comparison analysis..."
& $PYTHON "$REPO\harness\validate_prompt_timing.py" --compare-only
Write-Host "Done. Results in results/exp/validation/"
