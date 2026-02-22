#!/usr/bin/env bash
set -euo pipefail

# Single-command SQL deploy for AtlasUsers admin bootstrap/update.
# Defaults are set for this environment.

SQL_SERVER="${SQL_SERVER:-subc-broker01}"
SQL_DB="${SQL_DB:-AssetManagement}"
SQL_USER="${SQL_USER:-Remoteconnection}"
SQL_ENCRYPT="${SQL_ENCRYPT:-yes}"
SQL_TRUST_CERT="${SQL_TRUST_CERT:-yes}"

EMPLOYEE_ID="${EMPLOYEE_ID:-999999}"
ROLE="${ROLE:-Admin}"
MODE="${MODE:-reset}"   # reset | set
PIN_CODE="${PIN_CODE:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  echo "Missing local venv python at ${REPO_ROOT}/.venv/bin/python" >&2
  echo "Create it first (example): python3 -m venv .venv && source .venv/bin/activate && pip install -r asset_management/requirements.txt" >&2
  exit 1
fi

if ! "${REPO_ROOT}/.venv/bin/python" -c "import sqlalchemy" >/dev/null 2>&1; then
  echo "Installing missing Python dependencies into ${REPO_ROOT}/.venv ..."
  "${REPO_ROOT}/.venv/bin/python" -m pip install --upgrade pip >/dev/null
  "${REPO_ROOT}/.venv/bin/pip" install -r "${REPO_ROOT}/asset_management/requirements.txt"
fi

detect_odbc_driver() {
  local detected
  detected="$("${REPO_ROOT}/.venv/bin/python" - <<'PY'
import pyodbc
drivers = set(pyodbc.drivers())
preferred = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "FreeTDS",
]
for name in preferred:
    if name in drivers:
        print(name)
        break
PY
)"
  echo "${detected}"
}

SQL_DRIVER_RAW="${SQL_DRIVER_RAW:-}"
if [[ -z "${SQL_DRIVER_RAW}" ]]; then
  SQL_DRIVER_RAW="$(detect_odbc_driver)"
fi

if [[ -z "${SQL_DRIVER_RAW}" ]]; then
  echo "No SQL Server ODBC driver found on this machine." >&2
  echo "Install one, then retry." >&2
  echo "Debian/Ubuntu example (Driver 18):" >&2
  echo "  sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev" >&2
  exit 1
fi

SQL_DRIVER="${SQL_DRIVER_RAW// /+}"
echo "Using ODBC driver: ${SQL_DRIVER_RAW}"

if [[ "${MODE}" != "reset" && "${MODE}" != "set" ]]; then
  echo "MODE must be 'reset' or 'set'. Current: ${MODE}" >&2
  exit 1
fi

if [[ "${MODE}" == "set" && -z "${PIN_CODE}" ]]; then
  read -r -s -p "Enter PIN/code to set for employee ${EMPLOYEE_ID}: " PIN_CODE
  echo
fi

read -r -s -p "SQL password for ${SQL_USER}@${SQL_SERVER}: " SQL_PASSWORD
echo

export ASSET_MANAGEMENT_DB_URL="mssql+pyodbc://${SQL_USER}:${SQL_PASSWORD}@${SQL_SERVER}/${SQL_DB}?driver=${SQL_DRIVER}&Encrypt=${SQL_ENCRYPT}&TrustServerCertificate=${SQL_TRUST_CERT}"

cd "${REPO_ROOT}/asset_management"

if [[ "${MODE}" == "reset" ]]; then
  "${REPO_ROOT}/.venv/bin/python" scripts/upsert_atlas_user.py \
    --employee-id "${EMPLOYEE_ID}" \
    --role "${ROLE}" \
    --reset-password
else
  "${REPO_ROOT}/.venv/bin/python" scripts/upsert_atlas_user.py \
    --employee-id "${EMPLOYEE_ID}" \
    --role "${ROLE}" \
    --password "${PIN_CODE}"
fi

echo "Done. employee_id=${EMPLOYEE_ID} role=${ROLE} mode=${MODE}"
