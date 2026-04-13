#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ubuntu"
REQ_FILE="${ROOT_DIR}/requirements-ubuntu.txt"
SPEC_FILE="${ROOT_DIR}/SDS-WS-linux.spec"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "${REQ_FILE}" pyinstaller

pyinstaller --noconfirm "${SPEC_FILE}"

echo
echo "Build complete."
echo "Single executable:"
echo "  ${ROOT_DIR}/dist/SDS-WS"
