# ============================================================
# Starts the React dashboard (Vite dev server) on port 5173.
#
#   .\scripts\start-frontend.ps1              # foreground (Ctrl+C to stop)
#   .\scripts\start-frontend.ps1 -Background  # detached, survives the
#                                            # terminal closing; logs to
#                                            # logs\frontend.log
# ============================================================
param([switch]$Background)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot 'frontend'

$listener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port 5173 is already in use (pid $($listener.OwningProcess)) - dashboard looks running." -ForegroundColor Yellow
    exit 0
}

# npm.cmd, not npm: Windows PowerShell blocks the npm.ps1 shim under some
# execution policies, and the .cmd shim is unaffected.
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npm) { $npm = 'npm.cmd' }

if ($Background) {
    . (Join-Path $PSScriptRoot 'detached.ps1')
    $logDir = Join-Path $RepoRoot 'logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $log = Join-Path $logDir 'frontend.log'
    Start-Detached -WorkingDirectory $FrontendDir -CommandLine `
        "cmd /c cd /d `"$FrontendDir`" && `"$npm`" run dev >> `"$log`" 2>&1"
} else {
    Write-Host "==> Starting dashboard on http://localhost:5173" -ForegroundColor Cyan
    Set-Location $FrontendDir
    & $npm run dev
}
