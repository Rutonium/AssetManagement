#!/usr/bin/env pwsh

param(
    [string]$RemoteHost = "139.162.170.26",
    [string]$RemoteUser = "rune",
    [string]$RemotePath = "/home/rune/dev/asset_management",
    [string]$ServiceName = "asset_management",
    [string]$AppPort = "5001",
    [string]$SshPort = "22",
    [string]$SshKeyPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step
    )
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$scriptRoot = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$archiveName = "asset-management-$timestamp.tgz"
$tempDir = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
$localArchive = Join-Path $tempDir $archiveName
$remoteArchive = "/tmp/$archiveName"
$remote = "$RemoteUser@$RemoteHost"

$sshKeyArgs = @()
if ($SshKeyPath) {
    $resolvedKey = (Resolve-Path $SshKeyPath).Path
    $sshKeyArgs = @("-i", $resolvedKey)
}

Write-Host "Creating archive: $localArchive"
tar -czf $localArchive `
    --exclude=".git" `
    --exclude=".venv" `
    --exclude="venv" `
    --exclude="env" `
    --exclude="env1" `
    --exclude="__pycache__" `
    --exclude=".pytest_cache" `
    --exclude=".mypy_cache" `
    --exclude="bin" `
    --exclude="obj" `
    --exclude="dist" `
    --exclude="build" `
    --exclude="*.pyc" `
    --exclude="*.pyo" `
    -C $repoRoot `
    asset_management
Assert-LastExitCode -Step "Archive creation"

Write-Host "Deploy mode: full snapshot of local asset_management folder."

Write-Host "Copying archive to ${remote}:${remoteArchive}"
scp -P $SshPort @sshKeyArgs $localArchive "${remote}:${remoteArchive}"
Assert-LastExitCode -Step "SCP upload"

Write-Host "Deploying to $RemotePath and restarting $ServiceName"
ssh -tt -p $SshPort @sshKeyArgs $remote @"
set -e
sudo mkdir -p '$RemotePath'
sudo tar -xzf '$remoteArchive' -C '$RemotePath' --strip-components=1
rm -f '$remoteArchive'
cd '$RemotePath'

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart '$ServiceName'
sudo systemctl is-active --quiet '$ServiceName'
sudo systemctl --no-pager --full status '$ServiceName' | head -n 25

ok=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -fsS 'http://127.0.0.1:$AppPort/healthz' >/dev/null && curl -fsS 'http://127.0.0.1:$AppPort/api/healthz' >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done

if [ "`$ok" -ne 1 ]; then
  echo 'Health checks failed after waiting for startup. Showing recent journal logs:'
  sudo journalctl -u '$ServiceName' -n 80 --no-pager || true
  exit 7
fi

curl -fsS 'http://127.0.0.1:$AppPort/healthz'
curl -fsS 'http://127.0.0.1:$AppPort/api/healthz'
"@
Assert-LastExitCode -Step "Remote deploy/restart/health checks"

Write-Host "Cleaning up local archive"
Remove-Item -Force $localArchive

Write-Host "Deploy complete."
