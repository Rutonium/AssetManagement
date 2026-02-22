# Asset Management deployment checklist

Canonical operations reference: `BASICS.md`

These steps mirror the TimeApp + TED_Tender_Robot deployment pattern.

## Windows PC (Work)

Use the deploy script from repo root:

```powershell
.\deploy\deploy_to_debian.ps1 -AllowInteractiveAuth -AllowInteractiveSudo
```

What to expect:

1. Enter SSH password when prompted for `rune@139.162.170.26`.
2. Enter `sudo` password when prompted on the server.
3. Script uploads the package, deploys to `/home/rune/dev/asset_management`, installs requirements, restarts `asset_management`, and runs:
   - `http://127.0.0.1:5001/healthz`
   - `http://127.0.0.1:5001/api/healthz`

If the command completes with `Deploy complete.`, deployment succeeded.

## Linux Mint PC (Home)

## 1) Package the project locally (Windows PowerShell)

```
$src = "c:\Users\RV\OneDrive - SUBCPARTNER A S\22 - Visual Studio Repositories\AssetManagement\asset_management"
$stage = "asset_management_stage"

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
robocopy $src $stage /E /XD .git .vs __pycache__ .venv env env1 bin obj dist build

if (Test-Path "asset_management.zip") { Remove-Item "asset_management.zip" }
Compress-Archive -Path "$stage\*" -DestinationPath "asset_management.zip"
```

## 2) Upload to the server

```
scp asset_management.zip rune@139.162.170.26:~/dev/asset_management/
```

## 3) Unpack on the server

```
cd ~/dev/asset_management
unzip -o asset_management.zip
```

## 4) Install prerequisites (Debian)

```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unixodbc unixodbc-dev
```

If using SQL Server drivers:

```
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc > /dev/null
sudo curl -o /etc/apt/sources.list.d/mssql-release.list https://packages.microsoft.com/config/debian/12/prod.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18
```

## 5) Create env file for secrets

```
sudo mkdir -p /etc/asset_management
sudo nano /etc/asset_management/asset_management.env
```

Paste values from `.env.example` and set real SQL Server credentials.

## 5b) Database migration (ToolInstances)

Run the SQL script in SSMS or sqlcmd:

`SQL Queries/20260221_1400_schema_reconcile.sql`

`SQL Queries/20260221_1605_atlas_users.sql`

## 6) Install dependencies in the venv

```
cd ~/dev/asset_management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 7) Smoke test

```
ASSET_MANAGEMENT_PORT=5001 uvicorn AssetMan:app --host 0.0.0.0 --port 5001
```

## 7b) Health checks

```
curl -s http://127.0.0.1:5001/healthz
curl -s http://127.0.0.1:5001/api/healthz
```

## 8) Install the systemd service

```
sudo cp asset_management.service /etc/systemd/system/asset_management.service
sudo systemctl daemon-reload
sudo systemctl enable asset_management
sudo systemctl start asset_management
sudo systemctl status asset_management
```

## 9) Nginx (optional but recommended)

```
sudo apt install -y nginx
sudo cp nginx-asset_management.conf /etc/nginx/sites-available/asset_management
sudo ln -s /etc/nginx/sites-available/asset_management /etc/nginx/sites-enabled/asset_management
sudo nginx -t
sudo systemctl reload nginx
```

Remember to replace `server_name` in `nginx-asset_management.conf`.

If you deploy under a different base path, edit `static/app-config.js` to match:

```
window.ASSET_MANAGEMENT_BASE_PATH = '/asset_management';
```
