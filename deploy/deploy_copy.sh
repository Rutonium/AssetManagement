#!/usr/bin/env bash
set -euo pipefail

# Copy-only deploy: package local app and upload to server.
# No sudo calls are performed.

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
REMOTE_PATH="${REMOTE_PATH:-/home/rune/dev/asset_management}"
SSH_PORT="${SSH_PORT:-22}"
ARCHIVE_NAME="${ARCHIVE_NAME:-asset_management.tgz}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARCHIVE_PATH="${REPO_ROOT}/${ARCHIVE_NAME}"

SSH_OPTS=(
  -p "${SSH_PORT}"
  -o StrictHostKeyChecking=accept-new
)
SCP_OPTS=(
  -P "${SSH_PORT}"
  -o StrictHostKeyChecking=accept-new
)

cleanup() {
  rm -f "${ARCHIVE_PATH}" || true
}
trap cleanup EXIT

cd "${REPO_ROOT}"

echo "Packing local asset_management into ${ARCHIVE_NAME} ..."
tar -czf "${ARCHIVE_PATH}" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.venv_test' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='bin' \
  --exclude='obj' \
  asset_management

echo "Ensuring remote path exists: ${REMOTE_PATH}"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_PATH}'"

echo "Uploading archive to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/${ARCHIVE_NAME}"
scp "${SCP_OPTS[@]}" "${ARCHIVE_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/${ARCHIVE_NAME}"

echo "Copy complete. Next: SSH to server and run update_server.sh (no sudo) or manual update commands."
