"""
Register all bot handlers.

Each sub-module exposes a single ``register(dp, …)`` function that receives
the dispatcher plus the handful of injection points it needs.

``register_all`` is the only call-site — ``bot.py`` calls this once.
"""
from __future__ import annotations

from aiogram import Dispatcher


def register_all(dp: Dispatcher) -> None:
    """Register every handler group on *dp* in dependency order."""

    # ── shared dependencies ───────────────────────────────────────────────
    import game_config                         # constants → no db access
    from db_improved   import (get_db, execute_query, fetch_one, fetch_all,
                               add_xp_to_user, get_user_xp_level,
                               get_user_streak)
    from daily_tasks   import DAILY_TASKS, DEFAULT_DAILY_TASK_ID
    from profile_visibility import (
        get_profile_visibility, set_field_visibility, toggle_field_visibility,
        get_visible_fields, is_field_visible, ensure_user_exists, PROFILE_FIELDS,
    )

    # ── getters used by handlers ───────────────────────────────────────────
    def get_user_language(uid: int) -> str:
        from bot import _lang_cache
        cached = _lang_cache.get(uid)
        if cached in ("uk", "en"):
            return cached
        row = fetch_one("SELECT language FROM users WHERE user_id=?", (uid,))
        if row and row[0] in ("uk", "en"):
            _lang_cache[uid] = row[0]
            return row[0]
        _lang_cache[uid] = "uk"
        return "uk"

    def t_pair(lang: str, uk: str, en: str) -> str:
        return uk if lang == "uk" else en

    async def send_photo(chat_id: int, photo, caption: str = "") -> None:
        from aiogram import Bot
        bot: Bot = dp["_bot"]
        await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)

    # Attach bot ref so charts can use send_photo via closure
    dp["_bot"] = None   # replaced by bot.py after constructing Bot

    # ── handlers ───────────────────────────────────────────────────────────
    from handlers.charts   import register as _reg_charts
    from handlers.general  import register as _reg_general
    from handlers.workouts import register as _reg_workouts
    from handlers.tasks    import register as _reg_tasks
    from handlers.shop     import register as _reg_shop
    from handlers.diet     import register as _reg_diet
    from handlers.profile  import register as _reg_profile
    from handlers.level    import register as _reg_level

    _reg_charts(dp, get_user_language, send_photo)
    _reg_general(dp, get_user_language, t_pair)
    _reg_workouts(dp, get_user_language, t_pair, get_db, execute_query,
                  fetch_one, add_xp_to_user, get_user_xp_level, get_user_streak)
    _reg_tasks(dp, get_user_language, t_pair, get_db, fetch_one, fetch_all,
               DAILY_TASKS, DEFAULT_DAILY_TASK_ID)
    _reg_shop(dp, get_user_language, t_pair, get_db, fetch_one, fetch_all)
    _reg_diet(dp, get_user_language, t_pair, get_db)
    _reg_profile(dp, get_user_language, t_pair, get_db)
    _reg_level(dp, get_user_language, t_pair, get_db)
