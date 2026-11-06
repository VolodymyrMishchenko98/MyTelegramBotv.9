"""Atomic settlement of one action's XP, coins, streak and achievements."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from db_improved import get_db
from game_config import STREAK_BONUSES, STREAK_XP_MULTIPLIERS, MAX_XP_MULTIPLIER
from services.achievements import ACHIEVEMENTS, ACHIEVEMENT_REWARDS
from utils.levels import get_level_from_xp


def _multiplier(days: int) -> float:
    value = 1.0
    for threshold in sorted(STREAK_XP_MULTIPLIERS):
        if days >= threshold:
            value = STREAK_XP_MULTIPLIERS[threshold]
        else:
            break
    return min(value, MAX_XP_MULTIPLIER)


def _ensure_achievement_table(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            awarded_at TEXT NOT NULL,
            UNIQUE(user_id, achievement_key)
        )
    """)


def settle_action_rewards(
    user_id: int,
    workout_date: str,
    xp_amount: int,
    coin_amount: int,
    coin_source: str,
    update_streak: bool = True,
    action_key: str | None = None,
) -> dict[str, Any]:
    """Apply all rewards for one completed action in one SQLite transaction."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coin_rewards (
                user_id INTEGER NOT NULL, date TEXT NOT NULL, source TEXT NOT NULL,
                amount INTEGER NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(user_id, date, source)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reward_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                action_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, source, action_key)
            )
        """)
        cur.execute("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (user_id,))
        event_key = action_key or f"{coin_source}:{workout_date}"
        cur.execute(
            "INSERT OR IGNORE INTO reward_events (user_id, source, action_key, created_at) VALUES (?,?,?,?)",
            (user_id, coin_source, event_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        if cur.rowcount == 0:
            cur.execute("SELECT COALESCE(xp,0), COALESCE(level,1), COALESCE(streak_days,0) FROM users WHERE user_id=?", (user_id,))
            current_xp, current_level, current_streak = cur.fetchone()
            cur.execute("SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?", (user_id,))
            current_balance = int(cur.fetchone()[0])
            db.commit()
            return {
                "user_id": user_id, "xp": int(current_xp), "xp_awarded": 0,
                "level": int(current_level), "leveled_up": False,
                "streak_days": int(current_streak), "streak_bonus_coins": 0,
                "streak_bonus_xp": 0, "coins_awarded": 0, "balance": current_balance,
                "achievements": [], "already_settled": True,
            }
        cur.execute(
            "SELECT COALESCE(xp,0), COALESCE(level,1), COALESCE(streak_days,0), last_workout_date "
            "FROM users WHERE user_id=?",
            (user_id,),
        )
        old_xp, old_level, previous_streak, previous_date = cur.fetchone()

        if not update_streak:
            streak_days = previous_streak
            is_new_streak_day = False
        elif previous_date == workout_date:
            streak_days = previous_streak
            is_new_streak_day = False
        elif previous_date:
            gap = (datetime.strptime(workout_date, "%Y-%m-%d") -
                   datetime.strptime(previous_date, "%Y-%m-%d")).days
            streak_days = previous_streak + 1 if gap <= 1 else 1
            is_new_streak_day = True
        else:
            streak_days = 1
            is_new_streak_day = True

        base_xp = round(xp_amount * _multiplier(streak_days))
        bonus_coins, bonus_xp = STREAK_BONUSES.get(streak_days, (0, 0)) if is_new_streak_day else (0, 0)
        total_xp = base_xp + bonus_xp
        new_xp = int(old_xp) + total_xp
        new_level = get_level_from_xp(new_xp)

        if update_streak:
            cur.execute(
                "UPDATE users SET xp=?, level=?, streak_days=?, last_workout_date=? WHERE user_id=?",
                (new_xp, new_level, streak_days, workout_date, user_id),
            )
        else:
            cur.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (new_xp, new_level, user_id))

        action_coins = 0
        if coin_amount > 0:
            cur.execute(
                "INSERT OR IGNORE INTO coin_rewards (user_id,date,source,amount,created_at) VALUES (?,?,?,?,?)",
                (user_id, workout_date, coin_source, coin_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            if cur.rowcount == 1:
                action_coins = coin_amount

        total_coins = action_coins + bonus_coins
        if total_coins:
            cur.execute(
                "UPDATE users SET coin_balance=COALESCE(coin_balance,0)+? WHERE user_id=?",
                (total_coins, user_id),
            )

        _ensure_achievement_table(cur)
        cur.execute("SELECT achievement_key FROM achievements WHERE user_id=?", (user_id,))
        already_awarded = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (user_id,))
        workout_count = int(cur.fetchone()[0])
        early = late = 0
        try:
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=? AND recorded_at IS NOT NULL AND time(recorded_at) < '08:00:00'", (user_id,))
            early = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=? AND recorded_at IS NOT NULL AND time(recorded_at) >= '22:00:00'", (user_id,))
            late = int(cur.fetchone()[0])
        except Exception:
            # A legacy database without the nullable timestamp cannot prove time.
            early = late = 0

        stats = {
            "workout_count": workout_count,
            "max_streak": int(streak_days),
            "level": int(new_level),
            "early_workouts": early,
            "late_workouts": late,
        }
        new_achievements = []
        for key, achievement in ACHIEVEMENTS.items():
            if key in already_awarded or not achievement["check"](stats):
                continue
            cur.execute(
                "INSERT OR IGNORE INTO achievements (user_id, achievement_key, awarded_at) VALUES (?,?,?)",
                (user_id, key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            if cur.rowcount != 1:
                continue
            achievement_coins, achievement_xp = ACHIEVEMENT_REWARDS.get(key, (0, 0))
            if achievement_coins:
                cur.execute("UPDATE users SET coin_balance=COALESCE(coin_balance,0)+? WHERE user_id=?", (achievement_coins, user_id))
                total_coins += achievement_coins
            if achievement_xp:
                new_xp += achievement_xp
                new_level = get_level_from_xp(new_xp)
                cur.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (new_xp, new_level, user_id))
            new_achievements.append({**achievement, "key": key, "coins": achievement_coins, "xp": achievement_xp})

        cur.execute("SELECT COALESCE(coin_balance,0) FROM users WHERE user_id=?", (user_id,))
        balance = int(cur.fetchone()[0])
        db.commit()
        return {
            "user_id": user_id,
            "xp": new_xp,
            "xp_awarded": total_xp,
            "level": new_level,
            "leveled_up": new_level > int(old_level),
            "streak_days": streak_days,
            "streak_bonus_coins": bonus_coins,
            "streak_bonus_xp": bonus_xp,
            "coins_awarded": total_coins,
            "balance": balance,
            "achievements": new_achievements,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
