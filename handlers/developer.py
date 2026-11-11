"""User feedback flow and developer-only ticket actions."""
from __future__ import annotations

import html
import sqlite3
from collections.abc import Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from handlers.keyboards import add_home_button
from locales import t
from services import developer_feedback as feedback_db
from services.logging_config import get_logger

router = Router()
log = get_logger("handlers.developer")

MAX_MESSAGE_LENGTH = 1800
STATE_MODE = "developer_feedback_mode"
STATE_CATEGORY = "developer_feedback_category"
STATE_MESSAGE = "developer_feedback_message"
STATE_REPLY = "developer_feedback_reply"
STATE_USER_REPLY = "developer_feedback_user_reply"

_get_language: Callable[[int], str] | None = None
_get_state: Callable[[int], str | None] | None = None
_set_state: Callable[[int, str], None] | None = None
_clear_state: Callable[[int], None] | None = None
_welcome_keyboard: Callable[[str], InlineKeyboardMarkup] | None = None
_developer_chat_id: int | None = None
_pending: dict[int, dict] = {}

_CATEGORY_KEYS = {
    "idea": "developer_feedback_category_idea",
    "bug": "developer_feedback_category_bug",
    "question": "developer_feedback_category_question",
    "other": "developer_feedback_category_other",
}


def configure(
    get_language: Callable[[int], str],
    get_state: Callable[[int], str | None],
    set_state: Callable[[int, str], None],
    clear_state: Callable[[int], None],
    welcome_keyboard: Callable[[str], InlineKeyboardMarkup],
    developer_chat_id: int | None,
) -> None:
    global _get_language, _get_state, _set_state, _clear_state
    global _welcome_keyboard, _developer_chat_id
    _get_language = get_language
    _get_state = get_state
    _set_state = set_state
    _clear_state = clear_state
    _welcome_keyboard = welcome_keyboard
    _developer_chat_id = developer_chat_id
    _pending.clear()


def _lang(user_id: int) -> str:
    if _get_language is None:
        raise RuntimeError("Developer feedback handler is not configured")
    return _get_language(user_id)


def _state(user_id: int) -> str | None:
    if _get_state is None:
        raise RuntimeError("Developer feedback handler is not configured")
    return _get_state(user_id)


def _set(user_id: int, state: str) -> None:
    if _set_state is None:
        raise RuntimeError("Developer feedback handler is not configured")
    _set_state(user_id, state)


def _clear(user_id: int) -> None:
    if _clear_state is None:
        raise RuntimeError("Developer feedback handler is not configured")
    _pending.pop(user_id, None)
    _clear_state(user_id)


def _home_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(None, lang)


def _mode_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("developer_feedback_anonymous", lang),
                callback_data="devfb:mode:a",
            ),
            InlineKeyboardButton(
                text=t("developer_feedback_identified", lang),
                callback_data="devfb:mode:i",
            ),
        ],
        [InlineKeyboardButton(
            text=t("developer_feedback_back", lang),
            callback_data="devfb:back",
        )],
        [InlineKeyboardButton(
            text=t("developer_feedback_cancel", lang),
            callback_data="devfb:cancel",
        )],
    ])


def _category_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("developer_feedback_category_idea", lang),
                callback_data="devfb:category:idea",
            ),
            InlineKeyboardButton(
                text=t("developer_feedback_category_bug", lang),
                callback_data="devfb:category:bug",
            ),
        ],
        [
            InlineKeyboardButton(
                text=t("developer_feedback_category_question", lang),
                callback_data="devfb:category:question",
            ),
            InlineKeyboardButton(
                text=t("developer_feedback_category_other", lang),
                callback_data="devfb:category:other",
            ),
        ],
        [InlineKeyboardButton(
            text=t("developer_feedback_back", lang),
            callback_data="devfb:back",
        )],
        [InlineKeyboardButton(
            text=t("developer_feedback_cancel", lang),
            callback_data="devfb:cancel",
        )],
    ])


