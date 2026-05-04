#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rishi1700/SDS.git}"
BRANCH="${BRANCH:-gs-volume-gui}"
TARGET_DIR="${TARGET_DIR:-$HOME/SDS}"
VENV_DIR="${VENV_DIR:-$TARGET_DIR/.venv-macos}"
REQ_FILE="$TARGET_DIR/requirements-ubuntu.txt"
APP_PATH="$TARGET_DIR/dist/GS_VolumeManager"
PYTHON_BIN="${PYTHON_BIN:-}"

python_tk_version() {
  "$1" -c 'import tkinter; print(tkinter.TkVersion)' 2>/dev/null || true
}

is_supported_tk() {
  case "$1" in
    8.6*|8.7*|9.*) return 0 ;;
    *) return 1 ;;
  esac
}

select_python() {
  local candidate
  local tk_version
  local candidates=(
    "/opt/homebrew/opt/python@3.13/bin/python3.13"
    "/opt/homebrew/opt/python@3.12/bin/python3.12"
    "/opt/homebrew/opt/python@3.11/bin/python3.11"
    "/opt/homebrew/bin/python3"
    "/usr/local/opt/python@3.13/bin/python3.13"
    "/usr/local/opt/python@3.12/bin/python3.12"
    "/usr/local/opt/python@3.11/bin/python3.11"
    "/usr/local/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  )

  if [[ -n "$PYTHON_BIN" ]]; then
    candidates=("$PYTHON_BIN" "${candidates[@]}")
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      tk_version="$(python_tk_version "$candidate")"
      if is_supported_tk "$tk_version"; then
        PYTHON_BIN="$candidate"
        return 0
      fi
      echo "Skipping $candidate because it uses Tk $tk_version."
    fi
  done

  return 1
}

install_homebrew_python_tk() {
  if ! command -v brew >/dev/null 2>&1; then
    return 1
  fi

  echo "No Python with Tk 8.6+ was found. Trying Homebrew Python/Tk..."
  brew install python@3.12 tcl-tk python-tk@3.12 || \
    brew install python@3.13 tcl-tk python-tk@3.13 || \
    brew install python tcl-tk
}

echo "Starting GS_VolumeManager Mac build..."
echo "Repo   : $REPO_URL"
echo "Branch : $BRANCH"
echo "Target : $TARGET_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required."
  exit 1
fi

if ! select_python; then
  install_homebrew_python_tk || true
  select_python || {
    echo "A Python build with Tk 8.6+ is required for the Mac GUI build."
    echo "The Apple system Python usually uses deprecated Tk 8.5 and can produce a blank app window."
    echo "Install Homebrew Python/Tk, then rerun this command:"
    echo "  brew install python@3.12 tcl-tk python-tk@3.12"
    exit 1
  }
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "python3 with Tk 8.6+ is required."
  exit 1
fi

echo "Python : $PYTHON_BIN"
echo "Tk     : $(python_tk_version "$PYTHON_BIN")"

if [[ -e "$TARGET_DIR" && ! -d "$TARGET_DIR/.git" ]]; then
  echo "Target directory exists but is not a git repository:"
  echo "  $TARGET_DIR"
  echo "Please remove it or run with a different TARGET_DIR."
  exit 1
fi

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "Cloning repository..."
  git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
else
  echo "Updating existing repository..."
  git -C "$TARGET_DIR" fetch origin
  if git -C "$TARGET_DIR" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git -C "$TARGET_DIR" checkout "$BRANCH"
  else
    git -C "$TARGET_DIR" checkout -b "$BRANCH" "origin/$BRANCH"
  fi
  git -C "$TARGET_DIR" pull --ff-only origin "$BRANCH"
fi

if [[ -f "$VENV_DIR/pyvenv.cfg" ]] && ! grep -q "$(dirname "$PYTHON_BIN")" "$VENV_DIR/pyvenv.cfg"; then
  echo "Recreating virtual environment with selected Python..."
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "Installing build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r "$REQ_FILE" pyinstaller

echo "Building app..."
cd "$TARGET_DIR"
rm -rf "$TARGET_DIR/build" "$TARGET_DIR/dist/GS_VolumeManager"
pyinstaller \
  --noconfirm \
  --onefile \
  --windowed \
  --name GS_VolumeManager \
  --add-data "mount_services.py:." \
  --hidden-import mount_services \
  --hidden-import requests \
  --collect-all requests \
  --collect-all urllib3 \
  --collect-all certifi \
  --collect-all charset_normalizer \
  --collect-all idna \
  gs_volume_gui.py

if [[ ! -f "$APP_PATH" ]]; then
  echo "Build finished, but the expected app was not found:"
  echo "  $APP_PATH"
  exit 1
fi

chmod +x "$APP_PATH"

echo
echo "Build complete."
echo "App:"
echo "  $APP_PATH"
