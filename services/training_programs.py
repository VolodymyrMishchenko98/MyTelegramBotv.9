"""SQLite persistence for user-generated training programs."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from db_improved import get_db_context


def ensure_program_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            preferences_json TEXT NOT NULL,
            content_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
            archived_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_training_programs_user_status
        ON training_programs(user_id, status, created_at DESC)
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_training_programs_one_active
        ON training_programs(user_id) WHERE status='active'
    """)


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _decode(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "user_id": int(row[1]),
        "created_at": row[2],
        "preferences": json.loads(row[3]),
        "content": json.loads(row[4]),
        "status": row[5],
        "archived_at": row[6],
    }


def save_program(
    user_id: int,
    preferences: dict[str, Any],
    content: dict[str, Any],
) -> int:
    """Archive the previous active plan and atomically save its replacement."""
    created_at = _created_at()
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "UPDATE training_programs SET status='archived', archived_at=? "
            "WHERE user_id=? AND status='active'",
            (created_at, user_id),
        )
        cursor.execute(
            "INSERT INTO training_programs "
            "(user_id, created_at, preferences_json, content_json, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (
                user_id,
                created_at,
                json.dumps(preferences, ensure_ascii=False),
                json.dumps(content, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def get_active_program(user_id: int) -> dict[str, Any] | None:
    with get_db_context() as connection:
        row = connection.execute(
            "SELECT id, user_id, created_at, preferences_json, content_json, "
            "status, archived_at FROM training_programs "
            "WHERE user_id=? AND status='active'",
            (user_id,),
        ).fetchone()
    return _decode(row)


def get_program(user_id: int, program_id: int) -> dict[str, Any] | None:
    with get_db_context() as connection:
        row = connection.execute(
            "SELECT id, user_id, created_at, preferences_json, content_json, "
            "status, archived_at FROM training_programs WHERE user_id=? AND id=?",
            (user_id, program_id),
        ).fetchone()
    return _decode(row)


def list_archived_programs(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_db_context() as connection:
        rows = connection.execute(
            "SELECT id, user_id, created_at, preferences_json, content_json, "
            "status, archived_at FROM training_programs "
            "WHERE user_id=? AND status='archived' "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 50))),
        ).fetchall()
    return [program for row in rows if (program := _decode(row)) is not None]


def archive_program(user_id: int, program_id: int) -> bool:
    with get_db_context() as connection:
        cursor = connection.execute(
            "UPDATE training_programs SET status='archived', archived_at=? "
            "WHERE user_id=? AND id=? AND status='active'",
            (_created_at(), user_id, program_id),
        )
        return cursor.rowcount == 1


def get_user_age(user_id: int) -> int | None:
    with get_db_context() as connection:
        row = connection.execute(
            "SELECT age FROM users WHERE user_id=? AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
    if row is None or row[0] is None:
        return None
    try:
        age = int(row[0])
    except (TypeError, ValueError):
        return None
    return age if 1 <= age <= 120 else None
