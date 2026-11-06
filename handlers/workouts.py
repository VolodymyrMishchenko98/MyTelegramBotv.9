"""
/workout flow — user enters his workout as text (comma-separated exercises).

Steps:
1. ``/workout``  → set state, ask for text input.
2. Free-text → split by ``,``, save each row, award XP + coins.
"""
from __future__ import annotations

import datetime
import logging

from aiogram import Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import game_config
from services.logging_config import get_logger

log = get_logger("handlers.workouts")
router = Router()

# Keyboard builders (local aliases — no direct import of bot.py)
_SUGGEST_KB: callable  # set by register()


def register(
    dp: Dispatcher,
    get_user_language: callable,
    t_pair: callable,
    get_db: callable,
    _set_user_state: callable,      # set_user_state from bot
    clear_user_state: callable,
    build_workout: callable,        # generate_workout from bot
    suggest_keyboard: callable,     # keyboard builder
    award_xp_and_streak: callable,  # from bot
    claim_reward: callable,         # claim_daily_coin_reward from bot
    format_coin_reward: callable,
) -> None:
    global _SUGGEST_KB
    _SUGGEST_KB = suggest_keyboard

    @dp.message(Command("workout"))
    async def workout_cmd(message: Message):
        uid   = message.from_user.id
        lang  = get_user_language(uid)
        _set_user_state(uid, "workout")
        prompt_uk = (
            "Введи тренування.\n"
            "Можна через кому:\n"
            "Біг 30 хвилин, Відтискування 4x20"
        )
        prompt_en = (
            "Enter workout.\n"
            "Separate by commas:\n"
            "Running 30 min, Push ups 4x20"
        )
        await message.answer(t_pair(lang, prompt_uk, prompt_en))

    @dp.message(
        StateFilter("workout"),
        lambda m: m.text and not m.text.startswith("/"),
    )
    async def handle_workout(message: Message):
        uid   = message.from_user.id
        lang  = get_user_language(uid)
        if not message.text:
            await message.answer(
                t_pair(lang, "Введи хоча б одну вправу.", "Enter at least one exercise.")
            )
            return

        exercises = [x.strip() for x in message.text.split(",") if x.strip()]
        if not exercises:
            await message.answer(
                t_pair(lang, "Введи хоча б одну вправу.", "Enter at least one exercise.")
            )
            return

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        db   = get_db()
        cur  = db.cursor()
        for ex in exercises:
            cur.execute(
                "INSERT INTO workouts (user_id, text, date) VALUES (?, ?, ?)",
                (uid, ex, today_str),
            )
        db.commit()
        db.close()

        coin_reward = min(len(exercises) * game_config.WORKOUT_COIN_REWARD, 50)
        xp_amount   = min(len(exercises) * game_config.WORKOUT_XP_REWARD, 20)

        # Idempotent coin reward
        today    = datetime.datetime.now().strftime("%Y-%m-%d")
        idem_key = f"{uid}:{today}:workout"
        rewarded, balance = claim_reward(uid, "workout", coin_reward, idem_key, today) \
            if coin_reward else (False, 0)

        # XP + streak update
        sync_inf  = award_xp_and_streak(uid, today_str, xp_amount)
        balance  += sync_inf.get("streak_bonus_coins", 0)

        xp_line = f"\n⭐ +{xp_amount} XP"
        level_line = ""
        if sync_inf.get("leveled_up"):
            level_line = t_pair(
                lang,
                f"\n🏆 LEVEL UP! Рівень {sync_inf['level']}",
                f"\n🏆 LEVEL UP! Level {sync_inf['level']}",
            )
        streak_line = ""
        if sync_inf.get("streak_bonus_coins"):
            streak_line = t_pair(
                lang,
                f"\n🔥 Streak bonus: +{sync_inf['streak_bonus_coins']}🪙",
                f"\n🔥 Streak bonus: +{sync_inf['streak_bonus_coins']}🪙",
            )

        coin_line = (
            format_coin_reward(lang, coin_reward, balance)
            if rewarded else
            t_pair(
                lang,
                f"\n🪙 Нагорода за сьогодні вже отримана\nБаланс: {balance}",
                f"\n🪙 Today's reward already claimed\nBalance: {balance}",
            )
        )

        reply = t_pair(
            lang,
            f"Збережено: {len(exercises)}{coin_line}{xp_line}{level_line}{streak_line}",
            f"Saved: {len(exercises)}{coin_line}{xp_line}{level_line}{streak_line}",
        )
        await message.answer(reply)
        clear_user_state(uid)
