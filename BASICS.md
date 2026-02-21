# AssetManagement Basics

This is the single source of truth for day-to-day project operations.

## 1) Repo Structure

- App code: `asset_management/`
- Deployment script: `deploy/deploy_to_debian.ps1`
- Canonical SQL migration scripts:
  - `asset_management_stage/20260221_1400_schema_reconcile.sql`
  - `asset_management_stage/20260221_1605_atlas_users.sql`
- Shared login design spec: `ATLAS_LOGIN_SPEC.md`

## 2) Local Environment

Create local runtime env files from templates:

```bash
cp asset_management/.env.example asset_management/.env
cp asset_management_stage/.env.example asset_management_stage/.env
```

Set real secrets in local `.env` files only. Do not commit secrets.

## 3) Deploy (Windows PowerShell)

Primary deploy command:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_to_debian.ps1 -AllowInteractiveAuth -AllowInteractiveSudo
```

## 3b) Deploy (Linux Mint)

Use this as the standard Linux deploy flow (short version):

```bash
cd "/home/rune/Documents/VS Code repos/AssetManagement"
./deploy/linux_deploy.sh
```

Restart + health check only:

```bash
./deploy/linux_restart.sh
```

Optional: override defaults without editing scripts:

```bash
REMOTE_HOST=139.162.170.26 REMOTE_USER=rune ./deploy/linux_deploy.sh
```

## 4) DB Migrations (SSMS or sqlcmd)

Run:

1. `asset_management_stage/20260221_1400_schema_reconcile.sql`
2. `asset_management_stage/20260221_1605_atlas_users.sql`

## 5) DB Overview / Health Validation

Preferred from SSMS: run the structural overview query and save results as txt.

From CLI (Linux):

```bash
read -r -s -p "SQL password: " DB_PASS; echo
DB_URL="mssql+pyodbc://remoteconnection:${DB_PASS}@SUBC-BROKER01/AssetManagement?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
python3 asset_management/scripts/db_overview.py --db-url "$DB_URL" --samples 10 | tee db_overview.txt
```

If ODBC driver is missing:

```bash
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc unixodbc-dev
```

## 6) Local Run / Smoke Test

```bash
cd asset_management
ASSET_MANAGEMENT_PORT=5001 uvicorn AssetMan:app --host 0.0.0.0 --port 5001
```

Health endpoints:

- `http://127.0.0.1:5001/healthz`
- `http://127.0.0.1:5001/api/healthz`

## 7) Rules To Avoid Drift

- Use only one migration set (no alternate copies).
- Keep docs pointing to full relative paths.
- Keep `asset_management/.env.example` and `asset_management_stage/.env.example` aligned.
- Never store production tokens/passwords in tracked files.
