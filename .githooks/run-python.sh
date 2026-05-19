#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
  PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
else
  printf '%s\n' "Project virtualenv Python not found. Create or repair .venv before running hooks." >&2
  printf '%s\n' "Expected: .venv/bin/python or .venv/Scripts/python.exe" >&2
  exit 127
fi

exec "$PYTHON" "$@"
