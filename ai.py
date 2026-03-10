"""
ai.py — KI-API-Integration fuer den Prompt Manager CLI.
Unterstuetzt OpenAI-kompatible APIs, Claude via Anthropic API
sowie Manus-Tasks fuer orchestrierte Workflows.
"""

import json
import os
import time
from typing import Any, Callable

import requests

from db import add_history, get_config


OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
ANTHROPIC_API_VERSION = "2023-06-01"
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
DEFAULT_PERPLEXITY_MODEL = "sonar-pro"
MANUS_BASE_URL = "https://api.manus.ai"
DEFAULT_MANUS_MODEL = "manus-1.6-lite"


def _normalize_provider(provider: str | None) -> str:
    value = (provider or "").strip().lower()
    if value in {"anthropic", "claude", "claude-one", "cluode", "cluode-one", "cluode one", "claude one"}:
        return "anthropic"
    return "openai"


def get_primary_provider() -> str:
    provider = get_config("primary_provider") or os.environ.get("PROMPT_MANAGER_PROVIDER", "")
    return _normalize_provider(provider)


def get_primary_provider_label() -> str:
    return "Claude" if get_primary_provider() == "anthropic" else "OpenAI"


def _get_openai_api_key() -> str:
    key = get_config("openai_api_key")
    if not key:
        key = os.environ.get("OPENAI_API_KEY", "")
    return key


def has_openai_credentials() -> bool:
    return bool(_get_openai_api_key())


def _get_openai_model() -> str:
    return get_config("default_model") or DEFAULT_OPENAI_MODEL


def _get_openai_base_url() -> str:
    return get_config("api_base_url") or OPENAI_BASE_URL


def _get_anthropic_api_key() -> str:
    key = get_config("anthropic_api_key")
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        key = os.environ.get("CLAUDE_API_KEY", "")
    return key


def has_anthropic_credentials() -> bool:
    return bool(_get_anthropic_api_key())


def has_primary_credentials() -> bool:
    if get_primary_provider() == "anthropic":
        return has_anthropic_credentials()
    return has_openai_credentials()


def _get_anthropic_model() -> str:
    return get_config("anthropic_model") or DEFAULT_ANTHROPIC_MODEL


def _get_anthropic_base_url() -> str:
    return get_config("anthropic_api_url") or ANTHROPIC_BASE_URL


def get_default_chat_model() -> str:
    if get_primary_provider() == "anthropic":
        return _get_anthropic_model()
    return _get_openai_model()


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(stripped[start:end + 1])

    raise ValueError("Kein JSON-Objekt in der Antwort gefunden.")


def _get_perplexity_api_key() -> str:
    key = get_config("perplexity_api_key")
    if not key:
        key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not key:
        key = os.environ.get("PPLX_API_KEY", "")
    return key


def has_perplexity_credentials() -> bool:
    return bool(_get_perplexity_api_key())


def _get_perplexity_model() -> str:
    return get_config("perplexity_model") or DEFAULT_PERPLEXITY_MODEL


def _get_manus_api_key() -> str:
    key = get_config("manus_api_key")
    if not key:
        key = os.environ.get("MANUS_API_KEY", "")
    return key


def has_manus_credentials() -> bool:
    return bool(_get_manus_api_key())


def _get_manus_model() -> str:
    return get_config("manus_model") or DEFAULT_MANUS_MODEL


