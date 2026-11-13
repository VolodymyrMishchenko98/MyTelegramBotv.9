"""handlers/admin.py - Admin-only commands."""
from __future__ import annotations

import asyncio
from html import escape
import os
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from db_improved import fetch_one
from services.logging_config import get_logger
from services import admin_analytics
from backup_service import create_backup

log = get_logger("handlers.admin")
router = Router()

ADMIN_IDS: set[int] = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


_ANALYTICS_LABELS = {
    "users": "👥 Пользователи",
    "activity": "🏃 Активность",
    "workouts": "💪 Тренировки",
    "economy": "🪙 Экономика",
    "progress": "🏆 Прогресс",
}


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📊 Аналитика", callback_data="admin_analytics:menu:30"),
    ]])


def _analytics_keyboard(days: int, category: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if category is None:
        categories = list(_ANALYTICS_LABELS)
        rows.extend([
            [
                InlineKeyboardButton(
                    text=_ANALYTICS_LABELS[key],
                    callback_data=f"admin_analytics:view:{key}:{days}",
                )
                for key in categories[index:index + 2]
            ]
            for index in range(0, len(categories), 2)
        ])
    if category is None or category in {"activity", "workouts", "economy"}:
        rows.append([
            InlineKeyboardButton(
                text=f"{'✓ ' if days == period else ''}{period} дн.",
                callback_data=(
                    f"admin_analytics:period:{category}:{period}"
                    if category else f"admin_analytics:menu:{period}"
                ),
            )
            for period in admin_analytics.PERIODS
        ])
    if category:
        rows.append([
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=f"admin_analytics:refresh:{category}:{days}",
            ),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_analytics:menu:{days}"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin_analytics:menu:{days}"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_analytics:home"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_report(category: str, data: dict, days: int) -> str:
    if category == "users":
        lines = [
            f"Всего зарегистрировано: <b>{data['total']}</b>",
            f"Активных: <b>{data['active']}</b> · удалённых: <b>{data['deleted']}</b>",
            f"Средний уровень активных: <b>{data['average_level']:.1f}</b>",
            "Уровни активных: " + (
                ", ".join(f"{level}: {count}" for level, count in data["levels"]) or "нет данных"
            ),
        ]
        if not data["total"]:
            lines.append("Пользователей пока нет.")
    elif category == "activity":
        previous = data["previous_active_users"]
        if previous:
            change = data["active_users"] - previous
            comparison = f"{change:+d} к предыдущим {days} дн. ({previous})"
        elif data["active_users"]:
            comparison = f"нет данных за предыдущие {days} дн."
        else:
            comparison = f"нет данных за оба периода по {days} дн."
        lines = [
            f"Активные по тренировкам: <b>{data['active_users']}</b>",
            f"Тренировочных дней: <b>{data['training_days']}</b>",
            f"Сравнение: {comparison}",
        ]
        if not data["active_users"]:
            lines.append("За выбранный период тренировок нет.")
    elif category == "workouts":
        lines = [
            f"Тренировочных сессий: <b>{data['sessions']}</b>",
            f"Записей упражнений: <b>{data['exercises']}</b>",
            f"Челлендж-сессий: <b>{data['challenge_sessions']}</b>",
            "Популярные упражнения: " + (
                ", ".join(f"{escape(name[:80])} ({count})" for name, count in data["popular_exercises"])
                or "нет данных"
            ),
            "<i>Записи без session_id считаются отдельно: восстановить их сессии нельзя. "
            "Привязанные упражнения не дублируют сессии.</i>",
        ]
        if not data["exercises"]:
            lines.append("За выбранный период тренировок нет.")
    elif category == "economy":
        lines = [
            f"Баланс активных пользователей: <b>{data['balance']}</b> монет",
            f"Средний баланс: <b>{data['average_balance']:.1f}</b>",
            f"С ненулевым балансом: <b>{data['users_with_balance']}</b>",
            f"За {days} дн. зафиксировано начислений: <b>{data['recorded_rewards']}</b> монет "
            f"({data['reward_records']} записей coin_rewards)",
            "<i>Только записи coin_rewards, включая удалённые аккаунты; расходы не учитываются.</i>",
        ]
        if not data["reward_records"]:
            lines.append("За выбранный период зафиксированных начислений нет.")
    else:
        top = data["top_achievements"]
        lines = [
            f"Средний уровень активных: <b>{data['average_level']:.1f}</b>",
            f"Средний XP активных: <b>{data['average_xp']:.1f}</b>",
            f"Максимальный уровень: <b>{data['max_level']}</b>",
            f"Выдано достижений: <b>{data['achievements_count']}</b>",
            "Частые достижения: " + (
                ", ".join(f"{escape(title)} ({count})" for _, title, count in top) or "нет данных"
            ),
        ]
        if not data["total_users"]:
            lines.append("Данных о прогрессе пока нет.")
    if category in {"users", "progress"}:
        period_label = "всё время"
    elif category == "economy":
        period_label = f"текущий баланс · начисления за {days} дн."
    else:
        period_label = f"за {days} дн."
    return f"<b>{_ANALYTICS_LABELS[category]}</b> · {period_label}\n\n" + "\n".join(lines)


def _analytics_menu_text(days: int) -> str:
    return (
        f"<b>📊 Аналитика SportBot</b>\n"
        f"Период для показателей с временным фильтром: <b>{days} дней</b>.\n"
        "Выберите раздел:"
    )


async def _show_admin_home(target) -> None:
    total_users = fetch_one(
        "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL"
    )[0]
    active_today = fetch_one(
        "SELECT COUNT(DISTINCT user_id) FROM workouts WHERE date = ?",
        (datetime.now().strftime("%Y-%m-%d"),),
    )[0]
    top_xp = fetch_one(
        "SELECT user_id, xp FROM users WHERE deleted_at IS NULL ORDER BY xp DESC LIMIT 1"
    )
    top_xp_text = f"user {top_xp[0]} with {top_xp[1]} XP" if top_xp else "n/a"
    text = (
        f"📊 <b>Admin Stats</b>\n\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"🏃 Active today: <b>{active_today}</b>\n"
        f"🏆 Top XP: {top_xp_text}"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=_admin_keyboard(), parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=_admin_keyboard(), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return
    await _show_admin_home(message)


@router.callback_query(F.data.startswith("admin_analytics:"))
async def handle_analytics_callback(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if not callback.message or not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    try:
        action = parts[1]
        if action == "home":
            await _show_admin_home(callback)
        elif action == "menu":
            days = int(parts[2])
            if days not in admin_analytics.PERIODS:
                raise ValueError("Invalid analytics period")
            await callback.message.edit_text(
                _analytics_menu_text(days),
                reply_markup=_analytics_keyboard(days),
                parse_mode="HTML",
            )
        elif action in {"view", "refresh", "period"}:
            category, days = parts[2], int(parts[3])
            if category not in admin_analytics.CATEGORIES or days not in admin_analytics.PERIODS:
                raise ValueError("Invalid analytics selection")
            data = admin_analytics.get_report(category, days)
            await callback.message.edit_text(
                _format_report(category, data, days),
                reply_markup=_analytics_keyboard(days, category),
                parse_mode="HTML",
            )
        else:
            raise ValueError("Unknown analytics action")
        await callback.answer()
    except Exception as exc:
        log.exception("Admin analytics callback failed")
        await callback.message.edit_text(
            f"❌ Не удалось загрузить аналитику ({type(exc).__name__}). Попробуйте обновить раздел.",
            reply_markup=_analytics_keyboard(30),
        )
        await callback.answer()


@router.message(Command("backup"))
async def cmd_backup(message: Message) -> None:
    """Run a verified backup manually; available only to configured admins."""
    if not message.from_user or not is_admin(message.from_user.id):
        return
    await message.answer("⏳ Создаю и проверяю резервную копию…")
    try:
        manifest = await asyncio.to_thread(create_backup)
        await message.answer(
            "✅ Резервная копия создана и проверена\n"
            f"Файл: <code>{manifest['file']}</code>\n"
            f"SHA-256: <code>{manifest['sha256']}</code>",
            parse_mode="HTML",
        )
    except Exception as exc:
        log.exception("Manual database backup failed")
        await message.answer(f"❌ Ошибка резервного копирования: <code>{type(exc).__name__}</code>", parse_mode="HTML")
