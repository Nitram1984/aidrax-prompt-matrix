#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DB = Path.home() / ".prompt-manager" / "prompts.db"
SKILLS_ROOT = Path.home() / ".codex" / "skills"
APP_FILES = ("ai.py", "db.py", "main.py", "gui.py", "requirements.txt")
ASSET_FILES = (
    "aidrax-icon-neon-cyberpunk.png",
    "aidrax-icon-neon-cyberpunk.ico",
    "aidrax-icon-neon-cyberpunk.svg",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Windows sync bundle for the current HQ prompt-manager and Codex skills state."
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "dist" / "windows-hq-sync"),
        help="Target directory for the generated bundle.",
    )
    parser.add_argument(
        "--hq-ip",
        action="append",
        default=[],
        help="IPv4 address of the HQ host that should be allowed through the Windows firewall. Repeat for multiple addresses.",
    )
    parser.add_argument(
        "--hq-public-key-file",
        help="Path to an SSH public key that should be installed for authorized HQ remote admin access.",
    )
    parser.add_argument(
        "--linux-admin-user",
        default="",
        help="Authorized Linux admin user that should receive the HQ public key in authorized_keys.",
    )
    return parser.parse_args()


def load_prompts() -> list[dict]:
    if not PROMPT_DB.exists():
        raise FileNotFoundError(f"Prompt database not found: {PROMPT_DB}")

    con = sqlite3.connect(PROMPT_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT id, title, description, content, tags, is_favorite, use_count, updated_at
            FROM prompts
            ORDER BY id
            """
        ).fetchall()
    finally:
        con.close()

    prompts: list[dict] = []
    for row in rows:
        item = dict(row)
        tags = item.get("tags")
        if isinstance(tags, str):
            try:
                item["tags"] = json.loads(tags)
            except json.JSONDecodeError:
                item["tags"] = tags
        prompts.append(item)
    return prompts


def load_skills() -> list[dict]:
    if not SKILLS_ROOT.exists():
        raise FileNotFoundError(f"Skills root not found: {SKILLS_ROOT}")

    skills: list[dict] = []
    for skill_md in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        skills.append(
            {
                "name": skill_dir.name,
                "relative_path": str(skill_dir.relative_to(SKILLS_ROOT)),
            }
        )
    return skills


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_prompt_db(target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    source = sqlite3.connect(PROMPT_DB)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def load_public_key(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser().resolve()
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Public key file is empty: {path}")
    return content


def fingerprint_public_key(public_key: str | None) -> str | None:
    if not public_key:
        return None
    parts = public_key.strip().split()
    if len(parts) < 2:
        return None
    try:
        decoded = base64.b64decode(parts[1].encode("ascii"))
    except Exception:
        return None
    digest = hashlib.sha256(decoded).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def detect_hq_ipv4_addresses() -> list[str]:
    result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, check=False)
    addresses: list[str] = []
    for token in result.stdout.split():
        try:
            addr = ipaddress.ip_address(token)
        except ValueError:
            continue
        if addr.version == 4 and not addr.is_loopback:
            addresses.append(str(addr))
    return sorted(dict.fromkeys(addresses))


def render_remote_access_script(allowed_remote_addresses: list[str], hq_public_key: str | None = None) -> str:
    safe_addresses = allowed_remote_addresses
    quoted_addresses = ", ".join(f'"{address}"' for address in safe_addresses)
    public_key_literal = hq_public_key or ""
    return rf"""$ErrorActionPreference = "Stop"

$AllowedRemoteAddresses = @({quoted_addresses})
$HqAuthorizedKey = @"
{public_key_literal}
"@

function Ensure-Admin {{
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
        throw "Dieses Skript muss in einer als Administrator gestarteten PowerShell ausgefuehrt werden."
    }}
}}

