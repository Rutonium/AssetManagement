#!/usr/bin/env bash
set -euo pipefail

# Run this ON THE SERVER after deploy_copy.sh has uploaded archive.
# No sudo calls are performed.

REMOTE_PATH="${REMOTE_PATH:-/home/rune/dev/asset_management}"
ARCHIVE_NAME="${ARCHIVE_NAME:-asset_management.tgz}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${REMOTE_PATH}"

if [[ ! -f "${ARCHIVE_NAME}" ]]; then
  echo "Archive not found: ${REMOTE_PATH}/${ARCHIVE_NAME}" >&2
  exit 1
fi

echo "Unpacking ${ARCHIVE_NAME} into ${REMOTE_PATH} ..."
tar -xzf "${ARCHIVE_NAME}" --strip-components=1
rm -f "${ARCHIVE_NAME}"

if [[ ! -d "venv" ]]; then
  echo "Creating venv in ${REMOTE_PATH}/venv ..."
  "${PYTHON_BIN}" -m venv venv
fi

echo "Installing requirements in venv ..."
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Update complete. Next: run sudo systemctl restart asset_management"
