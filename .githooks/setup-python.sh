#!/bin/sh
set -eu

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

OS_NAME=$(uname -s 2>/dev/null || printf '%s' unknown)
case "$OS_NAME" in
  MINGW*|MSYS*|CYGWIN*)
    VENV_PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
    ;;
  *)
    VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
    ;;
esac

python_is_312() {
  "$@" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' >/dev/null 2>&1
}

bootstrap_python_312() {
  for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && python_is_312 "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

needs_venv_repair=1
if [ -x "$VENV_PYTHON" ] && python_is_312 "$VENV_PYTHON"; then
  needs_venv_repair=0
fi

if [ "$needs_venv_repair" -eq 1 ]; then
  bootstrap_python=$(bootstrap_python_312 || true)
  if [ -z "$bootstrap_python" ]; then
    printf '%s\n' "Python 3.12 was not found. Install Python 3.12 or pin Python 3.12 in the Codex environment before running setup." >&2
    exit 127
  fi
  "$bootstrap_python" -m venv .venv
fi

if [ ! -x "$VENV_PYTHON" ]; then
  printf '%s\n' "Project virtualenv Python was not created: $VENV_PYTHON" >&2
  exit 127
fi

if [ ! -f requirements-dev.txt ]; then
  printf '%s\n' "requirements-dev.txt not found" >&2
  exit 127
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements-dev.txt

chmod +x .githooks/pre-commit .githooks/post-commit .githooks/pre-push .githooks/reference-transaction .githooks/run-python.sh .githooks/setup-python.sh 2>/dev/null || true
git config core.hooksPath .githooks
git config core.symlinks true

repair_tracked_symlink() {
  path="$1"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    rm -rf -- "$path"
    git checkout -- "$path"
  fi
}

repair_tracked_symlink "CLAUDE.md"
repair_tracked_symlink ".claude/skills"

printf '%s\n' "Python environment is ready: $VENV_PYTHON"
