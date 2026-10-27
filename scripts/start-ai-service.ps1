# ============================================================
# Starts the Python AI service (FastAPI + Uvicorn) on 127.0.0.1:8000.
#
#   .\scripts\start-ai-service.ps1              # foreground (Ctrl+C to stop)
#   .\scripts\start-ai-service.ps1 -Background  # detached, survives the
#                                               # terminal closing; logs to
#                                               # logs\ai-service.log
#
# Binds to loopback only - the AI service is an internal component
# behind Spring Boot, never exposed directly to the network.
# ============================================================
param([switch]$Background)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$AiDir = Join-Path $RepoRoot 'ai-service'
$Python = Join-Path $AiDir '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    Write-Error "Virtual environment missing at $AiDir\.venv - run scripts\bootstrap-toolchain.ps1 first."
}

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port 8000 is already in use (pid $($listener.OwningProcess)) - AI service looks running." -ForegroundColor Yellow
    exit 0
}

$uvicorn = Join-Path $AiDir '.venv\Scripts\uvicorn.exe'
$envVars = @{
    # PROJECT_ROOT anchors every storage path (uploads, screenshots, artifacts)
    # regardless of the working directory uvicorn starts from.
    PROJECT_ROOT = $RepoRoot
    PYTHONPATH   = $AiDir
}

if ($Background) {
    . (Join-Path $PSScriptRoot 'detached.ps1')
    $logDir = Join-Path $RepoRoot 'logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $log = Join-Path $logDir 'ai-service.log'
    $envPrefix = ConvertTo-CmdEnvPrefix -Variables $envVars
    Start-Detached -WorkingDirectory $AiDir -CommandLine `
        "cmd /c $envPrefix cd /d `"$AiDir`" && `"$uvicorn`" app.main:app --host 127.0.0.1 --port 8000 >> `"$log`" 2>&1"
} else {
    foreach ($k in $envVars.Keys) { Set-Item -Path "env:$k" -Value $envVars[$k] }
    Write-Host "==> Starting AI service on http://127.0.0.1:8000" -ForegroundColor Cyan
    Set-Location $AiDir
    & $uvicorn app.main:app --host 127.0.0.1 --port 8000
}
