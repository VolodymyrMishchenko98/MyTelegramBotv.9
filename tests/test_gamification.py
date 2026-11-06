import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_legacy
import services.achievements as achievements
import services.reward_settlement as reward_settlement
from services.reward_notifications import build_reward_summary


class GamificationTests(unittest.TestCase):
    def _reward_db(self):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "rewards.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
                coin_balance INTEGER DEFAULT 0, streak_days INTEGER DEFAULT 0,
                last_workout_date TEXT, deleted_at TEXT
            );
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT,
                date TEXT, is_challenge INTEGER DEFAULT 0, recorded_at TEXT
            );
            CREATE TABLE achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                achievement_key TEXT, awarded_at TEXT,
                UNIQUE(user_id, achievement_key)
            );
        """)
        connection.execute("INSERT INTO users (user_id) VALUES (7)")
        connection.commit()
        connection.close()
        return directory, path

    def test_reward_summary_is_localized_and_contains_only_real_values(self):
        text = build_reward_summary(
            "uk",
            action_uk="Тренування збережено",
            action_en="Workout saved",
            xp=25,
            coins=5,
            balance=20,
            streak_days=4,
            level=3,
            level_up=True,
            xp_total=240,
            xp_next=300,
            achievements=[{
                "title_uk": "Перший крок", "title_en": "First Step",
                "desc_uk": "Перше тренування", "desc_en": "First workout",
                "icon": "👣", "xp": 20, "coins": 10,
            }],
        )
        self.assertIn("Тренування збережено", text)
        self.assertIn("XP: +25", text)
        self.assertIn("НОВЕ ДОСЯГНЕННЯ", text)
        self.assertNotIn("+999", text)

        english = build_reward_summary("en", action_uk="Збережено", action_en="Saved", xp=1)
        self.assertIn("Saved", english)
        self.assertNotIn("Coins", english)

    def test_same_day_streak_milestone_is_not_paid_twice(self):
        updates = [
            {"streak_days": 3, "is_new": True},
            {"streak_days": 3, "is_new": False},
        ]
        with patch("utils.streak.update_streak", side_effect=updates), \
             patch.object(bot_legacy, "add_xp_to_user", return_value={
                 "xp": 100, "level": 1, "added": 10, "leveled_up": False,
             }), \
             patch.object(bot_legacy, "execute_query") as execute:
            first = bot_legacy.award_xp_and_streak(7, "2026-11-06", 10)
            second = bot_legacy.award_xp_and_streak(7, "2026-11-06", 10)

        self.assertEqual(first["streak_bonus_coins"], 15)
        self.assertEqual(second["streak_bonus_coins"], 0)
        self.assertEqual(execute.call_count, 1)

    def test_new_achievement_is_returned_once_with_its_real_reward(self):
        with patch.object(achievements, "_ensure_table_exists"), \
             patch.object(achievements, "get_user_achievements", side_effect=[[], ["first_workout"]]), \
             patch.object(achievements, "award_achievement", return_value=True), \
             patch.object(achievements, "execute_query"), \
             patch("db_improved.add_xp_to_user"):
            first = achievements.check_and_award(7, {"workout_count": 1})
            second = achievements.check_and_award(7, {"workout_count": 1})

        self.assertEqual(first[0]["key"], "first_workout")
        self.assertEqual(first[0]["coins"], 10)
        self.assertEqual(first[0]["xp"], 20)
        self.assertEqual(second, [])

    def test_legacy_coin_reward_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coins.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE users (user_id INTEGER PRIMARY KEY, coin_balance INTEGER DEFAULT 0);
                CREATE TABLE coin_rewards (
                    user_id INTEGER, date TEXT, source TEXT, amount INTEGER, created_at TEXT,
                    UNIQUE(user_id, date, source)
                );
            """)
            connection.close()

            def ensure(uid):
                connection = sqlite3.connect(path)
                connection.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
                connection.commit()
                connection.close()

            with patch.object(bot_legacy, "get_db", lambda: sqlite3.connect(path)), \
                 patch.object(bot_legacy, "ensure_user", ensure):
                first = bot_legacy.claim_daily_coin_reward(7, "workout", 10)
                second = bot_legacy.claim_daily_coin_reward(7, "workout", 10)

            connection = sqlite3.connect(path)
            balance = connection.execute("SELECT coin_balance FROM users WHERE user_id=7").fetchone()[0]
            connection.close()

        self.assertEqual(first[0], True)
        self.assertEqual(second[0], False)
        self.assertEqual(balance, 10)

    def test_atomic_settlement_rolls_back_all_reward_fields_on_error(self):
        directory, path = self._reward_db()
        try:
            with patch.object(reward_settlement, "get_db", lambda: sqlite3.connect(path)), \
                 patch.object(reward_settlement, "_ensure_achievement_table", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    reward_settlement.settle_action_rewards(7, "2026-11-06", 10, 10, "workout")

            connection = sqlite3.connect(path)
            user = connection.execute(
                "SELECT xp, level, coin_balance, streak_days, last_workout_date FROM users WHERE user_id=7"
            ).fetchone()
            rewards = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='coin_rewards'").fetchone()[0]
            connection.close()
            self.assertEqual(user, (0, 1, 0, 0, None))
            self.assertEqual(rewards, 0)
        finally:
            directory.cleanup()

    def test_same_action_key_does_not_repeat_xp_or_streak(self):
        directory, path = self._reward_db()
        try:
            with patch.object(reward_settlement, "get_db", lambda: sqlite3.connect(path)):
                first = reward_settlement.settle_action_rewards(
                    7, "2026-11-06", 10, 10, "workout", action_key="manual:retry-safe"
                )
                second = reward_settlement.settle_action_rewards(
                    7, "2026-11-06", 10, 10, "workout", action_key="manual:retry-safe"
                )
            self.assertGreater(first["xp_awarded"], 0)
            self.assertEqual(second["xp_awarded"], 0)
            self.assertTrue(second["already_settled"])
        finally:
            directory.cleanup()

    def test_only_timestamped_workouts_can_unlock_time_achievements(self):
        directory, path = self._reward_db()
        try:
            connection = sqlite3.connect(path)
            connection.execute(
                "INSERT INTO workouts (user_id, text, date, recorded_at) VALUES (7, 'old', '2026-11-05', NULL)"
            )
            connection.execute(
                "INSERT INTO workouts (user_id, text, date, recorded_at) VALUES (7, 'morning', '2026-11-05', '2026-11-05 07:30:00')"
            )
            connection.commit()
            connection.close()

            with patch.object(reward_settlement, "get_db", lambda: sqlite3.connect(path)):
                result = reward_settlement.settle_action_rewards(7, "2026-11-06", 0, 0, "workout")

            keys = {item["key"] for item in result["achievements"]}
            self.assertIn("early_bird", keys)
            self.assertNotIn("night_owl", keys)
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
