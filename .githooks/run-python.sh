#!/bin/sh
set -eu

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OS_NAME=$(uname -s 2>/dev/null || printf '%s' unknown)

case "$OS_NAME" in
  MINGW*|MSYS*|CYGWIN*)
    PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
    EXPECTED=".venv/Scripts/python.exe"
    ;;
  *)
    PYTHON="$REPO_ROOT/.venv/bin/python"
    EXPECTED=".venv/bin/python"
    ;;
esac

if [ ! -x "$PYTHON" ]; then
  printf '%s\n' "Project virtualenv Python not found for $OS_NAME. Create or repair .venv before running hooks." >&2
  printf '%s\n' "Expected: $EXPECTED" >&2
  exit 127
fi

exec "$PYTHON" "$@"
