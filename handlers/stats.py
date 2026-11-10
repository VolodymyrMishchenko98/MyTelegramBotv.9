"""Compact statistics dashboard and its inline navigation."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from handlers.keyboards import chart_keyboard, style_block
from services.achievements import ACHIEVEMENTS
from services.workout_stats import (
    format_activity_calendar,
    load_personal_records,
    load_stats_data,
)
from utils.levels import get_progress_in_level, xp_for_next_level

router = Router()

_language_getter: Callable[[int], str] | None = None


def configure(get_user_language: Callable[[int], str]) -> None:
    """Inject the existing user-language lookup."""
    global _language_getter
    _language_getter = get_user_language


def _language_for(user_id: int) -> str:
    if _language_getter is None:
        from bot_legacy import get_user_language

        return get_user_language(user_id)
    return _language_getter(user_id)


def _pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en


def _ukrainian_plural(value: int, one: str, few: str, many: str) -> str:
    last_two = value % 100
    last = value % 10
    if last == 1 and last_two != 11:
        return one
    if 2 <= last <= 4 and not 12 <= last_two <= 14:
        return few
    return many


def _dashboard_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_pair(lang, "📅 Активність", "📅 Activity"),
                callback_data="stats_activity",
            ),
            InlineKeyboardButton(
                text=_pair(lang, "📈 Графіки", "📈 Charts"),
                callback_data="stats_charts",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_pair(lang, "🏅 Досягнення", "🏅 Achievements"),
                callback_data="stats_records",
            ),
            InlineKeyboardButton(
                text=_pair(lang, "📖 Історія", "📖 History"),
                callback_data="stats_history",
            ),
        ],
    ])


def _back_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=_pair(lang, "⬅️ До статистики", "⬅️ Back to stats"),
            callback_data="stats_home",
        )
    ]])


def _achievement_title(key: str | None, lang: str) -> str | None:
    achievement = ACHIEVEMENTS.get(key or "")
    if achievement is None:
        return None
    return achievement["title_uk"] if lang == "uk" else achievement["title_en"]


def _dashboard_text(data: dict, lang: str) -> str:
    activity = data["activity"]
    delta = activity["current_week_sessions"] - activity["previous_week_sessions"]
    if delta > 0:
        comparison = f"↑ +{delta}"
    elif delta < 0:
        comparison = _pair(
            lang,
            f"↓ на {abs(delta)}",
            f"↓ by {abs(delta)}",
        )
    else:
        comparison = _pair(lang, "→ без змін", "→ no change")

    level = data["level"]
    xp = data["xp"]
    next_level_xp = xp_for_next_level(level)
    if next_level_xp is None:
        progress = _pair(lang, "Максимальний рівень", "Maximum level")
    else:
        current_xp, required_xp = get_progress_in_level(level, xp)
        percent = min(100, int(current_xp / required_xp * 100)) if required_xp else 100
        filled = percent // 10
        bar = "█" * filled + "░" * (10 - filled)
        progress = _pair(
            lang,
            f"{bar} {current_xp}/{required_xp} XP · {percent}% до наступного",
            f"{bar} {current_xp}/{required_xp} XP · {percent}% to next",
        )

    streak_days = activity["current_streak"]
    best_streak = activity["best_streak"]
    current_day_word = (
        _ukrainian_plural(streak_days, "день", "дні", "днів")
        if lang == "uk"
        else "day" if streak_days == 1 else "days"
    )
    best_day_word = (
        _ukrainian_plural(best_streak, "день", "дні", "днів")
        if lang == "uk"
        else "day" if best_streak == 1 else "days"
    )
    workout_count = activity["current_week_sessions"]
    workout_word = (
        _ukrainian_plural(workout_count, "тренування", "тренування", "тренувань")
        if lang == "uk"
        else "workout" if workout_count == 1 else "workouts"
    )
    lines = [
        _pair(
            lang,
            f"🏋️ Цього тижня: {workout_count} {workout_word}",
            f"🏋️ This week so far: {workout_count} {workout_word}",
        ),
        _pair(
            lang,
            f"До тих самих днів минулого тижня: {comparison}",
            f"Compared with same days last week: {comparison}",
        ),
        _pair(
            lang,
            f"📅 Активні дні за 28 днів: {activity['days_28']}",
            f"📅 Active days in 28 days: {activity['days_28']}",
        ),
        _pair(
            lang,
            f"🔥 Серія: {streak_days} {current_day_word} · рекорд: {best_streak} {best_day_word}",
            f"🔥 Streak: {streak_days} {current_day_word} · best: {best_streak} {best_day_word}",
        ),
        _pair(lang, f"⭐ Рівень {level} · {xp} XP", f"⭐ Level {level} · {xp} XP"),
        progress,
    ]
    achievement = _achievement_title(data.get("last_achievement_key"), lang)
    if achievement:
        lines.append(_pair(lang, f"🏅 Останнє досягнення: {achievement}", f"🏅 Latest achievement: {achievement}"))
    return style_block("Моя статистика" if lang == "uk" else "My stats", "\n".join(lines), icon="📊")


def _empty_stats_text(lang: str) -> str:
    return style_block(
        _pair(lang, "Моя статистика", "My stats"),
        _pair(
            lang,
            "Після першого тренування тут з’являться тижневий прогрес, активні дні, серія та рівень.\n\nПочни з першого тренування!",
            "Your weekly progress, active days, streak, and level will appear here after your first workout.\n\nLog your first workout to get started!",
        ),
        icon="📊",
    )


def _empty_stats_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=_pair(lang, "💪 Записати тренування", "💪 Record a workout"),
            callback_data="welcome_workout",
        )
    ]])


async def send_stats(message: Message, user_id: int | None = None) -> None:
    """Send the dashboard, also used by the existing welcome-menu callback."""
    uid = user_id or message.from_user.id
    today = date.today()
    lang, data = await asyncio.gather(
        asyncio.to_thread(_language_for, uid),
        asyncio.to_thread(load_stats_data, uid, today),
    )
    if data["activity"]["total_sessions"] == 0:
        await message.answer(
            _empty_stats_text(lang),
            reply_markup=_empty_stats_keyboard(lang),
            parse_mode="HTML",
        )
        return
    await message.answer(
        _dashboard_text(data, lang),
        reply_markup=_dashboard_keyboard(lang),
        parse_mode="HTML",
    )


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    await send_stats(message)


@router.callback_query(F.data == "stats_activity")
async def stats_activity(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    uid = callback.from_user.id
    today = date.today()
    lang, data = await asyncio.gather(
        asyncio.to_thread(_language_for, uid),
        asyncio.to_thread(load_stats_data, uid, today),
    )
    start = today - timedelta(days=27)
    range_text = _pair(
        lang,
        f"📅 Активність за 28 днів ({start:%d.%m}–{today:%d.%m})",
        f"📅 Activity for 28 days ({start:%d.%m}–{today:%d.%m})",
    )
    count_text = _pair(
        lang,
        f"Днів із тренуваннями: {data['activity']['days_28']}/28",
        f"Days with workouts: {data['activity']['days_28']}/28",
    )
    calendar = format_activity_calendar(data["dates"], today, lang)
    await callback.message.edit_text(
        f"{range_text}\n{count_text}\n\n{calendar}",
        reply_markup=_back_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "stats_charts")
async def stats_charts(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    lang = await asyncio.to_thread(_language_for, callback.from_user.id)
    title = _pair(lang, "📈 Оберіть графік:", "📈 Choose a chart:")
    chart_markup = chart_keyboard(lang)
    chart_markup.inline_keyboard.append([
        InlineKeyboardButton(
            text=_pair(lang, "⬅️ До статистики", "⬅️ Back to stats"),
            callback_data="stats_home",
        )
    ])
    await callback.message.edit_text(title, reply_markup=chart_markup)


@router.callback_query(F.data == "stats_records")
async def stats_records(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    uid = callback.from_user.id
    lang, records = await asyncio.gather(
        asyncio.to_thread(_language_for, uid),
        asyncio.to_thread(load_personal_records, uid),
    )
    lines = []
    title = _achievement_title(records["last_achievement_key"], lang)
    if title:
        lines.append(_pair(lang, f"🏅 Останнє досягнення: {title}", f"🏅 Latest achievement: {title}"))
    if records["max_weight"] is not None:
        unit = "кг" if lang == "uk" else "kg"
        weight = f"{records['max_weight']:g} {unit}"
        lines.append(_pair(lang, f"⚖️ Найбільша записана вага тіла: {weight}", f"⚖️ Highest recorded body weight: {weight}"))
    elif not title:
        lines.append(_pair(lang, "Досягнень і записів ваги ще немає.", "No achievements or weight entries yet."))
    await callback.message.edit_text(
        style_block("Досягнення" if lang == "uk" else "Achievements", "\n".join(lines), icon="🏅"),
        reply_markup=_back_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "stats_history")
async def stats_history(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    from bot_legacy import _history_list_message

    await _history_list_message(callback, 0, callback.from_user.id)


@router.callback_query(F.data == "stats_home")
async def stats_home(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    uid = callback.from_user.id
    today = date.today()
    lang, data = await asyncio.gather(
        asyncio.to_thread(_language_for, uid),
        asyncio.to_thread(load_stats_data, uid, today),
    )
    await callback.message.edit_text(
        _dashboard_text(data, lang),
        reply_markup=_dashboard_keyboard(lang),
        parse_mode="HTML",
    )
