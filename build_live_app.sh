#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$ROOT_DIR/dist-live"
APP_NAME="FC Fantasy Live"

rm -rf "$DIST_DIR" "$ROOT_DIR/build/$APP_NAME"
mkdir -p "$DIST_DIR"

PYINSTALLER_CONFIG_DIR=/tmp/pyinstaller \
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --collect-all pygame \
  --name "$APP_NAME" \
  "$ROOT_DIR/launcher.py"

cp "$ROOT_DIR/Football Game.py" "$DIST_DIR/Football Game.py"
cp "$ROOT_DIR/version.json" "$DIST_DIR/version.json"
cp "$ROOT_DIR/update_instructions.txt" "$DIST_DIR/update_instructions.txt"
mv "$ROOT_DIR/dist/$APP_NAME.app" "$DIST_DIR/$APP_NAME.app"

ditto -c -k --sequesterRsrc --keepParent \
  "$DIST_DIR/$APP_NAME.app" \
  "$DIST_DIR/$APP_NAME.zip"

echo "Live app created in $DIST_DIR"
