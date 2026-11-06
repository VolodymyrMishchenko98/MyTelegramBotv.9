"""DB connection pool for aiogram SQLite backend.

Uses WAL mode, per-thread connection caching, and an RLock so that
multiple sequential `fetch_all` / `execute_query` calls within the same
handler do not pay the cost of `SELECT 1` on every single invocation.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from services.logging_config import get_logger

# Keep the database location independent of the process working directory.
# This prevents the bot and tests launched from different directories from
# silently opening different SQLite files.
DB_PATH = str(Path(__file__).resolve().parent / "sportbot.db")
log = get_logger("db")

_db_lock                        = threading.RLock()
_thread_local                   = threading.local()
_thread_local._tl_conn: sqlite3.Connection | None = None   # type: ignore[attr-defined]
_last_health_check_ts: float    = 0.0
_HEALTH_CHECK_INTERVAL: float  = 60.0     # seconds


def _open_raw_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = 10000")
    return conn


def add_column_if_missing(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def _get_thread_connection() -> sqlite3.Connection:
    global _last_health_check_ts
    conn: sqlite3.Connection | None = getattr(_thread_local, "_tl_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.Error:
            try:
                conn.close()
            except Exception:
                pass
            _thread_local._tl_conn = None   # type: ignore[attr-defined]

    conn = _open_raw_connection()
    _thread_local._tl_conn = conn         # type: ignore[attr-defined]
    return conn


class _ConnectionProxy:
    """Thin wrapper making ``close()`` a cheap ``commit()``."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self):
        return self._conn.cursor()

    def close(self):
        self._conn.commit()

    def real_close(self):
        try:
            self._conn.close()
        except Exception:
            pass
        _thread_local._tl_conn = None   # type: ignore[attr-defined]


def get_db() -> _ConnectionProxy:
    with _db_lock:
        return _ConnectionProxy(_get_thread_connection())


@contextmanager
def get_db_context():
    with _db_lock:
        conn = _get_thread_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def execute_query(query, params=None) -> int:
    with _db_lock:
        conn = _get_thread_connection()
        cur  = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        conn.commit()
        return cur.rowcount


def fetch_one(query, params=None):
    with _db_lock:
        conn = _get_thread_connection()
        cur  = conn.cursor()
        cur.execute(query, params) if params else cur.execute(query)
        row = cur.fetchone()
        conn.commit()
        return row


def fetch_all(query, params=None):
    with _db_lock:
        conn = _get_thread_connection()
        cur  = conn.cursor()
        cur.execute(query, params) if params else cur.execute(query)
        rows = cur.fetchall()
        conn.commit()
        return rows


def execute_transaction(operations) -> bool:
    with _db_lock:
        conn = _get_thread_connection()
        cur  = conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            for operation in operations:
                if isinstance(operation, tuple):
                    cur.execute(*operation)
                else:
                    cur.execute(operation)
            cur.execute("COMMIT")
            conn.commit()
            return True
        except Exception:
            cur.execute("ROLLBACK")
            conn.commit()
            raise


def clear_user_all_data(user_id: int) -> bool:
    """Mark a user as deleted without removing recoverable data."""
    try:
        execute_query(
            "UPDATE users SET deleted_at = ? WHERE user_id = ?",
            (datetime.utcnow().isoformat(), user_id),
        )
        log.info("Soft-deleted user %s", user_id)
        return True
    except Exception as exc:
        log.error("clear_user_all_data(%s): %s", user_id, exc)
        return False


async def soft_delete_user(user_id: int) -> None:
    """Mark user as deleted without removing data (recoverable for 30 days)."""
    execute_query(
        "UPDATE users SET deleted_at = ? WHERE user_id = ?",
        (datetime.utcnow().isoformat(), user_id),
    )
    log.info("Soft-deleted user %s", user_id)


async def restore_user(user_id: int) -> None:
    """Restore a soft-deleted user."""
    execute_query(
        "UPDATE users SET deleted_at = NULL WHERE user_id = ?",
        (user_id,),
    )


