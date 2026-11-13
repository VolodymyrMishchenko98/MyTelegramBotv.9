"""Read-only aggregate queries for the admin analytics dashboard."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from db_improved import fetch_all
from services.achievements import ACHIEVEMENTS


PERIODS = (7, 30, 90)
CATEGORIES = {"users", "activity", "workouts", "economy", "progress"}


def _period_bounds(days: int, today: date) -> tuple[str, str, str, str]:
    if days not in PERIODS:
        raise ValueError(f"Unsupported analytics period: {days}")
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)
    previous_end = start - timedelta(days=1)
    return (
        start.isoformat(),
        today.isoformat(),
        previous_start.isoformat(),
        previous_end.isoformat(),
    )


def get_report(category: str, days: int = 30, today: date | None = None) -> dict[str, Any]:
    """Return one analytics section using the local calendar date."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown analytics category: {category}")
    today = today or date.today()

    if category == "users":
        rows = fetch_all(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END), 0),
                   AVG(CASE WHEN deleted_at IS NULL THEN COALESCE(level, 1) END)
            FROM users
            """
        )
        levels = fetch_all(
            """
            SELECT COALESCE(level, 1), COUNT(*)
            FROM users
            WHERE deleted_at IS NULL
            GROUP BY COALESCE(level, 1)
            ORDER BY COALESCE(level, 1)
            """
        )
        total, active, deleted, average_level = rows[0]
        return {
            "total": int(total or 0),
            "active": int(active or 0),
            "deleted": int(deleted or 0),
            "average_level": float(average_level or 0),
            "levels": [(int(level), int(count)) for level, count in levels],
        }

    if category == "progress":
        users = fetch_all(
            """
            SELECT AVG(COALESCE(level, 1)), AVG(COALESCE(xp, 0)),
                   COALESCE(MAX(COALESCE(level, 1)), 0), COUNT(*)
            FROM users
            WHERE deleted_at IS NULL
            """
        )[0]
        achievements = fetch_all(
            """
            SELECT achievement_key, COUNT(*)
            FROM achievements
            GROUP BY achievement_key
            ORDER BY COUNT(*) DESC, achievement_key
            LIMIT 5
            """
        )
        count = fetch_all("SELECT COUNT(*) FROM achievements")[0][0]
        return {
            "average_level": float(users[0] or 0),
            "average_xp": float(users[1] or 0),
            "max_level": int(users[2] or 0),
            "total_users": int(users[3] or 0),
            "achievements_count": int(count or 0),
            "top_achievements": [
                (key, ACHIEVEMENTS.get(key, {}).get("title_uk", key), int(amount))
                for key, amount in achievements
            ],
        }

    start, end, previous_start, previous_end = _period_bounds(days, today)
    if category == "activity":
        rows = fetch_all(
            """
            SELECT
                COUNT(DISTINCT CASE WHEN w.date BETWEEN ? AND ? THEN w.user_id END),
                COUNT(DISTINCT CASE WHEN w.date BETWEEN ? AND ? THEN w.date END),
                COUNT(DISTINCT CASE WHEN w.date BETWEEN ? AND ? THEN w.user_id END)
            FROM workouts AS w
            JOIN users AS u ON u.user_id = w.user_id
            WHERE u.deleted_at IS NULL
              AND (w.date BETWEEN ? AND ? OR w.date BETWEEN ? AND ?)
            """,
            (
                start, end, start, end, previous_start, previous_end,
                start, end, previous_start, previous_end,
            ),
        )[0]
        return {
            "active_users": int(rows[0] or 0),
            "training_days": int(rows[1] or 0),
            "previous_active_users": int(rows[2] or 0),
            "days": days,
        }

    if category == "workouts":
        row = fetch_all(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM workout_sessions AS s
                    JOIN users AS u ON u.user_id = s.user_id
                    WHERE u.deleted_at IS NULL AND s.date BETWEEN ? AND ?
                ) + (
                    SELECT COUNT(*)
                    FROM workouts AS w
                    JOIN users AS u ON u.user_id = w.user_id
                    WHERE u.deleted_at IS NULL
                      AND w.date BETWEEN ? AND ?
                      AND w.session_id IS NULL
                ) + (
                    SELECT COUNT(*)
                    FROM (
                        SELECT w.user_id, w.session_id
                        FROM workouts AS w
                        JOIN users AS u ON u.user_id = w.user_id
                        WHERE u.deleted_at IS NULL AND w.date BETWEEN ? AND ?
                          AND w.session_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM workout_sessions AS s
                              WHERE s.id = w.session_id AND s.user_id = w.user_id
                          )
                        GROUP BY w.user_id, w.session_id
                    )
                ),
                (
                    SELECT COUNT(*)
                    FROM workouts AS w
                    JOIN users AS u ON u.user_id = w.user_id
                    WHERE u.deleted_at IS NULL AND w.date BETWEEN ? AND ?
                ),
                (
                    SELECT COUNT(*)
                    FROM (
                        SELECT w.user_id,
                               COALESCE(w.session_id, -w.id) AS challenge_session
                        FROM workouts AS w
                        JOIN users AS u ON u.user_id = w.user_id
                        WHERE u.deleted_at IS NULL AND w.date BETWEEN ? AND ?
                          AND COALESCE(w.is_challenge, 0) = 1
                        GROUP BY w.user_id, COALESCE(w.session_id, -w.id)
                    )
                )
            """,
            (start, end, start, end, start, end, start, end, start, end),
        )[0]
        popular = fetch_all(
            """
            SELECT TRIM(text), COUNT(*)
            FROM workouts AS w
            JOIN users AS u ON u.user_id = w.user_id
            WHERE u.deleted_at IS NULL
              AND w.date BETWEEN ? AND ?
              AND text IS NOT NULL AND TRIM(text) != ''
            GROUP BY TRIM(text)
            ORDER BY COUNT(*) DESC, TRIM(text)
            LIMIT 5
            """,
            (start, end),
        )
        return {
            "sessions": int(row[0] or 0),
            "exercises": int(row[1] or 0),
            "challenge_sessions": int(row[2] or 0),
            "popular_exercises": [(name, int(count)) for name, count in popular],
            "days": days,
        }

    if category == "economy":
        balance = fetch_all(
            """
            SELECT COALESCE(SUM(COALESCE(coin_balance, 0)), 0),
                   AVG(COALESCE(coin_balance, 0)),
                   COALESCE(SUM(CASE WHEN COALESCE(coin_balance, 0) != 0 THEN 1 ELSE 0 END), 0)
            FROM users
            WHERE deleted_at IS NULL
            """
        )[0]
        rewards = fetch_all(
            """
            SELECT COALESCE(SUM(amount), 0), COUNT(*)
            FROM coin_rewards
            WHERE date BETWEEN ? AND ?
            """,
            (start, end),
        )[0]
        return {
            "balance": int(balance[0] or 0),
            "average_balance": float(balance[1] or 0),
            "users_with_balance": int(balance[2] or 0),
            "recorded_rewards": int(rewards[0] or 0),
            "reward_records": int(rewards[1] or 0),
            "days": days,
        }

    raise AssertionError("Unreachable analytics category")
