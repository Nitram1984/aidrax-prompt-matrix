#!/usr/bin/env python3.11
"""
╔══════════════════════════════════════════════════════╗
║          PROMPT MANAGER CLI — Ubuntu Edition         ║
║     KI-Prompt-Verwaltung direkt im Terminal          ║
╚══════════════════════════════════════════════════════╝

Verwendung:
    python3 main.py                  # Interaktives Menü
    python3 main.py list             # Alle Prompts anzeigen
    python3 main.py list --inactive  # Nicht aktivierte Prompts anzeigen
    python3 main.py new              # Neuen Prompt erstellen
    python3 main.py activate <ids>   # Prompt(s) aktivieren
    python3 main.py deactivate <ids> # Prompt(s) deaktivieren
    python3 main.py use <id>         # Prompt an KI senden
    python3 main.py use <id> feld=wert
    python3 main.py chat             # Freier Chat mit KI
    python3 main.py manus-status     # Status des letzten Manus-Tasks
    python3 main.py manus-open       # Manus im Browser oeffnen
    python3 main.py history          # Verlauf anzeigen
    python3 main.py config           # Konfiguration
    python3 main.py version          # Installierte Version anzeigen
"""

import sys
import os
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.rule import Rule
from rich.columns import Columns
from rich import box
from rich.markup import escape

import db
import ai
from prompt_manager_version import __version__

console = Console()

# ─── Farben / Stil ───────────────────────────────────────────────────────────
AIDRAX_BG = "#050611"
AIDRAX_SURFACE = "#090d1d"
AIDRAX_SURFACE_ALT = "#11152c"
AIDRAX_TEXT = "#e9ecff"
AIDRAX_MUTED = "#adc2ff"
AIDRAX_PRIMARY = "#00f7ff"
AIDRAX_SECONDARY = "#ff00ea"
AIDRAX_OK = "#00ff96"
AIDRAX_WARN = "#ffd166"
AIDRAX_DANGER = "#ff6b8a"
AIDRAX_EDGE = "#22304f"

PINK = AIDRAX_SECONDARY
CYAN = AIDRAX_PRIMARY
GREEN = AIDRAX_OK
YELLOW = AIDRAX_WARN
RED = AIDRAX_DANGER
DIM = AIDRAX_MUTED
HEADER = f"bold {AIDRAX_TEXT} on {AIDRAX_SURFACE}"
TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}")
SKIP_SCAN_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "backups",
    "aidrax_backups",
    "docker",
    "docker-volumes",
    ".pnpm-store",
}


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def clear():
    console.clear()


def section_title(title: str, color: str = AIDRAX_PRIMARY) -> str:
    return f"[bold {color}]▣ {escape(title)}[/bold {color}]"


def print_section(title: str, color: str = AIDRAX_PRIMARY):
    console.print(Rule(f"[bold {color}] {escape(title)} [/bold {color}]", style=color))