def _input_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("developer_feedback_back", lang),
            callback_data="devfb:back",
        )],
        [InlineKeyboardButton(
            text=t("developer_feedback_cancel", lang),
            callback_data="devfb:cancel",
        )],
    ])


def _developer_keyboard(feedback_id: int, status: str, lang: str) -> InlineKeyboardMarkup:
    if status == "open":
        rows = [[InlineKeyboardButton(
            text=t("developer_feedback_reply", lang),
            callback_data=f"devfb:reply:{feedback_id}",
        )], [InlineKeyboardButton(
            text=t("developer_feedback_close", lang),
            callback_data=f"devfb:close:{feedback_id}",
        )]]
    else:
        rows = [[InlineKeyboardButton(
            text=t("developer_feedback_reopen", lang),
            callback_data=f"devfb:reopen:{feedback_id}",
        )]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _user_reply_keyboard(feedback_id: int, status: str, lang: str) -> InlineKeyboardMarkup:
    markup = None
    if status == "open":
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=t("developer_feedback_user_reply", lang),
                callback_data=f"devfb:user_reply:{feedback_id}",
            ),
        ]])
    return add_home_button(markup, lang)


def _identity_text(user, lang: str, anonymous: bool) -> str:
    if anonymous:
        return ""
    lines = []
    full_name = html.escape((getattr(user, "full_name", "") or "").strip())
    username = html.escape(getattr(user, "username", "") or "")
    if full_name:
        lines.append(t("developer_feedback_identity_name", lang).format(name=full_name))
    if username:
        lines.append(
            t("developer_feedback_identity_username", lang).format(username=username)
        )
    return "".join(lines)


def _feedback_notification(
    feedback_id: int,
    category: str,
    anonymous: bool,
    user,
    message: str,
    lang: str,
    *,
    followup: bool = False,
) -> str:
    mode_key = (
        "developer_feedback_mode_anonymous"
        if anonymous
        else "developer_feedback_mode_identified"
    )
    values = {
        "ticket_id": feedback_id,
        "category": t(_CATEGORY_KEYS[category], lang),
        "mode": t(mode_key, lang),
        "identity": _identity_text(user, lang, anonymous),
        "message": html.escape(message),
    }
    key = (
        "developer_feedback_user_followup"
        if followup
        else "developer_feedback_dev_notification"
    )
    return t(key, lang).format(**values)


async def _show_start(message: Message, user_id: int, *, edit: bool = False) -> None:
    lang = _lang(user_id)
    _clear(user_id)
    text = t("developer_card", lang)
    markup = _mode_keyboard(lang)
    if _developer_chat_id is None:
        text += "\n\n" + t("developer_contact_unavailable", lang)
        markup = _home_keyboard(lang)
    else:
        _set(user_id, STATE_MODE)
        text += "\n\n" + t("developer_feedback_choose_mode", lang)
    display = message.edit_text if edit else message.answer
    await display(text, parse_mode="HTML", reply_markup=markup)


@router.message(Command("developer"))
async def cmd_developer(message: Message) -> None:
    if not message.from_user:
        return
    await _show_start(message, message.from_user.id)


def _feedback_message_filter(message: Message) -> bool:
    user = message.from_user
    if not user or (message.text and message.text.startswith("/")):
        return False
    return _state(user.id) in (STATE_MESSAGE, STATE_REPLY, STATE_USER_REPLY)