function Ensure-FirewallRule([string]$Name, [string]$DisplayName, [int]$Port) {{
    if ($AllowedRemoteAddresses.Count -eq 0) {{
        Write-Warning "Keine HQ-IP-Allowlist eingebettet. Firewall-Regel $Name wird nicht automatisch erstellt."
        return
    }}

    $existing = Get-NetFirewallRule -Name $Name -ErrorAction SilentlyContinue
    if ($existing) {{
        $existing | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Any | Out-Null
        $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $AllowedRemoteAddresses | Out-Null
        return
    }}

    New-NetFirewallRule `
        -Name $Name `
        -DisplayName $DisplayName `
        -Enabled True `
        -Direction Inbound `
        -Action Allow `
        -Profile Any `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress $AllowedRemoteAddresses | Out-Null
}}

function Ensure-AuthorizedKey([string]$PublicKey) {{
    if ([string]::IsNullOrWhiteSpace($PublicKey)) {{
        return
    }}

    $sshDir = Join-Path $env:ProgramData "ssh"
    $adminKeysPath = Join-Path $sshDir "administrators_authorized_keys"
    if (-not (Test-Path $sshDir)) {{
        New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    }}
    if (-not (Test-Path $adminKeysPath)) {{
        New-Item -ItemType File -Path $adminKeysPath -Force | Out-Null
    }}

    $trimmedKey = $PublicKey.Trim()
    $existingLines = @()
    if (Test-Path $adminKeysPath) {{
        $existingLines = Get-Content -Path $adminKeysPath -ErrorAction SilentlyContinue
    }}
    if ($existingLines -notcontains $trimmedKey) {{
        Add-Content -Path $adminKeysPath -Value $trimmedKey
    }}

    icacls $adminKeysPath /inheritance:r | Out-Null
    icacls $adminKeysPath /grant "Administrators:F" "SYSTEM:F" | Out-Null
}}

Ensure-Admin

$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
if ($sshCapability -and $sshCapability.State -ne "Installed") {{
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
}}
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Ensure-AuthorizedKey -PublicKey $HqAuthorizedKey
Ensure-FirewallRule -Name "HQ-SSH-In-TCP" -DisplayName "HQ SSH Zugriff" -Port 22

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Enable-PSRemoting -Force -SkipNetworkProfileCheck" | Out-Null
Set-Service -Name WinRM -StartupType Automatic
Start-Service WinRM
Ensure-FirewallRule -Name "HQ-WinRM-In-TCP" -DisplayName "HQ WinRM Zugriff" -Port 5985

Set-Service -Name LanmanServer -StartupType Automatic
Start-Service LanmanServer
if (Get-Command Set-SmbServerConfiguration -ErrorAction SilentlyContinue) {{
    Set-SmbServerConfiguration -EnableSMB2Protocol $true -Force | Out-Null
}}
Ensure-FirewallRule -Name "HQ-SMB-In-TCP-445" -DisplayName "HQ SMB Zugriff 445" -Port 445
Ensure-FirewallRule -Name "HQ-SMB-In-TCP-139" -DisplayName "HQ SMB Zugriff 139" -Port 139

Write-Host ""
Write-Host "Remote-Zugriff aktiviert." -ForegroundColor Green
if ($AllowedRemoteAddresses.Count -eq 0) {{
    Write-Host "Erlaubte HQ-IPs: keine eingebettet"
}} else {{
    Write-Host ("Erlaubte HQ-IPs: " + ($AllowedRemoteAddresses -join ", "))
}}
Write-Host "SSH:   Port 22"
Write-Host "WinRM: Port 5985"
Write-Host "SMB:   Ports 445 und 139"
if ([string]::IsNullOrWhiteSpace($HqAuthorizedKey)) {{
    Write-Host "SSH Public Key: nicht eingebettet"
}} else {{
    Write-Host "SSH Public Key: eingebettet"
}}
"""


def render_linux_remote_access_script(
    allowed_remote_addresses: list[str],
    hq_public_key: str | None = None,
    linux_admin_user: str | None = None,
) -> str:
    safe_addresses = allowed_remote_addresses
    address_lines = "\n".join(f'ALLOWED_REMOTE_ADDRESSES+=("{address}")' for address in safe_addresses)
    public_key_literal = hq_public_key or ""
    default_user = linux_admin_user or ""
    return rf"""#!/usr/bin/env bash
set -euo pipefail

DEFAULT_ADMIN_USER="{default_user}"
HQ_PUBLIC_KEY=$(cat <<'EOF'
{public_key_literal}
EOF
)
declare -a ALLOWED_REMOTE_ADDRESSES=()
{address_lines}

require_root() {{
  if [ "$(id -u)" -ne 0 ]; then
    echo "Dieses Skript muss als root laufen." >&2
    exit 1
  fi
}}

resolve_target_user() {{
  if [ -n "${{1:-}}" ]; then
    printf '%s\n' "$1"
    return
  fi
  if [ -n "$DEFAULT_ADMIN_USER" ]; then
    printf '%s\n' "$DEFAULT_ADMIN_USER"
    return
  fi
  echo "" >&2
}}

get_home_dir() {{
  getent passwd "$1" | cut -d: -f6
}}

enable_ssh_service() {{
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl nicht gefunden. SSH-Dienst bitte manuell pruefen."
    return
  fi

  if systemctl list-unit-files ssh.service >/dev/null 2>&1; then
    systemctl enable --now ssh.service
    return
  fi
  if systemctl list-unit-files sshd.service >/dev/null 2>&1; then
    systemctl enable --now sshd.service
    return
  fi

  echo "Kein ssh.service oder sshd.service gefunden."
}}

configure_ufw() {{
  if [ "${{#ALLOWED_REMOTE_ADDRESSES[@]}}" -eq 0 ]; then
    echo "Keine HQ-IP-Allowlist eingebettet. UFW-Regeln wurden nicht automatisch geaendert."
    return
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    echo "ufw nicht installiert. Firewall-Regeln manuell pruefen."
    return
  fi

  local status
  status=$(ufw status 2>/dev/null || true)
  if ! printf '%s\n' "$status" | grep -q "^Status: active"; then
    echo "ufw nicht aktiv. Firewall-Regeln wurden nicht geaendert."
    return
  fi

  for address in "${{ALLOWED_REMOTE_ADDRESSES[@]}}"; do
    ufw allow from "$address" to any port 22 proto tcp
  done
}}

install_public_key() {{
  local target_user="$1"
  local target_home="$2"
  local ssh_dir="$target_home/.ssh"
  local auth_keys="$ssh_dir/authorized_keys"

  mkdir -p "$ssh_dir"
  chmod 700 "$ssh_dir"
  touch "$auth_keys"
  chmod 600 "$auth_keys"
  chown "$target_user:$target_user" "$ssh_dir" "$auth_keys"

  if [ -z "$HQ_PUBLIC_KEY" ]; then
    echo "Kein HQ Public Key eingebettet. authorized_keys unveraendert."
    return
  fi

  if ! grep -qxF "$HQ_PUBLIC_KEY" "$auth_keys"; then
    printf '%s\n' "$HQ_PUBLIC_KEY" >> "$auth_keys"
  fi
  chown "$target_user:$target_user" "$auth_keys"
}}

main() {{
  require_root

  local target_user
  target_user=$(resolve_target_user "${{1:-}}")
  if [ -z "$target_user" ]; then
    echo "Linux-Admin-User fehlt. Uebergib ihn als erstes Argument oder baue das Bundle mit --linux-admin-user." >&2
    exit 1
  fi

  if ! getent passwd "$target_user" >/dev/null 2>&1; then
    echo "Benutzer nicht gefunden: $target_user" >&2
    exit 1
  fi

  local target_home
  target_home=$(get_home_dir "$target_user")
  if [ -z "$target_home" ]; then
    echo "Home-Verzeichnis fuer $target_user konnte nicht ermittelt werden." >&2
    exit 1
  fi

  install_public_key "$target_user" "$target_home"
  enable_ssh_service
  configure_ufw

  echo ""
  echo "Linux Remote-Zugriff vorbereitet."
  echo "Benutzer: $target_user"
  echo "Home:     $target_home"
  echo "SSH-Key:  $( [ -n "$HQ_PUBLIC_KEY" ] && echo eingebettet || echo nicht-eingebettet )"
  echo "Allowlist: ${{ALLOWED_REMOTE_ADDRESSES[*]}}"
}}

main "$@"
"""


def render_windows_installer(manifest_name: str) -> str:
    return rf"""param(
    [string]$BundleRoot = $(Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Stop"

$PayloadRoot = Join-Path $BundleRoot "payload"
$PromptDbSource = Join-Path $PayloadRoot "prompts.db"
$PromptsJsonSource = Join-Path $PayloadRoot "prompts.json"
$SkillsSource = Join-Path $PayloadRoot "skills"
$AppSource = Join-Path $PayloadRoot "prompt-manager-app"
$ManifestPath = Join-Path $BundleRoot "{manifest_name}"

$PromptStore = Join-Path $env:USERPROFILE ".prompt-manager"
$CodexRoot = Join-Path $env:USERPROFILE ".codex"
$SkillsTarget = Join-Path $CodexRoot "skills"
$AppRoot = Join-Path $env:LOCALAPPDATA "prompt-manager"
$BinRoot = Join-Path $env:USERPROFILE "bin"
$VenvRoot = Join-Path $AppRoot ".venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$PromptManagerCmd = Join-Path $BinRoot "prompt-manager.cmd"
$PromptManagerGuiCmd = Join-Path $BinRoot "prompt-manager-gui.cmd"
$ManusWebCmd = Join-Path $BinRoot "manus-web.cmd"
$RemoteAccessScript = Join-Path $BundleRoot "enable_windows_remote_access.ps1"

function Ensure-Directory([string]$Path) {{
    if (-not (Test-Path $Path)) {{
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }}
}}

Ensure-Directory $PromptStore
Ensure-Directory $SkillsTarget
Ensure-Directory $AppRoot
Ensure-Directory $BinRoot

Copy-Item -Path $PromptDbSource -Destination (Join-Path $PromptStore "prompts.db") -Force
Copy-Item -Path $PromptsJsonSource -Destination (Join-Path $PromptStore "prompts.json") -Force
Copy-Item -Path (Join-Path $SkillsSource "*") -Destination $SkillsTarget -Recurse -Force
Copy-Item -Path (Join-Path $AppSource "*") -Destination $AppRoot -Recurse -Force

$PythonAvailable = $false
if (Get-Command py -ErrorAction SilentlyContinue) {{
    & py -3 -m venv $VenvRoot
    $PythonAvailable = $true
}} elseif (Get-Command python -ErrorAction SilentlyContinue) {{
    & python -m venv $VenvRoot
    $PythonAvailable = $true
}}

if ($PythonAvailable -and (Test-Path $VenvPython)) {{
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $AppRoot "requirements.txt")

    @"
@echo off
cd /d "%LOCALAPPDATA%\prompt-manager"
"%LOCALAPPDATA%\prompt-manager\.venv\Scripts\python.exe" main.py %*
"@ | Set-Content -Path $PromptManagerCmd -Encoding ASCII

    @"
@echo off
cd /d "%LOCALAPPDATA%\prompt-manager"
"%LOCALAPPDATA%\prompt-manager\.venv\Scripts\python.exe" gui.py %*
"@ | Set-Content -Path $PromptManagerGuiCmd -Encoding ASCII

    @"
@echo off
call "%USERPROFILE%\bin\prompt-manager.cmd" manus-open %*
"@ | Set-Content -Path $ManusWebCmd -Encoding ASCII
}} else {{
    Write-Warning "Python wurde auf Windows nicht gefunden. Prompts und Skills sind kopiert, aber prompt-manager wurde nicht ausführbar eingerichtet."
}}

if (Test-Path $RemoteAccessScript) {{
    & $RemoteAccessScript
}}

$CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($CurrentUserPath)) {{
    $CurrentUserPath = $BinRoot
}} elseif (($CurrentUserPath -split ";") -notcontains $BinRoot) {{
    $CurrentUserPath = ($CurrentUserPath.TrimEnd(";") + ";" + $BinRoot)
}}
[Environment]::SetEnvironmentVariable("Path", $CurrentUserPath, "User")

Write-Host ""
Write-Host "Windows-Sync abgeschlossen." -ForegroundColor Green
Write-Host "Manifest: $ManifestPath"
Write-Host "Prompts:  $PromptStore"
Write-Host "Skills:   $SkillsTarget"
Write-Host "App:      $AppRoot"
Write-Host "Bin:      $BinRoot"
Write-Host ""
if (Test-Path $PromptManagerCmd) {{
    Write-Host "Starte danach in einem neuen Terminal: prompt-manager"
    Write-Host "GUI optional: prompt-manager-gui"
}} else {{
    Write-Host "Falls Python spaeter installiert wird, erneut ausfuehren: .\install_windows_sync.ps1"
}}
"""


def render_readme(manifest: dict, zip_name: str) -> str:
    hq_ips = ", ".join(manifest.get("hq_ipv4_addresses") or ["keine erkannt"])
    key_fingerprint = manifest.get("hq_public_key_fingerprint") or "kein eingebetteter Public Key"
    linux_admin_user = manifest.get("linux_admin_user") or "nicht gesetzt"
    return (
        "HQ Windows Sync Bundle\n"
        "======================\n\n"
        f"Erstellt: {manifest['generated_at_utc']}\n"
        f"Prompt-Anzahl: {manifest['prompt_count']}\n"
        f"Skill-Anzahl: {manifest['skill_count']}\n\n"
        "Inhalt:\n"
        "- install_windows_sync.ps1: installiert Prompts, Skills und prompt-manager auf Windows.\n"
        "- enable_windows_remote_access.ps1: aktiviert SSH, WinRM und SMB fuer HQ.\n"
        "- enable_linux_remote_access.sh: bereitet autorisierten SSH-Zugriff auf Linux fuer HQ vor.\n"
        "- manifest.json: Inventar der enthaltenen Prompts und Skills.\n"
        "- payload/: Rohdaten fuer die Installation.\n"
        f"- {zip_name}: gepackte Bundle-Version fuer einfache Uebertragung.\n\n"
        "Ausfuehrung auf Windows:\n"
        "1. Bundle auf den Windows-Rechner kopieren.\n"
        "2. PowerShell im Bundle-Ordner oeffnen.\n"
        "3. Optional: Set-ExecutionPolicy -Scope Process Bypass\n"
        "4. .\\install_windows_sync.ps1\n\n"
        "Ausfuehrung auf Linux / maidrax:\n"
        "1. Bundle auf den Linux-Host kopieren.\n"
        "2. chmod +x ./enable_linux_remote_access.sh\n"
        "3. sudo ./enable_linux_remote_access.sh <linux-admin-user>\n\n"
        "Remote-Zugriff:\n"
        f"- Erlaubte HQ-IPv4-Adressen: {hq_ips or 'keine erkannt'}\n"
        f"- Eingebetteter HQ-Public-Key: {key_fingerprint}\n"
        f"- Vorgesehener Linux-Admin-User: {linux_admin_user}\n"
        "- SSH wird auf Port 22 aktiviert.\n"
        "- WinRM wird auf Port 5985 aktiviert.\n"
        "- SMB wird auf Ports 445 und 139 aktiviert.\n\n"
        "Hinweis:\n"
        "- Diese Vorbereitung ist fuer autorisierte Admin-Zugriffe gedacht, nicht fuer verdeckte Persistenz.\n"
        "- Wenn keine HQ-IP eingebettet ist, das Bundle mit --hq-ip <adresse> erneut erzeugen.\n"
        "- Nach der Freischaltung immer aktiv pruefen: SSH, WinRM, SMB und die effektiven Firewall-Regeln.\n"
    )


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    payload_dir = output_dir / "payload"
    app_dir = payload_dir / "prompt-manager-app"
    assets_dir = app_dir / "assets"
    skills_dir = payload_dir / "skills"

    prompts = load_prompts()
    skills = load_skills()
    hq_ipv4_addresses = sorted(dict.fromkeys(args.hq_ip or detect_hq_ipv4_addresses()))
    hq_public_key = load_public_key(args.hq_public_key_file)
    hq_public_key_fingerprint = fingerprint_public_key(hq_public_key)

    if output_dir.exists():
        shutil.rmtree(output_dir)

    app_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.parent.mkdir(parents=True, exist_ok=True)

    for filename in APP_FILES:
        shutil.copy2(REPO_ROOT / filename, app_dir / filename)
    for filename in ASSET_FILES:
        shutil.copy2(REPO_ROOT / "assets" / filename, assets_dir / filename)

    export_prompt_db(payload_dir / "prompts.db")
    shutil.copytree(SKILLS_ROOT, skills_dir, dirs_exist_ok=True)

    write_json(payload_dir / "prompts.json", prompts)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_prompt_db": str(PROMPT_DB),
        "source_skills_root": str(SKILLS_ROOT),
        "hq_ipv4_addresses": hq_ipv4_addresses,
        "hq_public_key_fingerprint": hq_public_key_fingerprint,
        "linux_admin_user": args.linux_admin_user or None,
        "prompt_count": len(prompts),
        "skill_count": len(skills),
        "prompts": [
            {
                "id": prompt["id"],
                "title": prompt["title"],
                "tags": prompt["tags"],
                "is_favorite": prompt["is_favorite"],
                "updated_at": prompt["updated_at"],
            }
            for prompt in prompts
        ],
        "skills": skills,
    }

    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    (output_dir / "enable_windows_remote_access.ps1").write_text(
        render_remote_access_script(hq_ipv4_addresses, hq_public_key=hq_public_key), encoding="utf-8"
    )
    linux_remote_access_path = output_dir / "enable_linux_remote_access.sh"
    linux_remote_access_path.write_text(
        render_linux_remote_access_script(
            hq_ipv4_addresses,
            hq_public_key=hq_public_key,
            linux_admin_user=args.linux_admin_user,
        ),
        encoding="utf-8",
    )
    linux_remote_access_path.chmod(0o755)
    (output_dir / "install_windows_sync.ps1").write_text(
        render_windows_installer(manifest_path.name), encoding="utf-8"
    )

    zip_base = output_dir.parent / output_dir.name
    zip_name = f"{zip_base.name}.zip"
    readme = render_readme(manifest, zip_name)
    (output_dir / "README.txt").write_text(readme, encoding="utf-8")
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=output_dir)

    print(f"Bundle directory: {output_dir}")
    print(f"Bundle archive: {archive_path}")
    print(f"Prompt count: {len(prompts)}")
    print(f"Skill count: {len(skills)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
