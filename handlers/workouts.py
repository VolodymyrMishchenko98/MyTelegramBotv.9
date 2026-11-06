"""Handlers for starting the manual workout input flow."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()

_get_user_language = None
_set_user_state = None
_t_pair = None


def configure(get_user_language: callable, set_user_state: callable, t_pair: callable) -> None:
    """Inject the manual-state and localization dependencies."""
    global _get_user_language, _set_user_state, _t_pair
    _get_user_language = get_user_language
    _set_user_state = set_user_state
    _t_pair = t_pair


def _workout_note_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=_t_pair(lang, "Пропустити", "Skip"),
        callback_data="workout_note_skip",
    )]])


@router.message(Command("workout"))
async def workout(message: Message):
    uid = message.from_user.id
    lang = _get_user_language(uid)
    await start_workout_for_user(message, uid, lang)


async def start_workout_for_user(message: Message, user_id: int, lang: str | None = None):
    """Start the same workout flow for a command or an inline-menu action."""
    lang = lang or _get_user_language(user_id)
    _set_user_state(user_id, "workout")
    await message.answer(
        _t_pair(
            lang,
            "Введи тренування.\nМожна через кому:\nБіг 30 хвилин, Відтискування 4x20",
            "Enter workout.\nYou can separate by commas:\nRunning 30 min, Push ups 4x20",
        )
    )