@router.message(_feedback_message_filter)
async def receive_feedback_message(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    user_id = user.id
    lang = _lang(user_id)
    current_state = _state(user_id)

    if not message.text:
        await message.answer(t("developer_feedback_text_only", lang))
        return
    text = message.text.strip()
    if not text:
        await message.answer(t("developer_feedback_empty", lang))
        return
    if len(text) > MAX_MESSAGE_LENGTH:
        await message.answer(t("developer_feedback_too_long", lang))
        return

    if current_state == STATE_MESSAGE:
        await _submit_new_feedback(message, user_id, text, lang)
    elif current_state == STATE_USER_REPLY:
        await _submit_user_reply(message, user_id, text, lang)
    elif current_state == STATE_REPLY:
        await _submit_developer_reply(message, user_id, text, lang)


async def _submit_new_feedback(
    message: Message,
    user_id: int,
    text: str,
    lang: str,
) -> None:
    details = _pending.get(user_id)
    if not details or details.get("category") not in _CATEGORY_KEYS:
        _clear(user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return
    if _developer_chat_id is None:
        _clear(user_id)
        await message.answer(
            t("developer_contact_unavailable", lang),
            reply_markup=_home_keyboard(lang),
        )
        return

    try:
        feedback_id = feedback_db.create_feedback(
            user_id,
            bool(details["anonymous"]),
            details["category"],
            text,
        )
    except sqlite3.Error as exc:
        log.error("Feedback storage failed error_type=%s", type(exc).__name__)
        await message.answer(t("developer_feedback_save_error", lang))
        return
    if feedback_id is None:
        await message.answer(t("developer_feedback_rate_limited", lang))
        return

    _clear(user_id)
    dev_lang = _lang(_developer_chat_id) if _developer_chat_id > 0 else "uk"
    notification = _feedback_notification(
        feedback_id,
        details["category"],
        bool(details["anonymous"]),
        message.from_user,
        text,
        dev_lang,
    )
    try:
        await message.bot.send_message(
            chat_id=_developer_chat_id,
            text=notification,
            parse_mode="HTML",
            reply_markup=_developer_keyboard(feedback_id, "open", dev_lang),
        )
    except TelegramAPIError as exc:
        _mark_feedback_notification(feedback_id, False)
        log.warning(
            "Feedback notification failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )
        await message.answer(
            t("developer_feedback_delivery_failed", lang).format(ticket_id=feedback_id),
            reply_markup=_home_keyboard(lang),
        )
        return

    _mark_feedback_notification(feedback_id, True)
    await message.answer(
        t("developer_feedback_saved", lang).format(ticket_id=feedback_id),
        reply_markup=_home_keyboard(lang),
    )


def _mark_feedback_notification(feedback_id: int, delivered: bool) -> None:
    try:
        feedback_db.mark_feedback_notification(feedback_id, delivered)
    except sqlite3.Error as exc:
        log.error(
            "Feedback notification status update failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )


async def _submit_user_reply(
    message: Message,
    user_id: int,
    text: str,
    lang: str,
) -> None:
    details = _pending.get(user_id, {})
    feedback_id = details.get("feedback_id")
    if not isinstance(feedback_id, int):
        _clear(user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return
    if _developer_chat_id is None:
        _clear(user_id)
        await message.answer(
            t("developer_contact_unavailable", lang),
            reply_markup=_home_keyboard(lang),
        )
        return
    try:
        result = feedback_db.add_user_message(feedback_id, user_id, text)
    except sqlite3.Error as exc:
        log.error("Feedback reply storage failed ticket_id=%s error_type=%s", feedback_id, type(exc).__name__)
        await message.answer(t("developer_feedback_save_error", lang))
        return
    if result == "rate_limited":
        await message.answer(t("developer_feedback_rate_limited", lang))
        return
    if result == "not_found":
        _clear(user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return
    if result == "closed":
        _clear(user_id)
        await message.answer(t("developer_feedback_closed_user", lang))
        return

    try:
        ticket = feedback_db.get_user_feedback(feedback_id, user_id)
    except sqlite3.Error as exc:
        _clear(user_id)
        _mark_feedback_notification(feedback_id, False)
        log.error(
            "Feedback follow-up lookup failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )
        await message.answer(
            t("developer_feedback_followup_delivery_failed", lang).format(
                ticket_id=feedback_id
            ),
            reply_markup=_home_keyboard(lang),
        )
        return
    if ticket is None:
        _clear(user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return
    _clear(user_id)
    dev_lang = _lang(_developer_chat_id) if _developer_chat_id > 0 else "uk"
    notification = _feedback_notification(
        feedback_id,
        ticket["category"],
        ticket["anonymous"],
        message.from_user,
        text,
        dev_lang,
        followup=True,
    )
    try:
        await message.bot.send_message(
            chat_id=_developer_chat_id,
            text=notification,
            parse_mode="HTML",
            reply_markup=_developer_keyboard(feedback_id, "open", dev_lang),
        )
    except TelegramAPIError as exc:
        _mark_feedback_notification(feedback_id, False)
        log.warning(
            "Feedback follow-up notification failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )
        await message.answer(
            t("developer_feedback_followup_delivery_failed", lang).format(ticket_id=feedback_id),
            reply_markup=_home_keyboard(lang),
        )
        return
    _mark_feedback_notification(feedback_id, True)
    await message.answer(
        t("developer_feedback_followup_sent", lang).format(ticket_id=feedback_id),
        reply_markup=_home_keyboard(lang),
    )


async def _submit_developer_reply(
    message: Message,
    developer_user_id: int,
    text: str,
    lang: str,
) -> None:
    details = _pending.get(developer_user_id, {})
    feedback_id = details.get("feedback_id")
    if not isinstance(feedback_id, int):
        _clear(developer_user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return
    try:
        pending_reply = feedback_db.create_developer_reply(feedback_id, text)
    except sqlite3.Error as exc:
        log.error("Feedback reply storage failed ticket_id=%s error_type=%s", feedback_id, type(exc).__name__)
        await message.answer(t("developer_feedback_reply_error", lang))
        return
    if pending_reply is None:
        _clear(developer_user_id)
        await message.answer(t("developer_feedback_not_found", lang))
        return

    sender_id, history_message_id = pending_reply
    _clear(developer_user_id)
    user_lang = _lang(sender_id)
    response_text = t("developer_feedback_reply_body", user_lang).format(
        message=html.escape(text)
    )
    try:
        await message.bot.send_message(
            chat_id=sender_id,
            text=response_text,
            parse_mode="HTML",
            reply_markup=_user_reply_keyboard(feedback_id, "open", user_lang),
        )
    except TelegramAPIError as exc:
        try:
            feedback_db.finish_developer_reply(history_message_id, False)
        except sqlite3.Error as db_exc:
            log.error(
                "Failed reply status update ticket_id=%s error_type=%s",
                feedback_id,
                type(db_exc).__name__,
            )
        log.warning(
            "Feedback reply delivery failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )
        await message.answer(
            t("developer_feedback_reply_failed", lang).format(ticket_id=feedback_id)
        )
        return

    try:
        feedback_db.finish_developer_reply(history_message_id, True)
    except sqlite3.Error as exc:
        log.error(
            "Feedback reply history update failed ticket_id=%s error_type=%s",
            feedback_id,
            type(exc).__name__,
        )
        await message.answer(
            t("developer_feedback_reply_history_failed", lang).format(
                ticket_id=feedback_id
            )
        )
        return
    await message.answer(
        t("developer_feedback_reply_saved", lang).format(ticket_id=feedback_id)
    )


def _developer_action_allowed(callback: CallbackQuery) -> bool:
    if _developer_chat_id is None or not callback.message:
        return False
    if callback.message.chat.id != _developer_chat_id:
        return False
    if _developer_chat_id > 0 and callback.from_user.id != _developer_chat_id:
        return False
    return True


@router.callback_query(F.data.startswith("devfb:"))
async def handle_feedback_callback(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    lang = _lang(user_id)
    parts = (callback.data or "").split(":")
    if len(parts) < 2:
        await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
        return
    action = parts[1]

    if action == "open":
        await callback.answer()
        await _show_start(callback.message, user_id, edit=True)
        return

    if action == "cancel":
        _clear(user_id)
        await callback.answer()
        await callback.message.edit_text(
            t("developer_feedback_cancelled", lang),
            reply_markup=_home_keyboard(lang),
        )
        return

    if action == "back":
        current_state = _state(user_id)
        if current_state == STATE_CATEGORY:
            _set(user_id, STATE_MODE)
            await callback.answer()
            await callback.message.edit_text(
                t("developer_card", lang) + "\n\n" + t("developer_feedback_choose_mode", lang),
                parse_mode="HTML",
                reply_markup=_mode_keyboard(lang),
            )
        elif current_state == STATE_MESSAGE:
            _set(user_id, STATE_CATEGORY)
            await callback.answer()
            await callback.message.edit_text(
                t("developer_feedback_choose_category", lang),
                reply_markup=_category_keyboard(lang),
            )
        else:
            _clear(user_id)
            await callback.answer()
            if _welcome_keyboard is None:
                raise RuntimeError("Developer feedback handler is not configured")
            await callback.message.edit_text(
                t("welcome", lang),
                parse_mode="HTML",
                reply_markup=_welcome_keyboard(lang),
            )
        return

    if action == "mode" and len(parts) == 3 and parts[2] in ("a", "i"):
        if _state(user_id) != STATE_MODE:
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        _pending[user_id] = {"anonymous": parts[2] == "a"}
        _set(user_id, STATE_CATEGORY)
        text = t("developer_feedback_choose_category", lang)
        if parts[2] == "a":
            text += "\n\n" + t("developer_feedback_anonymity_note", lang)
        await callback.answer()
        await callback.message.edit_text(text, reply_markup=_category_keyboard(lang))
        return

    if action == "category" and len(parts) == 3 and parts[2] in _CATEGORY_KEYS:
        if _state(user_id) != STATE_CATEGORY or user_id not in _pending:
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        _pending[user_id]["category"] = parts[2]
        _set(user_id, STATE_MESSAGE)
        await callback.answer()
        await callback.message.edit_text(
            t("developer_feedback_write_message", lang),
            reply_markup=_input_keyboard(lang),
        )
        return

    if action == "user_reply" and len(parts) == 3 and parts[2].isdigit():
        feedback_id = int(parts[2])
        ticket = feedback_db.get_user_feedback(feedback_id, user_id)
        if ticket is None:
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        if ticket["status"] != "open":
            await callback.answer(t("developer_feedback_closed_user", lang), show_alert=True)
            return
        _pending[user_id] = {"feedback_id": feedback_id}
        _set(user_id, STATE_USER_REPLY)
        await callback.answer()
        await callback.message.answer(
            t("developer_feedback_reply_prompt", lang),
            reply_markup=_input_keyboard(lang),
        )
        return

    if action in ("reply", "close", "reopen"):
        if len(parts) != 3 or not parts[2].isdigit():
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        if not _developer_action_allowed(callback):
            await callback.answer(t("developer_feedback_unauthorized", lang), show_alert=True)
            return
        feedback_id = int(parts[2])
        ticket = feedback_db.get_feedback(feedback_id)
        if ticket is None:
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        if action == "reply":
            if ticket["status"] != "open":
                await callback.answer(t("developer_feedback_closed_user", lang), show_alert=True)
                return
            _pending[user_id] = {"feedback_id": feedback_id}
            _set(user_id, STATE_REPLY)
            await callback.answer()
            await callback.message.answer(
                t("developer_feedback_reply_prompt", lang),
                reply_markup=_input_keyboard(lang),
            )
            return
        new_status = "closed" if action == "close" else "open"
        changed = feedback_db.set_feedback_status(feedback_id, new_status)
        if not changed:
            await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
            return
        await callback.message.edit_reply_markup(
            reply_markup=_developer_keyboard(feedback_id, new_status, lang)
        )
        await callback.answer(t(
            "developer_feedback_closed" if new_status == "closed"
            else "developer_feedback_reopened",
            lang,
        ))
        return

    await callback.answer(t("developer_feedback_not_found", lang), show_alert=True)
