# Deploy Script Recipe (Repeatable Updates)

Purpose: define one stable PowerShell deployment flow so every code change can be deployed with the same `.ps1` command.

## Target Script

Use one script path only:

`deploy/deploy_to_debian.ps1`

Run it the same way each time:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_to_debian.ps1
```

## What The Script Must Do

1. Validate required settings (host, user, SSH key/agent, local project path, remote path, service name).
2. Build a clean deploy payload from `asset_management` (exclude `.git`, `.venv`, `__pycache__`, `bin`, `obj`, local temp files).
3. Copy changed project files to the server path (idempotent sync; safe to run repeatedly).
4. Run remote dependency update if needed (`pip install -r requirements.txt` inside venv).
5. Restart systemd service: `asset_management`.
6. Verify service status and run health checks:
   - `/healthz`
   - `/api/healthz`
7. Fail fast on any error and return non-zero exit code.

## Required Parameters/Config

Keep these configurable in one place (param block or `.env` loaded by script):

- `ServerHost` (example: `139.162.170.26`)
- `ServerUser` (example: `rune`)
- `RemoteAppDir` (example: `~/dev/asset_management`)
- `ServiceName` (default: `asset_management`)
- `LocalAppDir` (default: `.\asset_management`)
- `Port` (default: `5001`)

## Remote Commands (Expected)

The script should effectively perform this sequence on the server:

```bash
cd ~/dev/asset_management
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart asset_management
sudo systemctl is-active asset_management
curl -fsS http://127.0.0.1:5001/healthz
curl -fsS http://127.0.0.1:5001/api/healthz
```

## Acceptance Criteria

1. Same command works for every deploy.
2. Re-running without code changes is safe.
3. Deploy fails if service restart or health checks fail.
4. Output clearly shows: sync, restart, health result, final success/failure.

## Usage Contract

After any code change:

1. Save changes locally.
2. Run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\deploy_to_debian.ps1
   ```
3. Confirm script reports healthy service.

