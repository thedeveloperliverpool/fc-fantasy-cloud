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
echo "Pushed release $NEW_VERSION"
