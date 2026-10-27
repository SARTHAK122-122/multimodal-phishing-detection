# ============================================================
# Shared helper: start a service process that survives console teardown.
#
# Two observed failure modes motivated this design:
#   1. Start-Process children inherit the launcher's console; when the
#      terminal (or a non-interactive shell) exits, they get a close
#      signal and die (log showed only "^C").
#   2. WMI-created cmd.exe still allocates its own console, and that
#      console proved killable when the launching shell was force-killed.
#
# This helper launches wscript.exe (a GUI-subsystem host: it has NO
# console at all) via WMI (parented to the WMI service, not the shell).
# wscript runs a small generated .vbs that spawns `cmd /c <command>`
# hidden (window style 0) and does not wait. Nothing in the caller's
# session - console, job object, or process tree - can reach the service.
#
# Callers embed their own `>> "logfile" 2>&1` redirection in $CommandLine.
# ============================================================
function Start-Detached {
    param(
        [Parameter(Mandatory)] [string]$CommandLine,
        [string]$WorkingDirectory = (Get-Location).Path
    )

    $vbsDir = Join-Path $env:TEMP 'phishguard-detach'
    if (-not (Test-Path $vbsDir)) { New-Item -ItemType Directory -Path $vbsDir | Out-Null }

    # Timestamped per-launch file: no races between the three start scripts.
    # Stale copies (if a delete ever hits a still-open file) are cleaned up
    # on the next start.
    Get-ChildItem $vbsDir -Filter 'launch-*.vbs' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-1) } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $stamp = Get-Date -Format 'yyyyMMddHHmmssfff'
    $vbs = Join-Path $vbsDir "launch-$PID-$stamp.vbs"

    # VBS string literals escape a double quote by doubling it.
    $wdEsc  = $WorkingDirectory.Replace('"', '""')
    $cmdEsc = $CommandLine.Replace('"', '""')
    @"
Option Explicit
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "$wdEsc"
sh.Run "cmd /c $cmdEsc", 0, False
"@ | Set-Content -Path $vbs -Encoding ASCII

    $wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
    $args = "`"$vbs`""

    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine      = "`"$wscript`" $args"
        CurrentDirectory = $WorkingDirectory
    }
    if ($r.ReturnValue -ne 0) {
        # Fallback: wscript is GUI-subsystem, so even a plain Start-Process
        # launch is not attached to any console.
        $p = Start-Process -FilePath $wscript -ArgumentList $args `
            -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru
        $pid_ = $p.Id
    } else {
        $pid_ = $r.ProcessId
    }

    # wscript has read the script by now; if the file is still locked, the
    # hourly stale sweep above removes it later.
    Start-Sleep -Milliseconds 300
    Remove-Item $vbs -Force -ErrorAction SilentlyContinue

    $shown = if ($CommandLine.Length -gt 100) { $CommandLine.Substring(0, 100) + '...' } else { $CommandLine }
    Write-Host "    detached pid $pid_ (wscript launcher): $shown"
    return $pid_
}

# Builds a `set "K=V" && ...` prefix so environment variables reach a
# WMI-spawned process (which does not inherit this shell's environment).
function ConvertTo-CmdEnvPrefix {
    param([hashtable]$Variables)
    $prefix = ''
    foreach ($k in $Variables.Keys) {
        if ($Variables[$k]) { $prefix += "set `"$k=$($Variables[$k])`" && " }
    }
    return $prefix
}
