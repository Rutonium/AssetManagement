#!/usr/bin/env bash
set -euo pipefail

# Run remote update_server.sh from local machine (no sudo).

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_PATH="${REMOTE_PATH:-/home/rune/dev/asset_management}"
ARCHIVE_NAME="${ARCHIVE_NAME:-asset_management.tgz}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ssh -t -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${REMOTE_HOST}" \
  "REMOTE_PATH='${REMOTE_PATH}' ARCHIVE_NAME='${ARCHIVE_NAME}' PYTHON_BIN='${PYTHON_BIN}' bash -s" < "${SCRIPT_DIR}/update_server.sh"
