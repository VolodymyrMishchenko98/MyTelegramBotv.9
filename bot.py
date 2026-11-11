"""SportBot runtime facade.

The historical handlers are preserved in ``bot_legacy`` while the remaining
split is completed module by module. This file stays small and owns the public
entry point expected by deploy scripts and tests.
"""
from __future__ import annotations

import asyncio

from game_config import (
    SHOP_ITEMS,
)
from locales import pick_lang, t, t_pair

MAX_POWER_PLANS = 3
MAX_MOTIVATION_PACKS = 2
MAX_COIN_BOOSTERS = 1
MAX_RESTORE_TOKENS = 2

from bot_legacy import (
    bot,
    dp,
    get_user_language,
    set_user_state,
    get_user_state,
    clear_user_state,
    invalidate_language_cache,
    main,
    DEVELOPER_CHAT_ID,
    welcome_keyboard,
    set_user_language,
    toggle_user_language,
)
from handlers import admin, calories, daily, developer, profile, reminders, shop, stats, workouts

workouts.configure(get_user_language, set_user_state, t_pair)
stats.configure(get_user_language)
developer.configure(
    get_user_language,
    get_user_state,
    set_user_state,
    clear_user_state,
    welcome_keyboard,
    DEVELOPER_CHAT_ID,
)

for router in (
    reminders.router,
    shop.router,
    profile.router,
    workouts.router,
    calories.router,
    daily.router,
    stats.router,
    developer.router,
    admin.router,
):
    dp.include_router(router)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
