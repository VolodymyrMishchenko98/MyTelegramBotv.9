import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_legacy
import db_improved
import services.reward_settlement as reward_settlement


class BackupV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "backup.sqlite3"
        self._create_db(with_ledger=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_db(self, with_ledger: bool):
        db = sqlite3.connect(self.path)
        db.executescript("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY, height INTEGER, gender TEXT, age INTEGER,
                goal TEXT, current_weight REAL, weekly_goal INTEGER,
                streak_days INTEGER, last_workout_date TEXT, xp INTEGER, level INTEGER,
                coin_balance INTEGER, language TEXT, show_height INTEGER, show_gender INTEGER,
                show_age INTEGER, show_weight INTEGER, show_goal INTEGER, deleted_at TEXT
            );
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, date TEXT,
                is_challenge INTEGER DEFAULT 0, session_id INTEGER, recorded_at TEXT
            );
            CREATE TABLE workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT,
                note TEXT, recorded_at TEXT
            );
            CREATE TABLE weights (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, weight REAL, date TEXT);
            CREATE TABLE daily_tasks (user_id INTEGER, date TEXT, task_id TEXT, progress INTEGER, completed INTEGER,
                                      PRIMARY KEY(user_id, date));
            CREATE TABLE coin_rewards (user_id INTEGER, date TEXT, source TEXT, amount INTEGER,
                                       idem_key TEXT, created_at TEXT, UNIQUE(user_id, date, source));
            CREATE TABLE user_items (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id TEXT, purchased_at TEXT);
        """)
        if with_ledger:
            db.executescript("""
                CREATE TABLE reward_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source TEXT,
                    action_key TEXT, created_at TEXT, UNIQUE(user_id, source, action_key)
                );
                CREATE TABLE achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                    achievement_key TEXT, awarded_at TEXT, UNIQUE(user_id, achievement_key)
                );
            """)
        db.executemany(
            "INSERT INTO users (user_id, xp, level, coin_balance, language) VALUES (?, ?, ?, ?, ?)",
            [(1, 50, 2, 30, "uk"), (2, 1, 1, 0, "en")],
        )
        db.execute("INSERT INTO workouts (user_id, text, date, recorded_at) VALUES (1, 'Run', '2026-11-06', '2026-11-06 07:30:00')")
        db.execute("INSERT INTO coin_rewards VALUES (1, '2026-11-06', 'suggest', 25, 'idem-1', '2026-11-06 08:00:00')")
        if with_ledger:
            db.execute("INSERT INTO reward_events (user_id, source, action_key, created_at) VALUES (1, 'suggest', 'suggest:2026-11-06', '2026-11-06 08:00:00')")
            db.execute("INSERT INTO achievements (user_id, achievement_key, awarded_at) VALUES (1, 'first_workout', '2026-11-06 08:00:00')")
        db.commit()
        db.close()

    def _db(self):
        return sqlite3.connect(self.path)

    def test_export_v3_is_user_scoped_and_contains_ledgers(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)

        self.assertEqual(backup["backup_version"], 3)
        self.assertEqual(backup["reward_events"], [{
            "source": "suggest", "action_key": "suggest:2026-11-06", "created_at": "2026-11-06 08:00:00"
        }])
        self.assertEqual(backup["achievements"][0]["achievement_key"], "first_workout")
        self.assertEqual(backup["coin_rewards"][0]["amount"], 25)

    def test_import_v3_replaces_target_and_restores_ledger(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
            ok, message = bot_legacy.import_user_data(2, backup)

        self.assertTrue(ok, message)
        db = self._db()
        self.assertEqual(db.execute("SELECT xp, coin_balance FROM users WHERE user_id=2").fetchone(), (50, 30))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM reward_events WHERE user_id=2").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=2").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM reward_events WHERE user_id=1").fetchone()[0], 1)
        db.close()

    def test_import_reactivates_soft_deleted_user_and_restores_xp_level(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
            backup["profile"]["xp"] = 130
            backup["profile"]["level"] = 2
            db = self._db()
            db.execute("UPDATE users SET deleted_at=? WHERE user_id=2", ("2026-11-06T21:00:00",))
            db.commit()
            db.close()
            ok, message = bot_legacy.import_user_data(2, backup)
        self.assertTrue(ok, message)

        db = self._db()
        self.assertEqual(db.execute("SELECT deleted_at, xp, level FROM users WHERE user_id=2").fetchone(), (None, 130, 2))
        db.close()

        def fetch_one_from_fixture(query, params=None):
            conn = self._db()
            try:
                return conn.execute(query, params or ()).fetchone()
            finally:
                conn.close()

        with patch.object(db_improved, "fetch_one", side_effect=fetch_one_from_fixture):
            xp_info = db_improved.get_user_xp_level(2)
        self.assertEqual((xp_info["xp"], xp_info["level"]), (130, 2))

    def test_import_keeps_active_user_active(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
            ok, message = bot_legacy.import_user_data(2, backup)
        self.assertTrue(ok, message)
        db = self._db()
        self.assertIsNone(db.execute("SELECT deleted_at FROM users WHERE user_id=2").fetchone()[0])
        db.close()

    def test_same_imported_action_key_cannot_pay_again(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
            ok, _ = bot_legacy.import_user_data(2, backup)
        self.assertTrue(ok)

        with patch.object(reward_settlement, "get_db", self._db):
            result = reward_settlement.settle_action_rewards(
                2, "2026-11-06", 20, 25, "suggest", action_key="suggest:2026-11-06"
            )
        self.assertTrue(result["already_settled"])
        self.assertEqual(result["xp_awarded"], 0)

    def test_old_backup_fences_historical_achievements_without_paying(self):
        old_backup = {
            "profile": {"xp": 50, "level": 2, "coin_balance": 30, "language": "uk"},
            "workouts": [{"text": "Run", "date": "2026-11-06", "is_challenge": 0}],
            "workout_sessions": [], "weights": [], "daily_tasks": [],
            "coin_rewards": [{"date": "2026-11-06", "source": "suggest", "amount": 25}],
            "user_items": [],
        }
        with patch.object(bot_legacy, "get_db", self._db):
            ok, message = bot_legacy.import_user_data(2, old_backup)
        self.assertTrue(ok, message)
        db = self._db()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM achievements WHERE user_id=2 AND achievement_key='first_workout'").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM reward_events WHERE user_id=2 AND action_key='suggest:2026-11-06'").fetchone()[0], 1)
        db.close()

    def test_import_rolls_back_ledger_and_profile_on_duplicate_event(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
        backup["reward_events"].append(dict(backup["reward_events"][0]))

        db = self._db()
        db.execute("UPDATE users SET deleted_at=?, xp=?, level=? WHERE user_id=2", ("deleted-before-import", 7, 1))
        db.commit()
        db.close()

        with patch.object(bot_legacy, "get_db", self._db):
            ok, _ = bot_legacy.import_user_data(2, backup)
        self.assertFalse(ok)
        db = self._db()
        self.assertEqual(db.execute("SELECT xp, coin_balance, deleted_at FROM users WHERE user_id=2").fetchone(), (7, 0, "deleted-before-import"))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM reward_events WHERE user_id=2").fetchone()[0], 0)
        db.close()

    def test_repeated_import_does_not_duplicate_user_data(self):
        with patch.object(bot_legacy, "get_db", self._db):
            backup = bot_legacy.get_user_export_data(1)
            self.assertTrue(bot_legacy.import_user_data(2, backup)[0])
            self.assertTrue(bot_legacy.import_user_data(2, backup)[0])
        db = self._db()
        for table in ("workouts", "workout_sessions", "coin_rewards", "reward_events", "achievements"):
            self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=2").fetchone()[0],
                             db.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=1").fetchone()[0], table)
        db.close()

    def test_import_on_old_schema_creates_ledger_tables(self):
        old_path = Path(self.tmp.name) / "old.sqlite3"
        db = sqlite3.connect(old_path)
        db.executescript("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY, height INTEGER, gender TEXT, age INTEGER,
                goal TEXT, current_weight REAL, weekly_goal INTEGER, streak_days INTEGER,
                last_workout_date TEXT, xp INTEGER, level INTEGER, coin_balance INTEGER,
                language TEXT, show_height INTEGER, show_gender INTEGER, show_age INTEGER,
                show_weight INTEGER, show_goal INTEGER
            );
            CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, date TEXT, is_challenge INTEGER, session_id INTEGER, recorded_at TEXT);
            CREATE TABLE workout_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, note TEXT, recorded_at TEXT);
            CREATE TABLE weights (id INTEGER, user_id INTEGER, weight REAL, date TEXT);
            CREATE TABLE daily_tasks (user_id INTEGER, date TEXT, task_id TEXT, progress INTEGER, completed INTEGER);
            CREATE TABLE coin_rewards (user_id INTEGER, date TEXT, source TEXT, amount INTEGER, created_at TEXT);
            CREATE TABLE user_items (id INTEGER, user_id INTEGER, item_id TEXT, purchased_at TEXT);
            INSERT INTO users (user_id, xp, level, coin_balance) VALUES (2, 0, 1, 0);
        """)
        db.commit(); db.close()
        old_backup = {
            "profile": {"xp": 2, "level": 1, "coin_balance": 3},
            "workouts": [], "weights": [], "daily_tasks": [], "coin_rewards": [], "user_items": []
        }
        with patch.object(bot_legacy, "get_db", lambda: sqlite3.connect(old_path)):
            ok, message = bot_legacy.import_user_data(2, old_backup)
        self.assertTrue(ok, message)
        db = sqlite3.connect(old_path)
        self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='reward_events'").fetchone())
        db.close()


if __name__ == "__main__":
    unittest.main()
