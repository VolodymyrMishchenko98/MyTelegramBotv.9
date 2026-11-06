"""Persistence service for workout sessions."""
from __future__ import annotations

from datetime import datetime

from db_improved import get_db


def save_workout_session(
    user_id: int,
    exercises: list[str],
    note: str | None,
    workout_date: str,
) -> int:
    """Save one session and all exercises atomically, returning its ID."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")
    if not isinstance(exercises, (list, tuple)) or not exercises:
        raise ValueError("exercises must be a non-empty list")
    if not isinstance(workout_date, str) or not workout_date.strip():
        raise ValueError("workout_date must be a non-empty string")
    if any(not isinstance(exercise, str) or not exercise.strip() for exercise in exercises):
        raise ValueError("exercise names must be non-empty strings")

    db = get_db()
    cur = db.cursor()
    recorded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("PRAGMA table_info(workout_sessions)")
        has_recorded_at = any(row[1] == "recorded_at" for row in cur.fetchall())
        if has_recorded_at:
            cur.execute(
                "INSERT INTO workout_sessions (user_id, date, note, recorded_at) VALUES (?, ?, ?, ?)",
                (user_id, workout_date, note, recorded_at),
            )
        else:
            cur.execute(
                "INSERT INTO workout_sessions (user_id, date, note) VALUES (?, ?, ?)",
                (user_id, workout_date, note),
            )
        session_id = cur.lastrowid
        cur.execute("PRAGMA table_info(workouts)")
        has_workout_time = any(row[1] == "recorded_at" for row in cur.fetchall())
        for exercise in exercises:
            if has_workout_time:
                cur.execute(
                    "INSERT INTO workouts (user_id, text, date, session_id, recorded_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, exercise, workout_date, session_id, recorded_at),
                )
            else:
                cur.execute(
                    "INSERT INTO workouts (user_id, text, date, session_id) VALUES (?, ?, ?, ?)",
                    (user_id, exercise, workout_date, session_id),
                )
        db.commit()
        return int(session_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
