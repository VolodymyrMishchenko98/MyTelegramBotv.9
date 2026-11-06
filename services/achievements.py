"""Achievement system: track and award user accomplishments."""
from __future__ import annotations

import sqlite3
from typing import Any

from db_improved import execute_query, fetch_one, fetch_all, get_db
from services.logging_config import get_logger

log = get_logger("services.achievements")

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    "first_workout": {
        "title_uk": "Перший крок",
        "title_en": "First Step",
        "desc_uk": "Перша тренування в боті",
        "desc_en": "First workout logged",
        "icon": "👣",
        "check": lambda stats: stats.get("workout_count", 0) >= 1,
    },
    "workout_warrior": {
        "title_uk": "Воїн тренувань",
        "title_en": "Workout Warrior",
        "desc_uk": "10 тренувань",
        "desc_en": "10 workouts completed",
        "icon": "⚔️",
        "check": lambda stats: stats.get("workout_count", 0) >= 10,
    },
    "century": {
        "title_uk": "Сотня",
        "title_en": "Century",
        "desc_uk": "100 тренувань",
        "desc_en": "100 workouts completed",
        "icon": "💯",
        "check": lambda stats: stats.get("workout_count", 0) >= 100,
    },
    "streak_3": {
        "title_uk": "Серія 3",
        "title_en": "Streak 3",
        "desc_uk": "3 дні підряд",
        "desc_en": "3 day streak",
        "icon": "🔥",
        "check": lambda stats: stats.get("max_streak", 0) >= 3,
    },
    "streak_7": {
        "title_uk": "Тижневий монстр",
        "title_en": "Week Warrior",
        "desc_uk": "7 днів підряд",
        "desc_en": "7 day streak",
        "icon": "🔥🔥",
        "check": lambda stats: stats.get("max_streak", 0) >= 7,
    },
    "streak_30": {
        "title_uk": "Місячний чемпіон",
        "title_en": "Monthly Champion",
        "desc_uk": "30 днів підряд",
        "desc_en": "30 day streak",
        "icon": "🔥👑",
        "check": lambda stats: stats.get("max_streak", 0) >= 30,
    },
    "level_5": {
        "title_uk": "Атлет",
        "title_en": "Athlete",
        "desc_uk": "Досягнуто рівня 5",
        "desc_en": "Reached level 5",
        "icon": "🏅",
        "check": lambda stats: stats.get("level", 1) >= 5,
    },
    "level_10": {
        "title_uk": "Спортсмен",
        "title_en": "Pro Athlete",
        "desc_uk": "Досягнуто рівня 10",
        "desc_en": "Reached level 10",
        "icon": "🏆",
        "check": lambda stats: stats.get("level", 1) >= 10,
    },
    "level_20": {
        "title_uk": "Еліта",
        "title_en": "Elite",
        "desc_uk": "Досягнуто рівня 20",
        "desc_en": "Reached level 20",
        "icon": "⭐",
        "check": lambda stats: stats.get("level", 1) >= 20,
    },
    "early_bird": {
        "title_uk": "Ранні пташки",
        "title_en": "Early Bird",
        "desc_uk": "Тренування до 8:00",
        "desc_en": "Workout before 8 AM",
        "icon": "🌅",
        "check": lambda stats: stats.get("early_workouts", 0) >= 1,
    },
    "night_owl": {
        "title_uk": "Нічна сова",
        "title_en": "Night Owl",
        "desc_uk": "Тренування після 22:00",
        "desc_en": "Workout after 10 PM",
        "icon": "🌙",
        "check": lambda stats: stats.get("late_workouts", 0) >= 1,
    },
}

# Rewards for achievements (coins, xp)
ACHIEVEMENT_REWARDS: dict[str, tuple[int, int]] = {
    "first_workout": (10, 20),
    "workout_warrior": (30, 50),
    "century": (100, 200),
    "streak_3": (20, 30),
    "streak_7": (50, 80),
    "streak_30": (200, 500),
    "level_5": (25, 40),
    "level_10": (60, 100),
    "level_20": (150, 300),
    "early_bird": (15, 20),
    "night_owl": (15, 20),
}


