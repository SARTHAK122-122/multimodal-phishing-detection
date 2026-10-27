$c = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
if ($c) { Stop-Process -Id $c.OwningProcess -Force; Write-Output ("killed pid " + $c.OwningProcess) }
else { Write-Output 'no listener on 8088' }