def verify_user_exists(user_id: int) -> bool:
    return fetch_one("SELECT 1 FROM users WHERE user_id=? AND deleted_at IS NULL", (user_id,)) is not None


def get_user_data_safe(user_id: int) -> dict | None:
    row = fetch_one(
        """
        SELECT height, gender, age, goal, current_weight,
               show_height, show_gender, show_age, show_weight, show_goal
        FROM users WHERE user_id=? AND deleted_at IS NULL
        """,
        (user_id,),
    )
    if row is None:
        return None
    return {
        "height": row[0],
        "gender": row[1],
        "age": row[2],
        "goal": row[3],
        "current_weight": row[4],
        "show_height": bool(row[5]) if row[5] is not None else True,
        "show_gender": bool(row[6]) if row[6] is not None else True,
        "show_age": bool(row[7]) if row[7] is not None else True,
        "show_weight": bool(row[8]) if row[8] is not None else True,
        "show_goal": bool(row[9]) if row[9] is not None else True,
    }


def init_db() -> None:
    conn = _open_raw_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            height INTEGER,
            gender TEXT,
            age INTEGER,
            goal TEXT,
            weekly_goal INTEGER,
            current_weight REAL DEFAULT 0,
            reminders_enabled INTEGER DEFAULT 1,
            language TEXT DEFAULT 'uk',
            coin_balance INTEGER DEFAULT 0,
            show_height INTEGER DEFAULT 1,
            show_gender INTEGER DEFAULT 1,
            show_age INTEGER DEFAULT 1,
            show_weight INTEGER DEFAULT 1,
            show_goal INTEGER DEFAULT 1,
            streak_days INTEGER DEFAULT 0,
            last_workout_date TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            deleted_at TEXT DEFAULT NULL
        )
        """
    )

    for name, definition in (
        ("height", "INTEGER"),
        ("gender", "TEXT"),
        ("age", "INTEGER"),
        ("goal", "TEXT"),
        ("weekly_goal", "INTEGER"),
        ("current_weight", "REAL DEFAULT 0"),
        ("reminders_enabled", "INTEGER DEFAULT 1"),
        ("language", "TEXT DEFAULT 'uk'"),
        ("coin_balance", "INTEGER DEFAULT 0"),
        ("show_height", "INTEGER DEFAULT 1"),
        ("show_gender", "INTEGER DEFAULT 1"),
        ("show_age", "INTEGER DEFAULT 1"),
        ("show_weight", "INTEGER DEFAULT 1"),
        ("show_goal", "INTEGER DEFAULT 1"),
        ("streak_days", "INTEGER DEFAULT 0"),
        ("last_workout_date", "TEXT"),
        ("xp", "INTEGER DEFAULT 0"),
        ("level", "INTEGER DEFAULT 1"),
        ("deleted_at", "TEXT DEFAULT NULL"),
    ):
        add_column_if_missing(cur, "users", name, definition)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            date TEXT,
            is_challenge INTEGER DEFAULT 0
        )
        """
    )
    add_column_if_missing(cur, "workouts", "is_challenge", "INTEGER DEFAULT 0")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            note TEXT
        )
        """
    )
    add_column_if_missing(cur, "workouts", "session_id", "INTEGER")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_workout_sessions_user_date ON workout_sessions(user_id, date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_workouts_session_id ON workouts(session_id)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            weight REAL,
            date TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id TEXT,
            purchased_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_tasks (
            user_id INTEGER,
            date TEXT,
            task_id TEXT,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS coin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            amount INTEGER NOT NULL,
            idem_key TEXT UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    for name, definition in (
        ("idem_key", "TEXT"),
        ("created_at", "TEXT"),
    ):
        try:
            add_column_if_missing(cur, "coin_rewards", name, definition)
        except sqlite3.OperationalError:
            pass
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_coin_rewards_user_date "
        "ON coin_rewards(user_id, date)"
    )

    conn.commit()
    conn.close()


def init_connection() -> None:
    _open_raw_connection().close()


def migrate_profile_gender_values() -> int:
    """Normalize legacy gender values to canonical 'male' / 'female'."""
    import re as _re
    db = get_db(); cur = db.cursor()
    changed = 0
    for row in cur.execute("SELECT user_id, gender FROM users WHERE deleted_at IS NULL"):
        uid, g = row
        if not g:
            continue
        gv = str(g).strip().lower()
        if gv in ("male", "female"):
            continue
        if gv in ("ч", "м") or "чолов" in gv or gv.startswith("man"):
            new = "male"
        elif gv in ("ж") or "жін" in gv or "жин" in gv or "woman" in gv:
            new = "female"
        else:
            continue
        cur.execute("UPDATE users SET gender=? WHERE user_id=?", (new, uid))
        changed += 1
    if changed:
        db.commit()
    db.close()
    return changed


# ── Streak helpers ───────────────────────────────────────────────────────────

def get_user_streak(user_id: int) -> dict:
    """Return ``{streak_days, last_workout_date}`` for *user_id*."""
    row = fetch_one(
        "SELECT streak_days, last_workout_date FROM users WHERE user_id=? AND deleted_at IS NULL",
        (user_id,),
    )
    if not row:
        return {"streak_days": 0, "last_workout_date": None}
    return {
        "streak_days":      int(row[0] or 0),
        "last_workout_date": row[1],
    }


# ── XP helpers ───────────────────────────────────────────────────────────────

def add_xp_to_user(user_id: int, amount: int) -> dict:
    """Add ``amount`` XP to *user_id* and return the updated state.

    The function also bumps the ``level`` column when XP crosses a threshold,
    powering the ``/level`` display.
    """
    from utils.levels import XP_TABLE, get_level_from_xp

    row = fetch_one(
        "SELECT COALESCE(xp, 0), COALESCE(level, 1) FROM users WHERE user_id=? AND deleted_at IS NULL",
        (user_id,),
    )
    if not row and not verify_user_exists(user_id):
        ensure_user_exists(user_id)
        current_xp, current_level = 0, 1
    elif row:
        current_xp, current_level = int(row[0]), int(row[1])
    else:
        current_xp, current_level = 0, 1

    total_xp   = current_xp + amount
    new_level  = get_level_from_xp(total_xp)
    leveled_up = new_level > current_level

    execute_query(
        "UPDATE users SET xp=?, level=? WHERE user_id=?",
        (total_xp, new_level, user_id),
    )

    return {
        "xp":         total_xp,
        "level":      new_level,
        "leveled_up": leveled_up,
        "added":      amount,
        "total_xp":   total_xp,
    }


def get_user_xp_level(user_id: int) -> dict:
    """Return ``{xp, level, total_xp}`` for *user_id*."""
    row = fetch_one(
        "SELECT COALESCE(xp, 0), COALESCE(level, 1) FROM users WHERE user_id=? AND deleted_at IS NULL",
        (user_id,),
    )
    if not row and not verify_user_exists(user_id):
        ensure_user_exists(user_id)
        return {"xp": 0, "level": 1, "total_xp": 0}
    if not row:
        return {"xp": 0, "level": 1, "total_xp": 0}
    from utils.levels import get_level_from_xp
    raw_xp = int(row[0])
    lvl    = int(row[1])
    effective_level = max(lvl, get_level_from_xp(raw_xp))
    return {"xp": raw_xp, "level": effective_level, "total_xp": raw_xp}


def acquire_single_instance_lock() -> None:
    import fcntl, os
    lock_path = os.path.join(os.path.dirname(DB_PATH), ".sportbot.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        globals()["_instance_lock_handle"] = fd
    except (IOError, OSError):
        try:
            os.close(fd)
        except Exception:
            pass
        raise RuntimeError(
            "Another instance of SportBot is already running. "
            f"Remove {lock_path} if this is a stale lock."
        )
