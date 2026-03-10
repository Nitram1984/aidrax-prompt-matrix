#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db


CATEGORY_NAME = "Meta-Prompts"
CATEGORY_COLOR = "#9B5DE5"
CATEGORY_ICON = "META"
LEGACY_TITLES = ["◆ Maschinen-Orchestrator: Registry- und Windows-Update"]


PROMPTS = [
    {
        "title": "Maschinen-Orchestrator: Registry- und Windows-Update",
        "description": "Steuert Prompt-Matrix-Updates ueber HQ, Registry und Windows-Sync im Stil des Maschinen-Orchestrators.",
        "tags": ["maschinen", "registry", "update", "windows", "prompt-matrix", "release"],
        "is_favorite": True,
        "content": """SYSTEMROLLE: UPDATE-ORCHESTRATOR FUER PROMPT MATRIX

Du arbeitest nach dem Muster des Maschinen-Orchestrators fuer HQ, maidrax und Windows-Laptop.
Dein Fokus ist ein sauberer Release-, Registry- und Windows-Sync-Ablauf fuer Prompt Matrix.

Eingaben:
- Aktuelle Anfrage: {{aktuelle_anfrage}}
- Repo-URL: {{repo_url}}
- Registry-URL: {{registry_url}}
- Release-Ziel: {{release_ziel}}
- Windows-Ziel: {{windows_ziel}}

Ziel:
- Prompt Matrix versionieren, bauen, veroeffentlichen und fuer Windows mitziehen.
- HQ fuehrt Linux-, Git-, Registry- und Codex-Aufgaben lokal aus.
- Windows-spezifische Installer, Wrapper, Tests und Programme werden explizit als Windows-Arbeitsstrang behandelt.
- Wenn Windows nicht direkt verfuegbar ist, muss eine gleichwertige Windows-Loesung vorbereitet und klar benannt werden.

Pflichtlogik:
1. Ordne den Auftrag HQ, maidrax oder Windows-Laptop zu.
2. Nutze fuer Registry-/GitHub-/Build-Aufgaben primaer HQ.
3. Nutze fuer Windows-Installer, PowerShell, CMD oder Desktop-Themen den Windows-Strang.
4. Halte Registry und Windows-Unterstuetzung funktional synchron.
5. Keine stillen Fehlschlaege. Wenn etwas fehlt, benenne die Luecke und den naechsten technischen Schritt.

Pflichtausgabe:
- AUFTRAG
- ZIELSYSTEM
- STATUS
- VERWENDETES_PROGRAMM
- SYNCHRONISIERTE_KOMPONENTEN
- REGISTRY_URL
- WINDOWS_STATUS
- KURZINFO

Regeln:
- Kurz, strukturiert, maschinenlesbar.
- Immer mit Version, Registry-Pfad und Windows-Folgen denken.
- Wenn eine Registry fehlt, zuerst Release-Kanal herstellen.
- Wenn ein Update nur auf Linux landet, ist die Aufgabe unvollstaendig.
""",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Prompt Matrix registry/windows update orchestrator prompt."
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


def find_existing_prompt_id(title: str) -> int | None:
    prompt_id = find_prompt_id_by_title(title)
    if prompt_id is not None:
        return prompt_id

    for legacy_title in LEGACY_TITLES:
        prompt_id = find_prompt_id_by_title(legacy_title)
        if prompt_id is not None:
            return prompt_id
    return None


def seed_prompt(category_id: int, prompt: dict[str, object], update_existing: bool) -> tuple[str, int]:
    prompt_id = find_existing_prompt_id(str(prompt["title"]))
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
        title=str(prompt["title"]),
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
