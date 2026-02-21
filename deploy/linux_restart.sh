#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
SERVICE_NAME="${SERVICE_NAME:-asset_management}"
APP_PORT="${APP_PORT:-5001}"
SSH_PORT="${SSH_PORT:-22}"

ssh -t -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${REMOTE_HOST}" \
  "set -e
   sudo -v
   sudo systemctl restart '${SERVICE_NAME}'
   sudo systemctl is-active '${SERVICE_NAME}'
   curl -fsS http://127.0.0.1:${APP_PORT}/healthz
   echo
   curl -fsS http://127.0.0.1:${APP_PORT}/api/healthz
   echo"
