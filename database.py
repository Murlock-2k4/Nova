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
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
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

    initialize_identity_tables()


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


def save_exchange(
    user_message: str,
    assistant_message: str,
    source: str,
    client_id: str | None = None,
    room_id: int | None = None,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO conversation_messages (
                role, content, source, created_at, client_id, room_id
            ) VALUES ('user', ?, NULL, ?, ?, ?)
            """,
            (user_message.strip(), created_at, client_id, room_id),
        )
        connection.execute(
            """
            INSERT INTO conversation_messages (
                role, content, source, created_at, client_id, room_id
            ) VALUES ('assistant', ?, ?, ?, ?, ?)
            """,
            (assistant_message.strip(), source, created_at, client_id, room_id),
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


def get_setting(key: str, default: str | None = None) -> str | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()

    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    cleaned_key = key.strip()
    cleaned_value = value.strip()

    if not cleaned_key:
        raise ValueError("Setting key cannot be empty")

    updated_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (cleaned_key, cleaned_value, updated_at),
        )
        connection.commit()


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def initialize_identity_tables() -> None:
    """Create the room/client tables and apply lightweight schema migrations."""
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                room_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_clients_room_id
            ON clients(room_id)
            """
        )

        # Give a first installation one useful room immediately.
        connection.execute(
            """
            INSERT INTO rooms (name, created_at)
            SELECT 'Main Room', ?
            WHERE NOT EXISTS (SELECT 1 FROM rooms)
            """,
            (now,),
        )

        message_columns = _table_columns(connection, "conversation_messages")
        if "client_id" not in message_columns:
            connection.execute(
                "ALTER TABLE conversation_messages ADD COLUMN client_id TEXT"
            )
        if "room_id" not in message_columns:
            connection.execute(
                "ALTER TABLE conversation_messages ADD COLUMN room_id INTEGER"
            )

        connection.commit()


def list_rooms() -> list[dict[str, Any]]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT r.id, r.name, r.created_at, COUNT(c.id) AS client_count
            FROM rooms AS r
            LEFT JOIN clients AS c ON c.room_id = r.id
            GROUP BY r.id
            ORDER BY r.name COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_room(name: str) -> dict[str, Any]:
    cleaned_name = " ".join(name.strip().split())
    if not cleaned_name:
        raise ValueError("Room name cannot be empty")

    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect()) as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO rooms (name, created_at) VALUES (?, ?)",
                (cleaned_name, now),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("A room with that name already exists") from error

        row = connection.execute(
            "SELECT id, name, created_at FROM rooms WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def get_client(client_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT c.id, c.name, c.room_id, r.name AS room_name,
                   c.created_at, c.updated_at, c.last_seen_at
            FROM clients AS c
            LEFT JOIN rooms AS r ON r.id = c.room_id
            WHERE c.id = ?
            """,
            (client_id,),
        ).fetchone()
    return dict(row) if row else None


def register_client(
    client_id: str,
    name: str,
    room_id: int | None,
) -> dict[str, Any]:
    cleaned_id = client_id.strip()
    cleaned_name = " ".join(name.strip().split()) or "Nova Display"
    if not cleaned_id:
        raise ValueError("Client ID cannot be empty")

    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect()) as connection:
        if room_id is not None:
            room = connection.execute(
                "SELECT id FROM rooms WHERE id = ?",
                (room_id,),
            ).fetchone()
            if room is None:
                raise ValueError("Selected room does not exist")

        connection.execute(
            """
            INSERT INTO clients (
                id, name, room_id, created_at, updated_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                room_id = excluded.room_id,
                updated_at = excluded.updated_at,
                last_seen_at = excluded.last_seen_at
            """,
            (cleaned_id, cleaned_name, room_id, now, now, now),
        )
        connection.commit()

    client = get_client(cleaned_id)
    if client is None:
        raise RuntimeError("Client registration failed")
    return client


def touch_client(client_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect()) as connection:
        connection.execute(
            "UPDATE clients SET last_seen_at = ? WHERE id = ?",
            (now, client_id),
        )
        connection.commit()
