"""Pure streak service — returns data, does not send Telegram messages."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from db_improved import get_db, fetch_one
from services.logging_config import get_logger

log = get_logger("services.streak")

_STREAK_GAP_DAYS = 1

_STREAK_BONUS_COINS: dict[int, int] = {
    3: 10, 5: 20, 7: 30, 10: 40, 14: 50, 21: 75, 30: 100,
}
_STREAK_BONUS_XP: dict[int, int] = {
    3: 10, 5: 25, 7: 50, 10: 80, 14: 120, 21: 200, 30: 350,
}

_STREAK_XP_MULTIPLIERS: dict[int, float] = {
    7: 1.10, 14: 1.20, 21: 1.30, 30: 1.50,
}
_MAX_MULTIPLIER = 1.50


# ── helpers ───────────────────────────────────────────────────────────────

def _streak_xp_multiplier(days: int) -> float:
    mult = 1.0
    for threshold in sorted(_STREAK_XP_MULTIPLIERS):
        if days >= threshold:
            mult = _STREAK_XP_MULTIPLIERS[threshold]
        else:
            break
    return round(min(mult, _MAX_MULTIPLIER), 2)


def _get_bonus(days: int) -> tuple[int, int]:
    coins = next((c for t, c in sorted(_STREAK_BONUS_COINS.items(), reverse=True) if days >= t), 0)
    xp    = next((x for t, x in sorted(_STREAK_BONUS_XP.items(),   reverse=True) if days >= t), 0)
    return coins, xp


# ── public ────────────────────────────────────────────────────────────────

def calculate_current_streak(workout_dates: list[str]) -> int:
    """Calculate consecutive days count ending on today (or most recent day)."""
    used: set[str] = set(workout_dates)
    today = datetime.now().date()
    streak = 0
    while True:
        day = today - timedelta(days=streak)
        if day.strftime("%Y-%m-%d") in used:
            streak += 1
        else:
            break
    return streak


def get_user_streak_info(user_id: int) -> dict[str, Any]:
    """Return current streak info from the DB."""
    row = fetch_one(
        "SELECT streak_days, last_workout_date FROM users WHERE user_id=?",
        (user_id,),
    )
    if not row:
        return {"streak_days": 0, "last_workout_date": None}
    return {"streak_days": int(row[0] or 0), "last_workout_date": row[1]}


def update_streak_for_workout(user_id: int, workout_date: str) -> dict[str, Any]:
    """Update the streak after logging a workout for *workout_date*.

    Returns dict with:
        streak_days, bonus_coins, bonus_xp, xp_multiplier, is_new_streak
    """
    db  = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT streak_days, last_workout_date FROM users WHERE user_id=?",
        (user_id,),
    )
    row = cur.fetchone()
    prev_streak = int(row[0] or 0) if row else 0
    prev_date   = row[1] if row else None

    if prev_date == workout_date:
        curr_streak = prev_streak
        is_new      = False
    elif prev_date:
        gap = abs(
            (datetime.strptime(workout_date, "%Y-%m-%d")
             - datetime.strptime(prev_date,    "%Y-%m-%d")).days
        )
        if gap > _STREAK_GAP_DAYS:
            curr_streak = 1
            is_new      = True
        else:
            curr_streak = prev_streak + 1
            is_new      = True
    else:
        curr_streak = 1
        is_new      = True

    bonus_coins, bonus_xp = _get_bonus(curr_streak)
    xp_mult = _streak_xp_multiplier(curr_streak)

    cur.execute(
        "UPDATE users SET streak_days=?, last_workout_date=? WHERE user_id=?",
        (curr_streak, workout_date, user_id),
    )
    db.commit()
    db.close()

    log.debug("User %s streak: %d (bonus: %s coins, %s XP, mult=%.2f)",
              user_id, curr_streak, bonus_coins, bonus_xp, xp_mult)

    return {
        "streak_days":   curr_streak,
        "bonus_coins":   bonus_coins,
        "bonus_xp":      bonus_xp,
        "xp_multiplier": xp_mult,
        "is_new":        is_new,
    }
