param(
    [string]$RemoteHost = "139.162.170.26",
    [string]$RemoteUser = "rune",
    [string]$RemotePath = "/dev/peopleplanner",
    [string]$ServiceName = "crew-rotation-planner",
    [string]$SshPort = "22"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Workflow note: keep this script updated at the end of each delivered change set.
# Last touched to accompany project modal calculation fix (person-days converted to 12h workday hours).
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
$archiveName = "peopleplanner-$timestamp.tgz"
$localArchive = Join-Path $env:TEMP $archiveName
$remoteArchive = "/tmp/$archiveName"
$remote = "$RemoteUser@$RemoteHost"

Write-Host "Creating archive: $localArchive"
tar -czf $localArchive `
    --exclude=".git" `
    --exclude=".venv" `
    --exclude="venv" `
    --exclude="__pycache__" `
    --exclude=".pytest_cache" `
    --exclude="pytest-cache-files-*" `
    --exclude=".mypy_cache" `
    -C $repoRoot .
Assert-LastExitCode -Step "Archive creation"

Write-Host "Deploy mode: full snapshot of current local repo (includes any previous undeployed changes)."

Write-Host "Copying archive to ${remote}:${remoteArchive}"
scp -P $SshPort $localArchive "${remote}:${remoteArchive}"
Assert-LastExitCode -Step "SCP upload"

Write-Host "Deploying to $remotePath and restarting $ServiceName"
ssh -tt -p $SshPort $remote @"
set -e
sudo mkdir -p '$RemotePath'
sudo tar -xzf '$remoteArchive' -C '$RemotePath'
rm -f '$remoteArchive'
sudo systemctl restart '$ServiceName'
sudo systemctl --no-pager --full status '$ServiceName' | head -n 25
"@
Assert-LastExitCode -Step "Remote deploy/restart"

Write-Host "Cleaning up local archive"
Remove-Item -Force $localArchive

Write-Host "Deploy complete."
