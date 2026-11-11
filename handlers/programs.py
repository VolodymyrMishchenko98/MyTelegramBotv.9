"""Interactive training-program survey, generation, and plan navigation."""
from __future__ import annotations

import asyncio
import html
import sqlite3
from collections.abc import Callable
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from handlers.keyboards import add_home_button
from locales import t
from services.program_generator import (
    DURATIONS,
    EQUIPMENT,
    FREQUENCIES,
    GOALS,
    LEVELS,
    LOCATIONS,
    MAX_NOTES_LENGTH,
    generate_program,
    validate_preferences,
)
from services import training_programs as program_db
from services.logging_config import get_logger

router = Router()
log = get_logger("handlers.programs")

STATE_GOAL = "training_program_goal"
STATE_LOCATION = "training_program_location"
STATE_FREQUENCY = "training_program_frequency"
STATE_DURATION = "training_program_duration"
STATE_LEVEL = "training_program_level"
STATE_EQUIPMENT = "training_program_equipment"
STATE_EQUIPMENT_OTHER = "training_program_equipment_other"
STATE_NOTES = "training_program_notes"
STATE_CONFIRM = "training_program_confirm"
STATE_SAVING = "training_program_saving"
STATE_ARCHIVE_CONFIRM = "training_program_archive_confirm"

_get_language: Callable[[int], str] | None = None
_get_state: Callable[[int], str | None] | None = None
_set_state: Callable[[int, str], None] | None = None
_clear_state: Callable[[int], None] | None = None
_drafts: dict[int, dict[str, Any]] = {}

_OPTIONS = {
    "goal": (GOALS, STATE_GOAL, "program_question_goal"),
    "location": (LOCATIONS, STATE_LOCATION, "program_question_location"),
    "frequency": (FREQUENCIES, STATE_FREQUENCY, "program_question_frequency"),
    "duration": (DURATIONS, STATE_DURATION, "program_question_duration"),
    "level": (LEVELS, STATE_LEVEL, "program_question_level"),
}
_OPTION_LABEL_KEYS = {
    "general": "program_goal_general",
    "strength": "program_goal_strength",
    "endurance": "program_goal_endurance",
    "mobility": "program_goal_mobility",
    "sport": "program_goal_sport",
    "home": "program_location_home",
    "gym": "program_location_gym",
    "outdoors": "program_location_outdoors",
    "2-3": "program_frequency_2_3",
    "4": "program_frequency_4",
    "5": "program_frequency_5",
    "15-20": "program_duration_15_20",
    "30": "program_duration_30",
    "45": "program_duration_45",
    "60": "program_duration_60",
    "beginner": "program_level_beginner",
    "intermediate": "program_level_intermediate",
    "advanced": "program_level_advanced",
    "none": "program_equipment_none",
    "dumbbells": "program_equipment_dumbbells",
    "pullup_bar": "program_equipment_pullup_bar",
    "machines": "program_equipment_machines",
    "other": "program_equipment_other",
}
_QUESTION_STATES = (
    STATE_GOAL,
    STATE_LOCATION,
    STATE_FREQUENCY,
    STATE_DURATION,
    STATE_LEVEL,
    STATE_EQUIPMENT,
    STATE_EQUIPMENT_OTHER,
    STATE_NOTES,
    STATE_CONFIRM,
)


def configure(
    get_language: Callable[[int], str],
    get_state: Callable[[int], str | None],
    set_state: Callable[[int, str], None],
    clear_state: Callable[[int], None],
) -> None:
    global _get_language, _get_state, _set_state, _clear_state
    _get_language = get_language
    _get_state = get_state
    _set_state = set_state
    _clear_state = clear_state
    _drafts.clear()


def _lang(user_id: int) -> str:
    if _get_language is None:
        raise RuntimeError("Training program handler is not configured")
    return _get_language(user_id)


def _state(user_id: int) -> str | None:
    if _get_state is None:
        raise RuntimeError("Training program handler is not configured")
    return _get_state(user_id)


