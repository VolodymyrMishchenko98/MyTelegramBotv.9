"""Persistence helpers for developer feedback tickets and conversation history."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Literal

from db_improved import get_db_context

DeliveryStatus = Literal["pending", "sent", "failed"]


def ensure_feedback_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS developer_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            anonymous INTEGER NOT NULL DEFAULT 0 CHECK (anonymous IN (0, 1)),
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
            notification_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (notification_status IN ('pending', 'sent', 'failed')),
            created_at TEXT NOT NULL,
            replied_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_developer_feedback_sender_created
        ON developer_feedback(sender_id, created_at)
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS developer_feedback_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL REFERENCES developer_feedback(id) ON DELETE CASCADE,
            sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'developer')),
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'sent'
                CHECK (delivery_status IN ('pending', 'sent', 'failed'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_developer_feedback_messages_ticket
        ON developer_feedback_messages(feedback_id, id)
    """)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def create_feedback(
    sender_id: int,
    anonymous: bool,
    category: str,
    message: str,
    *,
    now: datetime | None = None,
) -> int | None:
    """Create one ticket and its first message; None means the sender is rate limited."""
    current_time = now or _utc_now()
    created_at = _timestamp(current_time)
    cutoff = _timestamp(current_time - timedelta(minutes=10))
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT COUNT(*) FROM developer_feedback_messages m "
            "JOIN developer_feedback f ON f.id=m.feedback_id "
            "WHERE f.sender_id=? AND m.sender_type='user' AND m.created_at>=?",
            (sender_id, cutoff),
        )
        if int(cursor.fetchone()[0]) >= 3:
            return None
        cursor.execute(
            "INSERT INTO developer_feedback "
            "(sender_id, anonymous, category, message, status, created_at) "
            "VALUES (?, ?, ?, ?, 'open', ?)",
            (sender_id, int(anonymous), category, message, created_at),
        )
        feedback_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO developer_feedback_messages "
            "(feedback_id, sender_type, message, created_at) VALUES (?, 'user', ?, ?)",
            (feedback_id, message, created_at),
        )
        return feedback_id


def get_feedback(feedback_id: int) -> dict | None:
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, sender_id, anonymous, category, message, status, "
            "notification_status, created_at, replied_at "
            "FROM developer_feedback WHERE id=?",
            (feedback_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "sender_id": int(row[1]),
            "anonymous": bool(row[2]),
            "category": row[3],
            "message": row[4],
            "status": row[5],
            "notification_status": row[6],
            "created_at": row[7],
            "replied_at": row[8],
        }


def get_user_feedback(feedback_id: int, sender_id: int) -> dict | None:
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, sender_id, anonymous, category, message, status, "
            "notification_status, created_at, replied_at "
            "FROM developer_feedback WHERE id=? AND sender_id=?",
            (feedback_id, sender_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "sender_id": int(row[1]),
            "anonymous": bool(row[2]),
            "category": row[3],
            "message": row[4],
            "status": row[5],
            "notification_status": row[6],
            "created_at": row[7],
            "replied_at": row[8],
        }


def mark_feedback_notification(feedback_id: int, delivered: bool) -> None:
    status: DeliveryStatus = "sent" if delivered else "failed"
    with get_db_context() as connection:
        connection.execute(
            "UPDATE developer_feedback SET notification_status=? WHERE id=?",
            (status, feedback_id),
        )


def add_user_message(feedback_id: int, sender_id: int, message: str) -> str:
    """Append a user message only to their own open ticket."""
    created_at = _timestamp(_utc_now())
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT status FROM developer_feedback WHERE id=? AND sender_id=?",
            (feedback_id, sender_id),
        )
        row = cursor.fetchone()
        if row is None:
            return "not_found"
        if row[0] != "open":
            return "closed"
        cutoff = _timestamp(_utc_now() - timedelta(minutes=10))
        cursor.execute(
            "SELECT COUNT(*) FROM developer_feedback_messages m "
            "JOIN developer_feedback f ON f.id=m.feedback_id "
            "WHERE f.sender_id=? AND m.sender_type='user' AND m.created_at>=?",
            (sender_id, cutoff),
        )
        if int(cursor.fetchone()[0]) >= 3:
            return "rate_limited"
        cursor.execute(
            "INSERT INTO developer_feedback_messages "
            "(feedback_id, sender_type, message, created_at) VALUES (?, 'user', ?, ?)",
            (feedback_id, message, created_at),
        )
        return "ok"


def create_developer_reply(feedback_id: int, message: str) -> tuple[int, int] | None:
    """Record a pending developer reply and return (sender_id, history_message_id)."""
    created_at = _timestamp(_utc_now())
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT sender_id FROM developer_feedback WHERE id=? AND status='open'",
            (feedback_id,),
        )
        ticket = cursor.fetchone()
        if ticket is None:
            return None
        cursor.execute(
            "INSERT INTO developer_feedback_messages "
            "(feedback_id, sender_type, message, created_at, delivery_status) "
            "VALUES (?, 'developer', ?, ?, 'pending')",
            (feedback_id, message, created_at),
        )
        return int(ticket[0]), int(cursor.lastrowid)


def finish_developer_reply(message_id: int, delivered: bool) -> None:
    status: DeliveryStatus = "sent" if delivered else "failed"
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE developer_feedback_messages SET delivery_status=? "
            "WHERE id=? AND sender_type='developer' AND delivery_status='pending'",
            (status, message_id),
        )
        if delivered:
            cursor.execute(
                "UPDATE developer_feedback SET replied_at=? "
                "WHERE id=(SELECT feedback_id FROM developer_feedback_messages WHERE id=?)",
                (_timestamp(_utc_now()), message_id),
            )


def set_feedback_status(feedback_id: int, status: Literal["open", "closed"]) -> bool:
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE developer_feedback SET status=? WHERE id=?",
            (status, feedback_id),
        )
        return cursor.rowcount == 1


def get_feedback_messages(feedback_id: int) -> list[dict]:
    with get_db_context() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, sender_type, message, created_at, delivery_status "
            "FROM developer_feedback_messages WHERE feedback_id=? ORDER BY id",
            (feedback_id,),
        )
        return [
            {
                "id": int(row[0]),
                "sender_type": row[1],
                "message": row[2],
                "created_at": row[3],
                "delivery_status": row[4],
            }
            for row in cursor.fetchall()
        ]