def _chat_openai(
    prompt_content: str,
    system_prompt: str,
    model: str | None,
    stream: bool,
) -> tuple[str, int | None, str]:
    api_key = _get_openai_api_key()
    if not api_key:
        raise ValueError("Kein OpenAI-API-Key konfiguriert. Fuehre 'config' aus und setze deinen OpenAI API-Key.")

    used_model = model or _get_openai_model()
    base_url = _get_openai_base_url()
    full_response = ""
    tokens_used = None

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": used_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_content},
                ],
                "stream": stream,
                "temperature": 0.7,
            },
            stream=stream,
            timeout=120,
        )
        resp.raise_for_status()

        if stream:
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        full_response += delta
                        print(delta, end="", flush=True)
                    if chunk.get("usage"):
                        tokens_used = chunk["usage"].get("total_tokens")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
            print()
        else:
            data = resp.json()
            full_response = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens")

        return full_response, tokens_used, used_model
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Keine Verbindung zur KI-API. Pruefe deine Internetverbindung.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError("Ungueltiger OpenAI-API-Key. Pruefe deinen OpenAI API-Key in der Konfiguration.")
        if e.response.status_code == 429:
            raise ValueError("OpenAI-API-Limit erreicht. Warte kurz und versuche es erneut.")
        raise ValueError(f"OpenAI-API-Fehler {e.response.status_code}: {e.response.text[:200]}")


def _extract_anthropic_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in data.get("content", []):
        if block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    return "\n".join(parts).strip()


def _chat_anthropic(
    prompt_content: str,
    system_prompt: str,
    model: str | None,
    stream: bool,
) -> tuple[str, int | None, str]:
    api_key = _get_anthropic_api_key()
    if not api_key:
        raise ValueError("Kein Claude-API-Key konfiguriert. Fuehre 'config' aus und setze deinen Anthropic API-Key.")

    used_model = model or _get_anthropic_model()
    base_url = _get_anthropic_base_url()

    try:
        resp = requests.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": used_model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt_content}],
                "max_tokens": 4096,
                "temperature": 0.7,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        full_response = _extract_anthropic_text(data)
        if stream and full_response:
            print(full_response)
        usage = data.get("usage") or {}
        tokens_used = None
        if usage:
            tokens_used = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
        return full_response, tokens_used, used_model
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Keine Verbindung zur Claude-API. Pruefe deine Internetverbindung.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (401, 403):
            raise ValueError("Ungueltiger Claude-API-Key. Pruefe deinen Anthropic API-Key in der Konfiguration.")
        if e.response.status_code == 429:
            raise ValueError("Claude-API-Limit erreicht. Warte kurz und versuche es erneut.")
        raise ValueError(f"Claude-API-Fehler {e.response.status_code}: {e.response.text[:200]}")


def chat(
    prompt_content: str,
    system_prompt: str = "Du bist ein hilfreicher KI-Assistent.",
    model: str | None = None,
    stream: bool = True,
    prompt_id: int | None = None,
    prompt_title: str | None = None,
) -> str:
    """
    Sendet einen Prompt an den aktuell konfigurierten Primaer-Provider.
    """
    start = time.time()
    provider = get_primary_provider()

    if provider == "anthropic":
        full_response, tokens_used, used_model = _chat_anthropic(
            prompt_content=prompt_content,
            system_prompt=system_prompt,
            model=model,
            stream=stream,
        )
        history_model = f"anthropic:{used_model}"
    else:
        full_response, tokens_used, used_model = _chat_openai(
            prompt_content=prompt_content,
            system_prompt=system_prompt,
            model=model,
            stream=stream,
        )
        history_model = used_model

    duration_ms = int((time.time() - start) * 1000)

    add_history(
        prompt_content=prompt_content,
        response=full_response,
        model=history_model,
        prompt_id=prompt_id,
        prompt_title=prompt_title,
        tokens_used=tokens_used,
        duration_ms=duration_ms,
        status="completed",
    )

    return full_response


