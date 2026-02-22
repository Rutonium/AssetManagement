#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy/recover_runtime.sh
#   REMOTE_HOST=1.2.3.4 REMOTE_USER=rune ./deploy/recover_runtime.sh

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
SSH_PORT="${SSH_PORT:-22}"
SERVICE_NAME="${SERVICE_NAME:-asset_management}"
APP_PORT="${APP_PORT:-5001}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/etc/asset_management/asset_management.env}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> [1/3] Ensuring local .venv exists and has activate script"
cd "${REPO_ROOT}"
if [[ ! -f ".venv/bin/activate" ]]; then
  echo "Local .venv is missing or broken. Recreating..."
  rm -rf .venv
  if python3 -m venv .venv 2>/dev/null; then
    echo "Created .venv via python3 -m venv."
  else
    echo "python3 -m venv failed, trying virtualenv fallback..."
    if [[ ! -x "${HOME}/.local/bin/virtualenv" ]]; then
      python3 -m pip install --user --break-system-packages virtualenv
    fi
    "${HOME}/.local/bin/virtualenv" .venv
    echo "Created .venv via virtualenv."
  fi
else
  echo "Local .venv looks OK."
fi

echo "==> [2/3] Fixing remote runtime env + restarting ${SERVICE_NAME}"
echo "==> [2/3a] Validating remote sudo credentials + [2/3b] applying fixes in same session"
ssh -tt -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${REMOTE_HOST}" \
  "SERVICE_NAME='${SERVICE_NAME}' APP_PORT='${APP_PORT}' REMOTE_ENV_FILE='${REMOTE_ENV_FILE}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-asset_management}"
APP_PORT="${APP_PORT:-5001}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/etc/asset_management/asset_management.env}"

# Validate sudo in this same TTY session.
sudo -v

sudo -n mkdir -p "$(dirname "${REMOTE_ENV_FILE}")"
sudo -n touch "${REMOTE_ENV_FILE}"
sudo -n chmod 640 "${REMOTE_ENV_FILE}"

current_secret="$(sudo -n awk -F= '/^SESSION_SIGNING_SECRET=/{print substr($0, index($0,$2)); exit}' "${REMOTE_ENV_FILE}" || true)"
if [[ -z "${current_secret}" || ${#current_secret} -lt 32 ]]; then
  if command -v openssl >/dev/null 2>&1; then
    new_secret="$(openssl rand -hex 32)"
  else
    new_secret="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  fi
  if sudo -n grep -q '^SESSION_SIGNING_SECRET=' "${REMOTE_ENV_FILE}"; then
    sudo -n sed -i "s|^SESSION_SIGNING_SECRET=.*|SESSION_SIGNING_SECRET=${new_secret}|" "${REMOTE_ENV_FILE}"
  else
    echo "SESSION_SIGNING_SECRET=${new_secret}" | sudo -n tee -a "${REMOTE_ENV_FILE}" >/dev/null
  fi
  echo "Updated SESSION_SIGNING_SECRET in ${REMOTE_ENV_FILE}."
else
  echo "SESSION_SIGNING_SECRET already valid."
fi

if ! sudo -n grep -q '^CORS_ALLOW_ORIGINS=' "${REMOTE_ENV_FILE}"; then
  echo "CORS_ALLOW_ORIGINS=http://139.162.170.26,http://localhost,http://127.0.0.1" | sudo -n tee -a "${REMOTE_ENV_FILE}" >/dev/null
fi
if ! sudo -n grep -q '^CORS_ALLOW_CREDENTIALS=' "${REMOTE_ENV_FILE}"; then
  echo "CORS_ALLOW_CREDENTIALS=true" | sudo -n tee -a "${REMOTE_ENV_FILE}" >/dev/null
fi

sudo -n systemctl daemon-reload
sudo -n systemctl restart "${SERVICE_NAME}"
sudo -n systemctl is-active "${SERVICE_NAME}"

echo "Health checks:"
curl -fsS "http://127.0.0.1:${APP_PORT}/healthz" && echo
curl -fsS "http://127.0.0.1:${APP_PORT}/api/healthz" && echo
REMOTE_SCRIPT

echo "==> [3/3] Done"
echo "Open: http://${REMOTE_HOST}/asset_management/"
