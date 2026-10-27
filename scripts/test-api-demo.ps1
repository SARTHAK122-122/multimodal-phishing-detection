# End-to-end API demonstration of the manual preprocessing workflow.
# Prereqs: PostgreSQL running, AI service on :8000, backend on :8088.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$api = 'http://localhost:8088/api'
$csv = Join-Path $PSScriptRoot '..\datasets\sample_urls_demo.csv'
$script:failed = $false

# Local-dev default from .env.example; override by exporting PGPASSWORD first.
if (-not $env:PGPASSWORD) { $env:PGPASSWORD = 'postgres' }

function Check($name, $cond, $detail = '') {
    if ($cond) { Write-Host "[PASS] $name $detail" -ForegroundColor Green }
    else { Write-Host "[FAIL] $name $detail" -ForegroundColor Red; $script:failed = $true }
}

# 1. Health (includes database status)
$health = Invoke-RestMethod "$api/health" -TimeoutSec 30
Check 'health endpoint' ($health.status -in @('OK', 'UP', 'ok')) "status=$($health.status)"
Check 'database reachable' ($health.database.status -in @('OK', 'UP', 'ok')) "db=$($health.database.status)"

# 2. List datasets
$datasets = Invoke-RestMethod "$api/datasets" -TimeoutSec 20
Check 'list datasets' ($datasets.Count -ge 1) "count=$($datasets.Count)"

