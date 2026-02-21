#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
REMOTE_PATH="${REMOTE_PATH:-/home/rune/dev/asset_management}"
SERVICE_NAME="${SERVICE_NAME:-asset_management}"
APP_PORT="${APP_PORT:-5001}"
SSH_PORT="${SSH_PORT:-22}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARCHIVE_PATH="${REPO_ROOT}/asset_management.tgz"
CONTROL_PATH="${TMPDIR:-/tmp}/asset_mgmt_${REMOTE_USER}_${REMOTE_HOST}_${SSH_PORT}.sock"

SSH_OPTS=(
  -p "${SSH_PORT}"
  -o StrictHostKeyChecking=accept-new
  -o ControlMaster=auto
  -o ControlPersist=10m
  -o ControlPath="${CONTROL_PATH}"
)
SCP_OPTS=(
  -P "${SSH_PORT}"
  -o StrictHostKeyChecking=accept-new
  -o ControlMaster=auto
  -o ControlPersist=10m
  -o ControlPath="${CONTROL_PATH}"
)

cleanup() {
  rm -f "${ARCHIVE_PATH}" || true
  ssh "${SSH_OPTS[@]}" -O exit "${REMOTE_USER}@${REMOTE_HOST}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "${REPO_ROOT}"

echo "Opening SSH control connection..."
ssh "${SSH_OPTS[@]}" -Nf "${REMOTE_USER}@${REMOTE_HOST}" || true

echo "Packing project..."
tar -czf "${ARCHIVE_PATH}" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='bin' \
  --exclude='obj' \
  asset_management

echo "Uploading archive..."
scp "${SCP_OPTS[@]}" "${ARCHIVE_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"

echo "Deploying on server and restarting ${SERVICE_NAME}..."
ssh "${SSH_OPTS[@]}" -t "${REMOTE_USER}@${REMOTE_HOST}" \
  "set -e
   cd '${REMOTE_PATH}'
   tar -xzf asset_management.tgz --strip-components=1
   rm -f asset_management.tgz
   '${REMOTE_PATH}/venv/bin/python' -m pip install -r requirements.txt
   sudo -v
   sudo systemctl restart '${SERVICE_NAME}'
   sudo systemctl is-active '${SERVICE_NAME}'
   curl -fsS http://127.0.0.1:${APP_PORT}/healthz
   echo
   curl -fsS http://127.0.0.1:${APP_PORT}/api/healthz
   echo"

echo "Deploy complete."
