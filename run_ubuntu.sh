#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ubuntu"
REQ_FILE="${ROOT_DIR}/requirements-ubuntu.txt"

missing_cmds=()
for cmd in python3 ping iscsiadm mount.cifs mount.nfs xdg-open; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_cmds+=("$cmd")
  fi
done

if ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  echo "Missing Python Tk support for the GUI."
  echo "Install Ubuntu packages:"
  echo "  sudo apt update && sudo apt install -y python3-tk"
  exit 1
fi

if ((${#missing_cmds[@]} > 0)); then
  echo "Missing required system commands: ${missing_cmds[*]}"
  echo "Install Ubuntu packages:"
  echo "  sudo apt update && sudo apt install -y iputils-ping open-iscsi cifs-utils nfs-common"
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "${REQ_FILE}"

exec python "${ROOT_DIR}/sds_gui.py"
