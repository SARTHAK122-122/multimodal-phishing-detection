# ============================================================
# Starts the Spring Boot backend on port 8088.
#
#   .\scripts\start-backend.ps1              # foreground (Ctrl+C to stop)
#   .\scripts\start-backend.ps1 -Background  # detached, survives the terminal
#                                            # closing; logs to backend\
#                                            # spring-boot.log
#
# Reads .env (if present) for SPRING_DATASOURCE_* / AI_SERVICE_URL values.
# Default port 8088 (was 8080: another Java process occupied it locally).
# ============================================================
param([switch]$Background)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'env.ps1')

$BackendDir = Join-Path $RepoRoot 'backend'

$listener = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port 8088 is already in use (pid $($listener.OwningProcess)) - backend looks running." -ForegroundColor Yellow
    exit 0
}

$envOverrides = @{}
$envPath = Join-Path $RepoRoot '.env'
if (Test-Path $envPath) {
    foreach ($line in Get-Content $envPath) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $name = $Matches[1]; $val = $Matches[2].Trim().Trim('"')
            Set-Item -Path "env:$name" -Value $val
            $envOverrides[$name] = $val
        }
    }
    Write-Host "Loaded $envPath into environment."
}

if ($Background) {
    . (Join-Path $PSScriptRoot 'detached.ps1')

    # Resolve Maven deterministically: env.ps1 puts the local copy on PATH.
    $mvn = (Get-Command mvn.cmd -ErrorAction SilentlyContinue).Source
    if (-not $mvn) {
        $mvn = Join-Path $env:LOCALAPPDATA 'Temp\opencode\tools\apache-maven-3.9.9\bin\mvn.cmd'
    }
    if (-not (Test-Path $mvn)) {
        Write-Error "mvn.cmd not found - run scripts\\bootstrap-toolchain.ps1 (or install Maven on PATH)."
    }
    $log = Join-Path $BackendDir 'spring-boot.log'
    $envPrefix = ConvertTo-CmdEnvPrefix -Variables $envOverrides
    Start-Detached -WorkingDirectory $BackendDir -CommandLine `
        "cmd /c $envPrefix cd /d `"$BackendDir`" && `"$mvn`" -q spring-boot:run >> `"$log`" 2>&1"
} else {
    Write-Host "==> Starting backend on http://localhost:8088" -ForegroundColor Cyan
    Set-Location $BackendDir
    mvn.cmd -q spring-boot:run
}
