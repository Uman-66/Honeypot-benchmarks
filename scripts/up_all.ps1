# scripts/up_all.ps1
# Bring up all honeypot containers and both ground-truth services.
# Usage (from repo root):
#   .\scripts\up_all.ps1
#
# Each compose file is started with --build so any image changes are picked up.
# Volumes are never removed by this script.
# After starting, the script waits up to 120 s per published port for a TCP
# connection, then reports which targets are ready.

param()

Set-StrictMode -Version Latest
# Use Continue so that docker compose failures are warnings, not terminating errors.
$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot

# ── Compose files and the TCP port to probe ─────────────────────────────────

$services = @(
    @{ File = "docker/deceive.compose.yaml";           Port = 8022;  Name = "deceive"        },
    @{ File = "docker/beelzebub.compose.yaml";         Port = 2222;  Name = "beelzebub"      },
    @{ File = "docker/cowrie.compose.yaml";            Port = 2223;  Name = "cowrie"         },
    @{ File = "docker/advshellm.compose.yaml";         Port = 2224;  Name = "advshellm"      },
    @{ File = "docker/llmhoneypot.compose.yaml";       Port = 2227;  Name = "llmhoneypot"    },
    @{ File = "docker/galah.compose.yaml";             Port = 8088;  Name = "galah"          },
    @{ File = "docker/groundtruth_ssh.compose.yaml";   Port = 2225;  Name = "groundtruth_ssh"  },
    @{ File = "docker/groundtruth_http.compose.yaml";  Port = 2226;  Name = "groundtruth_http" }
)

# ── Start each service ───────────────────────────────────────────────────────

foreach ($svc in $services) {
    $composeFile = Join-Path $root $svc.File
    Write-Host "Starting $($svc.Name) ..." -ForegroundColor Cyan
    docker compose -f $composeFile up -d --build
    if (-not $?) {
        Write-Warning "docker compose up failed for $($svc.Name)"
    }
}

# ── Show running containers ──────────────────────────────────────────────────

Write-Host ""
Write-Host "=== docker ps ===" -ForegroundColor Cyan
docker ps

# ── Wait for TCP ports ────────────────────────────────────────────────────────

function Wait-Port {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 120
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $tcp = [System.Net.Sockets.TcpClient]::new()
            $conn = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
            $ok   = $conn.AsyncWaitHandle.WaitOne(1000, $false)
            if ($ok -and $tcp.Connected) {
                $tcp.Close()
                return $true
            }
            $tcp.Close()
        } catch {
            # Not yet listening
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host ""
Write-Host "=== Port readiness ===" -ForegroundColor Cyan

foreach ($svc in $services) {
    Write-Host -NoNewline "  $($svc.Name) (127.0.0.1:$($svc.Port)) ... "
    $ready = Wait-Port -Name $svc.Name -Port $svc.Port -TimeoutSeconds 120
    if ($ready) {
        Write-Host "READY" -ForegroundColor Green
    } else {
        Write-Host "TIMEOUT (not responding after 120 s)" -ForegroundColor Red
    }
}
