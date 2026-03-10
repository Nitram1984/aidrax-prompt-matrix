# PROMPT MANAGER CLI — Ubuntu Edition

Ein interaktives Terminal-Tool zur Verwaltung und Nutzung von KI-Prompts direkt im Ubuntu-Terminal.

---

## Funktionen

- **Prompt-Bibliothek** — Prompts erstellen, bearbeiten, löschen und durchsuchen
- **Aktivierungsstatus** — Prompts aktivieren, deaktivieren und nach aktiv/inaktiv filtern
- **Kategorien** — Prompts in Kategorien organisieren (Coding, Writing, etc.)
- **KI-Chat** — Prompts direkt an OpenAI oder Claude senden
- **Streaming-Ausgabe** — KI-Antworten werden in Echtzeit ausgegeben
- **Template-Platzhalter** — Variablen wie `{{aktuelle_anfrage}}` beim Ausführen ersetzen
- **Automatische Orchestrierung** — Orchestrator-Prompts routen lokal: Systeminventur direkt lokal, normale Antworten direkt an den Primaer-Provider, Build-Aufgaben ueber Manus
- **Verlauf** — Alle gesendeten Prompts und Antworten werden lokal gespeichert
- **KI-Vorschläge** — Automatische Titel-, Tag- und Kategorie-Vorschläge
- **Freier Chat** — Direkte Konversation mit der KI ohne gespeicherten Prompt
- **Lokale SQLite-Datenbank** — Alle Daten werden in `~/.prompt-manager/prompts.db` gespeichert
- **Manus-Integration** — Task-ID, Statusabfrage und Browser-Launcher fuer Manus

---

## Installation

### Schnellinstallation

```bash
chmod +x install.sh
./install.sh
```

### Manuelle Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install .
prompt-manager
```

### PATH einrichten (nach install.sh)

Falls `prompt-manager` nicht gefunden wird, füge folgendes in deine `~/.bashrc` ein:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

---

## Verwendung

### Interaktives Menü (empfohlen)

```bash
prompt-manager
# oder
python3 main.py
```

### Direkte Befehle

| Befehl | Beschreibung |
|---|---|
| `prompt-manager list` | Alle Prompts anzeigen |
| `prompt-manager list --inactive` | Nicht aktivierte Prompts anzeigen |
| `prompt-manager list --active` | Aktivierte Prompts anzeigen |
| `prompt-manager list <suche>` | Prompts durchsuchen |
| `prompt-manager new` | Neuen Prompt erstellen |
| `prompt-manager activate <id ...>` | Prompt(s) aktivieren |
| `prompt-manager deactivate <id ...>` | Prompt(s) deaktivieren |
| `prompt-manager show <id>` | Prompt anzeigen |
| `prompt-manager edit <id>` | Prompt bearbeiten |
| `prompt-manager delete <id>` | Prompt löschen |
| `prompt-manager use <id>` | Prompt an KI senden |
| `prompt-manager use <id> gpt-4o` | Mit bestimmtem Modell senden |
| `prompt-manager use <id> aktuelle_anfrage="..."` | Template-Feld direkt setzen |
| `prompt-manager use <id> gpt-4o aktuelle_anfrage="..."` | Modell und Template-Wert setzen |
| `prompt-manager chat` | Freier KI-Chat |
| `prompt-manager manus-status [task_id]` | Letzten oder einen bestimmten Manus-Task anzeigen |
| `prompt-manager manus-open [task_id]` | Letzten oder einen bestimmten Manus-Task im Browser oeffnen |
| `prompt-manager history` | Verlauf anzeigen |
| `prompt-manager categories` | Kategorien verwalten |
| `prompt-manager config` | Primaer-Provider, OpenAI, Claude und Manus konfigurieren |

---

## Konfiguration

Beim ersten Start `config` aufrufen und die benoetigten API-Keys eingeben:

```bash
prompt-manager config
```

Alternativ als Umgebungsvariable:

```bash
export PROMPT_MANAGER_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export MANUS_API_KEY="..."
prompt-manager
```

## Registry-Updates

Die gestarteten Wrapper `prompt-manager` und `prompt-manager-gui` pruefen beim Start per `pip index versions`, ob fuer das Paket `aidrax-prompt-matrix` eine neuere Version in der Registry verfuegbar ist. Falls ja, fuehren sie automatisch `pip install --upgrade` in der lokalen venv aus.

Standardmaessig wird die Default-Registry von `pip` verwendet. Fuer eine private Registry oder einen anderen Paketnamen kannst du diese Variablen setzen:

```bash
export PROMPT_MATRIX_PACKAGE_NAME="aidrax-prompt-matrix"
export PROMPT_MATRIX_PIP_INDEX_URL="https://<deine-registry>/simple"
export PROMPT_MATRIX_PIP_EXTRA_INDEX_URL="https://<fallback-registry>/simple"
```

Nutzliche Befehle:

```bash
prompt-manager version
prompt-manager --help
```

### Release in eine Registry

Lokalen Build erzeugen:

```bash
bash scripts/build_python_package.sh
```

In eine Registry hochladen:

```bash
export TWINE_REPOSITORY_URL="https://<deine-registry>/"
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="<dein-token>"
bash scripts/publish_python_package.sh
```

Standard-Ziel fuer automatische Updates ist:

```bash
https://nitram1984.github.io/aidrax-prompt-matrix/simple
```

### Windows

Windows kann denselben Registry-Kanal verwenden. Installation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_prompt_matrix_windows.ps1
```

