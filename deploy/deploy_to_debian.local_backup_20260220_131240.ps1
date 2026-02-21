param(
    [string]$ServerHost = "139.162.170.26",
    [string]$ServerUser = "rune",
    [string]$RemoteAppDir = "~/dev/asset_management",
    [string]$ServiceName = "asset_management",
    [string]$LocalAppDir = ".\asset_management",
    [int]$Port = 5001,
    [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

function Escape-BashSingleQuote {
    param([string]$Value)
    return $Value -replace "'", "'""'""'"
}

Write-Host "==> Validating prerequisites..."
Require-Command "ssh"
Require-Command "scp"
Require-Command "robocopy"
Require-Command "Compress-Archive"

if (-not (Test-Path -Path $LocalAppDir)) {
    throw "Local app directory not found: $LocalAppDir"
}

$repoRoot = (Resolve-Path ".").Path
$localAppPath = (Resolve-Path $LocalAppDir).Path
$stageDir = Join-Path $env:TEMP "asset_management_stage"
$zipPath = Join-Path $env:TEMP "asset_management_deploy.zip"
$remoteZip = "/tmp/asset_management_deploy.zip"
$remoteScript = "/tmp/asset_management_deploy.sh"

if (Test-Path $stageDir) { Remove-Item -Recurse -Force $stageDir }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Write-Host "==> Building deploy payload from $localAppPath..."
$null = robocopy $localAppPath $stageDir /E /XD .git .vs __pycache__ .venv venv env env1 bin obj dist build .pytest_cache .mypy_cache .ruff_cache /XF *.pyc *.pyo *.pyd *.log
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    throw "robocopy failed with exit code $robocopyExit"
}

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

Write-Host "==> Uploading payload to $ServerUser@$ServerHost..."
scp $zipPath "$ServerUser@$ServerHost`:$remoteZip"

$remoteAppDirEsc = Escape-BashSingleQuote $RemoteAppDir
$serviceEsc = Escape-BashSingleQuote $ServiceName
$portText = $Port.ToString()
$skipPip = if ($SkipPipInstall) { "1" } else { "0" }

$remoteBodyTemplate = @'
#!/usr/bin/env bash
set -euo pipefail

REMOTE_APP_DIR='__REMOTE_APP_DIR__'
SERVICE_NAME='__SERVICE_NAME__'
PORT='__PORT__'
REMOTE_ZIP='__REMOTE_ZIP__'
SKIP_PIP='__SKIP_PIP__'

mkdir -p "$REMOTE_APP_DIR"
unzip -oq "$REMOTE_ZIP" -d "$REMOTE_APP_DIR"
rm -f "$REMOTE_ZIP"

cd "$REMOTE_APP_DIR"
if [ ! -d venv ]; then
  python3 -m venv venv
fi

if [ "$SKIP_PIP" != "1" ]; then
  source venv/bin/activate
  pip install -r requirements.txt
fi

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"
curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null
curl -fsS "http://127.0.0.1:$PORT/api/healthz" >/dev/null
echo "Deploy OK: service restarted and health checks passed."
'@

$remoteBody = $remoteBodyTemplate.
    Replace('__REMOTE_APP_DIR__', $remoteAppDirEsc).
    Replace('__SERVICE_NAME__', $serviceEsc).
    Replace('__PORT__', $portText).
    Replace('__REMOTE_ZIP__', $remoteZip).
    Replace('__SKIP_PIP__', $skipPip)

$localRemoteScript = Join-Path $env:TEMP "asset_management_deploy.sh"
Set-Content -Path $localRemoteScript -Value $remoteBody -Encoding ascii

Write-Host "==> Uploading remote deploy script..."
scp $localRemoteScript "$ServerUser@$ServerHost`:$remoteScript"

Write-Host "==> Running remote deploy steps..."
ssh "$ServerUser@$ServerHost" "bash $remoteScript && rm -f $remoteScript"

Write-Host "==> Cleaning local temp files..."
Remove-Item -Force $localRemoteScript
Remove-Item -Force $zipPath
if (Test-Path $stageDir) { Remove-Item -Recurse -Force $stageDir }

Write-Host "Deploy completed successfully."
