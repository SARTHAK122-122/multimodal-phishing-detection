# ============================================================
# Brings the whole platform up in order:
#   1. PostgreSQL (checked, not started - install it as a service)
#   2. Python AI service   http://127.0.0.1:8000
#   3. Spring Boot backend http://localhost:8088
#   4. React dashboard     http://localhost:5173
#
#   .\scripts\start-all.ps1
#
# Use scripts\stop-all.ps1 to shut everything down.
# ============================================================
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Multimodal Phishing Detection Platform ===" -ForegroundColor Green

# --- 1. PostgreSQL -----------------------------------------------------
$pg = Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue
if ($pg) {
    Write-Host "[1/4] PostgreSQL is listening on 5432" -ForegroundColor Green
} else {
    Write-Host "[1/4] PostgreSQL is NOT listening on 5432." -ForegroundColor Red
    Write-Host "      Start the service (services.msc -> postgresql) and re-run,"
    Write-Host "      or run scripts\setup-database.ps1 once the service is up."
    exit 1
}

# --- 2. AI service -----------------------------------------------------
& (Join-Path $PSScriptRoot 'start-ai-service.ps1') -Background
Write-Host "[2/4] AI service starting on http://127.0.0.1:8000" -ForegroundColor Green

# --- 3. Backend --------------------------------------------------------
& (Join-Path $PSScriptRoot 'start-backend.ps1') -Background
Write-Host "[3/4] Backend starting on http://localhost:8088 (first boot runs Flyway migrations)" -ForegroundColor Green

# --- 4. Frontend -------------------------------------------------------
& (Join-Path $PSScriptRoot 'start-frontend.ps1') -Background
Write-Host "[4/4] Dashboard starting on http://localhost:5173" -ForegroundColor Green

Write-Host ""
Write-Host "Waiting for the services to accept connections..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(90)
$aiUp = $false; $beUp = $false
while ((Get-Date) -lt $deadline -and -not ($aiUp -and $beUp)) {
    if (-not $aiUp) {
        try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; $aiUp = $true } catch {}
    }
    if (-not $beUp) {
        try { Invoke-WebRequest -Uri 'http://localhost:8088/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; $beUp = $true } catch {}
    }
    if (-not ($aiUp -and $beUp)) { Start-Sleep -Seconds 3 }
}

if ($aiUp) { Write-Host "  AI service:  UP  (http://127.0.0.1:8000/docs)" -ForegroundColor Green }
else       { Write-Host "  AI service:  not up yet - check scripts\start-ai-service.ps1 output" -ForegroundColor Yellow }
if ($beUp) { Write-Host "  Backend:     UP  (http://localhost:8088/api/health)" -ForegroundColor Green }
else       { Write-Host "  Backend:     not up yet - check backend\spring-boot.log" -ForegroundColor Yellow }
Write-Host "  Dashboard:   http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Open http://localhost:5173 and use Analyze to scan a website, email, SMS or QR code." -ForegroundColor Cyan