# 3. Upload the sample CSV (STEP 1)
$boundary = [Guid]::NewGuid().ToString()
$enc = [System.Text.Encoding]::GetEncoding('iso-8859-1')
$name = Split-Path $csv -Leaf
$sb = New-Object System.Text.StringBuilder
[void]$sb.Append("--$boundary`r`n")
[void]$sb.Append("Content-Disposition: form-data; name=`"file`"; filename=`"$name`"`r`n")
[void]$sb.Append("Content-Type: text/csv`r`n`r`n")
$head = $enc.GetBytes($sb.ToString())
$mid = [System.IO.File]::ReadAllBytes($csv)
# The sample file is generated demo data - flag it as synthetic so the
# datasets.is_synthetic column tells the truth.
$field = "`r`n--$boundary`r`nContent-Disposition: form-data; name=`"synthetic`"`r`n`r`ntrue"
$sb2 = New-Object System.Text.StringBuilder
[void]$sb2.Append("`r`n--$boundary--`r`n")
$tail = $enc.GetBytes($sb2.ToString())
$midField = $enc.GetBytes($field)
$ms = New-Object System.IO.MemoryStream
$ms.Write($head, 0, $head.Length)
$ms.Write($mid, 0, $mid.Length)
$ms.Write($midField, 0, $midField.Length)
$ms.Write($tail, 0, $tail.Length)
$bytes = $ms.ToArray(); $ms.Close()
$resp = Invoke-RestMethod -Method Post -Uri "$api/datasets/upload" `
    -ContentType "multipart/form-data; boundary=$boundary" -Body $bytes -TimeoutSec 60
$ds = $resp.dataset
Check 'upload dataset' ($null -ne $ds.id) "id=$($ds.id) rows=$($ds.totalRows) status=$($ds.status)"
Check 'upload flagged as synthetic' ($ds.synthetic -eq $true) "is_synthetic=$($ds.synthetic)"
$dsId = $ds.id

# 4. Preview (STEP 2)
$preview = Invoke-RestMethod "$api/datasets/$dsId/preview?targetColumn=label" -TimeoutSec 60
$labels = ($preview.target.distribution.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ','
Check 'preview dataset' ($preview.columnNames.Count -gt 0 -and $preview.head.Count -gt 0) `
    "rows=$($preview.rows) columns=$($preview.columnNames.Count) headRows=$($preview.head.Count) labels: $labels"
Check 'duplicate rows detected' ($preview.duplicateRows -ge 1) "duplicateRows=$($preview.duplicateRows)"

# 5. Execute preprocessing (STEP 3 + 4)
$runReq = [ordered]@{
    targetColumn = 'label'
    options      = [ordered]@{
        normalizeLabels          = $true
        dropInvalidRows          = $true
        detectConflictingDuplicates = $true
        removeDuplicates         = $true
        handleMissing            = $true
        missingStrategy          = 'drop_rows'
        dedupeOnColumn           = 'url'
        validateFeatures         = $true
        labelMapping             = @{ suspicious = 'phishing' }
    }
}
$run = Invoke-RestMethod -Method Post -Uri "$api/datasets/$dsId/preprocessing-runs" `
    -ContentType 'application/json' -Body ($runReq | ConvertTo-Json -Depth 6) -TimeoutSec 120
Check 'preprocessing run created' ($null -ne $run.id) "id=$($run.id) status=$($run.status)"

# 6. Poll until finished (STEP 5)
$status = ''
for ($i = 0; $i -lt 60; $i++) {
    $run = Invoke-RestMethod "$api/preprocessing-runs/$($run.id)" -TimeoutSec 30
    $status = $run.status
    if ($status -in @('COMPLETED', 'FAILED')) { break }
    Start-Sleep -Seconds 1
}
Check 'run completed' ($status -eq 'COMPLETED') "status=$status in=$($run.inputRows) out=$($run.outputRows) dupes=$($run.duplicatesRemoved) invalid=$($run.invalidRowsRemoved) missing=$($run.missingValuesHandled) elapsed=$($run.elapsedMs)ms"
$before = ($run.classDistributionBefore.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ','
$after = ($run.classDistributionAfter.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ','
Write-Host "       class balance before: $before"
Write-Host "       class balance after:  $after"
Write-Host "       transformations: $($run.transformations.Count), warnings: $($run.warnings.Count)"

# 7. Download processed dataset (STEP 6)
$dl = "$api/preprocessing-runs/$($run.id)/download"
$tmp = Join-Path $env:TEMP 'processed_demo.csv'
Invoke-WebRequest -Uri $dl -OutFile $tmp -TimeoutSec 60
$lines = (Get-Content $tmp | Measure-Object -Line).Lines
Check 'download processed CSV' ($lines -ge 2) "lines=$lines file=$tmp"

# 8. Verify PostgreSQL row (read-only)
$sql = "SELECT id, dataset_id, status, input_rows, output_rows, duplicates_removed FROM preprocessing_runs ORDER BY id DESC LIMIT 1;"
$psqlOut = & psql -U postgres -d phishing_detection -c $sql 2>&1 | Out-String
Check 'preprocessing_runs row in PostgreSQL' ($psqlOut -match 'COMPLETED') ''
Write-Host $psqlOut

# 9. Audit: the upload must have received id > 1 (sequence past the seeded row)
$sql2 = "SELECT max(id) FROM datasets;"
$maxId = (& psql -U postgres -d phishing_detection -w -t -c $sql2 2>&1 | Out-String).Trim()
Check 'datasets sequence advanced' ([int]$maxId -ge 2) "max(dataset id)=$maxId"

# 10. Phase 4: trained URL models must be registered as EVALUATED with measured metrics
$models = Invoke-RestMethod "$api/models" -TimeoutSec 15
$evaluated = @($models | Where-Object { $_.evaluationStatus -eq 'EVALUATED' -and $_.modelName -like 'url_*' })
Check 'URL models EVALUATED in registry' ($evaluated.Count -ge 2) "evaluated=$($evaluated.Count)/$($models.Count) total"

# 11. Phase 4: evaluation_runs rows must carry real hold-out metrics + the seed
$evals = Invoke-RestMethod "$api/evaluations" -TimeoutSec 15
$measured = @($evals | Where-Object { $null -ne $_.accuracy -and $_.randomSeed -eq 42 -and $_.splitStrategy -match '80/20' })
Check 'evaluation_runs hold measured metrics' ($measured.Count -ge 2) "runs=$($measured.Count) acc=$([math]::Round($measured[0].accuracy, 4))"

Write-Host ''
if ($script:failed) { Write-Host 'API DEMO: FAILED' -ForegroundColor Red; exit 1 }
Write-Host 'API DEMO: ALL CHECKS PASSED' -ForegroundColor Green
