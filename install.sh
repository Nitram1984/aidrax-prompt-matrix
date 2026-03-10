#!/usr/bin/env bash
# ============================================================
#  PROMPT MANAGER CLI — Installationsskript fuer Ubuntu
# ============================================================
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/prompt-manager"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/.venv"
ASSETS_DIR="$INSTALL_DIR/assets"
PACKAGE_NAME="${PROMPT_MATRIX_PACKAGE_NAME:-aidrax-prompt-matrix}"
PIP_INDEX_URL="${PROMPT_MATRIX_PIP_INDEX_URL:-https://nitram1984.github.io/aidrax-prompt-matrix/simple}"
PIP_EXTRA_INDEX_URL="${PROMPT_MATRIX_PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}"

build_pip_index_args() {
    PIP_INDEX_ARGS=()
    if [ -n "$PIP_INDEX_URL" ]; then
        PIP_INDEX_ARGS+=(--index-url "$PIP_INDEX_URL")
    fi
    if [ -n "$PIP_EXTRA_INDEX_URL" ]; then
        PIP_INDEX_ARGS+=(--extra-index-url "$PIP_EXTRA_INDEX_URL")
    fi
}

copy_install_tree() {
    echo "→  Kopiere Dateien nach $INSTALL_DIR ..."
    mkdir -p "$INSTALL_DIR" "$ASSETS_DIR"
    cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/main.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/gui.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/db.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/ai.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/prompt_manager_version.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/prompt_manager_launchers.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/assets/aidrax-icon-neon-cyberpunk.png" "$ASSETS_DIR/"
    cp "$SCRIPT_DIR/assets/aidrax-icon-neon-cyberpunk.ico" "$ASSETS_DIR/"
    cp "$SCRIPT_DIR/assets/aidrax-icon-neon-cyberpunk.svg" "$ASSETS_DIR/"
    chmod +x "$INSTALL_DIR/install.sh"
    echo "✔  Dateien kopiert."
}

write_wrapper() {
    local target="$1"
    local inner_command="$2"

    cat > "$target" <<EOF
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$INSTALL_DIR"
SOURCE_DIR="$SCRIPT_DIR"
VENV_DIR="$VENV_DIR"
PACKAGE_NAME="\${PROMPT_MATRIX_PACKAGE_NAME:-$PACKAGE_NAME}"
PIP_INDEX_URL="\${PROMPT_MATRIX_PIP_INDEX_URL:-$PIP_INDEX_URL}"
PIP_EXTRA_INDEX_URL="\${PROMPT_MATRIX_PIP_EXTRA_INDEX_URL:-$PIP_EXTRA_INDEX_URL}"
UPDATE_TIMEOUT_SEC="\${PROMPT_MATRIX_UPDATE_TIMEOUT_SEC:-8}"
LOCK_FILE="\$HOME/.cache/prompt-manager-update.lock"
INNER_COMMAND="$inner_command"

build_pip_index_args() {
    PIP_INDEX_ARGS=()
    if [ -n "\$PIP_INDEX_URL" ]; then
        PIP_INDEX_ARGS+=(--index-url "\$PIP_INDEX_URL")
    fi
    if [ -n "\$PIP_EXTRA_INDEX_URL" ]; then
        PIP_INDEX_ARGS+=(--extra-index-url "\$PIP_EXTRA_INDEX_URL")
    fi
}

run_install_script() {
    local install_script=""
    if [ -x "\$INSTALL_DIR/install.sh" ]; then
        install_script="\$INSTALL_DIR/install.sh"
    elif [ -x "\$SOURCE_DIR/install.sh" ]; then
        install_script="\$SOURCE_DIR/install.sh"
    fi

    if [ -z "\$install_script" ]; then
        printf 'Prompt Matrix ist nicht installiert und es wurde kein Installationsskript gefunden.\n' >&2
        return 1
    fi

    bash "\$install_script" >/dev/null 2>&1
}

ensure_install_present() {
    if [ -x "\$VENV_DIR/bin/python" ] && [ -x "\$VENV_DIR/bin/\$INNER_COMMAND" ]; then
        return 0
    fi

    printf 'Prompt Matrix wird initial installiert ...\n' >&2
    if ! run_install_script; then
        printf 'Prompt Matrix konnte nicht installiert werden.\n' >&2
        exit 1
    fi
}

get_installed_version() {
    PROMPT_MATRIX_PACKAGE_NAME="\$PACKAGE_NAME" "\$VENV_DIR/bin/python" -c 'import importlib.metadata as metadata, os; print(metadata.version(os.environ["PROMPT_MATRIX_PACKAGE_NAME"]))' 2>/dev/null || true
}

get_latest_version() {
    local output latest
    build_pip_index_args

    if command -v timeout >/dev/null 2>&1; then
        output="\$(timeout "\${UPDATE_TIMEOUT_SEC}s" "\$VENV_DIR/bin/python" -m pip index versions "\$PACKAGE_NAME" "\${PIP_INDEX_ARGS[@]}" 2>/dev/null || true)"
    else
        output="\$("\$VENV_DIR/bin/python" -m pip index versions "\$PACKAGE_NAME" "\${PIP_INDEX_ARGS[@]}" 2>/dev/null || true)"
    fi

    latest="\$(printf '%s\n' "\$output" | awk -F: '/LATEST:/ {gsub(/[[:space:]]/, "", \$2); print \$2; exit}')"
    if [ -n "\$latest" ]; then
        printf '%s\n' "\$latest"
        return 0
    fi

    latest="\$(printf '%s\n' "\$output" | sed -n '1s/.*(//; 1s/).*//p' | tr -d '[:space:]')"
    printf '%s\n' "\$latest"
}

run_update_check() {
    local installed_version latest_version newest_version

    if [ "\${PROMPT_MATRIX_DISABLE_AUTO_UPDATE:-0}" = "1" ]; then
        return 0
    fi

    installed_version="\$(get_installed_version | tr -d '[:space:]')"
    if [ -z "\$installed_version" ]; then
        return 0
    fi

    latest_version="\$(get_latest_version | tr -d '[:space:]')"
    if [ -z "\$latest_version" ] || [ "\$installed_version" = "\$latest_version" ]; then
        return 0
    fi

    newest_version="\$(printf '%s\n%s\n' "\$installed_version" "\$latest_version" | sort -V | tail -n1)"
    if [ "\$newest_version" != "\$latest_version" ]; then
        return 0
    fi

    build_pip_index_args
    printf 'Prompt Matrix-Update verfuegbar: %s -> %s\n' "\$installed_version" "\$latest_version" >&2
    if "\$VENV_DIR/bin/python" -m pip install --upgrade "\${PIP_INDEX_ARGS[@]}" "\$PACKAGE_NAME" >/dev/null 2>&1; then
        printf 'Prompt Matrix wurde auf %s aktualisiert.\n' "\$latest_version" >&2
    else
        printf 'Prompt Matrix-Update fehlgeschlagen, starte weiter mit %s.\n' "\$installed_version" >&2
    fi
}

mkdir -p "\$HOME/.cache"
if command -v flock >/dev/null 2>&1; then
    exec 9>"\$LOCK_FILE"
    flock 9
fi

ensure_install_present
run_update_check

exec "\$VENV_DIR/bin/\$INNER_COMMAND" "\$@"
EOF

    chmod +x "$target"
}

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   PROMPT MANAGER CLI — Installation          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "✘  Python 3 nicht gefunden. Installiere mit: sudo apt install python3"
    exit 1
