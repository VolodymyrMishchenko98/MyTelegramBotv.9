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
                if button.callback_data
            }
            self.assertEqual(
                callbacks,
                {"welcome_workout", "welcome_stats", "welcome_history", "welcome_help",
                 "welcome_lang_en" if lang == "uk" else "welcome_lang_uk"},
            )
            welcome = t("welcome", lang)
            self.assertIn("SportBot", welcome)
            self.assertIn(
                "вправи через кому" if lang == "uk" else "exercises separated by commas",
                welcome,
            )
            self.assertIn(
                "фактично нараховані" if lang == "uk" else "actually granted",
                welcome,
            )
            self.assertIn("/workout", t("help", lang))

    def test_start_is_repeatable_and_keeps_existing_language(self):
        message = _Message(88)
        with patch.object(bot_legacy, "ensure_user") as ensure, \
             patch.object(bot_legacy, "get_user_language", return_value="en"):
            asyncio.run(bot_legacy.start(message))
            asyncio.run(bot_legacy.start(message))

        self.assertEqual(ensure.call_count, 2)
        self.assertEqual(len(message.answers), 2)
        self.assertIn("workout journal", message.answers[0][0])
        self.assertIn("exercises separated by commas", message.answers[0][0])

    def test_first_save_combines_confirmation_rewards_and_next_step(self):
        def save(uid, exercises, note, date):
            with patch.object(workout_service, "get_db", self.db):
                return workout_service.save_workout_session(uid, exercises, note, date)

        def settled(uid, *args, **kwargs):
            return {
                "user_id": uid,
                "xp_awarded": 10,
                "coins_awarded": 5,
                "balance": 15,
                "level": 2,
                "xp": 100,
                "leveled_up": True,
                "achievements": [],
            }

        common = patch.multiple(
            bot_legacy,
            get_db=self.db,
            save_workout_session=save,
            settle_action_rewards=settled,
            get_user_xp_level=lambda uid: {"xp": 100, "level": 2},
            get_user_language=lambda uid: "en",
            t_pair=lambda lang, uk, en: en,
            clear_user_state=lambda uid: None,
        )
        first = _Message()
        second = _Message()
        with common:
            asyncio.run(bot_legacy._save_workout_with_note(first, ["Run"], None, 77))
            asyncio.run(bot_legacy._save_workout_with_note(second, ["Walk"], None, 77))

        self.assertEqual(len(first.answers), 1)
        first_text, first_kwargs = first.answers[0]
        self.assertIn("Workout saved!", first_text)
        self.assertIn("XP: +10", first_text)
        self.assertIn("Coins: +5", first_text)
        self.assertIn("first workout", first_text)
        first_callbacks = {
            button.callback_data
            for row in first_kwargs["reply_markup"].inline_keyboard
            for button in row
        }
        self.assertEqual(first_callbacks, {"welcome_stats", "welcome_menu"})
        self.assertEqual(len(second.answers), 1)
        self.assertNotIn("first workout", second.answers[0][0])

    def test_legacy_workout_without_session_is_not_mistaken_for_first(self):
        connection = self.db()
        connection.execute(
            "INSERT INTO workouts (user_id, text, date, session_id) VALUES (79, 'Old workout', '2024-01-01', NULL)"
        )
        connection.commit()
        connection.close()

        def save(uid, exercises, note, date):
            with patch.object(workout_service, "get_db", self.db):
                return workout_service.save_workout_session(uid, exercises, note, date)

        with patch.multiple(
            bot_legacy,
            get_db=self.db,
            save_workout_session=save,
            settle_action_rewards=lambda uid, *args, **kwargs: {
                "user_id": uid, "xp_awarded": 0, "coins_awarded": 0,
                "balance": 0, "level": 1, "xp": 0, "leveled_up": False,
                "achievements": [],
            },
            get_user_xp_level=lambda uid: {"xp": 0, "level": 1},
            get_user_language=lambda uid: "en",
            clear_user_state=lambda uid: None,
        ):
            message = _Message(79)
            asyncio.run(bot_legacy._save_workout_with_note(message, ["Run"], None, 79))

        self.assertEqual(len(message.answers), 1)
        self.assertNotIn("first workout", message.answers[0][0])
        self.assertNotIn("welcome_stats", {
            button.callback_data
            for row in message.answers[0][1]["reply_markup"].inline_keyboard
            for button in row
        })

    def test_help_has_return_to_menu(self):
        callbacks = {
            button.callback_data
            for row in bot_legacy.help_keyboard("uk").inline_keyboard
            for button in row
        }
        self.assertIn("welcome_menu", callbacks)


if __name__ == "__main__":
    unittest.main()
