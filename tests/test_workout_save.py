import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_legacy


class _Message:
    def __init__(self, message_user_id):
        self.from_user = type("User", (), {"id": message_user_id})()
        self.answers = []

    async def answer(self, text):
        self.answers.append(text)


class WorkoutSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.sqlite3"
        db = self._connect()
        db.executescript(
            """
            CREATE TABLE workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, date TEXT NOT NULL, note TEXT
            );
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, text TEXT, date TEXT, session_id INTEGER
            );
            CREATE TABLE users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0,
                               level INTEGER DEFAULT 1, coin_balance INTEGER DEFAULT 0);
            """
        )
        db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _db(self):
        return self._connect()

    def _patches(self):
        return patch.multiple(
            bot_legacy,
            get_db=self._db,
            claim_daily_coin_reward=lambda *args: (False, 0),
            get_coin_balance=lambda uid: 0,
            award_xp_and_streak=lambda *args: {"streak_bonus_coins": 0},
            get_user_language=lambda uid: "en",
            t_pair=lambda lang, uk, en: en,
            clear_user_state=lambda uid: None,
        )

    def test_explicit_callback_user_owns_all_rows_and_is_visible_to_stats_queries(self):
        real_user = 101
        bot_user = 999
        message = _Message(bot_user)

        with self._patches():
            asyncio.run(bot_legacy._save_workout_with_note(message, ["Run", "Push ups"], None, real_user))

        db = self._connect()
        self.assertEqual(db.execute("SELECT user_id FROM workout_sessions").fetchone()[0], real_user)
        self.assertEqual(
            {row[0] for row in db.execute("SELECT user_id FROM workouts")},
            {real_user},
        )
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (real_user,)).fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (bot_user,)).fetchone()[0], 0)
        db.close()

    def test_save_failure_rolls_back_session_and_exercises(self):
        db = self._connect()
        db.execute("CREATE TRIGGER fail_second_exercise BEFORE INSERT ON workouts WHEN NEW.text='FAIL' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        db.commit()
        db.close()

        with self._patches(), self.assertRaises(sqlite3.IntegrityError):
            asyncio.run(bot_legacy._save_workout_with_note(_Message(999), ["Run", "FAIL"], None, 101))

        db = self._connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workout_sessions").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
