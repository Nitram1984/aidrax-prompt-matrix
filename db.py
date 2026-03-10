"""
db.py — SQLite-Datenbankschicht für den Prompt Manager CLI.
Speichert Prompts, Kategorien und Chat-Verlauf lokal.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".prompt-manager" / "prompts.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Erstellt alle Tabellen, falls sie noch nicht existieren."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL UNIQUE,
                color     TEXT    NOT NULL DEFAULT '#00FFFF',
                icon      TEXT,
                created_at TEXT   NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS prompts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                description TEXT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                tags        TEXT    NOT NULL DEFAULT '[]',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                use_count   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id      INTEGER REFERENCES prompts(id) ON DELETE SET NULL,
                prompt_title   TEXT,
                prompt_content TEXT    NOT NULL,
                response       TEXT,
                model          TEXT    NOT NULL DEFAULT 'gpt-4o-mini',
                tokens_used    INTEGER,
                duration_ms    INTEGER,
                status         TEXT    NOT NULL DEFAULT 'completed',
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        prompt_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(prompts)").fetchall()
        }
        if "is_active" not in prompt_columns:
            conn.execute(
                "ALTER TABLE prompts ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )
            conn.execute(
                "UPDATE prompts SET is_active = CASE WHEN use_count > 0 THEN 1 ELSE 0 END"
            )


# ─── Config ──────────────────────────────────────────────────────────────────

def get_config(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ─── Kategorien ──────────────────────────────────────────────────────────────

def list_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def create_category(name: str, color: str = "#00FFFF", icon: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO categories(name,color,icon) VALUES(?,?,?)",
            (name, color, icon or None),
        )
        return cur.lastrowid


def delete_category(cat_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))


# ─── Prompts ─────────────────────────────────────────────────────────────────

def list_prompts(
    search: str = "",
    category_id: int | None = None,
    favorites_only: bool = False,
    active_only: bool | None = None,
) -> list[dict]:
    query = "SELECT p.*, c.name AS category_name, c.color AS category_color FROM prompts p LEFT JOIN categories c ON p.category_id=c.id WHERE 1=1"
    params: list = []
    if search:
        query += " AND (p.title LIKE ? OR p.content LIKE ? OR p.tags LIKE ?)"
        s = f"%{search}%"
        params += [s, s, s]
    if category_id is not None:
        query += " AND p.category_id=?"
        params.append(category_id)
    if favorites_only:
        query += " AND p.is_favorite=1"
    if active_only is not None:
        query += " AND p.is_active=?"
        params.append(int(active_only))
    query += " ORDER BY p.updated_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_prompt(prompt_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.*, c.name AS category_name FROM prompts p LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?",
            (prompt_id,),
        ).fetchone()
        return dict(row) if row else None


def create_prompt(
    title: str,
    content: str,
    description: str = "",
    category_id: int | None = None,
    tags: list[str] | None = None,
    is_favorite: bool = False,
    is_active: bool = True,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO prompts(title,content,description,category_id,tags,is_favorite,is_active,updated_at)
               VALUES(?,?,?,?,?,?,?,datetime('now'))""",
            (
                title,
                content,
                description or None,
                category_id,
                json.dumps(tags or []),
                int(is_favorite),
                int(is_active),
            ),
        )
        return cur.lastrowid


def update_prompt(prompt_id: int, **kwargs) -> None:
    allowed = {"title", "content", "description", "category_id", "tags", "is_favorite", "is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if "tags" in fields and isinstance(fields["tags"], list):
        fields["tags"] = json.dumps(fields["tags"])
    if "is_favorite" in fields:
        fields["is_favorite"] = int(fields["is_favorite"])
    if "is_active" in fields:
        fields["is_active"] = int(fields["is_active"])
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [prompt_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE prompts SET {set_clause}, updated_at=datetime('now') WHERE id=?",
            values,
        )


def delete_prompt(prompt_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM prompts WHERE id=?", (prompt_id,))


def increment_use_count(prompt_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE prompts SET use_count=use_count+1, is_active=1 WHERE id=?",
            (prompt_id,),
        )


def set_prompt_active(prompt_ids: list[int], is_active: bool) -> int:
    if not prompt_ids:
        return 0
    placeholders = ",".join("?" for _ in prompt_ids)
    params = [int(is_active), *prompt_ids]
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE prompts SET is_active=?, updated_at=datetime('now') WHERE id IN ({placeholders})",
            params,
        )
        return cur.rowcount


# ─── Verlauf ─────────────────────────────────────────────────────────────────

def add_history(
    prompt_content: str,
    response: str,
    model: str,
    prompt_id: int | None = None,
    prompt_title: str | None = None,
    tokens_used: int | None = None,
    duration_ms: int | None = None,
    status: str = "completed",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO history(prompt_id,prompt_title,prompt_content,response,model,tokens_used,duration_ms,status)
               VALUES(?,?,?,?,?,?,?,?)""",
            (prompt_id, prompt_title, prompt_content, response, model, tokens_used, duration_ms, status),
        )
        return cur.lastrowid


def list_history(search: str = "", limit: int = 50) -> list[dict]:
    query = "SELECT * FROM history WHERE 1=1"
    params: list = []
    if search:
        s = f"%{search}%"
        query += " AND (prompt_content LIKE ? OR response LIKE ? OR prompt_title LIKE ?)"
        params += [s, s, s]
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def delete_history_entry(entry_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM history WHERE id=?", (entry_id,))
