"""Pure aggregate calculations for workout statistics."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Iterable

from db_improved import fetch_all, fetch_one
from utils.streak import calculate_best_streak, calculate_streak


_SESSION_ROWS_QUERY = """
    SELECT date, 's:' || CAST(id AS TEXT) AS session_key
    FROM workout_sessions
    WHERE user_id = ?
    UNION
    SELECT w.date,
           'w:' || CAST(w.id AS TEXT) AS session_key
    FROM workouts AS w
    WHERE w.user_id = ?
      AND w.session_id IS NULL
    UNION
    SELECT MIN(w.date), 's:' || CAST(w.session_id AS TEXT) AS session_key
    FROM workouts AS w
    WHERE w.user_id = ?
      AND w.session_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM workout_sessions AS s
          WHERE s.id = w.session_id AND s.user_id = w.user_id
      )
    GROUP BY w.session_id
"""


def _normalize_exercise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _count_sessions(rows: Iterable[tuple[str, str, int | None]]) -> int:
    session_ids: set[int] = set()
    legacy_count = 0
    for _, _, session_id in rows:
        if session_id is None:
            legacy_count += 1
        else:
            session_ids.add(int(session_id))
    return len(session_ids) + legacy_count


def _parse_workout_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def build_activity_calendar(
    workout_dates: Iterable[str | None],
    today: date | None = None,
) -> list[list[tuple[date, bool]]]:
    """Return the last 28 local calendar days in four chronological weeks."""
    today = today or date.today()
    trained_dates = {
        parsed
        for value in workout_dates
        if (parsed := _parse_workout_date(value)) is not None and parsed <= today
    }
    start = today - timedelta(days=27)
    days = [
        (start + timedelta(days=offset), start + timedelta(days=offset) in trained_dates)
        for offset in range(28)
    ]
    return [days[offset:offset + 7] for offset in range(0, 28, 7)]


def format_activity_calendar(
    workout_dates: Iterable[str | None],
    today: date | None = None,
    lang: str = "uk",
) -> str:
    """Render a compact, localized 4x7 activity calendar."""
    today = today or date.today()
    weeks = build_activity_calendar(workout_dates, today)
    week_label = "Тиждень" if lang == "uk" else "Week"
    weekday_labels = (
        ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд")
        if lang == "uk"
        else ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    )
    month_labels = (
        ("січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру")
        if lang == "uk"
        else ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    )
    marker = (
        "● — тренування · — день без запису"
        if lang == "uk"
        else "● — workout · — no workout recorded"
    )
    first_day = weeks[0][0][0]
    headers = [
        weekday_labels[(first_day.weekday() + offset) % 7]
        for offset in range(7)
    ]
    lines = [
        " ".join(headers)
    ]
    for index, week in enumerate(weeks, 1):
        start, end = week[0][0], week[-1][0]
        start_label = f"{start.day:02d} {month_labels[start.month - 1]}"
        end_label = f"{end.day:02d} {month_labels[end.month - 1]}"
        date_range = (
            f"{start.day:02d}–{end.day:02d} {month_labels[end.month - 1]}"
            if start.month == end.month
            else f"{start_label}–{end_label}"
        )
        cells = [
            f"{day.day:02d}{'●' if trained else '·'}"
            for day, trained in week
        ]
        today_index = next(
            (offset for offset, (day, _) in enumerate(week) if day == today),
            None,
        )
        if today_index is not None:
            cells[today_index] = f"<b>{cells[today_index]}</b>"
        lines.append(
            f"{week_label} {index} ({date_range}): " + " ".join(cells)
        )
    return "\n".join((*lines, marker))


def summarize_activity(
    session_rows: Iterable[tuple[str | None, str | None]],
    today: date | None = None,
) -> dict[str, int]:
    """Summarize canonical sessions without treating exercise rows as sessions."""
    today = today or date.today()
    sessions: dict[str, date] = {}
    for workout_date, session_key in session_rows:
        parsed = _parse_workout_date(workout_date)
        if parsed is not None and session_key:
            key = str(session_key)
            if key not in sessions or parsed < sessions[key]:
                sessions[key] = parsed

    current_week_start = today - timedelta(days=today.weekday())
    previous_week_start = current_week_start - timedelta(days=7)
    elapsed_days = today.weekday() + 1
    current_period_end = current_week_start + timedelta(days=elapsed_days)
    previous_period_end = previous_week_start + timedelta(days=elapsed_days)
    recent_start = today - timedelta(days=27)

    valid_dates = [workout_date for workout_date in sessions.values() if workout_date <= today]
    recent_dates = {workout_date for workout_date in valid_dates if workout_date >= recent_start}

    return {
        "total_sessions": len(valid_dates),
        "current_week_sessions": sum(
            current_week_start <= workout_date < current_period_end
            for workout_date in sessions.values()
        ),
        "previous_week_sessions": sum(
            previous_week_start <= workout_date < previous_period_end
            for workout_date in sessions.values()
        ),
        "days_28": len(recent_dates),
        "current_streak": calculate_streak(
            None,
            [workout_date.isoformat() for workout_date in valid_dates],
            today=today,
        ),
        "best_streak": calculate_best_streak(
            [workout_date.isoformat() for workout_date in valid_dates]
        ),
    }


def load_workout_sessions(user_id: int) -> list[tuple[str | None, str | None]]:
    """Load each session once, including separate rows for legacy workouts."""
    return fetch_all(_SESSION_ROWS_QUERY, (user_id, user_id, user_id))


def load_stats_data(user_id: int, today: date | None = None) -> dict:
    """Load the small data set needed by the statistics dashboard."""
    sessions = load_workout_sessions(user_id)
    activity = summarize_activity(sessions, today)
    user = fetch_one(
        "SELECT COALESCE(level, 1), COALESCE(xp, 0) FROM users "
        "WHERE user_id = ? AND deleted_at IS NULL",
        (user_id,),
    )
    achievement = fetch_one(
        "SELECT achievement_key FROM achievements "
        "WHERE user_id = ? ORDER BY awarded_at DESC, id DESC LIMIT 1",
        (user_id,),
    )
    return {
        "activity": activity,
        "dates": [workout_date for workout_date, _ in sessions],
        "level": int(user[0]) if user else 1,
        "xp": int(user[1]) if user else 0,
        "last_achievement_key": achievement[0] if achievement else None,
    }


def load_personal_records(user_id: int) -> dict:
    """Return only persisted achievements and a genuine body-weight maximum."""
    achievement = fetch_one(
        "SELECT achievement_key FROM achievements "
        "WHERE user_id = ? ORDER BY awarded_at DESC, id DESC LIMIT 1",
        (user_id,),
    )
    weight = fetch_one(
        "SELECT MAX(weight) FROM weights WHERE user_id = ? AND weight > 0",
        (user_id,),
    )
    return {
        "last_achievement_key": achievement[0] if achievement else None,
        "max_weight": float(weight[0]) if weight and weight[0] is not None else None,
    }


def summarize_workouts(
    rows: list[tuple[str, str, int | None]],
    today: date | None = None,
) -> dict:
    """Aggregate ``(YYYY-MM-DD, text, session_id)`` rows without double counting."""
    today = today or date.today()
    current_week_start = today - timedelta(days=today.weekday())
    previous_week_start = current_week_start - timedelta(days=7)
    previous_period_end = previous_week_start + timedelta(days=today.weekday() + 1)
    month_start = today.replace(day=1)

    def in_range(value: str, start: date, end: date) -> bool:
        try:
            current = date.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        return start <= current < end

    current_week = [row for row in rows if in_range(row[0], current_week_start, today + timedelta(days=1))]
    previous_week = [row for row in rows if in_range(row[0], previous_week_start, previous_period_end)]
    current_month = [row for row in rows if in_range(row[0], month_start, today + timedelta(days=1))]

    popular = Counter()
    display_names: dict[str, str] = {}
    for _, text, _ in rows:
        normalized = _normalize_exercise(text)
        if normalized:
            popular[normalized] += 1
            display_names.setdefault(normalized, re.sub(r"\s+", " ", str(text).strip()))
    popular_name = None
    popular_count = 0
    if popular:
        popular_name, popular_count = popular.most_common(1)[0]

    return {
        "total_sessions": _count_sessions(rows),
        "total_exercises": len(rows),
        "current_week_sessions": _count_sessions(current_week),
        "previous_week_sessions": _count_sessions(previous_week),
        "current_month_sessions": _count_sessions(current_month),
        "popular_exercise": display_names.get(popular_name) if popular_name else None,
        "popular_exercise_count": popular_count,
    }
