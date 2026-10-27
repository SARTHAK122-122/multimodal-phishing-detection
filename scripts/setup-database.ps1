# ============================================================
# Creates the application database, the least-privilege role and
# applies schema + seed. Run once (safe to re-run).
#
#   .\scripts\setup-database.ps1
#
# Reads credentials from .env if present, otherwise uses the
# development defaults from .env.example.
# ============================================================
param(
    [string]$EnvFile = (Join-Path (Split-Path -Parent $PSScriptRoot) '.env')
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

$superUser = 'postgres'
$superPass = 'postgres'
$dbName    = 'phishing_detection'
$dbUser    = 'phish_app'
$dbPass    = 'change_this_password'

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $key = $parts[0].Trim(); $val = $parts[1].Trim()
            switch ($key) {
                'POSTGRES_SUPERUSER'          { $superUser = $val }
                'POSTGRES_SUPERUSER_PASSWORD' { $superPass = $val }
                'POSTGRES_DB'                 { $dbName = $val }
                'POSTGRES_USER'               { $dbUser = $val }
                'POSTGRES_PASSWORD'           { $dbPass = $val }
            }
        }
    }
}

function Invoke-Psql {
    param([string]$Sql, [string]$User, [string]$Password, [string]$Database)
    $env:PGPASSWORD = $Password
    # Run through cmd.exe so psql NOTICE/WARNING output on stderr is not
    # treated as a PowerShell terminating error.
    $out = $Sql | cmd /c "psql -U $User -h localhost -d $Database -v ON_ERROR_STOP=1 -q 2>&1"
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed (exit $LASTEXITCODE):`n$($out -join "`n")"
    }
    return $out
}

Write-Host "==> Creating role $dbUser (if missing)" -ForegroundColor Cyan
Invoke-Psql -User $superUser -Password $superPass -Database 'postgres' -Sql @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$dbUser') THEN
        CREATE ROLE $dbUser LOGIN PASSWORD '$dbPass';
    END IF;
END
`$`$;
"@ | Out-Null

Write-Host "==> Creating database $dbName (if missing)" -ForegroundColor Cyan
$env:PGPASSWORD = $superPass
$exists = cmd /c "psql -U $superUser -h localhost -d postgres -tAc `"SELECT 1 FROM pg_database WHERE datname = '$dbName'`" 2>&1"
if ($LASTEXITCODE -ne 0) { throw "could not list databases: $exists" }
if ($exists.Trim() -ne '1') {
    Invoke-Psql -User $superUser -Password $superPass -Database 'postgres' -Sql "CREATE DATABASE $dbName OWNER $dbUser;" | Out-Null
} else {
    Write-Host "    database already exists"
}

Write-Host "==> Applying schema (database/schema/001_initial_schema.sql)" -ForegroundColor Cyan
$schema = Get-Content (Join-Path $RepoRoot 'database\schema\001_initial_schema.sql') -Raw
# Applied as the superuser so it works whether or not the app role already
# owns pre-existing tables; the app role receives full grants right after.
Invoke-Psql -User $superUser -Password $superPass -Database $dbName -Sql $schema | Out-Null

Write-Host "==> Transferring table/sequence ownership to $dbUser" -ForegroundColor Cyan
# Flyway runs as the application role, and PostgreSQL only lets an object
# owner ALTER it - so every object in public must belong to $dbUser.
$ownership = @"
DO `$`$
DECLARE obj RECORD;
BEGIN
    FOR obj IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO %I', obj.tablename, '$dbUser');
    END LOOP;
    FOR obj IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER SEQUENCE public.%I OWNER TO %I', obj.sequencename, '$dbUser');
    END LOOP;
END
`$`$;
"@
Invoke-Psql -User $superUser -Password $superPass -Database $dbName -Sql $ownership | Out-Null

Write-Host "==> Applying incremental migrations (database/migrations/*.sql)" -ForegroundColor Cyan
Get-ChildItem (Join-Path $RepoRoot 'database\migrations') -Filter '*.sql' | Sort-Object Name | ForEach-Object {
    Write-Host "    - $($_.Name)"
    Invoke-Psql -User $superUser -Password $superPass -Database $dbName -Sql (Get-Content $_.FullName -Raw) | Out-Null
}

Write-Host "==> Granting privileges to $dbUser" -ForegroundColor Cyan
Invoke-Psql -User $superUser -Password $superPass -Database $dbName -Sql @"
GRANT ALL ON SCHEMA public TO $dbUser;
GRANT CREATE ON SCHEMA public TO $dbUser;
GRANT ALL ON ALL TABLES IN SCHEMA public TO $dbUser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $dbUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $dbUser;
"@ | Out-Null
# The database itself must be owned by (or owned by a role that can be) the app role.
$owner = cmd /c "psql -U $superUser -h localhost -d postgres -tAc `"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '$dbName'`" 2>&1"
Write-Host "    database owner: $($owner.Trim())"

Write-Host "==> Applying seed (labelled synthetic / demo rows)" -ForegroundColor Cyan
$seed = Get-Content (Join-Path $RepoRoot 'database\seed\seed_demo_data.sql') -Raw
Invoke-Psql -User $dbUser -Password $dbPass -Database $dbName -Sql $seed | Out-Null

Write-Host "==> Copying the synthetic sample CSV into the upload directory" -ForegroundColor Cyan
$uploadDir = Join-Path $RepoRoot 'uploads'
New-Item -ItemType Directory -Force -Path $uploadDir | Out-Null
$sampleSrc = Join-Path $RepoRoot 'datasets\sample_urls_demo.csv'
Copy-Item $sampleSrc (Join-Path $uploadDir 'sample_urls_demo.csv') -Force

$csv = Import-Csv $sampleSrc
$total = $csv.Count
$phish = @($csv | Where-Object { $_.label -eq 'phishing' }).Count
$legit = @($csv | Where-Object { $_.label -eq 'legitimate' }).Count
$size = (Get-Item $sampleSrc).Length
$update = @"
UPDATE datasets
SET total_rows = $total,
    phishing_rows = $phish,
    legitimate_rows = $legit,
    file_size_bytes = $size,
    status = 'UPLOADED'
WHERE id = 1 AND is_synthetic;
"@
Invoke-Psql -User $dbUser -Password $dbPass -Database $dbName -Sql $update | Out-Null
Write-Host "    sample rows=$total phishing=$phish legitimate=$legit (other labels are reported as warnings)" -ForegroundColor Green

Write-Host "==> Tables now in $dbName" -ForegroundColor Cyan
$env:PGPASSWORD = $dbPass
cmd /c "psql -U $dbUser -h localhost -d $dbName -c `"\dt`" 2>&1"
Write-Host "==> Row counts" -ForegroundColor Cyan
$counts = "SELECT 'users' t, count(*) FROM users UNION ALL SELECT 'datasets', count(*) FROM datasets UNION ALL SELECT 'preprocessing_runs', count(*) FROM preprocessing_runs UNION ALL SELECT 'scans', count(*) FROM scans UNION ALL SELECT 'modality_results', count(*) FROM modality_results UNION ALL SELECT 'evidence', count(*) FROM evidence UNION ALL SELECT 'model_versions', count(*) FROM model_versions UNION ALL SELECT 'evaluation_runs', count(*) FROM evaluation_runs;"
cmd /c "psql -U $dbUser -h localhost -d $dbName -c `"$counts`" 2>&1"
Write-Host "Done. jdbc:postgresql://localhost:5432/$dbName  user=$dbUser" -ForegroundColor Green
