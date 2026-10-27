# ============================================================
# Local toolchain paths used by every script in this repository.
# Dot-source it:   . .\scripts\env.ps1
# ============================================================
$RepoRoot = Split-Path -Parent $PSScriptRoot
$MavenHome = Join-Path $env:LOCALAPPDATA 'Temp\opencode\tools\apache-maven-3.9.9'

if (Test-Path (Join-Path $MavenHome 'bin\mvn.cmd')) {
    $env:PATH = "$MavenHome\bin;$env:PATH"
} else {
    Write-Warning "Maven not found at $MavenHome - run scripts/bootstrap-toolchain.ps1 first."
}

# Python 3.11 is required by the AI service. Prefer the project virtual
# environment (ai-service/.venv) where all requirements are installed.
$VenvPython = Join-Path $RepoRoot 'ai-service\.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if (-not $Python) {
        Write-Warning "Python 3.11 not found. Install it with: winget install --id Python.Python.3.11"
        $Python = 'python'
    }
}
$env:PROJECT_PYTHON = $Python

$env:PROJECT_ROOT = $RepoRoot

# Shared storage directories: the Spring backend and the Python AI service MUST
# read/write the same folders. Absolute paths make both services cwd-independent.
$env:UPLOAD_DIR = Join-Path $RepoRoot 'uploads'
$env:PROCESSED_DIR = Join-Path $RepoRoot 'uploads\processed'
$env:MODEL_DIR = Join-Path $RepoRoot 'models'
