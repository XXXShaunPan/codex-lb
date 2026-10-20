[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$PreparedRepoDir = (Split-Path -Parent $PSScriptRoot),
    [ValidateRange(30,1800)][int]$HealthTimeoutSeconds = 300,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$PreparedRepoDir = (Resolve-Path -LiteralPath $PreparedRepoDir).Path
$DataDir = (Resolve-Path -LiteralPath $DataDir).Path
$serviceDir = Join-Path $DataDir 'service'
$serviceXml = Join-Path $serviceDir 'codex-lb-service.xml'
$wrapper = Join-Path $serviceDir 'codex-lb-service.exe'
[xml]$xml = Get-Content -LiteralPath $serviceXml -Raw
$activeRepo = (Resolve-Path -LiteralPath ([string]$xml.service.workingdirectory)).Path
$serviceName = [string]$xml.service.id
if (git -C $PreparedRepoDir status --porcelain) { throw 'Prepared checkout has uncommitted changes.' }
if (git -C $activeRepo status --porcelain) { throw 'Active checkout has uncommitted changes.' }
$sha = git -C $PreparedRepoDir rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the prepared revision.' }
$tag = git -C $PreparedRepoDir describe --tags --exact-match HEAD
if ($LASTEXITCODE -ne 0 -or $tag -notlike 'custom-*') { throw 'Prepared checkout must be a tagged custom release.' }
git -C $activeRepo merge-base --is-ancestor HEAD $sha
if ($LASTEXITCODE -ne 0) { throw 'Prepared release is not a fast-forward of the active checkout.' }
$static = Join-Path $PreparedRepoDir 'app\static'
$manifest = Get-Content -LiteralPath (Join-Path $static 'relay-build.json') -Raw | ConvertFrom-Json
$tree = git -C $PreparedRepoDir rev-parse HEAD:frontend
if ($LASTEXITCODE -ne 0 -or $manifest.frontendTree -ne $tree) { throw 'Frontend source does not match the prepared build.' }
if (-not ($manifest.files | Where-Object { $_.path -eq 'index.html' })) { throw 'Frontend index is missing from the manifest.' }
foreach ($file in $manifest.files) {
    $path = [IO.Path]::GetFullPath((Join-Path $static $file.path))
    if (-not $path.StartsWith($static + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Invalid build manifest path.'
    }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256) { throw "Build checksum mismatch: $($file.path)" }
}
$python = Join-Path $activeRepo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Active runtime is missing.' }
git -C $activeRepo diff --quiet HEAD $sha -- uv.lock pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'Runtime dependencies changed; prepare a matching runtime before using this fast activation script.' }
Write-Host "Prepared release: $tag ($sha)"
Write-Host "Active checkout: $activeRepo"
Write-Host "Verified frontend files: $($manifest.files.Count)"
if ($CheckOnly) {
    Write-Host 'Read-only checks passed. Service, deployment and database were not changed.'
    return
}
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run activation in an Administrator PowerShell window.'
}
$backup = Join-Path $DataDir ("backups\pre-prepared-release-" + (Get-Date -Format 'yyyyMMddTHHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $serviceXml -Destination (Join-Path $backup 'codex-lb-service.xml')
Copy-Item -LiteralPath (Join-Path $DataDir 'encryption.key') -Destination (Join-Path $backup 'encryption.key')
Copy-Item -LiteralPath (Join-Path $activeRepo 'app\static') -Destination (Join-Path $backup 'static') -Recurse
$oldSha = git -C $activeRepo rev-parse HEAD
$oldSha | Out-File -LiteralPath (Join-Path $backup 'previous-commit.txt') -Encoding ascii
Write-Host "Backup directory: $backup"
& $wrapper stop
if ($LASTEXITCODE -ne 0) { throw 'Failed to stop service.' }
$deadline = [DateTime]::UtcNow.AddSeconds(40)
while ((Get-Service -Name $serviceName).Status -ne 'Stopped') {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Service did not stop; activation aborted.' }
    Start-Sleep -Milliseconds 250
}
$savedPythonPath = $env:PYTHONPATH
$savedDataDir = $env:CODEX_LB_DATA_DIR
try {
    $env:PYTHONPATH = ''
    $env:CODEX_LB_DATA_DIR = $DataDir
    $backupCode = 'import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()'
    & $python -c $backupCode (Join-Path $DataDir 'store.db') (Join-Path $backup 'store.db')
    if ($LASTEXITCODE -ne 0) { throw 'Database backup failed.' }
    git -C $activeRepo merge --ff-only $sha
    if ($LASTEXITCODE -ne 0) { throw 'Fast-forward failed.' }
    $destination = Join-Path $activeRepo 'app\static'
    foreach ($file in $manifest.files) {
        $target = [IO.Path]::GetFullPath((Join-Path $destination $file.path))
        if (-not $target.StartsWith($destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Invalid target path.'
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $static $file.path) -Destination $target -Force
    }
    Push-Location $activeRepo
    try {
        & $python -m app.db.migrate upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
        & $python -m app.db.migrate check
        if ($LASTEXITCODE -ne 0) { throw 'Schema validation failed.' }
    } finally { Pop-Location }
    & $wrapper start
    if ($LASTEXITCODE -ne 0) { throw 'Service failed to start.' }
    $deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
    $healthy = $false
    do {
        try {
            $health = Invoke-WebRequest 'http://127.0.0.1:8080/health' -UseBasicParsing -TimeoutSec 3
            $healthy = $health.StatusCode -eq 200 -and [string]$health.Headers['x-relay-version'] -eq $tag
        } catch { $healthy = $false }
        if (-not $healthy) { Start-Sleep -Milliseconds 500 }
    } while (-not $healthy -and [DateTime]::UtcNow -lt $deadline)
    if (-not $healthy) { throw "Expected release did not become healthy within $HealthTimeoutSeconds seconds." }
    Write-Host "Release activated and healthy: $tag. Refresh the dashboard."
} catch {
    Write-Host "Activation failed. Backup: $backup. Previous commit: $oldSha. Inspect service state before recovery." -ForegroundColor Red
    throw
} finally {
    $env:PYTHONPATH = $savedPythonPath
    $env:CODEX_LB_DATA_DIR = $savedDataDir
}
