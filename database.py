from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATABASE_FILE


def _connect() -> sqlite3.Connection:
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database() -> None:
    with closing(_connect()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                source TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_created_at
            ON conversation_messages(created_at DESC)
            """
        )
        connection.commit()


def save_message(role: str, content: str, source: str | None = None) -> int:
    cleaned_content = content.strip()

    if role not in {"user", "assistant"}:
        raise ValueError(f"Unsupported conversation role: {role}")

    if not cleaned_content:
        raise ValueError("Conversation content cannot be empty")

    created_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversation_messages (role, content, source, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (role, cleaned_content, source, created_at),
        )
        connection.commit()
        return int(cursor.lastrowid)


def save_exchange(user_message: str, assistant_message: str, source: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO conversation_messages (role, content, source, created_at)
            VALUES ('user', ?, NULL, ?)
            """,
            (user_message.strip(), created_at),
        )
        connection.execute(
            """
            INSERT INTO conversation_messages (role, content, source, created_at)
            VALUES ('assistant', ?, ?, ?)
            """,
            (assistant_message.strip(), source, created_at),
        )
        connection.commit()


def get_recent_messages(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))

    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, role, content, source, created_at
            FROM (
                SELECT id, role, content, source, created_at
                FROM conversation_messages
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (safe_limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_conversation_history() -> int:
    with closing(_connect()) as connection:
        cursor = connection.execute("DELETE FROM conversation_messages")
        connection.commit()
        return max(cursor.rowcount, 0)
