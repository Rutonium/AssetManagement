#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-rune}"
REMOTE_HOST="${REMOTE_HOST:-139.162.170.26}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_PATH="${REMOTE_PATH:-/home/rune/dev/asset_management}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FILES=(
  "AssetMan.py"
  "static/main.js"
  "static/api-simulation.js"
  "static/admin.html"
)

echo "== Local hashes =="
for f in "${FILES[@]}"; do
  sha256sum "${REPO_ROOT}/asset_management/${f}"
done

echo
echo "== Remote hashes =="
ssh -t -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${REMOTE_HOST}" \
  "cd '${REMOTE_PATH}' && sha256sum ${FILES[*]}"

echo
echo "== Remote markers (new auth + atlas-only login) =="
ssh -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${REMOTE_HOST}" \
  "REMOTE_PATH='${REMOTE_PATH}' bash -s" <<'REMOTE_EOF'
set -euo pipefail
cd "${REMOTE_PATH}"

find_text() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -n "${pattern}" "${file}" || true
  else
    grep -nE "${pattern}" "${file}" || true
  fi
}

echo "-- AssetMan.py markers --"
find_text "SessionMiddleware|/api/auth/users|request\.session\[\"user\"\]" AssetMan.py

echo "-- static/main.js markers --"
find_text "getLoginUsers|Type at least 2 letters|loginEmployee\(" static/main.js

echo "-- static/api-simulation.js markers --"
find_text "getLoginUsers|credentials: 'include'|isAuthEndpoint" static/api-simulation.js

REMOTE_EOF

echo
echo "If local and remote hashes differ, deploy did not apply fully."