fi

PYTHON=$(command -v python3.11 || command -v python3)
echo "✔  Python gefunden: $($PYTHON --version)"

copy_install_tree

if [ ! -d "$VENV_DIR" ]; then
    echo "→  Erstelle virtuelle Umgebung ..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "✔  Virtuelle Umgebung erstellt."
else
    echo "✔  Virtuelle Umgebung vorhanden."
fi

echo "→  Installiere Paket und Abhaengigkeiten ..."
build_pip_index_args
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall "${PIP_INDEX_ARGS[@]}" "$INSTALL_DIR"
echo "✔  Paket installiert."

mkdir -p "$BIN_DIR"
write_wrapper "$BIN_DIR/prompt-manager" "prompt-manager"
echo "✔  Befehl 'prompt-manager' erstellt."

write_wrapper "$BIN_DIR/prompt-manager-gui" "prompt-manager-gui"
echo "✔  Befehl 'prompt-manager-gui' erstellt."

cat > "$BIN_DIR/manus-web" <<EOF
#!/usr/bin/env bash
exec "$BIN_DIR/prompt-manager" manus-open "\$@"
EOF
chmod +x "$BIN_DIR/manus-web"
echo "✔  Befehl 'manus-web' erstellt."

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/manus-web.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Manus
Comment=Open Manus in the default browser
Exec=$BIN_DIR/manus-web
Terminal=false
Categories=Utility;Network;
Icon=web-browser
StartupNotify=true
EOF
echo "✔  Desktop-Launcher 'Manus' erstellt."

cat > "$DESKTOP_DIR/prompt-manager-gui.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AIDRAX Prompt Matrix
Comment=Prompt Manager im AIDRAX Neon GUI Stil starten
Exec=$BIN_DIR/prompt-manager-gui
Terminal=false
Categories=Utility;Development;
Icon=$ASSETS_DIR/aidrax-icon-neon-cyberpunk.png
StartupNotify=true
EOF
echo "✔  Desktop-Launcher 'AIDRAX Prompt Matrix' erstellt."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "⚠  '$BIN_DIR' ist nicht in deinem PATH."
    echo "   Fuege folgende Zeile zu deiner ~/.bashrc oder ~/.zshrc hinzu:"
    echo ""
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "   Dann: source ~/.bashrc"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Installation abgeschlossen!                ║"
echo "║                                              ║"
echo "║   Starten mit:  prompt-manager               ║"
echo "║   Oder direkt:  prompt-manager-gui           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
