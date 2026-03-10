#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/.local/share/prompt-manager/.venv"
OUT_DIR="${1:-$ROOT_DIR/dist/python-package}"
PACKAGE_NAME="${PROMPT_MATRIX_PACKAGE_NAME:-aidrax-prompt-matrix}"

if [ -z "${TWINE_REPOSITORY_URL:-}" ] && [ -z "${TWINE_REPOSITORY:-}" ]; then
    printf 'Setze TWINE_REPOSITORY_URL oder TWINE_REPOSITORY vor dem Upload.\n' >&2
    exit 1
fi

bash "$ROOT_DIR/scripts/build_python_package.sh" "$OUT_DIR" >/dev/null
"$VENV_DIR/bin/python" -m pip install --upgrade twine >/dev/null

printf 'Veroeffentliche %s nach %s ...\n' "$PACKAGE_NAME" "${TWINE_REPOSITORY_URL:-${TWINE_REPOSITORY:-default}}"
"$VENV_DIR/bin/python" -m twine upload "$OUT_DIR"/*
