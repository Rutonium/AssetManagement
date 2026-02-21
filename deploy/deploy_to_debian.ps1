#!/usr/bin/env pwsh

param(
    [string]$RemoteHost = "139.162.170.26",
    [string]$RemoteUser = "rune",
    [string]$RemotePath = "/home/rune/dev/asset_management",
    [string]$ServiceName = "asset_management",
    [string]$AppPort = "5001",
    [string]$SshPort = "22",
    [string]$SshKeyPath = "",
    [switch]$AllowInteractiveAuth,
    [switch]$AllowInteractiveSudo
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
$remoteScriptName = "asset-management-deploy-$timestamp.sh"
$tempDir = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
$localArchive = Join-Path $tempDir $archiveName
$localRemoteScript = Join-Path $tempDir $remoteScriptName
$remoteArchive = "/tmp/$archiveName"
$remoteScriptPath = "/tmp/$remoteScriptName"
$remote = "$RemoteUser@$RemoteHost"
$batchModeValue = if ($AllowInteractiveAuth) { "no" } else { "yes" }
$sshCommonArgs = @(
    "-p", $SshPort,
    "-o", "BatchMode=$batchModeValue",
    "-o", "ConnectTimeout=20",
    "-o", "StrictHostKeyChecking=accept-new"
)
$scpCommonArgs = @(
    "-P", $SshPort,
    "-o", "BatchMode=$batchModeValue",
    "-o", "ConnectTimeout=20",
    "-o", "StrictHostKeyChecking=accept-new"
)

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
scp @scpCommonArgs @sshKeyArgs $localArchive "${remote}:${remoteArchive}"
Assert-LastExitCode -Step "SCP upload"

Write-Host "Deploying to $RemotePath and restarting $ServiceName"
$sudoCmd = if ($AllowInteractiveSudo) { "sudo" } else { "sudo -n" }
$sshArgs = @()
if ($AllowInteractiveSudo) {
    $sshArgs += "-tt"
}

$remoteScript = @"
set -e
$sudoCmd -v
$sudoCmd mkdir -p '$RemotePath'
$sudoCmd tar -xzf '$remoteArchive' -C '$RemotePath' --strip-components=1
rm -f '$remoteArchive'
cd '$RemotePath'

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

$sudoCmd systemctl restart '$ServiceName'
$sudoCmd systemctl is-active --quiet '$ServiceName'
$sudoCmd systemctl --no-pager --full status '$ServiceName' | head -n 25

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
  $sudoCmd journalctl -u '$ServiceName' -n 80 --no-pager || true
  exit 7
fi

curl -fsS 'http://127.0.0.1:$AppPort/healthz'
curl -fsS 'http://127.0.0.1:$AppPort/api/healthz'
"@
$remoteScript = $remoteScript -replace "`r", ""
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($localRemoteScript, $remoteScript, $utf8NoBom)
scp @scpCommonArgs @sshKeyArgs $localRemoteScript "${remote}:${remoteScriptPath}"
Assert-LastExitCode -Step "SCP remote script upload"

ssh @sshArgs @sshCommonArgs @sshKeyArgs $remote "bash '$remoteScriptPath'; rc=`$?; rm -f '$remoteScriptPath'; exit `$rc"
Assert-LastExitCode -Step "Remote deploy/restart/health checks"

Write-Host "Cleaning up local archive"
Remove-Item -Force $localArchive
if (Test-Path $localRemoteScript) {
    Remove-Item -Force $localRemoteScript
}

Write-Host "Deploy complete."
