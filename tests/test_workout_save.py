import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_legacy
import services.workout_service as workout_service


class _Message:
    def __init__(self, message_user_id):
        self.from_user = type("User", (), {"id": message_user_id})()
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


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

    def _save_direct(self, user_id=101, exercises=None, note=None, workout_date="2026-11-06"):
        with patch.object(workout_service, "get_db", self._db):
            return workout_service.save_workout_session(
                user_id, exercises or ["Run", "Push ups"], note, workout_date
            )

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
            with patch.object(workout_service, "get_db", self._db):
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

        with self._patches(), patch.object(workout_service, "get_db", self._db), self.assertRaises(sqlite3.IntegrityError):
            asyncio.run(bot_legacy._save_workout_with_note(_Message(999), ["Run", "FAIL"], None, 101))

        db = self._connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workout_sessions").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0], 0)
        db.close()

    def test_service_saves_multiple_exercises_with_one_session(self):
        session_id = self._save_direct(note="Morning workout")

        db = self._connect()
        self.assertEqual(
            db.execute("SELECT id FROM workout_sessions WHERE user_id=101").fetchone()[0],
            session_id,
        )
        rows = db.execute(
            "SELECT user_id, text, session_id FROM workouts ORDER BY id"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[0] for row in rows}, {101})
        self.assertEqual({row[2] for row in rows}, {session_id})
        db.close()

    def test_empty_exercises_raise_before_database_connection(self):
        with patch.object(workout_service, "get_db") as get_db:
            with self.assertRaises(ValueError):
                workout_service.save_workout_session(101, [], None, "2026-11-06")
        get_db.assert_not_called()

    def test_invalid_user_id_raises_before_database_connection(self):
        with patch.object(workout_service, "get_db") as get_db:
            for user_id in (0, -1, "101", True):
                with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                    workout_service.save_workout_session(
                        user_id, ["Run"], None, "2026-11-06"
                    )
        get_db.assert_not_called()

    def test_invalid_exercise_and_date_raise_before_database_connection(self):
        with patch.object(workout_service, "get_db") as get_db:
            with self.assertRaises(ValueError):
                workout_service.save_workout_session(101, ["  "], None, "2026-11-06")
            with self.assertRaises(ValueError):
                workout_service.save_workout_session(101, ["Run"], None, "   ")
        get_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
