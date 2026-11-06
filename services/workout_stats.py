"""Pure aggregate calculations for workout statistics."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Iterable


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


def summarize_workouts(
    rows: list[tuple[str, str, int | None]],
    today: date | None = None,
) -> dict:
    """Aggregate ``(YYYY-MM-DD, text, session_id)`` rows without double counting."""
    today = today or date.today()
    current_week_start = today - timedelta(days=today.weekday())
    previous_week_start = current_week_start - timedelta(days=7)
    month_start = today.replace(day=1)

    def in_range(value: str, start: date, end: date) -> bool:
        try:
            current = date.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        return start <= current < end

    current_week = [row for row in rows if in_range(row[0], current_week_start, today + timedelta(days=1))]
    previous_week = [row for row in rows if in_range(row[0], previous_week_start, current_week_start)]
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
