import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import bot_legacy
import services.workout_service as workout_service
from locales import t


class _Message:
    def __init__(self, user_id=77):
        self.from_user = type("User", (), {"id": user_id})()
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "onboarding.sqlite3"
        db = sqlite3.connect(self.path)
        db.executescript("""
            CREATE TABLE workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, date TEXT, note TEXT
            );
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, text TEXT, date TEXT, session_id INTEGER
            );
        """)
        db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def db(self):
        return sqlite3.connect(self.path)

    def test_welcome_menu_has_all_real_actions_in_both_languages(self):
        for lang in ("uk", "en"):
            callbacks = {
                button.callback_data
                for row in bot_legacy.welcome_keyboard(lang).inline_keyboard
                for button in row
            }
            self.assertEqual(
                callbacks,
                {"welcome_workout", "welcome_stats", "welcome_history", "welcome_help",
                 "welcome_lang_en" if lang == "uk" else "welcome_lang_uk"},
            )
            self.assertIn("SportBot", t("welcome", lang))
            self.assertIn("/workout", t("help", lang))

    def test_start_is_repeatable_and_keeps_existing_language(self):
        message = _Message(88)
        with patch.object(bot_legacy, "ensure_user") as ensure, \
             patch.object(bot_legacy, "get_user_language", return_value="en"):
            asyncio.run(bot_legacy.start(message))
            asyncio.run(bot_legacy.start(message))

        self.assertEqual(ensure.call_count, 2)
        self.assertEqual(len(message.answers), 2)
        self.assertIn("personal workout journal", message.answers[0][0])

    def test_first_save_notification_is_only_sent_once(self):
        def save(uid, exercises, note, date):
            with patch.object(workout_service, "get_db", self.db):
                return workout_service.save_workout_session(uid, exercises, note, date)

        common = patch.multiple(
            bot_legacy,
            get_db=self.db,
            save_workout_session=save,
            claim_daily_coin_reward=lambda *args: (False, 0),
            get_coin_balance=lambda uid: 0,
            award_xp_and_streak=lambda *args: {"streak_bonus_coins": 0},
            get_user_language=lambda uid: "en",
            t_pair=lambda lang, uk, en: en,
            clear_user_state=lambda uid: None,
        )
        first = _Message()
        second = _Message()
        with common:
            asyncio.run(bot_legacy._save_workout_with_note(first, ["Run"], None, 77))
            asyncio.run(bot_legacy._save_workout_with_note(second, ["Walk"], None, 77))

        self.assertEqual(len(first.answers), 2)
        self.assertIn("first workout", first.answers[1][0])
        self.assertEqual(len(second.answers), 1)

    def test_help_has_return_to_menu(self):
        callbacks = {
            button.callback_data
            for row in bot_legacy.help_keyboard("uk").inline_keyboard
            for button in row
        }
        self.assertIn("welcome_menu", callbacks)


if __name__ == "__main__":
    unittest.main()
