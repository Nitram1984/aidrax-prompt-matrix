#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db


CATEGORY_NAME = "HQ / Remote Access"
CATEGORY_COLOR = "#2274A5"
CATEGORY_ICON = "NET"


PROMPTS = [
    {
        "title": "HQ Remote Admin: Windows und Maidrax Freischaltplan",
        "description": "Plant autorisierte Dauerzugriffe zwischen HQ, Windows und maidrax.",
        "tags": ["hq", "windows", "maidrax", "remote-access", "operations"],
        "is_favorite": True,
        "content": """Du bist Enterprise Platform Engineer fuer autorisierte Remote-Administration.

Ziel:
Plane einen belastbaren, legitimen Dauerzugriff zwischen HQ, Windows und maidrax.

Eingaben:
- HQ-IP(s) / Subnetze: {{hq_ips}}
- HQ-Public-Key-Fingerprint: {{hq_key_fingerprint}}
- Windows-Ziel: {{windows_ziel}}
- Linux-Ziel: {{linux_ziel}}
- Gewuenschter Linux-Admin-User: {{linux_admin_user}}
- Besondere Restriktionen oder Policies: {{restriktionen}}

Liefere:
1. Rollout-Reihenfolge
2. Welche Services auf Windows und Linux aktiviert werden sollen
3. Welche Firewall- und Allowlist-Regeln gesetzt werden sollen
4. Welche Verifikationsschritte direkt nach Freischaltung Pflicht sind
5. Welche Rollback-Schritte vorbereitet sein muessen

Regeln:
- Nur autorisierte Admin-Wege
- Keine versteckte Persistenz
- Public-Key-basierter SSH-Zugriff bevorzugt
- Fakten, Annahmen und Empfehlungen trennen
""",
    },
    {
        "title": "HQ Remote Admin: Verifikation und Drift-Check",
        "description": "Prueft, ob der vorbereitete Remote-Zugriff wirklich stabil und eingegrenzt ist.",
        "tags": ["hq", "remote-access", "verification", "drift"],
        "is_favorite": False,
        "content": """Du verifizierst eine bereits vorbereitete Remote-Admin-Fabric.

Inventar und Beobachtungen:
{{inventar}}

Liefere:
1. Eine Verifikationsmatrix fuer Windows, maidrax und HQ
2. Hinweise auf Drift oder Fehlkonfiguration
3. Die 5 wichtigsten Risiken, wenn der Zugriff so bleibt wie beschrieben
4. Exakte Nachtests fuer SSH, WinRM, SMB und Firewall
5. Eine klare Aussage, ob der Zugriff als "betriebsfaehig" gelten kann

Regeln:
- Nicht nur "Port offen" als Erfolg werten
- Listener, Authentisierung und Allowlist getrennt pruefen
- Keine unautorisierten oder verdeckten Methoden empfehlen
""",
    },
    {
        "title": "HQ Remote Admin: Runbook und Entzug",
        "description": "Erstellt ein Runbook fuer Betrieb, Rotation und Entzug des Dauerzugriffs.",
        "tags": ["hq", "remote-access", "runbook", "rotation", "rollback"],
        "is_favorite": False,
        "content": """Erstelle ein knappes Betriebs- und Entzugs-Runbook fuer autorisierten Dauerzugriff.

Umgebung:
{{umgebung}}

Zugangsdetails:
{{zugangsdetails}}

Das Runbook soll enthalten:
1. Wer Zugriff hat und worueber
2. Welche Key-Fingerprints und Allowlists gelten
3. Regelmaessige Pruefungen
4. Was bei Ausfall des Zugriffs zuerst geprueft wird
5. Wie Zugriff rotiert oder entzogen wird
6. Welche Logs oder Nachweise aufbewahrt werden sollen

Form:
- betrieblich
- kurz
- exakt
- ohne generische Sicherheitsfloskeln
""",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed curated HQ remote access prompts into prompt-manager."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without DB writes.")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update prompts when a seed title already exists.",
    )
    return parser.parse_args()


def get_or_create_category() -> int:
    with db.get_conn() as conn:
        row = conn.execute("SELECT id FROM categories WHERE name=?", (CATEGORY_NAME,)).fetchone()
        if row:
            return int(row["id"])
    return db.create_category(CATEGORY_NAME, color=CATEGORY_COLOR, icon=CATEGORY_ICON)


def find_prompt_id_by_title(title: str) -> int | None:
    with db.get_conn() as conn:
        row = conn.execute("SELECT id FROM prompts WHERE title=?", (title,)).fetchone()
        return int(row["id"]) if row else None


def seed_prompt(category_id: int, prompt: dict[str, object], update_existing: bool) -> tuple[str, int]:
    prompt_id = find_prompt_id_by_title(str(prompt["title"]))
    if prompt_id is None:
        prompt_id = db.create_prompt(
            title=str(prompt["title"]),
            content=str(prompt["content"]),
            description=str(prompt["description"]),
            category_id=category_id,
            tags=list(prompt["tags"]),
            is_favorite=bool(prompt["is_favorite"]),
            is_active=True,
        )
        return "created", prompt_id

    if not update_existing:
        return "skipped", prompt_id

    db.update_prompt(
        prompt_id,
        content=str(prompt["content"]),
        description=str(prompt["description"]),
        category_id=category_id,
        tags=list(prompt["tags"]),
        is_favorite=bool(prompt["is_favorite"]),
        is_active=True,
    )
    return "updated", prompt_id


def main() -> int:
    args = parse_args()
    category_id = get_or_create_category()

    if args.dry_run:
        print(f"Category: {CATEGORY_NAME} (id={category_id})")
        for prompt in PROMPTS:
            existing_id = find_prompt_id_by_title(str(prompt["title"]))
            if existing_id is None:
                action = "would create"
            elif args.update_existing:
                action = "would update"
            else:
                action = "would skip"
            print(f"- {action}: {prompt['title']}")
        return 0

    for prompt in PROMPTS:
        action, prompt_id = seed_prompt(category_id, prompt, args.update_existing)
        print(f"{action}: #{prompt_id} {prompt['title']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
