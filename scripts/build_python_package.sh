#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/.local/share/prompt-manager/.venv"
OUT_DIR="${1:-$ROOT_DIR/dist/python-package}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    bash "$ROOT_DIR/install.sh"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade build >/dev/null

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

cd "$ROOT_DIR"
"$VENV_DIR/bin/python" -m build --outdir "$OUT_DIR"

printf 'Package artifacts written to %s\n' "$OUT_DIR"
ls -1 "$OUT_DIR"
