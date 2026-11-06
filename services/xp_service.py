"""Pure XP service — returns data, does not send Telegram messages."""
from __future__ import annotations

from typing import Any

from db_improved import get_db, execute_query, fetch_one, add_xp_to_user
from services.logging_config import get_logger
from utils.levels import get_rank, xp_for_next_level, total_xp_for_level, get_progress_in_level

log = get_logger("services.xp")

WORKOUT_XP_REWARD    = 10
DAILY_TASK_XP_REWARD = 15
SUGGESTED_XP_REWARD  = 20
CHALLENGE_XP_REWARD  = 15


# ── public ────────────────────────────────────────────────────────────────

def get_xp_info(user_id: int) -> dict[str, Any]:
    """Return the current XP / level / rank for *user_id*."""
    info = get_user_xp_level(user_id)
    lvl  = info.get("level", 1)
    xp   = info.get("xp", 0)
    rank_uk, rank_en = get_rank(lvl)
    xp_needed = xp_for_next_level(lvl)

    cur_xp_in_lvl, xp_need = get_progress_in_level(lvl, xp)
    pct = int(cur_xp_in_lvl / xp_need * 100) if xp_need else 100

    return {
        "level":     lvl,
        "xp":        xp,
        "rank_uk":   rank_uk,
        "rank_en":   rank_en,
        "xp_needed": xp_needed,
        "xp_to_next": xp_needed - cur_xp_in_lvl if xp_needed else 0,
        "pct":       pct,
        "full":      info,
    }


def award_xp(user_id: int, amount: int) -> dict[str, Any]:
    """Add XP and return the new level state."""
    return add_xp_to_user(user_id, amount)


def level_from_xp(xp: int) -> int:
    from utils.levels import get_level_from_xp
    return get_level_from_xp(xp)