def _set(user_id: int, state: str) -> None:
    if _set_state is None:
        raise RuntimeError("Training program handler is not configured")
    _set_state(user_id, state)


def _clear(user_id: int) -> None:
    if _clear_state is None:
        raise RuntimeError("Training program handler is not configured")
    _drafts.pop(user_id, None)
    _clear_state(user_id)


def discard_draft(user_id: int) -> None:
    """Drop unsaved survey data when another flow replaces its state."""
    _drafts.pop(user_id, None)


def _keyboard(
    rows: list[list[InlineKeyboardButton]],
    lang: str,
) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=rows), lang)


def _button(text_key: str, callback_data: str, lang: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=t(text_key, lang), callback_data=callback_data)


def _step_keyboard(lang: str, *, back: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if back:
        rows.append([_button("program_back", "program:back", lang)])
    rows.append([_button("program_cancel", "program:cancel", lang)])
    return _keyboard(rows, lang)


def _choice_keyboard(
    field: str,
    options: set[str],
    lang: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    choices = sorted(options)
    for offset in range(0, len(choices), 2):
        rows.append([
            _button(
                _OPTION_LABEL_KEYS[key],
                f"program:choose:{field}:{key}",
                lang,
            )
            for key in choices[offset:offset + 2]
        ])
    rows.extend(_step_keyboard(lang).inline_keyboard)
    return _keyboard(rows, lang)


def _equipment_keyboard(user_id: int, lang: str) -> InlineKeyboardMarkup:
    selected = set(_drafts[user_id].get("equipment", []))
    rows = []
    items = sorted(EQUIPMENT)
    for offset in range(0, len(items), 2):
        row = []
        for item in items[offset:offset + 2]:
            prefix = "✅ " if item in selected else ""
            row.append(InlineKeyboardButton(
                text=prefix + t(_OPTION_LABEL_KEYS[item], lang),
                callback_data=f"program:equipment:{item}",
            ))
        rows.append(row)
    rows.append([_button("program_continue", "program:equipment:done", lang)])
    rows.extend(_step_keyboard(lang).inline_keyboard)
    return _keyboard(rows, lang)


def _equipment_label(preferences: dict[str, Any], lang: str) -> str:
    equipment = preferences.get("equipment", [])
    labels = [t(_OPTION_LABEL_KEYS[key], lang) for key in equipment]
    details = preferences.get("other_equipment", "").strip()
    if details:
        labels.append(html.escape(details))
    return ", ".join(labels) if labels else t("program_not_selected", lang)


def _preference_lines(preferences: dict[str, Any], lang: str) -> str:
    lines = [
        t("program_parameter_goal", lang).format(
            value=t(_OPTION_LABEL_KEYS[preferences["goal"]], lang)
        ),
        t("program_parameter_location", lang).format(
            value=t(_OPTION_LABEL_KEYS[preferences["location"]], lang)
        ),
        t("program_parameter_frequency", lang).format(
            value=t(_OPTION_LABEL_KEYS[preferences["frequency"]], lang)
        ),
        t("program_parameter_duration", lang).format(
            value=t(_OPTION_LABEL_KEYS[preferences["duration"]], lang)
        ),
        t("program_parameter_level", lang).format(
            value=t(_OPTION_LABEL_KEYS[preferences["level"]], lang)
        ),
        t("program_parameter_equipment", lang).format(
            value=_equipment_label(preferences, lang)
        ),
    ]
    notes = preferences.get("notes", "").strip()
    if notes:
        lines.append(
            t("program_parameter_notes", lang).format(value=html.escape(notes))
        )
    return "\n".join(lines)


def _summary_text(program: dict[str, Any], lang: str) -> str:
    content = program["content"]
    preferences = program["preferences"]
    sessions = content["sessions"]
    day_lines = [
        t("program_schedule_line", lang).format(
            day=t(session["day_key"], lang),
            title=t(session["title_key"], lang),
        )
        for session in sessions
    ]
    progression = "\n".join(
        t(key, lang) for key in content["progression_keys"]
    )
    parts = [
        t("program_saved_title", lang).format(program_id=program["id"]),
        _preference_lines(preferences, lang),
        t("program_weekly_schedule", lang).format(days="\n".join(day_lines)),
        t("program_recovery_notice", lang),
        t("program_progression", lang).format(steps=progression),
        t(content["safety_key"], lang),
    ]
    if preferences["frequency"] == "2-3":
        parts.append(t("program_two_day_option_note", lang))
    if preferences["frequency"] == "5":
        parts.append(t("program_five_day_note", lang))
    if preferences.get("notes"):
        parts.append(t("program_notes_caution", lang))
    if preferences["goal"] == "sport":
        parts.append(t("program_sport_caution", lang))
    return "\n\n".join(parts)


def _session_text(program: dict[str, Any], index: int, lang: str) -> str | None:
    sessions = program["content"]["sessions"]
    if index < 0 or index >= len(sessions):
        return None
    session = sessions[index]
    exercise_lines = []
    for exercise in session["exercises"]:
        prescription = t(exercise["prescription_key"], lang).format(
            sets=exercise["sets"],
            reps=exercise["reps"],
            minutes=exercise["minutes"],
        )
        exercise_lines.append(
            "• " + t(exercise["key"], lang) + " — " + prescription
        )
    return "\n".join((
        t("program_day_title", lang).format(
            day=t(session["day_key"], lang),
            title=t(session["title_key"], lang),
        ),
        t("program_objective", lang).format(
            value=t(session["objective_key"], lang)
        ),
        t("program_warmup", lang).format(
            value=t(session["warmup_key"], lang)
        ),
        t("program_exercises", lang),
        "\n".join(exercise_lines),
        t("program_rest", lang).format(seconds=session["rest_seconds"]),
        t("program_cooldown", lang).format(
            value=t(session["cooldown_key"], lang)
        ),
        t("program_duration_estimate", lang).format(
            minutes=session["duration_minutes"]
        ),
        t("program_effort_note", lang),
    ))


def _plan_keyboard(
    program: dict[str, Any],
    lang: str,
    *,
    archived: bool = False,
) -> InlineKeyboardMarkup:
    rows = []
    days = program["content"]["sessions"]
    for index in range(0, len(days), 2):
        rows.append([
            InlineKeyboardButton(
                text=t(days[current]["day_key"], lang),
                callback_data=f"program:day:{program['id']}:{current}",
            )
            for current in range(index, min(index + 2, len(days)))
        ])
    rows.append([_button("program_create", "program:create", lang)])
    if not archived:
        rows.append([_button("program_archive", "program:archive", lang)])
    rows.append([_button("program_archives", "program:archives", lang)])
    return _keyboard(rows, lang)


async def _show_menu(message: Message, user_id: int, *, edit: bool = False) -> None:
    lang = _lang(user_id)
    active = await asyncio.to_thread(program_db.get_active_program, user_id)
    display = message.edit_text if edit else message.answer
    if active:
        text = _summary_text(active, lang)
        markup = _plan_keyboard(active, lang)
    else:
        text = t("program_empty", lang)
        markup = _keyboard([
            [_button("program_create", "program:create", lang)],
            [_button("program_archives", "program:archives", lang)],
        ], lang)
    await display(text, reply_markup=markup, parse_mode="HTML")


def _preview_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [[_button("program_generate", "program:confirm", lang)]]
    rows.extend(_step_keyboard(lang).inline_keyboard)
    return _keyboard(rows, lang)


async def _show_preview(message: Message, user_id: int, *, edit: bool = True) -> None:
    lang = _lang(user_id)
    draft = _drafts.get(user_id)
    if not draft:
        await _show_menu(message, user_id, edit=edit)
        return
    _set(user_id, STATE_CONFIRM)
    text = t("program_confirmation", lang).format(
        parameters=_preference_lines(draft, lang)
    )
    if await asyncio.to_thread(program_db.get_active_program, user_id):
        text += "\n\n" + t("program_replace_notice", lang)
    if draft["goal"] == "sport":
        text += "\n\n" + t("program_sport_caution", lang)
    display = message.edit_text if edit else message.answer
    await display(text, reply_markup=_preview_keyboard(lang), parse_mode="HTML")


async def _show_question(
    message: Message,
    user_id: int,
    state: str,
    *,
    edit: bool = True,
) -> None:
    lang = _lang(user_id)
    if state == STATE_EQUIPMENT:
        _set(user_id, state)
        display = message.edit_text if edit else message.answer
        await display(
            t("program_question_equipment", lang),
            reply_markup=_equipment_keyboard(user_id, lang),
        )
        return
    if state == STATE_NOTES:
        _set(user_id, state)
        keyboard = _keyboard([[
            _button("program_skip", "program:skip_notes", lang),
        ]] + _step_keyboard(lang).inline_keyboard, lang)
        display = message.edit_text if edit else message.answer
        await display(
            t("program_question_notes", lang),
            reply_markup=keyboard,
        )
        return
    if state == STATE_EQUIPMENT_OTHER:
        _set(user_id, state)
        keyboard = _keyboard([[
            _button("program_skip", "program:skip_other", lang),
        ]] + _step_keyboard(lang).inline_keyboard, lang)
        display = message.edit_text if edit else message.answer
        await display(
            t("program_question_other_equipment", lang),
            reply_markup=keyboard,
        )
        return

    field = next(
        (name for name, (_, option_state, _) in _OPTIONS.items()
         if option_state == state),
        None,
    )
    if field is None:
        await _show_menu(message, user_id, edit=edit)
        return
    _, _, prompt_key = _OPTIONS[field]
    _set(user_id, state)
    display = message.edit_text if edit else message.answer
    await display(
        t(prompt_key, lang),
        reply_markup=_choice_keyboard(field, _OPTIONS[field][0], lang),
    )


@router.message(Command("program"))
async def program_command(message: Message) -> None:
    if not message.from_user:
        return
    _clear(message.from_user.id)
    await _show_menu(message, message.from_user.id)


@router.message(
    lambda message: bool(
        message.from_user
        and _state(message.from_user.id) in (STATE_EQUIPMENT_OTHER, STATE_NOTES)
        and not (message.text or "").startswith("/")
    )
)
async def receive_program_text(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    user_id = user.id
    lang = _lang(user_id)
    state = _state(user_id)
    if not message.text:
        await message.answer(t("program_text_only", lang))
        return
    value = message.text.strip()
    if state == STATE_EQUIPMENT_OTHER:
        if not value:
            await message.answer(t("program_empty_input", lang))
            return
        if len(value) > 120:
            await message.answer(t("program_equipment_too_long", lang))
            return
        draft = _drafts.get(user_id)
        if draft is None:
            _clear(user_id)
            await message.answer(t("program_invalid_choice", lang))
            return
        draft["other_equipment"] = value
        await _show_question(message, user_id, STATE_NOTES, edit=False)
        return
    if state == STATE_NOTES:
        if not value:
            await message.answer(t("program_empty_input", lang))
            return
        if len(value) > MAX_NOTES_LENGTH:
            await message.answer(t("program_notes_too_long", lang))
            return
        draft = _drafts.get(user_id)
        if draft is None:
            _clear(user_id)
            await message.answer(t("program_invalid_choice", lang))
            return
        draft["notes"] = value
        await _show_preview(message, user_id, edit=False)


@router.message(
    lambda message: bool(
        message.from_user
        and _state(message.from_user.id) in _QUESTION_STATES + (STATE_SAVING,)
        and not (message.text or "").startswith("/")
    )
)
async def receive_program_non_text_answer(message: Message) -> None:
    if not message.from_user:
        return
    lang = _lang(message.from_user.id)
    if not message.text:
        await message.answer(t("program_text_only", lang))
    else:
        await message.answer(t("program_choose_button", lang))


@router.callback_query(F.data.startswith("program:"))
async def handle_program_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    user_id = callback.from_user.id
    lang = _lang(user_id)
    parts = (callback.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action in ("open", "menu", "view"):
        _clear(user_id)
        await callback.answer()
        await _show_menu(callback.message, user_id, edit=True)
        return
    if action == "create":
        _drafts[user_id] = {"equipment": []}
        await callback.answer()
        await _show_question(callback.message, user_id, STATE_GOAL)
        return
    if action == "cancel":
        _clear(user_id)
        await callback.answer()
        await _show_menu(callback.message, user_id, edit=True)
        return
    if action == "back":
        current = _state(user_id)
        sequence = (
            STATE_GOAL,
            STATE_LOCATION,
            STATE_FREQUENCY,
            STATE_DURATION,
            STATE_LEVEL,
            STATE_EQUIPMENT,
            STATE_EQUIPMENT_OTHER,
            STATE_NOTES,
            STATE_CONFIRM,
        )
        if current == STATE_GOAL or current not in sequence:
            _clear(user_id)
            await callback.answer()
            await _show_menu(callback.message, user_id, edit=True)
            return
        previous = sequence[sequence.index(current) - 1]
        if previous == STATE_EQUIPMENT_OTHER:
            previous = STATE_EQUIPMENT
        if current == STATE_NOTES and "other" not in _drafts.get(
            user_id, {}
        ).get("equipment", []):
            previous = STATE_EQUIPMENT
        await callback.answer()
        await _show_question(callback.message, user_id, previous)
        return

    if action == "choose" and len(parts) == 4:
        field, value = parts[2], parts[3]
        config = _OPTIONS.get(field)
        if not config or value not in config[0] or _state(user_id) != config[1]:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        if user_id not in _drafts:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        _drafts[user_id][field] = value
        next_states = {
            "goal": STATE_LOCATION,
            "location": STATE_FREQUENCY,
            "frequency": STATE_DURATION,
            "duration": STATE_LEVEL,
            "level": STATE_EQUIPMENT,
        }
        await callback.answer()
        await _show_question(callback.message, user_id, next_states[field])
        return

    if action == "equipment" and len(parts) == 3:
        if parts[2] == "done":
            if _state(user_id) != STATE_EQUIPMENT or user_id not in _drafts:
                await callback.answer(
                    t("program_invalid_choice", lang),
                    show_alert=True,
                )
                return
            selected = _drafts[user_id].get("equipment", [])
            if not selected:
                await callback.answer(
                    t("program_select_equipment", lang),
                    show_alert=True,
                )
                return
            await callback.answer()
            next_state = (
                STATE_EQUIPMENT_OTHER if "other" in selected else STATE_NOTES
            )
            if next_state == STATE_NOTES:
                _drafts[user_id].setdefault("notes", "")
            await _show_question(callback.message, user_id, next_state)
            return
        if _state(user_id) != STATE_EQUIPMENT or parts[2] not in EQUIPMENT:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        selected = set(_drafts.get(user_id, {}).get("equipment", []))
        item = parts[2]
        if item == "none":
            selected = set() if selected == {"none"} else {"none"}
        else:
            selected.discard("none")
            if item in selected:
                selected.remove(item)
            else:
                selected.add(item)
        _drafts[user_id]["equipment"] = sorted(selected)
        await callback.answer()
        await _show_question(callback.message, user_id, STATE_EQUIPMENT)
        return

    if action == "skip_other" and _state(user_id) == STATE_EQUIPMENT_OTHER:
        if user_id not in _drafts:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        _drafts[user_id]["other_equipment"] = ""
        _drafts[user_id].setdefault("notes", "")
        await callback.answer()
        await _show_question(callback.message, user_id, STATE_NOTES)
        return

    if action == "skip_notes" and _state(user_id) == STATE_NOTES:
        if user_id not in _drafts:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        _drafts[user_id]["notes"] = ""
        await callback.answer()
        await _show_preview(callback.message, user_id)
        return

    if action == "confirm":
        if _state(user_id) != STATE_CONFIRM or user_id not in _drafts:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        try:
            preferences = validate_preferences(_drafts[user_id])
        except ValueError:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        _set(user_id, STATE_SAVING)
        await callback.answer()
        try:
            age = await asyncio.to_thread(program_db.get_user_age, user_id)
            content = generate_program(preferences, age=age)
            program_id = await asyncio.to_thread(
                program_db.save_program,
                user_id,
                preferences,
                content,
            )
        except ValueError as exc:
            _set(user_id, STATE_CONFIRM)
            log.error(
                "Training program generation or save failed error_type=%s",
                type(exc).__name__,
            )
            await callback.message.answer(t("program_save_error", lang))
            return
        except sqlite3.Error as exc:
            _set(user_id, STATE_CONFIRM)
            log.error(
                "Training program persistence failed error_type=%s",
                type(exc).__name__,
                exc_info=True,
            )
            await callback.message.answer(t("program_save_error", lang))
            return
        _clear(user_id)
        saved = {
            "id": program_id,
            "preferences": preferences,
            "content": content,
        }
        await callback.message.edit_text(
            _summary_text(saved, lang),
            reply_markup=_plan_keyboard(saved, lang),
            parse_mode="HTML",
        )
        return

    if action == "day" and len(parts) == 4:
        try:
            program_id, index = int(parts[2]), int(parts[3])
        except ValueError:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        program = await asyncio.to_thread(program_db.get_program, user_id, program_id)
        text = _session_text(program, index, lang) if program else None
        if text is None:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        markup = _keyboard([[
            InlineKeyboardButton(
                text=t("program_back_to_plan", lang),
                callback_data=f"program:plan:{program_id}",
            ),
        ]], lang)
        await callback.answer()
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        return

    if action == "archives":
        archived = await asyncio.to_thread(program_db.list_archived_programs, user_id)
        if not archived:
            await callback.answer(t("program_no_archives", lang), show_alert=True)
            return
        rows = [[InlineKeyboardButton(
            text=t("program_archive_item", lang).format(
                program_id=item["id"],
                created=html.escape(item["created_at"][:10]),
            ),
            callback_data=f"program:archived:{item['id']}",
        )] for item in archived]
        rows.append([_button("program_to_menu", "program:menu", lang)])
        await callback.answer()
        await callback.message.edit_text(
            t("program_archives_title", lang),
            reply_markup=_keyboard(rows, lang),
        )
        return

    if action == "archived" and len(parts) == 3 and parts[2].isdigit():
        program_id = int(parts[2])
        program = await asyncio.to_thread(program_db.get_program, user_id, program_id)
        if not program or program["status"] != "archived":
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            _summary_text(program, lang),
            reply_markup=_plan_keyboard(program, lang, archived=True),
            parse_mode="HTML",
        )
        return

    if action == "plan" and len(parts) == 3 and parts[2].isdigit():
        program = await asyncio.to_thread(
            program_db.get_program,
            user_id,
            int(parts[2]),
        )
        if not program:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            _summary_text(program, lang),
            reply_markup=_plan_keyboard(
                program,
                lang,
                archived=program["status"] == "archived",
            ),
            parse_mode="HTML",
        )
        return

    if action == "archive":
        active = await asyncio.to_thread(program_db.get_active_program, user_id)
        if not active:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        _set(user_id, STATE_ARCHIVE_CONFIRM)
        rows = [[_button("program_archive_confirm", "program:archive_yes", lang)]]
        rows.append([_button("program_back_to_plan", "program:view", lang)])
        await callback.answer()
        await callback.message.edit_text(
            t("program_archive_confirmation", lang),
            reply_markup=_keyboard(rows, lang),
        )
        return

    if action == "archive_yes":
        if _state(user_id) != STATE_ARCHIVE_CONFIRM:
            await callback.answer(t("program_invalid_choice", lang), show_alert=True)
            return
        active = await asyncio.to_thread(program_db.get_active_program, user_id)
        if not active:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        archived = await asyncio.to_thread(
            program_db.archive_program,
            user_id,
            active["id"],
        )
        if not archived:
            await callback.answer(t("program_not_found", lang), show_alert=True)
            return
        _clear(user_id)
        await callback.answer(t("program_archived", lang))
        await _show_menu(callback.message, user_id, edit=True)
        return

    await callback.answer(t("program_invalid_choice", lang), show_alert=True)
