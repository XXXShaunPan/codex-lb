[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$RepoDir = (Split-Path -Parent $PSScriptRoot),
    [string]$ServiceName = 'codex-lb'
)
$ErrorActionPreference = 'Stop'
$RepoDir = (Resolve-Path -LiteralPath $RepoDir).Path
$DataDir = (Resolve-Path -LiteralPath $DataDir).Path
$python = Join-Path $RepoDir '.venv\Scripts\python.exe'
$serviceDir = Join-Path $DataDir 'service'
$serviceXml = Join-Path $serviceDir 'codex-lb-service.xml'
$wrapper = Join-Path $serviceDir 'codex-lb-service.exe'
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$backup = Join-Path $DataDir "backups\pre-native-relay-$stamp"
if (-not (Test-Path -LiteralPath (Join-Path $RepoDir 'app\static\index.html'))) {
    throw 'Build the production frontend before deployment.'
}
Push-Location $RepoDir
try {
    if (git status --porcelain) { throw 'Deploy only a committed, clean custom checkout.' }
    $tag = git describe --tags --exact-match HEAD
    if ($LASTEXITCODE -ne 0 -or $tag -notlike 'custom-*') { throw 'Deploy only a custom release tag.' }
    $env:PYTHONPATH = ''
    $env:CODEX_LB_DATA_DIR = $DataDir
    & $python -m scripts.check_relay_source
    if ($LASTEXITCODE -ne 0) { throw 'Native source policy failed.' }
    New-Item -ItemType Directory -Path $backup | Out-Null
    Copy-Item -LiteralPath $serviceXml -Destination (Join-Path $backup 'codex-lb-service.xml')
    Copy-Item -LiteralPath (Join-Path $DataDir 'encryption.key') -Destination (Join-Path $backup 'encryption.key')
    $injection = Join-Path $DataDir 'injections\model-source-account-pricing'
    if (Test-Path -LiteralPath $injection) {
        Copy-Item -LiteralPath $injection -Destination (Join-Path $backup 'legacy-injection') -Recurse
    }
    & $wrapper stop
    if ($LASTEXITCODE -ne 0) { throw 'Failed to stop the service.' }
    $deadline = [DateTime]::UtcNow.AddSeconds(40)
    while ((Get-Service -Name $ServiceName).Status -ne 'Stopped') {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Service did not stop; no database changes applied.' }
        Start-Sleep -Milliseconds 300
    }
    # A stopped writer plus SQLite backup gives a consistent database even if
    # there is a surviving WAL from a prior incomplete shutdown.
    $backupCode = 'import sqlite3,sys; source=sqlite3.connect(sys.argv[1]); target=sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()'
    & $python -c $backupCode (Join-Path $DataDir 'store.db') (Join-Path $backup 'store.db')
    if ($LASTEXITCODE -ne 0) { throw "Database backup failed. Service is stopped; backup directory: $backup" }
    $legacyVisitors = Join-Path $DataDir 'visitor-portal.db'
    if (Test-Path -LiteralPath $legacyVisitors) {
        & $python -c $backupCode $legacyVisitors (Join-Path $backup 'visitor-portal.db')
        if ($LASTEXITCODE -ne 0) { throw 'Visitor backup failed.' }
    }
    & $python -m app.db.migrate upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migration failed. Service is stopped; restore from $backup" }
    & $python -m app.db.migrate check
    if ($LASTEXITCODE -ne 0) { throw "Schema check failed. Service is stopped; backup: $backup" }
    $visitorCount = & $python -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT COUNT(*) FROM visitor_accounts").fetchone()[0]); c.close()' (Join-Path $DataDir 'store.db')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect visitor migration state.' }
    if ([int]$visitorCount -eq 0 -and (Test-Path -LiteralPath $legacyVisitors)) {
        & $python -m scripts.import_relay_visitors $legacyVisitors --apply
        if ($LASTEXITCODE -ne 0) { throw 'Visitor import failed.' }
    }
    [xml]$xml = Get-Content -LiteralPath $serviceXml -Raw
    $xml.service.workingdirectory = $RepoDir
    $legacyNames = @(
        'PYTHONPATH','CODEX_LB_MODEL_SOURCE_ACCOUNT_PRICING','CODEX_LB_MODEL_SOURCE_ACCOUNT_UI',
        'CODEX_LB_MODEL_SOURCE_VIRTUAL_ACCOUNTS','CODEX_LB_VISITOR_PORTAL',
        'CODEX_LB_SOURCE_STREAM_RELIABILITY','CODEX_LB_ENHANCED_PROFILE'
    )
    foreach ($name in $legacyNames) {
        $node = $xml.SelectSingleNode("/service/env[@name='$name']")
        if ($null -ne $node) { [void]$node.ParentNode.RemoveChild($node) }
    }
    $xml.Save($serviceXml)
    & $wrapper start
    if ($LASTEXITCODE -ne 0) { throw "Service start failed. Backup: $backup" }
    Write-Host "Native relay started: $tag"
    Write-Host "Backup: $backup"
    Write-Host 'Verify /health X-Relay-Version and run python -m scripts.smoke_relay_http.'
}
finally { Pop-Location }
