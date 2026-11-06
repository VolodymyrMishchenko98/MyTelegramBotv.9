"""Economy service — coins wallet, shop purchases, idempotent reward settlement."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from game_config import SHOP_ITEMS
from db_improved import get_db, fetch_one, fetch_all, execute_query

from services.logging_config import get_logger

log = get_logger("services.economy")


def _load_shop_items() -> None:
    return None


# ── coin wallet ────────────────────────────────────────────────────────────

def get_balance(user_id: int) -> int:
    row = fetch_one(
        """
        INSERT INTO users (user_id) VALUES (?)
        ON CONFLICT(user_id) DO UPDATE SET user_id=excluded.user_id
        RETURNING COALESCE(coin_balance, 0)
        """,
        (user_id,),
    )
    return int(row[0]) if row else 0


def add_coins(user_id: int, amount: int) -> int:
    execute_query(
        "UPDATE users SET coin_balance = COALESCE(coin_balance,0) + ? WHERE user_id=?",
        (amount, user_id),
    )
    return get_balance(user_id)


# ── idempotency key ────────────────────────────────────────────────────────

def reward_idempotency_key(user_id: int, date: str, source: str) -> str:
    """Deterministic key so repeated callbacks cannot give a double reward."""
    return f"{user_id}:{date}:{source}"


def settle_reward(
    user_id: int,
    source: str,
    amount: int,
    idem_key: str,
    today: str | None = None,
) -> tuple[bool, int]:
    """Debit/credit coins for *source* only if *idem_key* has not been used before.

    Returns ``(awarded, new_balance)``.
    Always idempotent — safe to call twice from two concurrent callbacks.
    """
    assert amount > 0
    today = today or datetime.now().strftime("%Y-%m-%d")

    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        # idempotency check: insert-and-forget, then check rowcount
        cur.execute(
            """
            INSERT OR IGNORE INTO coin_rewards (user_id, date, source, amount, idem_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, today, source, amount, idem_key,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        if cur.rowcount == 0:
            db.commit()
            return False, fetch_one(
                "SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?",
                (user_id,),
            )[0]

        cur.execute(
            "UPDATE users SET coin_balance = COALESCE(coin_balance,0) + ? WHERE user_id=?",
            (amount, user_id),
        )
        db.commit()
        balance_row = fetch_one(
            "SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?",
            (user_id,),
        )
        return True, int(balance_row[0]) if balance_row else 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.real_close()


# ── spend coins ────────────────────────────────────────────────────────────

def spend_coins(user_id: int, amount: int) -> int:
    """Spend *amount* coins; return new balance (or old balance if insufficient)."""
    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            """
            UPDATE users
            SET coin_balance = COALESCE(coin_balance,0) - ?
            WHERE user_id=? AND COALESCE(coin_balance,0) >= ?
            """,
            (amount, user_id, amount),
        )
        if cur.rowcount == 0:
            row = fetch_one(
                "SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?",
                (user_id,),
            )
            return int(row[0]) if row else 0
        db.commit()
        row = fetch_one(
            "SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?",
            (user_id,),
        )
        return int(row[0]) if row else 0
    finally:
        db.close()


# ── purchase ───────────────────────────────────────────────────────────────

def add_user_item(user_id: int, item_id: str) -> None:
    execute_query(
        "INSERT INTO user_items (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
        (user_id, item_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )


def get_user_items(user_id: int) -> dict[str, int]:
    rows = fetch_all(
        "SELECT item_id, COUNT(*) FROM user_items WHERE user_id=? GROUP BY item_id",
        (user_id,),
    )
    return {r[0]: r[1] for r in rows} if rows else {}


def buy_item(user_id: int, item_id: str, required_level: int) -> dict[str, Any]:
    """Buy a shop item with full transaction safety.

    Returns ``{"ok": bool, "balance": int, "balance": int, "status": str}``
    where status is one of: ``success | insufficient_coins | level_locked | limit_exceeded | error``.
    """
    _load_shop_items()
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return {"ok": False, "balance": get_balance(user_id), "status": "error"}

    user_lvl = fetch_one(
        "SELECT COALESCE(level,1) FROM users WHERE user_id=?", (user_id,),
    )
    user_lvl = int(user_lvl[0]) if user_lvl else 1

    if user_lvl < required_level:
        return {"ok": False, "balance": get_balance(user_id), "status": "level_locked"}

    cost   = int(item.get("cost", 0))
    limit  = item.get("max_count")

    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")

        if limit:
            cur.execute(
                "SELECT COUNT(*) FROM user_items WHERE user_id=? AND item_id=?",
                (user_id, item_id),
            )
            if int((cur.fetchone() or [0])[0]) >= limit:
                bal = get_balance(user_id)
                db.rollback()
                return {"ok": False, "balance": bal, "status": "limit_exceeded"}

        cur.execute(
            """
            UPDATE users
            SET coin_balance = COALESCE(coin_balance,0) - ?
            WHERE user_id=? AND COALESCE(coin_balance,0) >= ?
            RETURNING COALESCE(coin_balance,0)
            """,
            (cost, user_id, cost),
        )
        row = cur.fetchone()
        if not row:
            bal = get_balance(user_id)
            db.rollback()
            return {"ok": False, "balance": bal, "status": "insufficient_coins"}

        balance = int(row[0])
        add_user_item(user_id, item_id)
        db.commit()
        return {"ok": True, "balance": balance, "status": "success"}
    except Exception as exc:
        db.rollback()
        log.error("buy_item %s failed for user %s: %s", item_id, user_id, exc)
        return {"ok": False, "balance": get_balance(user_id), "status": "error"}
    finally:
        db.close()
