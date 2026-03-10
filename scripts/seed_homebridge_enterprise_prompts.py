#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db


CATEGORY_NAME = "Maidrax / Homebridge"
CATEGORY_COLOR = "#FF6A3D"
CATEGORY_ICON = "HB"


PROMPTS = [
    {
        "title": "Maidrax Homebridge: Bestandsaufnahme bewerten",
        "description": "Analysiert ein Homebridge-Inventar und priorisiert Instabilitaetsrisiken.",
        "tags": ["maidrax", "homebridge", "audit", "stability"],
        "is_favorite": True,
        "content": """Du bist Senior Platform Engineer fuer eine autorisierte Homebridge-Uebernahme auf einem selbst verwalteten Linux-Host.

Aufgabe:
Analysiere die folgende Bestandsaufnahme und liefere:
1. Eine Executive Summary in hoechstens 5 Saetzen
2. Die 5 wichtigsten Risiken in absteigender Prioritaet
3. Vermutete Instabilitaetsursachen mit Kennzeichnung als Fakt oder Inferenz
4. Sofortmassnahmen ohne Downtime
5. Wartungsfenster-Massnahmen mit Rollback-Hinweis
6. Offene Fragen, die vor Aenderungen geklaert werden muessen
7. Die naechsten 5 read-only Pruefschritte mit exakten Kommandos

Rahmen:
- Keine Annahmen von unautorisiertem Zugriff, Credential-Bypass oder "Kapern"
- Keine pauschalen Plugin-Upgrades
- HomeKit-Identitaet, persist-Daten und accessory cache nicht leichtfertig verwerfen
- Bei Unsicherheit Fakten, Annahmen und Empfehlungen strikt trennen

Bestandsaufnahme:
{{inventar}}
""",
    },
    {
        "title": "Maidrax Homebridge: Stabilisierungsplan entwerfen",
        "description": "Erzeugt einen phasenweisen Stabilisierungs- und Härtungsplan fuer Homebridge.",
        "tags": ["maidrax", "homebridge", "plan", "hardening"],
        "is_favorite": True,
        "content": """Du bist Technical Lead fuer die Stabilisierung einer autorisierten Homebridge-Instanz.

Erstelle einen umsetzbaren Plan fuer dieses Zielbild:
{{zielbild}}

Arbeite auf Basis dieses Inventars:
{{inventar}}

Geplantes Wartungsfenster:
{{wartungsfenster}}

Liefere:
1. Phasenplan von Baseline bis Betriebsuebergabe
2. Pro Phase: Ziel, konkrete Schritte, Risiko, Rollback, Verifikation
3. Reihenfolge der Aenderungen mit Begruendung
4. Welche Punkte sofort, welche spaeter, welche gar nicht angefasst werden sollten
5. Minimalen sicheren ersten Change-Set fuer das naechste Fenster

Rahmen:
- Nur autorisierte Admin-Arbeit
- Ein Risiko-Cluster pro Change-Set
- Keine Sammel-Upgrades ohne Vorqualifikation
- Klare Trennung zwischen read-only Diagnose und schreibenden Aenderungen
""",
    },
    {
        "title": "Maidrax Homebridge: Plugin-Risiken priorisieren",
        "description": "Bewertet Plugin-Sprawl, Ausfallrisiken und sinnvolle Upgrade-Reihenfolgen.",
        "tags": ["maidrax", "homebridge", "plugins", "risk"],
        "is_favorite": False,
        "content": """Du bewertest Plugin-Risiken in einer bestehenden Homebridge-Installation.

Inventar:
{{inventar}}

Bekannte Vorfaelle oder Symptome:
{{vorfaelle}}

Liefere:
1. Plugin-Tabelle mit Klassen: stabil, kritisch, veraltet, unklar, ungenutzt
2. Welche Plugins zuerst isoliert oder genauer untersucht werden sollten
3. Welche Plugins nur mit Snapshot und Wartungsfenster angefasst werden sollten
4. Welche Signale auf Mehrfachinstallationen oder Drift hindeuten
5. Eine sichere Reihenfolge fuer Bereinigung oder Upgrade

Regeln:
- Keine pauschale Empfehlung "alles updaten"
- Begruende jede Priorisierung technisch
- Wenn Informationen fehlen, benenne sie explizit
""",
    },
    {
        "title": "Maidrax Homebridge: Runbook schreiben",
        "description": "Erstellt ein belastbares Betriebs- und Incident-Runbook fuer Homebridge.",
        "tags": ["maidrax", "homebridge", "runbook", "operations"],
        "is_favorite": False,
        "content": """Du erstellst ein knappes, operatives Runbook fuer eine autorisierte Homebridge-Umgebung.

Inventar:
{{inventar}}

Ziel:
{{ziel}}

Das Runbook soll enthalten:
1. Systemueberblick
2. Kritische Dateien und Pfade
3. Start, Stop, Restart, Status und Log-Kommandos
4. Backup- und Restore-Grundschritte
5. Post-Change-Checks
6. Erstreaktion bei Stoerungen
7. Verbote und typische Fehler, die Instabilitaet erzeugen

Form:
- kurz
- betrieblich
- mit exakten Kommandos
- keine Marketing-Sprache
""",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed curated Maidrax/Homebridge stabilization prompts into prompt-manager."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without writing to the database.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update prompts when a seed title already exists.",
    )
    return parser.parse_args()


def get_or_create_category() -> int:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM categories WHERE name=?",
            (CATEGORY_NAME,),
        ).fetchone()
        if row:
            return int(row["id"])

    return db.create_category(CATEGORY_NAME, color=CATEGORY_COLOR, icon=CATEGORY_ICON)


def find_prompt_id_by_title(title: str) -> int | None:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM prompts WHERE title=?",
            (title,),
        ).fetchone()
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