def metric_card(label: str, value: str, color: str = AIDRAX_PRIMARY, note: str = "") -> Panel:
    body = [
        f"[{AIDRAX_MUTED}]{escape(label)}[/{AIDRAX_MUTED}]",
        f"[bold {color}]{escape(str(value))}[/bold {color}]",
    ]
    if note:
        body.append(f"[{AIDRAX_MUTED}]{escape(note)}[/{AIDRAX_MUTED}]")
    return Panel(
        Group(*body),
        border_style=color,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_menu_cards(options: list[tuple[str, str, str]]) -> Columns:
    chunks = [options[idx:idx + 4] for idx in range(0, len(options), 4)]
    cards: list[Panel] = []
    for chunk in chunks:
        lines = [
            f"[bold {color}]{key}[/bold {color}]  [{AIDRAX_TEXT}]{escape(label)}[/{AIDRAX_TEXT}]"
            for key, label, color in chunk
        ]
        cards.append(
            Panel(
                Group(*lines),
                border_style=AIDRAX_EDGE,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
    return Columns(cards, equal=True, expand=True)


def print_header():
    hero = Group(
        f"[bold {AIDRAX_WARN}]AIDRAX // PROMPT OPS[/bold {AIDRAX_WARN}]",
        f"[bold {AIDRAX_PRIMARY}]PROMPT MATRIX[/bold {AIDRAX_PRIMARY}] [bold {AIDRAX_SECONDARY}]NEON CLI[/bold {AIDRAX_SECONDARY}]",
        f"[{AIDRAX_TEXT}]Prompt-, Skill- und Orchestrierungssteuerung fuer Terminal-Operations[/{AIDRAX_TEXT}]",
        f"[bold {AIDRAX_OK}]● LIVE[/bold {AIDRAX_OK}] [{AIDRAX_MUTED}]Ubuntu Edition | SQLite | Multi-Provider | Manus[/{AIDRAX_MUTED}]",
    )
    console.print(
        Panel(
            hero,
            title=f"[bold {AIDRAX_SECONDARY}]AIDRAX[/bold {AIDRAX_SECONDARY}]",
            subtitle=f"[{AIDRAX_MUTED}]control surface[/{AIDRAX_MUTED}]",
            border_style=AIDRAX_PRIMARY,
            box=box.HEAVY,
            padding=(1, 2),
        )
    )


def print_success(msg: str):
    console.print(f"[bold {AIDRAX_OK}]▲[/bold {AIDRAX_OK}]  {msg}")


def print_error(msg: str):
    console.print(f"[bold {AIDRAX_DANGER}]✘[/bold {AIDRAX_DANGER}]  {msg}")


def print_info(msg: str):
    console.print(f"[bold {AIDRAX_PRIMARY}]ℹ[/bold {AIDRAX_PRIMARY}]  {msg}")


def format_date(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d.%m.%y %H:%M")
    except Exception:
        return date_str or "—"


def mask_secret(value: str, prefix_len: int = 3, suffix_len: int = 4) -> str:
    if not value:
        return "(nicht gesetzt)"
    if len(value) <= prefix_len + suffix_len:
        return "(gesetzt)"
    return f"{value[:prefix_len]}...{value[-suffix_len:]}"


def extract_template_fields(content: str) -> list[str]:
    fields: list[str] = []
    for match in TEMPLATE_PATTERN.finditer(content):
        name = match.group(1)
        if name not in fields:
            fields.append(name)
    return fields


def parse_use_args(args: list[str]) -> tuple[str | None, dict[str, str]]:
    model: str | None = None
    values: dict[str, str] = {}

    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"Ungültige Template-Zuweisung: {arg}")
            values[key] = value
            continue

        if model is None:
            model = arg
            continue

        raise ValueError(
            "Zu viele Argumente. Verwende: main.py use <id> [model] [feld=wert ...]"
        )

    return model, values


def parse_prompt_ids(args: list[str]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()

    for arg in args:
        for match in re.findall(r"\d+", arg):
            prompt_id = int(match)
            if prompt_id in seen:
                continue
            seen.add(prompt_id)
            ids.append(prompt_id)

    if not ids:
        raise ValueError("Keine gueltigen Prompt-IDs erkannt.")

    return ids


def render_template(content: str, provided_values: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    fields = extract_template_fields(content)
    if not fields:
        return content, {}

    values = dict(provided_values or {})

    for field in fields:
        if field in values:
            continue
        label = field.replace("_", " ")
        values[field] = Prompt.ask(f"[bold {AIDRAX_PRIMARY}]{label}[/bold {AIDRAX_PRIMARY}]")

    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), "")

    return TEMPLATE_PATTERN.sub(replace, content), {field: values[field] for field in fields}


def is_orchestrator_prompt(content: str) -> bool:
    markers = [
        "AUFTRAG FUER MANUS",
        "PHASE 1",
    ]
    return all(marker in content for marker in markers)


def extract_orchestrator_query_text(
    rendered_prompt: str,
    resolved_values: dict[str, str] | None = None,
) -> str:
    values = resolved_values or {}
    candidate_keys = [
        "aktuelle_anfrage",
        "anfrage",
        "benutzeranfrage",
        "user_request",
        "query",
        "task",
    ]
    for key in candidate_keys:
        value = values.get(key, "").strip()
        if value:
            return value

    patterns = [
        r"(?:aktuelle anfrage|erste anfrage|benutzer-input)\s*:\s*(.+)",
        r"\[HIER FUEGEN SIE IHRE AKTUELLE ANFRAGE EIN\]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, rendered_prompt, flags=re.I | re.S)
        if match:
            return match.group(1).strip()

    return ""


def extract_labeled_block(text: str, label: str, next_labels: list[str]) -> str | None:
    normalized = text.replace("\r\n", "\n")
    label_pattern = rf"(?:\*\*)?{re.escape(label)}(?:\*\*)?"
    lookaheads = [
        rf"\n\s*(?:[-*]\s*)?(?:\*\*)?{re.escape(next_label)}(?:\*\*)?"
        for next_label in next_labels
    ]
    lookaheads.append(r"\n\s*Ich warte nun auf die")
    lookaheads.append(r"\Z")
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:[-*]\s*)?{label_pattern}\s*(.+?)(?={'|'.join(lookaheads)})",
        re.S,
    )
    match = pattern.search(normalized)
    if not match:
        return None
    return match.group(1).strip()


def extract_phase1_assignments(text: str) -> tuple[str | None, str | None]:
    manus = extract_labeled_block(
        text,
        "AUFTRAG FUER MANUS:",
        [
            "AUFTRAG FUER PERPLEXITY:",
            "Ich warte nun auf die Antworten",
            "Ich warte nun auf die Antwort",
        ],
    )
    perplexity = extract_labeled_block(
        text,
        "AUFTRAG FUER PERPLEXITY:",
        ["Ich warte nun auf die Antworten", "Ich warte nun auf die Antwort"],
    )
    return manus, perplexity


def extract_review_assignments(text: str) -> tuple[str | None, str | None]:
    manus = extract_labeled_block(
        text,
        "UEBERPRUEFUNGSAUFTRAG FUER MANUS:",
        [
            "UEBERPRUEFUNGSAUFTRAG FUER PERPLEXITY:",
            "Ich warte nun auf die Rueckmeldungen",
            "Ich warte nun auf die Rueckmeldung",
        ],
    )
    perplexity = extract_labeled_block(
        text,
        "UEBERPRUEFUNGSAUFTRAG FUER PERPLEXITY:",
        ["Ich warte nun auf die Rueckmeldungen", "Ich warte nun auf die Rueckmeldung"],
    )
    return manus, perplexity


def print_text_panel(title: str, text: str, border_style: str = "cyan"):
    console.print(
        Panel(
            escape(text),
            title=section_title(title, border_style),
            subtitle=f"[{AIDRAX_MUTED}]AIDRAX channel[/{AIDRAX_MUTED}]",
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def is_local_prompt_inventory_query(query: str) -> bool:
    lowered = normalize_query(query)
    scope_markers = [
        "auf dem system",
        "im system",
        "lokal",
        "lokalen",
        "diesem system",
        "auf dem rechner",
        "codex",
        "prompt-manager",
    ]
    prompt_markers = ["prompt", "prompts", "skill", "skills", "agent", "agenten", "agentes", "agents"]
    inventory_markers = [
        "suche",
        "such",
        "finde",
        "finden",
        "zeige",
        "list",
        "auflist",
        "inventar",
        "bestand",
        "aktive",
        "aktiv",
        "vorhanden",
        "installiert",
        "laufend",
        "genutzt",
    ]
    return (
        any(marker in lowered for marker in prompt_markers)
        and any(marker in lowered for marker in inventory_markers)
        and any(marker in lowered for marker in scope_markers)
    )


def is_manus_creation_query(query: str) -> bool:
    lowered = normalize_query(query)
    creation_verbs = [
        "erstellen",
        "erstelle",
        "bauen",
        "baue",
        "entwickeln",
        "entwickle",
        "generieren",
        "generiere",
        "schreiben",
        "schreibe",
        "programmieren",
        "programmiere",
        "konzipieren",
        "konzipiere",
    ]
    creation_targets = [
        "skill",
        "skills",
        "agent",
        "agenten",
        "agents",
        "app",
        "apps",
        "programm",
        "programme",
        "tool",
        "tools",
        "website",
        "webseite",
        "workflow",
        "workflows",
    ]
    return any(verb in lowered for verb in creation_verbs) and any(
        target in lowered for target in creation_targets
    )


def scan_named_files(root: Path, file_names: set[str], limit: int = 200) -> list[Path]:
    matches: list[Path] = []
    if not root.exists():
        return matches

    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_SCAN_DIRS]
        for filename in filenames:
            if filename in file_names:
                matches.append(Path(current_root) / filename)
                if len(matches) >= limit:
                    return matches
    return matches


def format_path_list(paths: list[Path], root: Path | None = None, max_items: int = 12) -> list[str]:
    shown = paths[:max_items]
    labels: list[str] = []
    for path in shown:
        if root:
            try:
                labels.append(str(path.relative_to(root)))
                continue
            except ValueError:
                pass
        labels.append(str(path))
    if len(paths) > max_items:
        labels.append(f"... und {len(paths) - max_items} weitere")
    return labels


def build_local_prompt_inventory_report() -> str:
    prompts = db.list_prompts()
    prompt_lines = [
        (
            f"- #{prompt['id']} {prompt['title']} | Kategorie: {prompt.get('category_name') or '—'}"
            f" | Aktiv: {'ja' if prompt['is_active'] else 'nein'}"
            f" | Favorit: {'ja' if prompt['is_favorite'] else 'nein'}"
            f" | Verwendet: {prompt['use_count']}x"
        )
        for prompt in prompts
    ] or ["- Keine gespeicherten Prompts im prompt-manager."]

    agents_files = scan_named_files(Path("/data2"), {"AGENTS.md"})
    skill_root = Path.home() / ".codex" / "skills"
    skill_files = scan_named_files(skill_root, {"SKILL.md"})

    report_lines = [
        "Lokale Auswertung der aktiven Prompt-Quellen",
        "",
        "Hinweis:",
        "- Es gibt hier keine zentrale betriebssystemweite Liste 'aktiver Prompts'.",
        "- Ich werte als aktiv bzw. relevant die aktuell lokal vorhandenen Prompt-Quellen im prompt-manager- und Codex-Umfeld.",
        "",
        f"Prompt-Manager-Datenbank: {len(prompts)} Eintraege",
        *prompt_lines,
        "",
        f"AGENTS.md-Dateien unter /data2: {len(agents_files)}",
        *(f"- {item}" for item in format_path_list(agents_files, Path('/data2'))),
        "",
        f"Codex-Skills mit SKILL.md unter {skill_root}: {len(skill_files)}",
        *(f"- {item}" for item in format_path_list(skill_files, skill_root)),
    ]
    return "\n".join(report_lines)


def answer_local_orchestrator_query(prompt_id: int, prompt_title: str, query_text: str) -> None:
    report = build_local_prompt_inventory_report()
    print_info("Lokale Systemabfrage erkannt. Beantworte direkt aus dem System ohne Manus.")
    print_text_panel("LOKALE ANTWORT", report, border_style=AIDRAX_OK)
    db.add_history(
        prompt_content=query_text,
        response=report,
        model="local-system",
        prompt_id=prompt_id,
        prompt_title=f"{prompt_title} (local)",
        status="completed",
    )
    db.increment_use_count(prompt_id)


def answer_direct_primary_query(prompt_id: int, prompt_title: str, query_text: str, model: str) -> None:
    provider_label = ai.get_primary_provider_label()
    print_info(
        "Keine lokale Systemabfrage und keine Manus-Build-Anfrage erkannt. "
        f"Antworte direkt ueber {provider_label}."
    )
    answer = ai.chat(
        prompt_content=(
            "Beantworte die folgende Benutzeranfrage direkt, klar und auf Deutsch. "
            "Verwende keine Delegation und keinen Mehrphasen-Workflow.\n\n"
            f"{query_text}"
        ),
        model=model,
        stream=False,
        prompt_id=prompt_id,
        prompt_title=f"{prompt_title} (direct)",
    )
    print_text_panel("DIREKTE ANTWORT", answer, border_style=AIDRAX_SECONDARY)
    db.increment_use_count(prompt_id)


def handle_manus_status_event(event: dict) -> None:
    event_type = event.get("event")
    task_id = event.get("task_id") or event.get("id")
    task_url = event.get("task_url")

    if event_type == "created":
        if task_id:
            db.set_config("last_manus_task_id", str(task_id))
            print_info(f"Manus-Task erstellt: {task_id}")
        if task_url:
            db.set_config("last_manus_task_url", str(task_url))
            console.print(f"[dim]Manus-URL:[/dim] {task_url}")
        return

    if event_type == "status":
        task = event.get("task") or {}
        metadata = task.get("metadata") or {}
        task_url = metadata.get("task_url") or task_url
        if task_url:
            db.set_config("last_manus_task_url", str(task_url))
        if task_id:
            print_info(f"Manus-Status {task_id}: {event.get('status')}")
        return

    if event_type == "completed" and task_id:
        print_success(f"Manus-Task abgeschlossen: {task_id}")
        return

    if event_type == "failed" and task_id:
        print_error(f"Manus-Task fehlgeschlagen: {task_id}")
        return

    if event_type == "timeout" and task_id:
        print_error(f"Manus-Task Zeitlimit erreicht: {task_id}")


def run_orchestrator_workflow(
    prompt_id: int,
    prompt_title: str,
    rendered_prompt: str,
    model: str,
    query_text: str = "",
) -> None:
    normalized_query = query_text.strip()

    if normalized_query and is_local_prompt_inventory_query(normalized_query):
        answer_local_orchestrator_query(prompt_id, prompt_title, normalized_query)
        return

    if normalized_query and not is_manus_creation_query(normalized_query):
        if not ai.has_primary_credentials():
            raise ValueError(
                f"Fuer direkte Antworten fehlt die Konfiguration fuer {ai.get_primary_provider_label()}."
            )
        answer_direct_primary_query(prompt_id, prompt_title, normalized_query, model)
        return

    missing: list[str] = []
    if not ai.has_primary_credentials():
        if ai.get_primary_provider() == "anthropic":
            missing.append("anthropic_api_key")
        else:
            missing.append("openai_api_key")
    if not ai.has_manus_credentials():
        missing.append("manus_api_key")
    if missing:
        raise ValueError(
            "Fuer die automatische Orchestrierung fehlen Konfigurationen: "
            + ", ".join(missing)
        )

    print_info(f"Starte Orchestrator-Phase 1 ueber {ai.get_primary_provider_label()}.")
    phase1 = ai.chat(
        prompt_content=rendered_prompt,
        model=model,
        stream=False,
        prompt_id=prompt_id,
        prompt_title=f"{prompt_title} (phase1)",
    )
    print_text_panel("PHASE 1", phase1, border_style=AIDRAX_SECONDARY)

    manus_assignment, perplexity_assignment = extract_phase1_assignments(phase1)
    use_perplexity = bool(perplexity_assignment and ai.has_perplexity_credentials())

    if not manus_assignment:
        raise ValueError(
            "Die Phase-1-Antwort enthaelt keinen eindeutig parsebaren Auftrag fuer Manus."
        )

    print_info("Sende Auftrag automatisch an Manus.")
    manus_answer = ai.manus_chat(manus_assignment, status_callback=handle_manus_status_event)
    print_text_panel("ANTWORT VON MANUS", manus_answer, border_style=AIDRAX_WARN)

    perplexity_answer = ""
    if use_perplexity:
        print_info("Sende Auftrag automatisch an Perplexity.")
        perplexity_answer = ai.perplexity_chat(perplexity_assignment)
        print_text_panel("ANTWORT VON PERPLEXITY", perplexity_answer, border_style=AIDRAX_OK)

    print_info("Starte Konsolidierung und Ueberpruefungsauftraege.")
    phase2_parts = [
        rendered_prompt,
        f"DEINE PHASE-1-ANTWORT:\n{phase1}",
        f"ANTWORT VON MANUS:\n{manus_answer}",
    ]
    if use_perplexity:
        phase2_parts.append(f"ANTWORT VON PERPLEXITY:\n{perplexity_answer}")
    phase2_parts.append(
        "Setze den beschriebenen Workflow jetzt fort. "
        "Analysiere die vorhandenen Antworten, erstelle die konsolidierte Version "
        "und gib danach die passenden UEBERPRUEFUNGSAUFTRAEGE aus."
    )
    phase2_input = "\n\n".join(phase2_parts)
    phase2 = ai.chat(
        prompt_content=phase2_input,
        model=model,
        stream=False,
        prompt_id=prompt_id,
        prompt_title=f"{prompt_title} (phase2)",
    )
    print_text_panel("PHASE 2", phase2, border_style=AIDRAX_SECONDARY)

    manus_review_assignment, perplexity_review_assignment = extract_review_assignments(phase2)
    use_perplexity_review = bool(perplexity_review_assignment and use_perplexity)

    if not manus_review_assignment:
        raise ValueError(
            "Die Phase-2-Antwort enthaelt keinen eindeutig parsebaren Ueberpruefungsauftrag fuer Manus."
        )

    print_info("Hole Ueberpruefungsfeedback von Manus.")
    manus_review = ai.manus_chat(manus_review_assignment, status_callback=handle_manus_status_event)
    print_text_panel("RUECKMELDUNG VON MANUS", manus_review, border_style=AIDRAX_WARN)

    perplexity_review = ""
    if use_perplexity_review:
        print_info("Hole Ueberpruefungsfeedback von Perplexity.")
        perplexity_review = ai.perplexity_chat(perplexity_review_assignment)
        print_text_panel("RUECKMELDUNG VON PERPLEXITY", perplexity_review, border_style=AIDRAX_OK)

    print_info("Erstelle finale Antwort.")
    final_parts = [
        rendered_prompt,
        f"DEINE PHASE-1-ANTWORT:\n{phase1}",
        f"DEINE PHASE-2-ANTWORT:\n{phase2}",
        f"RUECKMELDUNG VON MANUS:\n{manus_review}",
    ]
    if use_perplexity_review:
        final_parts.append(f"RUECKMELDUNG VON PERPLEXITY:\n{perplexity_review}")
    final_parts.append(
        "Fuehre jetzt Phase 3 aus. "
        "Bewerte die Korrekturen, integriere die relevanten Punkte und gib nur die finale Antwort fuer den Benutzer aus."
    )
    final_input = "\n\n".join(final_parts)
    final_answer = ai.chat(
        prompt_content=final_input,
        model=model,
        stream=False,
        prompt_id=prompt_id,
        prompt_title=f"{prompt_title} (final)",
    )
    print_text_panel("FINALE ANTWORT", final_answer, border_style=AIDRAX_SECONDARY)
    db.increment_use_count(prompt_id)


def get_editor_input(initial: str = "") -> str:
    """Öffnet den Standard-Editor ($EDITOR) für mehrzeilige Eingabe."""
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(initial)
        fname = f.name
    try:
        subprocess.call([editor, fname])
        with open(fname) as f:
            return f.read().strip()
    finally:
        os.unlink(fname)


def pick_category(categories: list[dict], current_id: int | None = None) -> int | None:
    """Interaktive Kategorieauswahl."""
    if not categories:
        console.print("[dim]Keine Kategorien vorhanden. Erstelle zuerst eine Kategorie.[/dim]")
        return None

    console.print(f"\n[bold {AIDRAX_PRIMARY}]Kategorie waehlen:[/bold {AIDRAX_PRIMARY}]")
    console.print(f"  [{AIDRAX_MUTED}]0[/{AIDRAX_MUTED}]  Keine")
    for cat in categories:
        marker = " ◀" if cat["id"] == current_id else ""
        console.print(f"  [{AIDRAX_MUTED}]{cat['id']}[/{AIDRAX_MUTED}]  {cat['name']}{marker}")

    choice = Prompt.ask("ID eingeben", default="0")
    try:
        val = int(choice)
        if val == 0:
            return None
        if any(c["id"] == val for c in categories):
            return val
    except ValueError:
        pass
    return current_id


# ─── Prompt-Liste ─────────────────────────────────────────────────────────────

def cmd_list(
    search: str = "",
    category_id: int | None = None,
    favorites_only: bool = False,
    active_only: bool | None = None,
):
    prompts = db.list_prompts(
        search=search,
        category_id=category_id,
        favorites_only=favorites_only,
        active_only=active_only,
    )
    categories = {c["id"]: c for c in db.list_categories()}

    print_section("PROMPT INDEX", AIDRAX_PRIMARY)

    if not prompts:
        console.print(
            Panel(
                f"[{AIDRAX_MUTED}]Keine Prompts fuer den aktuellen Filter gefunden.[/{AIDRAX_MUTED}]",
                title=section_title("EMPTY STATE", AIDRAX_WARN),
                border_style=AIDRAX_EDGE,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return

    table = Table(
        show_header=True,
        header_style=f"bold {AIDRAX_PRIMARY}",
        border_style=AIDRAX_EDGE,
        box=box.ROUNDED,
        expand=True,
        row_styles=[f"on {AIDRAX_SURFACE}", f"on {AIDRAX_SURFACE_ALT}"],
    )
    table.add_column("ID", style=AIDRAX_MUTED, width=4, justify="right")
    table.add_column("Status", width=8, justify="center")
    table.add_column("Prompt", style=f"bold {AIDRAX_TEXT}", min_width=28)
    table.add_column("Tags", style=AIDRAX_SECONDARY, width=18)
    table.add_column("×", width=4, justify="right", style=AIDRAX_MUTED)
    table.add_column("Geaendert", style=AIDRAX_MUTED, width=14)

    for p in prompts:
        cat = categories.get(p["category_id"])
        cat_name = cat["name"] if cat else "—"
        cat_color = cat.get("color") if cat else AIDRAX_PRIMARY
        tags = json.loads(p["tags"]) if p["tags"] else []
        tags_str = ", ".join(tags[:3]) if tags else "—"
        active = (
            f"[bold {AIDRAX_OK}]● LIVE[/bold {AIDRAX_OK}]"
            if p["is_active"]
            else f"[bold {AIDRAX_DANGER}]○ PAUSE[/bold {AIDRAX_DANGER}]"
        )
        title = f"◆ {p['title']}" if p["is_favorite"] else p["title"]
        prompt_cell = (
            f"[bold {AIDRAX_TEXT}]{escape(title)}[/bold {AIDRAX_TEXT}]\n"
            f"[{cat_color}]{escape(cat_name)}[/{cat_color}]"
        )
        table.add_row(
            str(p["id"]),
            active,
            prompt_cell,
            escape(tags_str),
            str(p["use_count"]),
            format_date(p["updated_at"]),
        )

    console.print(table)
    console.print(f"[{AIDRAX_MUTED}]{len(prompts)} Prompt(s) im Raster[/{AIDRAX_MUTED}]")


# ─── Neuer Prompt ─────────────────────────────────────────────────────────────

def cmd_new():
    print_section("NEUER PROMPT", AIDRAX_SECONDARY)
    categories = db.list_categories()

    title = Prompt.ask(f"[bold {AIDRAX_PRIMARY}]Titel[/bold {AIDRAX_PRIMARY}]")
    if not title.strip():
        print_error("Titel darf nicht leer sein.")
        return

    console.print(
        f"[bold {AIDRAX_PRIMARY}]Inhalt[/bold {AIDRAX_PRIMARY}] "
        f"[{AIDRAX_MUTED}](Editor oeffnet sich...)[/{AIDRAX_MUTED}]"
    )
    input("  → Enter drücken zum Öffnen des Editors")
    content = get_editor_input()
    if not content.strip():
        print_error("Inhalt darf nicht leer sein.")
        return

    description = Prompt.ask(
        f"[bold {AIDRAX_PRIMARY}]Beschreibung[/bold {AIDRAX_PRIMARY}] "
        f"[{AIDRAX_MUTED}](optional)[/{AIDRAX_MUTED}]",
        default="",
    )
    category_id = pick_category(categories)

    # Tags
    tags_input = Prompt.ask(
        f"[bold {AIDRAX_PRIMARY}]Tags[/bold {AIDRAX_PRIMARY}] "
        f"[{AIDRAX_MUTED}](kommagetrennt, optional)[/{AIDRAX_MUTED}]",
        default="",
    )
    tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]

    is_favorite = Confirm.ask(f"[bold {AIDRAX_PRIMARY}]Als Favorit markieren?[/bold {AIDRAX_PRIMARY}]", default=False)

    # KI-Vorschläge
    if Confirm.ask(
        f"[bold {AIDRAX_PRIMARY}]KI-Vorschlaege fuer Metadaten generieren?[/bold {AIDRAX_PRIMARY}]",
        default=True,
    ):
        with console.status(f"[{AIDRAX_PRIMARY}]Analysiere Prompt...[/{AIDRAX_PRIMARY}]"):
            suggestions = ai.suggest_metadata(content)
        if suggestions:
            if not title.strip() and suggestions.get("title"):
                title = suggestions["title"]
                print_info(f"KI-Titel: {title}")
            if not description and suggestions.get("description"):
                description = suggestions["description"]
                print_info(f"KI-Beschreibung: {description}")
            if not tags and suggestions.get("tags"):
                tags = suggestions["tags"]
                print_info(f"KI-Tags: {', '.join(tags)}")
            # Kategorie vorschlagen
            if not category_id and suggestions.get("category"):
                cat_name = suggestions["category"]
                existing = next((c for c in categories if c["name"].lower() == cat_name.lower()), None)
                if existing:
                    category_id = existing["id"]
                    print_info(f"KI-Kategorie: {existing['name']}")
                elif Confirm.ask(f"Kategorie '{cat_name}' erstellen?", default=True):
                    category_id = db.create_category(cat_name)
                    categories = db.list_categories()
                    print_success(f"Kategorie '{cat_name}' erstellt.")

    prompt_id = db.create_prompt(
        title=title,
        content=content,
        description=description,
        category_id=category_id,
        tags=tags,
        is_favorite=is_favorite,
    )
    print_success(f"Prompt #{prompt_id} '[bold]{escape(title)}[/bold]' gespeichert.")

    if Confirm.ask("Prompt jetzt an KI senden?", default=False):
        cmd_use(prompt_id)


# ─── Prompt anzeigen ──────────────────────────────────────────────────────────

def cmd_show(prompt_id: int):
    p = db.get_prompt(prompt_id)
    if not p:
        print_error(f"Prompt #{prompt_id} nicht gefunden.")
        return

    tags = json.loads(p["tags"]) if p["tags"] else []
    cat_name = p.get("category_name") or "—"
    cat_color = p.get("category_color") or AIDRAX_PRIMARY
    template_fields = extract_template_fields(p["content"])

    print_section(f"PROMPT DOSSIER // #{p['id']}", cat_color)
    console.print(
        Columns(
            [
                metric_card("STATUS", "LIVE" if p["is_active"] else "PAUSE", AIDRAX_OK if p["is_active"] else AIDRAX_DANGER, f"{p['use_count']}x genutzt"),
                metric_card("KATEGORIE", cat_name, cat_color, ", ".join(tags[:2]) if tags else "ohne tags"),
                metric_card("TEMPLATE", str(len(template_fields)), AIDRAX_SECONDARY, "Platzhalter im Prompt"),
            ],
            equal=True,
            expand=True,
        )
    )

    console.print(
        Panel(
            Group(
                f"[bold {AIDRAX_TEXT}]{escape(p['title'])}[/bold {AIDRAX_TEXT}]",
                "",
                f"[{AIDRAX_MUTED}]Kategorie:[/{AIDRAX_MUTED}] [{cat_color}]{escape(cat_name)}[/{cat_color}]   "
                f"[{AIDRAX_MUTED}]Aktiv:[/{AIDRAX_MUTED}] {'ja' if p['is_active'] else 'nein'}   "
                f"[{AIDRAX_MUTED}]Tags:[/{AIDRAX_MUTED}] [{AIDRAX_SECONDARY}]{escape(', '.join(tags) or '—')}[/{AIDRAX_SECONDARY}]   "
                f"[{AIDRAX_MUTED}]Erstellt:[/{AIDRAX_MUTED}] {format_date(p['created_at'])}",
            ),
            title=section_title(f"PROMPT #{p['id']}", cat_color),
            border_style=cat_color,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )

    if p.get("description"):
        console.print(f"[italic {AIDRAX_MUTED}]{escape(p['description'])}[/italic {AIDRAX_MUTED}]\n")

    if template_fields:
        console.print(
            f"[{AIDRAX_MUTED}]Template-Felder:[/{AIDRAX_MUTED}] [{AIDRAX_SECONDARY}]{', '.join(template_fields)}[/{AIDRAX_SECONDARY}]\n"
        )

    console.print(
        Panel(
            escape(p["content"]),
            title=section_title("INHALT", AIDRAX_PRIMARY),
            border_style=AIDRAX_EDGE,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


# ─── Prompt bearbeiten ────────────────────────────────────────────────────────

def cmd_edit(prompt_id: int):
    p = db.get_prompt(prompt_id)
    if not p:
        print_error(f"Prompt #{prompt_id} nicht gefunden.")
        return

    print_section(f"BEARBEITEN // #{prompt_id}", AIDRAX_SECONDARY)
    categories = db.list_categories()

    title = Prompt.ask(f"[bold {AIDRAX_PRIMARY}]Titel[/bold {AIDRAX_PRIMARY}]", default=p["title"])

    console.print(
        f"[bold {AIDRAX_PRIMARY}]Inhalt[/bold {AIDRAX_PRIMARY}] "
        f"[{AIDRAX_MUTED}](aktuell: {len(p['content'])} Zeichen)[/{AIDRAX_MUTED}]"
    )
    if Confirm.ask("Inhalt im Editor bearbeiten?", default=True):
        content = get_editor_input(p["content"])
    else:
        content = p["content"]

    description = Prompt.ask(
        f"[bold {AIDRAX_PRIMARY}]Beschreibung[/bold {AIDRAX_PRIMARY}]",
        default=p.get("description") or "",
    )
    category_id = pick_category(categories, current_id=p.get("category_id"))

    tags_current = json.loads(p["tags"]) if p["tags"] else []
    tags_input = Prompt.ask(
        f"[bold {AIDRAX_PRIMARY}]Tags[/bold {AIDRAX_PRIMARY}]",
        default=", ".join(tags_current),
    )
    tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]

    is_active = Confirm.ask(f"[bold {AIDRAX_PRIMARY}]Aktiv?[/bold {AIDRAX_PRIMARY}]", default=bool(p["is_active"]))
    is_favorite = Confirm.ask(f"[bold {AIDRAX_PRIMARY}]Favorit?[/bold {AIDRAX_PRIMARY}]", default=bool(p["is_favorite"]))

    db.update_prompt(
        prompt_id,
        title=title,
        content=content,
        description=description,
        category_id=category_id,
        tags=tags,
        is_active=is_active,
        is_favorite=is_favorite,
    )
    print_success(f"Prompt #{prompt_id} aktualisiert.")


def cmd_set_active(prompt_ids: list[int], is_active: bool) -> None:
    prompts: list[dict] = []
    missing: list[int] = []

    for prompt_id in prompt_ids:
        prompt = db.get_prompt(prompt_id)
        if prompt:
            prompts.append(prompt)
        else:
            missing.append(prompt_id)

    if missing:
        print_error(
            f"Prompt(s) nicht gefunden: {', '.join(f'#{prompt_id}' for prompt_id in missing)}"
        )
        return

    db.set_prompt_active(prompt_ids, is_active=is_active)
    action = "aktiviert" if is_active else "deaktiviert"
    print_success(f"{len(prompts)} Prompt(s) {action}.")
    for prompt in prompts:
        console.print(f"[{AIDRAX_MUTED}]- #{prompt['id']} {escape(prompt['title'])}[/{AIDRAX_MUTED}]")


# ─── Prompt löschen ───────────────────────────────────────────────────────────

def cmd_delete(prompt_id: int):
    p = db.get_prompt(prompt_id)
    if not p:
        print_error(f"Prompt #{prompt_id} nicht gefunden.")
        return
    if Confirm.ask(f"[red]Prompt #{prompt_id} '{escape(p['title'])}' wirklich löschen?[/red]", default=False):
        db.delete_prompt(prompt_id)
        print_success("Prompt gelöscht.")


# ─── Prompt an KI senden ──────────────────────────────────────────────────────

def cmd_use(prompt_id: int, model: str | None = None, template_values: dict[str, str] | None = None):
    p = db.get_prompt(prompt_id)
    if not p:
        print_error(f"Prompt #{prompt_id} nicht gefunden.")
        return

    cmd_show(prompt_id)
    print_section("KI-ANTWORT", AIDRAX_SECONDARY)

    provider_label = ai.get_primary_provider_label()
    used_model = model or ai.get_default_chat_model()
    console.print(f"[{AIDRAX_MUTED}]Provider:[/{AIDRAX_MUTED}] [{AIDRAX_PRIMARY}]{provider_label}[/{AIDRAX_PRIMARY}]")
    console.print(f"[{AIDRAX_MUTED}]Modell:[/{AIDRAX_MUTED}] [{AIDRAX_SECONDARY}]{used_model}[/{AIDRAX_SECONDARY}]\n")

    try:
        rendered_prompt, resolved_values = render_template(p["content"], template_values)
        query_text = extract_orchestrator_query_text(rendered_prompt, resolved_values)
        if resolved_values:
            console.print(
                f"[{AIDRAX_MUTED}]Template-Werte:[/{AIDRAX_MUTED}] "
                f"[{AIDRAX_SECONDARY}]{', '.join(f'{key}={value}' for key, value in resolved_values.items())}[/{AIDRAX_SECONDARY}]\n"
            )

        if is_orchestrator_prompt(p["content"]):
            run_orchestrator_workflow(
                prompt_id=prompt_id,
                prompt_title=p["title"],
                rendered_prompt=rendered_prompt,
                model=used_model,
                query_text=query_text,
            )
            return

        ai.chat(
            prompt_content=rendered_prompt,
            model=used_model,
            stream=True,
            prompt_id=prompt_id,
            prompt_title=p["title"],
        )
        db.increment_use_count(prompt_id)
    except (ValueError, ConnectionError) as e:
        print_error(str(e))
    except TimeoutError as e:
        print_error(str(e))


# ─── Freier Chat ──────────────────────────────────────────────────────────────

def cmd_chat():
    print_section("FREIER KI-CHAT", AIDRAX_SECONDARY)
    print_info("Tippe 'exit' oder drücke Ctrl+C zum Beenden.")
    print_info("Tippe 'clear' zum Leeren des Bildschirms.")
    print_info("Tippe 'model <name>' zum Wechseln des Modells.")

    model = ai.get_default_chat_model()
    console.print(f"[{AIDRAX_MUTED}]Aktiver Provider:[/{AIDRAX_MUTED}] [{AIDRAX_PRIMARY}]{ai.get_primary_provider_label()}[/{AIDRAX_PRIMARY}]")
    console.print(f"[{AIDRAX_MUTED}]Aktives Modell:[/{AIDRAX_MUTED}] [{AIDRAX_SECONDARY}]{model}[/{AIDRAX_SECONDARY}]\n")

    while True:
        try:
            user_input = Prompt.ask(f"[bold {AIDRAX_SECONDARY}]Du[/bold {AIDRAX_SECONDARY}]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Chat beendet.[/dim]")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            break
        if user_input.lower() == "clear":
            clear()
            continue
        if user_input.lower().startswith("model "):
            model = user_input[6:].strip()
            print_info(f"Modell gewechselt zu: {model}")
            continue
        if not user_input.strip():
            continue

        console.print(f"[bold {AIDRAX_PRIMARY}]KI[/bold {AIDRAX_PRIMARY}]  ", end="")
        try:
            ai.chat(prompt_content=user_input, model=model, stream=True)
        except (ValueError, ConnectionError) as e:
            print_error(str(e))
        console.print()


# ─── Verlauf ──────────────────────────────────────────────────────────────────

def cmd_history(search: str = "", limit: int = 20):
    entries = db.list_history(search=search, limit=limit)

    print_section("VERLAUF", AIDRAX_PRIMARY)

    if not entries:
        console.print(
            Panel(
                f"[{AIDRAX_MUTED}]Noch keine Verlaufseintraege vorhanden.[/{AIDRAX_MUTED}]",
                title=section_title("EMPTY STATE", AIDRAX_WARN),
                border_style=AIDRAX_EDGE,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return

    for entry in entries:
        status_color = AIDRAX_OK if entry["status"] == "completed" else AIDRAX_DANGER
        console.print(
            Panel(
                Group(
                    f"[bold {AIDRAX_TEXT}]{escape(entry['prompt_content'][:120])}{'...' if len(entry['prompt_content']) > 120 else ''}[/bold {AIDRAX_TEXT}]",
                    "",
                    f"[{AIDRAX_PRIMARY}]Antwort:[/{AIDRAX_PRIMARY}] {escape((entry.get('response') or '')[:200])}{'...' if len(entry.get('response') or '') > 200 else ''}",
                ),
                title=section_title(
                    f"#{entry['id']} // {format_date(entry['created_at'])} // {entry['status']} // {entry['model']}",
                    status_color,
                ),
                subtitle=(
                    f"[{AIDRAX_MUTED}]{entry['tokens_used']} tokens[/{AIDRAX_MUTED}]"
                    if entry.get("tokens_used")
                    else f"[{AIDRAX_MUTED}]ohne token-metrik[/{AIDRAX_MUTED}]"
                ),
                border_style=AIDRAX_EDGE,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    console.print(f"[{AIDRAX_MUTED}]{len(entries)} Eintraege angezeigt[/{AIDRAX_MUTED}]")


# ─── Kategorien ───────────────────────────────────────────────────────────────

def cmd_categories():
    while True:
        print_section("KATEGORIEN", AIDRAX_PRIMARY)
        categories = db.list_categories()

        if categories:
            table = Table(
                show_header=True,
                header_style=f"bold {AIDRAX_PRIMARY}",
                box=box.ROUNDED,
                border_style=AIDRAX_EDGE,
                row_styles=[f"on {AIDRAX_SURFACE}", f"on {AIDRAX_SURFACE_ALT}"],
            )
            table.add_column("ID", style=AIDRAX_MUTED, width=4)
            table.add_column("Name", style=f"bold {AIDRAX_TEXT}")
            table.add_column("Farbe", width=10)
            for cat in categories:
                table.add_row(str(cat["id"]), cat["name"], f"[{cat['color']}]■ {cat['color']}[/{cat['color']}]")
            console.print(table)
        else:
            console.print(f"[{AIDRAX_MUTED}]Keine Kategorien vorhanden.[/{AIDRAX_MUTED}]")

        console.print(f"\n[bold {AIDRAX_PRIMARY}]Aktionen:[/bold {AIDRAX_PRIMARY}]")
        console.print(f"  [bold {AIDRAX_OK}]n[/bold {AIDRAX_OK}]  Neue Kategorie")
        console.print(f"  [bold {AIDRAX_DANGER}]d[/bold {AIDRAX_DANGER}]  Kategorie loeschen")
        console.print(f"  [{AIDRAX_MUTED}]q[/{AIDRAX_MUTED}]  Zurueck")

        choice = Prompt.ask("Aktion").strip().lower()

        if choice == "q":
            break
        elif choice == "n":
            name = Prompt.ask("Name")
            if not name.strip():
                continue
            color = Prompt.ask("Farbe (Hex)", default="#00FFFF")
            db.create_category(name.strip(), color)
            print_success(f"Kategorie '{name}' erstellt.")
        elif choice == "d":
            if not categories:
                continue
            cat_id = IntPrompt.ask("ID der zu löschenden Kategorie")
            if Confirm.ask(f"Kategorie #{cat_id} wirklich löschen?", default=False):
                db.delete_category(cat_id)
                print_success("Kategorie gelöscht.")


# ─── Konfiguration ────────────────────────────────────────────────────────────

def cmd_config():
    print_section("KONFIGURATION", AIDRAX_SECONDARY)

    current_provider = db.get_config("primary_provider") or "openai"
    current_key = db.get_config("openai_api_key")
    current_model = db.get_config("default_model") or "gpt-4o-mini"
    current_url = db.get_config("api_base_url") or "https://api.openai.com/v1"
    current_anthropic_key = db.get_config("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    current_anthropic_model = db.get_config("anthropic_model") or "claude-sonnet-4-5"
    current_anthropic_url = db.get_config("anthropic_api_url") or "https://api.anthropic.com/v1"
    current_manus_key = db.get_config("manus_api_key") or os.environ.get("MANUS_API_KEY", "")
    current_manus_model = db.get_config("manus_model") or "manus-1.6-lite"
    last_manus_task_id = db.get_config("last_manus_task_id")

    console.print(
        Columns(
            [
                metric_card("PROVIDER", current_provider, AIDRAX_PRIMARY, current_model),
                metric_card("CLAUDE", mask_secret(current_anthropic_key, prefix_len=2), AIDRAX_WARN, current_anthropic_model),
                metric_card("MANUS", mask_secret(current_manus_key, prefix_len=2), AIDRAX_SECONDARY, current_manus_model),
            ],
            equal=True,
            expand=True,
        )
    )
    console.print(
        Panel(
            Group(
                f"[{AIDRAX_MUTED}]OpenAI Key:[/{AIDRAX_MUTED}] {mask_secret(current_key)}",
                f"[{AIDRAX_MUTED}]OpenAI API-URL:[/{AIDRAX_MUTED}] {current_url}",
                f"[{AIDRAX_MUTED}]Claude API-URL:[/{AIDRAX_MUTED}] {current_anthropic_url}",
                f"[{AIDRAX_MUTED}]Letzter Manus-Task:[/{AIDRAX_MUTED}] {last_manus_task_id or '—'}",
            ),
            title=section_title("SYSTEM LINKS", AIDRAX_PRIMARY),
            border_style=AIDRAX_EDGE,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()

    if Confirm.ask("Primaeren Provider aendern?", default=False):
        provider = Prompt.ask("Provider", default=current_provider)
        provider = ai._normalize_provider(provider)
        db.set_config("primary_provider", provider)
        print_success(f"Primaerer Provider auf '{provider}' gesetzt.")

    if Confirm.ask("OpenAI API-Key ändern?", default=False):
        key = Prompt.ask("OpenAI API-Key", password=True)
        if key.strip():
            db.set_config("openai_api_key", key.strip())
            print_success("API-Key gespeichert.")

    if Confirm.ask("OpenAI-Modell ändern?", default=False):
        model = Prompt.ask("Modell eingeben", default=current_model)
        db.set_config("default_model", model.strip())
        print_success(f"Modell auf '{model}' gesetzt.")

    if Confirm.ask("OpenAI API-URL ändern? (für Ollama/lokale Modelle)", default=False):
        url = Prompt.ask("API-Basis-URL", default=current_url)
        db.set_config("api_base_url", url.strip())
        print_success("API-URL gespeichert.")

    if Confirm.ask("Claude API-Key aendern?", default=False):
        key = Prompt.ask("Anthropic API-Key", password=True)
        if key.strip():
            db.set_config("anthropic_api_key", key.strip())
            print_success("Claude API-Key gespeichert.")

    if Confirm.ask("Claude-Modell aendern?", default=False):
        model = Prompt.ask("Claude-Modell", default=current_anthropic_model)
        db.set_config("anthropic_model", model.strip())
        print_success(f"Claude-Modell auf '{model}' gesetzt.")

    if Confirm.ask("Claude API-URL aendern?", default=False):
        url = Prompt.ask("Claude API-Basis-URL", default=current_anthropic_url)
        db.set_config("anthropic_api_url", url.strip())
        print_success("Claude API-URL gespeichert.")

    if Confirm.ask("Manus API-Key ändern?", default=False):
        key = Prompt.ask("Manus API-Key", password=True)
        if key.strip():
            db.set_config("manus_api_key", key.strip())
            print_success("Manus API-Key gespeichert.")

    if Confirm.ask("Manus-Modell ändern?", default=False):
        model = Prompt.ask("Manus-Agent-Profile", default=current_manus_model)
        db.set_config("manus_model", model.strip())
        print_success(f"Manus-Modell auf '{model}' gesetzt.")


def cmd_manus_status(task_id: str | None = None):
    resolved_task_id = task_id or db.get_config("last_manus_task_id")
    if not resolved_task_id:
        print_error("Kein Manus-Task bekannt. Fuehre zuerst einen Manus-Lauf aus oder uebergib eine Task-ID.")
        return

    try:
        task = ai.manus_get_task(resolved_task_id)
    except (ValueError, ConnectionError, LookupError) as e:
        print_error(str(e))
        return

    metadata = task.get("metadata") or {}
    task_url = metadata.get("task_url") or db.get_config("last_manus_task_url")
    if task_url:
        db.set_config("last_manus_task_url", task_url)

    lines = [
        f"Task-ID: {resolved_task_id}",
        f"Status: {task.get('status') or 'unbekannt'}",
        f"Titel: {metadata.get('task_title') or task.get('task_title') or '—'}",
        f"Modell: {task.get('model') or '—'}",
        f"URL: {task_url or '—'}",
    ]
    print_text_panel("MANUS STATUS", "\n".join(lines), border_style=AIDRAX_WARN)

    output_preview = ""
    outputs = task.get("output") or []
    if outputs:
        output_preview = ai._extract_manus_output_text(task)
    elif task.get("error"):
        output_preview = str(task.get("error"))

    if output_preview:
        print_text_panel("MANUS AUSGABE", output_preview[:4000], border_style=AIDRAX_EDGE)


def cmd_manus_open(task_id: str | None = None):
    url = ""
    if task_id:
        try:
            task = ai.manus_get_task(task_id)
            metadata = task.get("metadata") or {}
            url = metadata.get("task_url") or ""
            if url:
                db.set_config("last_manus_task_url", url)
                db.set_config("last_manus_task_id", task_id)
        except (ValueError, ConnectionError, LookupError) as e:
            print_error(str(e))
            return

    if not url:
        url = db.get_config("last_manus_task_url") or "https://manus.im"

    if not shutil.which("xdg-open"):
        print_error("xdg-open wurde nicht gefunden.")
        return

    print_info(f"Oeffne Manus im Browser: {url}")
    subprocess.run(["xdg-open", url], check=False)


# ─── Hauptmenü ────────────────────────────────────────────────────────────────

def interactive_menu():
    while True:
        clear()
        print_header()

        prompts = db.list_prompts()
        categories = db.list_categories()
        history = db.list_history(limit=1)

        console.print(
            Columns(
                [
                    metric_card("PROMPTS", str(len(prompts)), AIDRAX_PRIMARY, "aktive Bibliothek"),
                    metric_card("KATEGORIEN", str(len(categories)), AIDRAX_WARN, "Design-Slots"),
                    metric_card("VERLAUF", str(len(db.list_history())), AIDRAX_SECONDARY, "Operations-Spur"),
                ],
                equal=True,
                expand=True,
            )
        )
        if history:
            last_entry = history[0]
            console.print(
                Panel(
                    f"[{AIDRAX_MUTED}]Letzte Aktivitaet:[/{AIDRAX_MUTED}] "
                    f"[{AIDRAX_TEXT}]{escape((last_entry.get('prompt_title') or last_entry.get('prompt_content') or '')[:96])}[/{AIDRAX_TEXT}]",
                    title=section_title("RECENT SIGNAL", AIDRAX_OK),
                    border_style=AIDRAX_EDGE,
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

        print_section("MENUE", AIDRAX_PRIMARY)
        options = [
            ("1", "Alle Prompts anzeigen",     CYAN),
            ("2", "Neuen Prompt erstellen",     GREEN),
            ("3", "Prompt anzeigen",            DIM),
            ("4", "Prompt bearbeiten",          DIM),
            ("5", "Prompt löschen",             RED),
            ("6", "Prompt an KI senden",        PINK),
            ("7", "Freier KI-Chat",             PINK),
            ("8", "Verlauf anzeigen",           DIM),
            ("9", "Kategorien verwalten",       CYAN),
            ("c", "Konfiguration",              YELLOW),
            ("s", "Suchen",                     DIM),
            ("q", "Beenden",                    DIM),
        ]
        console.print(render_menu_cards(options))

        console.print()
        choice = Prompt.ask(f"[bold {AIDRAX_SECONDARY}]Auswahl[/bold {AIDRAX_SECONDARY}]").strip().lower()

        if choice == "q":
            console.print(f"[{AIDRAX_MUTED}]AIDRAX Prompt Matrix offline.[/{AIDRAX_MUTED}]")
            break

        elif choice == "1":
            clear()
            print_header()
            cmd_list()
            input("\n  → Enter zum Fortfahren")

        elif choice == "2":
            clear()
            print_header()
            cmd_new()
            input("\n  → Enter zum Fortfahren")

        elif choice == "3":
            clear()
            cmd_list()
            try:
                pid = IntPrompt.ask("Prompt-ID")
                cmd_show(pid)
            except Exception:
                pass
            input("\n  → Enter zum Fortfahren")

        elif choice == "4":
            clear()
            cmd_list()
            try:
                pid = IntPrompt.ask("Prompt-ID")
                cmd_edit(pid)
            except Exception:
                pass
            input("\n  → Enter zum Fortfahren")

        elif choice == "5":
            clear()
            cmd_list()
            try:
                pid = IntPrompt.ask("Prompt-ID")
                cmd_delete(pid)
            except Exception:
                pass
            input("\n  → Enter zum Fortfahren")

        elif choice == "6":
            clear()
            cmd_list()
            try:
                pid = IntPrompt.ask("Prompt-ID")
                clear()
                cmd_use(pid)
            except Exception:
                pass
            input("\n  → Enter zum Fortfahren")

        elif choice == "7":
            clear()
            cmd_chat()
            input("\n  → Enter zum Fortfahren")

        elif choice == "8":
            clear()
            print_header()
            search = Prompt.ask("[dim]Suche im Verlauf (leer = alle)[/dim]", default="")
            cmd_history(search=search)
            input("\n  → Enter zum Fortfahren")

        elif choice == "9":
            clear()
            cmd_categories()

        elif choice == "c":
            clear()
            cmd_config()
            input("\n  → Enter zum Fortfahren")

        elif choice == "s":
            clear()
            search = Prompt.ask(f"[bold {AIDRAX_PRIMARY}]Suchbegriff[/bold {AIDRAX_PRIMARY}]")
            cmd_list(search=search)
            input("\n  → Enter zum Fortfahren")

        else:
            print_error("Ungültige Auswahl.")
            import time; time.sleep(1)


# ─── CLI-Einstiegspunkt ───────────────────────────────────────────────────────

def main():
    db.init_db()

    args = sys.argv[1:]

    if not args:
        interactive_menu()
        return

    cmd = args[0].lower()

    if cmd == "list":
        search_terms: list[str] = []
        active_only: bool | None = None

        for arg in args[1:]:
            if arg == "--active":
                active_only = True
            elif arg == "--inactive":
                active_only = False
            else:
                search_terms.append(arg)

        cmd_list(search=" ".join(search_terms), active_only=active_only)

    elif cmd == "list-active":
        cmd_list(active_only=True)

    elif cmd == "list-inactive":
        cmd_list(active_only=False)

    elif cmd == "new":
        cmd_new()

    elif cmd == "activate":
        if len(args) < 2:
            print_error("Verwendung: main.py activate <id ...>")
            sys.exit(1)
        try:
            prompt_ids = parse_prompt_ids(args[1:])
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        cmd_set_active(prompt_ids, is_active=True)

    elif cmd == "deactivate":
        if len(args) < 2:
            print_error("Verwendung: main.py deactivate <id ...>")
            sys.exit(1)
        try:
            prompt_ids = parse_prompt_ids(args[1:])
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        cmd_set_active(prompt_ids, is_active=False)

    elif cmd == "show":
        if len(args) < 2:
            print_error("Verwendung: main.py show <id>")
            sys.exit(1)
        cmd_show(int(args[1]))

    elif cmd == "edit":
        if len(args) < 2:
            print_error("Verwendung: main.py edit <id>")
            sys.exit(1)
        cmd_edit(int(args[1]))

    elif cmd == "delete":
        if len(args) < 2:
            print_error("Verwendung: main.py delete <id>")
            sys.exit(1)
        cmd_delete(int(args[1]))

    elif cmd == "use":
        if len(args) < 2:
            print_error("Verwendung: main.py use <id> [model] [feld=wert ...]")
            sys.exit(1)
        try:
            model, template_values = parse_use_args(args[2:])
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        cmd_use(int(args[1]), model=model, template_values=template_values)

    elif cmd == "chat":
        cmd_chat()

    elif cmd == "history":
        search = args[1] if len(args) > 1 else ""
        cmd_history(search=search)

    elif cmd == "categories":
        cmd_categories()

    elif cmd == "config":
        cmd_config()

    elif cmd == "manus-status":
        task_id = args[1] if len(args) > 1 else None
        cmd_manus_status(task_id=task_id)

    elif cmd == "manus-open":
        task_id = args[1] if len(args) > 1 else None
        cmd_manus_open(task_id=task_id)

    elif cmd in ("version", "--version", "-V"):
        console.print(__version__)

    elif cmd in ("help", "--help", "-h"):
        console.print(__doc__)

    else:
        print_error(f"Unbekannter Befehl: {cmd}")
        console.print("[dim]Verwende 'help' für eine Übersicht.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