def _ensure_table_exists() -> None:
    execute_query("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            awarded_at TEXT NOT NULL,
            UNIQUE(user_id, achievement_key)
        )
    """)
    execute_query("""
        CREATE INDEX IF NOT EXISTS idx_achievements_user
        ON achievements(user_id)
    """)


def get_user_achievements(user_id: int) -> list[str]:
    _ensure_table_exists()
    rows = fetch_all(
        "SELECT achievement_key FROM achievements WHERE user_id = ?",
        (user_id,),
    )
    return [row[0] for row in rows]


def award_achievement(user_id: int, key: str) -> bool:
    """Award an achievement to user. Returns True if newly awarded."""
    _ensure_table_exists()
    
    try:
        execute_query(
            "INSERT INTO achievements (user_id, achievement_key, awarded_at) VALUES (?, ?, datetime('now'))",
            (user_id, key),
        )
        return True
    except Exception:
        return False


def check_and_award(user_id: int, stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Check all achievements and award newly unlocked ones."""
    _ensure_table_exists()
    current = set(get_user_achievements(user_id))
    awarded = []
    
    for key, ach in ACHIEVEMENTS.items():
        if key in current:
            continue
        if ach["check"](stats):
            if award_achievement(user_id, key):
                coins, xp = ACHIEVEMENT_REWARDS.get(key, (0, 0))
                if coins > 0:
                    execute_query(
                        "UPDATE users SET coin_balance=COALESCE(coin_balance,0)+? WHERE user_id=?",
                        (coins, user_id)
                    )
                if xp > 0:
                    from db_improved import add_xp_to_user
                    add_xp_to_user(user_id, xp)
                awarded.append({
                    "key": key,
                    "title_uk": ach["title_uk"],
                    "title_en": ach["title_en"],
                    "desc_uk": ach["desc_uk"],
                    "desc_en": ach["desc_en"],
                    "icon": ach["icon"],
                    "coins": coins,
                    "xp": xp,
                })
    return awarded


def get_user_stats(user_id: int) -> dict[str, Any]:
    """Get user statistics for achievement checking."""
    from db_improved import fetch_one
    
    row = fetch_one(
        """
        SELECT 
            (SELECT COUNT(*) FROM workouts WHERE user_id = ?) as workout_count,
            (SELECT COALESCE(MAX(streak_days), 0) FROM users WHERE user_id = ?) as max_streak,
            COALESCE(xp, 0) as xp,
            COALESCE(level, 1) as level
        """,
        (user_id, user_id),
    )
    
    workout_count = int(row[0]) if row else 0
    max_streak = int(row[1]) if row else 0
    level = int(row[3]) if row else 1
    
    # ``date`` is historically calendar-only (YYYY-MM-DD). Only rows with the
    # new nullable ``recorded_at`` timestamp can prove the time of day.
    try:
        early = fetch_one(
            "SELECT COUNT(*) FROM workouts WHERE user_id = ? "
            "AND recorded_at IS NOT NULL AND time(recorded_at) < '08:00:00'",
            (user_id,),
        )
        late = fetch_one(
            "SELECT COUNT(*) FROM workouts WHERE user_id = ? "
            "AND recorded_at IS NOT NULL AND time(recorded_at) >= '22:00:00'",
            (user_id,),
        )
    except sqlite3.OperationalError:
        # Legacy test/import databases may not have completed the nullable migration.
        early, late = (0,), (0,)
    
    return {
        "workout_count": workout_count,
        "max_streak": max_streak,
        "level": level,
        "early_workouts": int(early[0]) if early else 0,
        "late_workouts": int(late[0]) if late else 0,
    }


def get_achievement_list(user_id: int) -> list[dict[str, Any]]:
    """Get list of achievements with unlock status."""
    unlocked = set(get_user_achievements(user_id))
    result = []
    
    for key, ach in ACHIEVEMENTS.items():
        result.append({
            "key": key,
            "title_uk": ach["title_uk"],
            "title_en": ach["title_en"],
            "desc_uk": ach["desc_uk"],
            "desc_en": ach["desc_en"],
            "icon": ach["icon"],
            "unlocked": key in unlocked,
        })
    return result
