"""handlers/admin.py - Admin-only commands."""
from __future__ import annotations

import os

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db_improved import fetch_one
from services.logging_config import get_logger

log = get_logger("handlers.admin")
router = Router()

ADMIN_IDS: set[int] = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        return

    total_users = fetch_one(
        "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL"
    )[0]
    active_today = fetch_one(
        "SELECT COUNT(DISTINCT user_id) FROM workouts WHERE date = date('now')"
    )[0]
    top_xp = fetch_one(
        "SELECT user_id, xp FROM users WHERE deleted_at IS NULL ORDER BY xp DESC LIMIT 1"
    )

    top_xp_text = "n/a"
    if top_xp:
        top_xp_text = f"user {top_xp[0]} with {top_xp[1]} XP"

    await message.answer(
        f"📊 <b>Admin Stats</b>\n\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"🏃 Active today: <b>{active_today}</b>\n"
        f"🏆 Top XP: {top_xp_text}",
        parse_mode="HTML",
    )
