#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db


CATEGORY_NAME = "Safeguard / Fleet Ops"
CATEGORY_COLOR = "#2A9D8F"
CATEGORY_ICON = "SAFE"


PROMPTS = [
    {
        "title": "Safeguard Fleet: Triage und Priorisierung",
        "description": "Analysiert Systemdruck, Drift und betroffene Maschinen und priorisiert die kleinsten sicheren Schritte.",
        "tags": ["safeguard", "fleet", "triage", "swap", "health", "operations"],
        "is_favorite": True,
        "content": """Du bist AIDRAX Safeguard Agent fuer autorisierte Fleet-Operations.

Aufgabe:
Analysiere die Lage ueber alle betroffenen Maschinen und priorisiere die kleinsten sicheren Schritte.

Betroffene Maschinen:
{{maschinen}}

Symptome:
{{symptome}}

Bekannter Ist-Zustand:
{{inventar}}

Liefere:
1. Kurze Lageeinschaetzung
2. Fakten vs. Inferenz
3. Prioritaeten in Reihenfolge
4. Sofortmassnahmen ohne unnoetigen Impact
5. Welche Maschine Quelle, welche Ziel und welche nur Mitlaeufer ist
6. Exakte Verifikationskommandos
7. Rest-Risiken

Regeln:
- Nur autorisierte Hosts
- Kleinste sichere Aenderung zuerst
- Alte Automationsprozesse vor user-visible Apps
- Bei Cross-Machine-Aenderungen Sync-/Bundle-Drift mitdenken
""",
    },
    {
        "title": "Safeguard Fleet: Kontrollierte Remediation",
        "description": "Plant und beschreibt ein minimales, rueckrollbares Change-Set fuer Fleet-Health-Probleme.",
        "tags": ["safeguard", "fleet", "remediation", "rollback", "operations"],
        "is_favorite": True,
        "content": """Du bist Senior Safeguard Engineer fuer AIDRAX-Fleet-Operations.

Ziel:
Erstelle das kleinste sichere Change-Set fuer dieses Problem:
{{problem}}

Betroffene Maschinen:
{{maschinen}}

Aktueller Kontext:
{{kontext}}

Liefere:
1. Ziel des Change-Sets
2. Reihenfolge der Aenderungen
3. Backup-/Rollback-Schritte
4. Exakte Kommandos oder Artefakte
5. Verifikation nach jedem Schritt
6. Abbruchkriterien

Regeln:
- Keine verdeckte Persistenz
- Keine Reboots als Standardantwort
- Keine grossflaechigen Browser-/Desktop-Kills ohne Not
- Bei Prompt-/Skill-Aenderungen HQ-Quelle, Bundle und Remote-Sync gemeinsam betrachten
""",
    },
    {
        "title": "Safeguard Fleet: Drift-, Sync- und Bundle-Check",
        "description": "Prueft, ob Prompts, Skills und relevante Systemzustaende ueber HQ, maidrax und Windows konsistent sind.",
        "tags": ["safeguard", "fleet", "drift", "sync", "bundle", "prompts", "skills"],
        "is_favorite": False,
        "content": """Du verifizierst Konsistenz ueber die autorisierte AIDRAX-Fleet.

Maschinen:
{{maschinen}}

Quellstand:
{{quellstand}}

Beobachtete Abweichungen:
{{abweichungen}}

Liefere:
1. Konsistenzmatrix fuer Prompts, Skills, Bundle und relevante Services
2. Welche Abweichungen harmlos, kritisch oder latent riskant sind
3. Welche Quelle als Truth gelten soll
4. Kleinsten sicheren Sync-/Bundle-Plan
5. Nachtests fuer jede betroffene Maschine

Regeln:
- Dist-Ordner nicht als primaere Quelle behandeln
- Prompt-Manager-DB und Skills als Quellobjekte betrachten
- Bundle nur aus sauberem Quellstand neu bauen
""",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed curated Safeguard fleet operations prompts into prompt-manager."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without DB writes.")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update prompts when a seed title already exists.",
    )
    return parser.parse_args()


def find_category_id_by_name(name: str) -> int | None:
    with db.get_conn() as conn:
        row = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
        return int(row["id"]) if row else None


def get_or_create_category() -> int:
    category_id = find_category_id_by_name(CATEGORY_NAME)
    if category_id is not None:
        return category_id
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

    if args.dry_run:
        category_id = find_category_id_by_name(CATEGORY_NAME)
        print(f"Category: {CATEGORY_NAME} (id={category_id if category_id is not None else 'missing'})")
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

    category_id = get_or_create_category()

    for prompt in PROMPTS:
        action, prompt_id = seed_prompt(category_id, prompt, args.update_existing)
        print(f"{action}: #{prompt_id} {prompt['title']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
