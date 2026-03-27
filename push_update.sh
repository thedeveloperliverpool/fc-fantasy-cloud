#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ $# -gt 1 ]]; then
  echo "Usage: ./push_update.sh [base-version]"
  echo "Example: ./push_update.sh 1.2"
  exit 1
fi

NEW_VERSION="$(python3 "$ROOT_DIR/bump_version.py" "${1:-}")"
git add version.json

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A -- . ":(exclude)build" ":(exclude)dist" ":(exclude)dist-live" ":(exclude)dist-live-old" ":(exclude)__pycache__"
  git commit -m "Release $NEW_VERSION"
fi

git push origin main
PENDING_UPDATES="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("version.json").read_text(encoding="utf-8"))
print(int(data.get("pending_updates", 0) or 0))
PY
)"
BUMP_EVERY="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("version.json").read_text(encoding="utf-8"))
print(int(data.get("bump_every", 2) or 2))
PY
)"
if [[ "$PENDING_UPDATES" -eq 0 ]]; then
  echo "Pushed release $NEW_VERSION"
else
  echo "Pushed update $PENDING_UPDATES/$BUMP_EVERY for release $NEW_VERSION"
fi
