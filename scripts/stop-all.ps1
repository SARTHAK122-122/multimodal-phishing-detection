# ============================================================
# Stops every locally started platform component:
# AI service (8000), backend (8088), dashboard (5173).
# PostgreSQL is left running - it is a system service.
#
#   .\scripts\stop-all.ps1
# ============================================================
foreach ($port in @(8000, 8088, 5173)) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Output ("stopped pid {0} on port {1}" -f $c.OwningProcess, $port)
    } else {
        Write-Output ("nothing listening on {0}" -f $port)
    }
}
Write-Output "done (PostgreSQL left running)"
