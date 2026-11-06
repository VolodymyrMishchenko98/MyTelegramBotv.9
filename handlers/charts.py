"""Chart command and 4 chart-type callbacks.

All errors go through log.error(); nothing is silently swallowed.
"""
from __future__ import annotations

import traceback as _tb

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import game_config
from services.charts import (
    weight_chart   as _weight_chart,
    workout_chart  as _workout_chart,
    streak_chart   as _streak_chart,
    volume_chart   as _volume_chart,
)
from services.logging_config import get_logger
from db_improved import fetch_all as _chart_fetch_all

log = get_logger("handlers.charts")

_CHART_MAP: dict[str, tuple[str, str]] = {
    "chart_weight":   ("⚖️ Зміна ваги",     "⚖️ Weight change"),
    "chart_workouts": ("🏋️ Тренування",      "🏋️ Workouts"),
    "chart_streak":   ("🔥 Серія днів",       "🔥 Training streak"),
    "chart_volume":   ("📦 Обсяг тренувань",  "📦 Training volume"),
}

_CHART_FN: dict[str, object] = {
    "chart_weight":   _weight_chart,
    "chart_workouts": _workout_chart,
    "chart_streak":   _streak_chart,
    "chart_volume":   _volume_chart,
}


def register(dp, get_user_language):
    """Register all chart-related handlers on *dp*."""

    @dp.message(Command("chart"))
    async def chart_cmd(message: Message):
        lang = get_user_language(message.from_user.id)
        from handlers.keyboards  import chart_keyboard
        await message.answer(
            "📊 Оберіть графік:" if lang == "uk" else "📊 Pick a chart:",
            reply_markup=chart_keyboard(lang),
        )

    for cb_data, (cap_uk, cap_en) in _CHART_MAP.items():
        chart_fn = _CHART_FN[cb_data]

        # Capture per-iteration values via default args
        @dp.callback_query(F.data == cb_data)
        async def chart_callback(
            callback: CallbackQuery,
            _fn   = chart_fn,
            _uk   = cap_uk,
            _en   = cap_en,
            _key  = cb_data,
        ) -> None:
            uid     = callback.from_user.id
            lang    = get_user_language(uid)
            chat_id = callback.message.chat.id if callback.message else uid
            try:
                buf  = _fn(uid, _chart_fetch_all)
                cap  = _uk if lang == "uk" else _en
                await callback.bot.send_photo(chat_id=chat_id, photo=buf, caption=cap)
            except Exception as exc:
                log.error(
                    "[chart %s] user=%s chat=%s: %s\n%s",
                    _key, uid, chat_id, exc, _tb.format_exc(),
                )
                err_uk = "❌ Не вдалося згенерувати графік."
                err_en = "❌ Failed to generate chart."
                try:
                    await callback.message.answer(err_uk if lang == "uk" else err_en)
                except Exception:
                    pass
            finally:
                await callback.answer()