Der Installer legt unter `%USERPROFILE%\bin` Wrapper fuer `prompt-manager.cmd`, `prompt-manager-gui.cmd` und `manus-web.cmd` an. Diese Wrapper pruefen beim Start ebenfalls auf neue Registry-Versionen und aktualisieren sich bei Bedarf automatisch.

Fuer automatische Orchestrierung werden ein Primaer-Provider und Manus benoetigt:

- `primary_provider`: `openai` oder `anthropic`/`claude`
- je nach Provider:
  - `openai_api_key`
  - oder `anthropic_api_key`
- `manus_api_key`

Optionale Modelle:

- OpenAI: `default_model`
- Claude: `anthropic_model`
- Manus: `manus_model` wie `manus-1.6-lite`

### Lokale Modelle (Ollama)

Für lokale Modelle mit Ollama die API-URL in der Konfiguration ändern:

```
API-URL: http://localhost:11434/v1
Modell:  llama3.2
API-Key: ollama  (beliebiger Wert)
```

## Prompt-Templates

Prompts koennen Platzhalter im Format `{{name}}` enthalten.

Beispiel:

```text
Bitte beantworte diese Anfrage strukturiert:

{{aktuelle_anfrage}}
```

Beim Aufruf von `prompt-manager use <id>` fragt die CLI fehlende Werte interaktiv ab.
Alternativ koennen sie direkt per `feld=wert` uebergeben werden.

## Automatische Orchestrierung

Wenn ein Prompt als Orchestrator-Prompt erkannt wird, routet `prompt-manager use <id>` jetzt je nach Anfrage:

1. Lokale System-/Prompt-Inventur:
Direkte lokale Auswertung ohne API und ohne Manus
2. Normale Wissens- oder Antwortanfrage:
Direkte Antwort ueber den konfigurierten Primaer-Provider ohne Mehrphasen-Workflow
3. Erstellungsaufgabe fuer Skills, Agenten, Apps, Tools oder Programme:
Phase 1 ueber den Primaer-Provider, dann Build-/Review-Schritte ueber Manus, danach Konsolidierung ueber den Primaer-Provider

Dadurch bleibt Manus fest fuer Build- und Erstellungsaufgaben integriert, blockiert aber keine lokalen oder einfachen Anfragen.

Beispiel:

```bash
prompt-manager use 1 aktuelle_anfrage="Suche mir auf dem System alle aktiven Prompts."
```

---

## Datenspeicherung

Alle Daten werden lokal gespeichert:

```
~/.prompt-manager/
└── prompts.db    ← SQLite-Datenbank (Prompts, Kategorien, Verlauf)
```

Zusätzlich erstellt `install.sh`:

```text
~/.local/bin/manus-web
~/.local/share/applications/manus-web.desktop
```

Damit kannst du Manus aus dem App-Launcher oder per `manus-web` starten.

---

## Anforderungen

- Ubuntu 20.04 oder neuer
- Python 3.9 oder neuer
- Pakete: `rich`, `openai`, `requests`
- OpenAI- oder Claude-API-Key
- Manus-API-Key fuer automatische Manus-Tasks