def perplexity_chat(
    prompt_content: str,
    system_prompt: str | None = None,
    model: str | None = None,
) -> str:
    """
    Sendet einen Prompt an die Perplexity Sonar API und liefert den Textinhalt.
    Die API ist OpenAI-kompatibel, nutzt aber eigene Modelnamen wie sonar-pro.
    """
    api_key = _get_perplexity_api_key()
    if not api_key:
        raise ValueError(
            "Kein Perplexity-API-Key konfiguriert. Setze 'perplexity_api_key' oder PERPLEXITY_API_KEY."
        )

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt_content})

    try:
        resp = requests.post(
            f"{PERPLEXITY_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or _get_perplexity_model(),
                "messages": messages,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Keine Verbindung zur Perplexity-API. Prüfe deine Internetverbindung.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError("Ungültiger Perplexity-API-Key.")
        if e.response.status_code == 429:
            raise ValueError("Perplexity-API-Limit erreicht. Warte kurz und versuche es erneut.")
        raise ValueError(f"Perplexity-API-Fehler {e.response.status_code}: {e.response.text[:200]}")


def manus_create_task(task_prompt: str, model: str | None = None) -> dict[str, Any]:
    """
    Erstellt einen Manus-Task und liefert die API-Antwort zurueck.
    Laut Manus-Dokumentation liefert POST /v1/tasks eine task_id zur weiteren Abfrage.
    """
    api_key = _get_manus_api_key()
    if not api_key:
        raise ValueError(
            "Kein Manus-API-Key konfiguriert. Setze 'manus_api_key' oder MANUS_API_KEY."
        )

    try:
        resp = requests.post(
            f"{MANUS_BASE_URL}/v1/tasks",
            headers={
                "API_KEY": api_key,
                "Content-Type": "application/json",
            },
            json={
                "prompt": task_prompt,
                "agentProfile": model or _get_manus_model(),
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Keine Verbindung zur Manus-API. Prüfe deine Internetverbindung.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError("Ungültiger Manus-API-Key.")
        if e.response.status_code == 429:
            raise ValueError("Manus-API-Limit erreicht. Warte kurz und versuche es erneut.")
        raise ValueError(f"Manus-API-Fehler {e.response.status_code}: {e.response.text[:200]}")


def manus_get_task(task_id: str) -> dict[str, Any]:
    api_key = _get_manus_api_key()
    if not api_key:
        raise ValueError(
            "Kein Manus-API-Key konfiguriert. Setze 'manus_api_key' oder MANUS_API_KEY."
        )

    try:
        resp = requests.get(
            f"{MANUS_BASE_URL}/v1/tasks/{task_id}",
            headers={"API_KEY": api_key},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Keine Verbindung zur Manus-API. Prüfe deine Internetverbindung.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError("Ungültiger Manus-API-Key.")
        if e.response.status_code == 404:
            raise LookupError(f"Manus-Task {task_id} wurde noch nicht gefunden.")
        raise ValueError(f"Manus-API-Fehler {e.response.status_code}: {e.response.text[:200]}")


def _extract_manus_output_text(task: dict[str, Any]) -> str:
    outputs = task.get("output") or []
    parts: list[str] = []

    for message in outputs:
        for content in message.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])

    if parts:
        return "\n\n".join(parts).strip()

    if task.get("error"):
        return str(task["error"]).strip()

    return json.dumps(task, ensure_ascii=False, indent=2)


def _compact_manus_value(value: Any, max_length: int = 400) -> str:
    if isinstance(value, str):
        text = value.strip()
    else:
        text = json.dumps(value, ensure_ascii=False)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def _summarize_manus_failure(task: dict[str, Any], created: dict[str, Any] | None = None) -> str:
    metadata = task.get("metadata") or {}
    created = created or {}
    details: list[str] = []

    status = task.get("status")
    if status:
        details.append(f"status={status}")

    title = (
        metadata.get("task_title")
        or task.get("task_title")
        or created.get("task_title")
    )
    if title:
        details.append(f"title={_compact_manus_value(title, max_length=160)}")

    task_url = (
        metadata.get("task_url")
        or task.get("task_url")
        or created.get("task_url")
    )
    if task_url:
        details.append(f"url={task_url}")

    for key in ("error", "incomplete_details", "failure_reason", "message"):
        value = task.get(key)
        if value:
            details.append(f"{key}={_compact_manus_value(value)}")

    output_text = ""
    outputs = task.get("output") or []
    if outputs:
        output_text = _extract_manus_output_text(task)
    if output_text:
        details.append(f"output={_compact_manus_value(output_text, max_length=500)}")

    if not details:
        details.append(f"task={_compact_manus_value(task, max_length=700)}")

    return "; ".join(details)


def manus_chat(
    task_prompt: str,
    model: str | None = None,
    timeout_seconds: int = 300,
    poll_interval_seconds: int = 5,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """
    Erstellt einen Manus-Task und pollt ihn bis 'completed' oder 'failed'.
    """
    created = manus_create_task(task_prompt, model=model)
    task_id = created.get("task_id")
    if not task_id:
        return json.dumps(created, ensure_ascii=False, indent=2)
    if status_callback:
        status_callback({"event": "created", **created})

    deadline = time.time() + timeout_seconds
    last_status = "pending"
    reported_status = ""

    while time.time() < deadline:
        try:
            task = manus_get_task(task_id)
        except LookupError:
            time.sleep(poll_interval_seconds)
            continue
        last_status = task.get("status") or last_status
        if status_callback and last_status != reported_status:
            reported_status = last_status
            status_callback({"event": "status", "task_id": task_id, "status": last_status, "task": task})
        if last_status == "completed":
            if status_callback:
                status_callback({"event": "completed", "task_id": task_id, "task": task})
            return _extract_manus_output_text(task)
        if last_status == "failed":
            if status_callback:
                status_callback({"event": "failed", "task_id": task_id, "task": task})
            raise ValueError(
                "Manus-Task fehlgeschlagen: "
                + _summarize_manus_failure(task, created=created)
            )
        time.sleep(poll_interval_seconds)

    if status_callback:
        status_callback({"event": "timeout", "task_id": task_id})
    raise TimeoutError(f"Manus-Task {task_id} wurde nicht innerhalb von {timeout_seconds}s abgeschlossen.")


def suggest_metadata(prompt_content: str) -> dict:
    """
    Analysiert einen Prompt und schlägt Titel, Beschreibung, Tags und Kategorie vor.
    Gibt ein dict zurück: {title, description, tags, category}.
    """
    if not has_primary_credentials():
        return {}

    system = (
        "Du bist ein Assistent, der KI-Prompts analysiert. "
        "Antworte NUR mit einem JSON-Objekt mit den Feldern: "
        "title (kurzer Titel, max 50 Zeichen), "
        "description (1 Satz Beschreibung), "
        "tags (Array mit 2-4 Schlagwörtern auf Englisch, lowercase), "
        "category (eine Kategorie aus: Coding, Writing, Analysis, Creative, Business, Research, Other)."
    )

    try:
        if get_primary_provider() == "anthropic":
            resp = requests.post(
                f"{_get_anthropic_base_url()}/messages",
                headers={
                    "x-api-key": _get_anthropic_api_key(),
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": _get_anthropic_model(),
                    "system": system,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Analysiere diesen Prompt und antworte nur mit JSON:\n\n{prompt_content[:500]}",
                        }
                    ],
                    "max_tokens": 600,
                    "temperature": 0.2,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return _extract_json_object(_extract_anthropic_text(resp.json()))

        resp = requests.post(
            f"{_get_openai_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {_get_openai_api_key()}",
                "Content-Type": "application/json",
            },
            json={
                "model": _get_openai_model(),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Analysiere diesen Prompt:\n\n{prompt_content[:500]}"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:
        return {}


def list_models() -> list[str]:
    """Verfügbare Modelle von der API abrufen."""
    if get_primary_provider() == "anthropic":
        api_key = _get_anthropic_api_key()
        if not api_key:
            return [DEFAULT_ANTHROPIC_MODEL]
        try:
            resp = requests.get(
                f"{_get_anthropic_base_url()}/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                },
                timeout=10,
            )
            resp.raise_for_status()
            models = [m["id"] for m in resp.json().get("data", []) if m.get("id")]
            return sorted(models) or [DEFAULT_ANTHROPIC_MODEL]
        except Exception:
            return [DEFAULT_ANTHROPIC_MODEL]

    api_key = _get_openai_api_key()
    if not api_key:
        return [DEFAULT_OPENAI_MODEL]
    try:
        resp = requests.get(
            f"{_get_openai_base_url()}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", []) if "gpt" in m["id"]]
        return sorted(models) or [DEFAULT_OPENAI_MODEL]
    except Exception:
        return ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
