#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

VENV_DIR="${SCRIPT_DIR}/.venv_test"
PYTHON_BIN="python3"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "python3 is required but was not found." >&2
  exit 1
fi

create_venv() {
  if "${PYTHON_BIN}" -m venv "${VENV_DIR}" >/dev/null 2>&1; then
    return 0
  fi

  echo "python3 -m venv failed; trying virtualenv fallback..."
  if ! command -v "${HOME}/.local/bin/virtualenv" >/dev/null 2>&1; then
    "${PYTHON_BIN}" -m pip install --user --break-system-packages virtualenv
  fi
  "${HOME}/.local/bin/virtualenv" "${VENV_DIR}"
}

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating test virtual environment at ${VENV_DIR}"
  create_venv
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV_DIR}/bin/pip" install -r asset_management/requirements.txt >/dev/null

cd asset_management
"${VENV_DIR}/bin/python" -m unittest tests/test_security_and_flows.py -v
