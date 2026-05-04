#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rishi1700/SDS.git}"
BRANCH="${BRANCH:-gs-volume-gui}"
TARGET_DIR="${TARGET_DIR:-$HOME/SDS}"
VENV_DIR="${VENV_DIR:-$TARGET_DIR/.venv-macos}"
REQ_FILE="$TARGET_DIR/requirements-ubuntu.txt"
APP_PATH="$TARGET_DIR/dist/GS_VolumeManager"

echo "Starting GS_VolumeManager Mac build..."
echo "Repo   : $REPO_URL"
echo "Branch : $BRANCH"
echo "Target : $TARGET_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

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

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
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
