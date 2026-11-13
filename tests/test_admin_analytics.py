import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import admin
from services import admin_analytics


class AdminAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "analytics.sqlite3"
        with self._database() as db:
            db.executescript("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY, level INTEGER, xp INTEGER,
                    coin_balance INTEGER, deleted_at TEXT
                );
                CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, date TEXT,
                    is_challenge INTEGER, session_id INTEGER, recorded_at TEXT
                );
                CREATE TABLE workout_sessions (
                    id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, note TEXT,
                    recorded_at TEXT
                );
                CREATE TABLE coin_rewards (
                    id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, source TEXT,
                    amount INTEGER, created_at TEXT
                );
                CREATE TABLE achievements (
                    id INTEGER PRIMARY KEY, user_id INTEGER, achievement_key TEXT,
                    awarded_at TEXT
                );
            """)

        def fetch_all(query, params=None):
            with self._database() as db:
                return db.execute(query, params or ()).fetchall()

        self.fetch_all_patcher = patch.object(admin_analytics, "fetch_all", fetch_all)
        self.fetch_all_patcher.start()
        self.today = date(2026, 11, 13)

    @contextmanager
    def _database(self):
        db = sqlite3.connect(self.db_path)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def tearDown(self):
        self.fetch_all_patcher.stop()
        self.tmp.cleanup()

    def _insert_users(self):
        with self._database() as db:
            db.executemany(
                "INSERT INTO users (user_id, level, xp, coin_balance, deleted_at) VALUES (?, ?, ?, ?, ?)",
                [
                    (1, 2, 200, 100, None),
                    (2, None, None, None, None),
                    (3, 10, 900, 999, "deleted"),
                ],
            )

    def test_empty_database_returns_zeroes_for_every_section(self):
        for category in admin_analytics.CATEGORIES:
            with self.subTest(category=category):
                result = admin_analytics.get_report(category, 7, self.today)
                self.assertTrue(result)
        users = admin_analytics.get_report("users", 7, self.today)
        self.assertEqual((users["total"], users["active"], users["deleted"]), (0, 0, 0))
        self.assertEqual(admin_analytics.get_report("activity", 7, self.today)["active_users"], 0)
        self.assertEqual(admin_analytics.get_report("workouts", 7, self.today)["sessions"], 0)
        self.assertEqual(admin_analytics.get_report("economy", 7, self.today)["recorded_rewards"], 0)
        self.assertEqual(admin_analytics.get_report("progress", 7, self.today)["achievements_count"], 0)

    def test_users_include_deleted_accounts_and_handle_null_fields(self):
        self._insert_users()
        result = admin_analytics.get_report("users", 7, self.today)
        self.assertEqual((result["total"], result["active"], result["deleted"]), (3, 2, 1))
        self.assertEqual(result["average_level"], 1.5)
        self.assertEqual(result["levels"], [(1, 1), (2, 1)])

    def test_activity_periods_have_inclusive_current_and_previous_boundaries(self):
        self._insert_users()
        with self._database() as db:
            for days in admin_analytics.PERIODS:
                db.execute("DELETE FROM workouts")
                start = self.today - timedelta(days=days - 1)
                previous_start = start - timedelta(days=days)
                previous_end = start - timedelta(days=1)
                rows = [
                    (1, "current-start", start.isoformat()),
                    (1, "current-end", self.today.isoformat()),
                    (1, "same-day-duplicate", self.today.isoformat()),
                    (2, "previous-start", previous_start.isoformat()),
                    (2, "previous-end", previous_end.isoformat()),
                    (1, "outside-period", (previous_start - timedelta(days=1)).isoformat()),
                    (3, "deleted-account", self.today.isoformat()),
                ]
                db.executemany(
                    "INSERT INTO workouts (user_id, text, date) VALUES (?, ?, ?)", rows
                )
                db.commit()
                result = admin_analytics.get_report("activity", days, self.today)
                with self.subTest(days=days):
                    self.assertEqual(result["active_users"], 1)
                    self.assertEqual(result["training_days"], 2)
                    self.assertEqual(result["previous_active_users"], 1)

    def test_sessions_exercises_challenges_and_legacy_rows_are_not_double_counted(self):
        self._insert_users()
        today = self.today.isoformat()
        with self._database() as db:
            db.executemany(
                "INSERT INTO workout_sessions (id, user_id, date) VALUES (?, ?, ?)",
                [(10, 1, today), (11, 1, today), (12, 3, today)],
            )
            db.executemany(
                """
                INSERT INTO workouts (id, user_id, text, date, is_challenge, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 1, "Run", today, 0, 10),
                    (2, 1, "Push ups", today, 0, 10),
                    (3, 1, "Challenge", today, 1, 11),
                    (4, 1, "Challenge extra", today, 1, 11),
                    (5, 1, "Legacy one", today, 0, None),
                    (6, 1, "Legacy two", today, 0, None),
                    (8, 1, "Orphan session one", today, 0, 99),
                    (9, 1, "Orphan session two", today, 0, 99),
                    (7, 3, "Deleted user workout", today, 1, 12),
                ],
            )
        result = admin_analytics.get_report("workouts", 7, self.today)
        self.assertEqual(result["sessions"], 5)
        self.assertEqual(result["exercises"], 8)
        self.assertEqual(result["challenge_sessions"], 1)
        self.assertEqual(result["popular_exercises"][0], ("Challenge", 1))

    def test_economy_reports_current_active_balances_and_only_recorded_rewards(self):
        self._insert_users()
        with self._database() as db:
            db.executemany(
                "INSERT INTO coin_rewards (user_id, date, source, amount) VALUES (?, ?, ?, ?)",
                [
                    (1, self.today.isoformat(), "daily", 25),
                    (2, self.today.isoformat(), "workout", 10),
                    (3, self.today.isoformat(), "deleted-user", 700),
                    (1, "2026-10-01", "outside-period", 100),
                ],
            )
        result = admin_analytics.get_report("economy", 7, self.today)
        self.assertEqual(result["balance"], 100)
        self.assertEqual(result["average_balance"], 50)
        self.assertEqual(result["users_with_balance"], 1)
        self.assertEqual(result["recorded_rewards"], 735)
        self.assertEqual(result["reward_records"], 3)
        text = admin._format_report("economy", result, 7)
        self.assertIn("начисления за 7 дн.", text)
        self.assertIn("coin_rewards", text)
        self.assertIn("расходы не учитываются", text)

    def test_progress_uses_active_users_and_persisted_achievement_rows(self):
        self._insert_users()
        with self._database() as db:
            db.executemany(
                "INSERT INTO achievements (user_id, achievement_key, awarded_at) VALUES (?, ?, ?)",
                [
                    (1, "first_workout", "now"),
                    (2, "first_workout", "now"),
                    (3, "first_workout", "now"),
                ],
            )
        result = admin_analytics.get_report("progress", 30, self.today)
        self.assertEqual(result["average_level"], 1.5)
        self.assertEqual(result["average_xp"], 100)
        self.assertEqual(result["max_level"], 2)
        self.assertEqual(result["achievements_count"], 3)
        self.assertEqual(result["top_achievements"][0][2], 3)
        self.assertIn("всё время", admin._format_report("progress", result, 30))

    def test_invalid_category_and_period_are_rejected(self):
        with self.assertRaises(ValueError):
            admin_analytics.get_report("unknown", 7, self.today)
        with self.assertRaises(ValueError):
            admin_analytics.get_report("activity", 14, self.today)

    def test_report_escapes_user_supplied_exercise_labels(self):
        text = admin._format_report(
            "workouts",
            {
                "sessions": 1,
                "exercises": 1,
                "challenge_sessions": 0,
                "popular_exercises": [("<b>Run</b>", 1)],
                "days": 7,
            },
            7,
        )
        self.assertIn("&lt;b&gt;Run&lt;/b&gt;", text)
        self.assertNotIn("<b>Run</b>", text)


class AdminAnalyticsAccessTests(unittest.IsolatedAsyncioTestCase):
    def _callback(self, user_id, data="admin_analytics:menu:30"):
        return SimpleNamespace(
            data=data,
            from_user=SimpleNamespace(id=user_id),
            message=SimpleNamespace(edit_text=AsyncMock()),
            answer=AsyncMock(),
        )

    def test_menu_contains_all_sections_and_supported_periods(self):
        menu = admin._analytics_keyboard(30)
        callbacks = {
            button.callback_data
            for row in menu.inline_keyboard
            for button in row
        }
        self.assertTrue({
            f"admin_analytics:view:{category}:30"
            for category in admin_analytics.CATEGORIES
        }.issubset(callbacks))
        self.assertTrue({
            "admin_analytics:menu:7",
            "admin_analytics:menu:30",
            "admin_analytics:menu:90",
            "admin_analytics:home",
        }.issubset(callbacks))
        for category in ("users", "progress"):
            section = admin._analytics_keyboard(30, category)
            section_callbacks = {
                button.callback_data
                for row in section.inline_keyboard
                for button in row
            }
            self.assertFalse(any(":period:" in value for value in section_callbacks))

    async def test_admin_command_is_restricted_to_configured_admin_ids(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=40),
            answer=AsyncMock(),
        )
        with patch.object(admin, "ADMIN_IDS", {41}), patch.object(
            admin, "fetch_one"
        ) as fetch_one:
            await admin.cmd_admin(message)
        message.answer.assert_not_awaited()
        fetch_one.assert_not_called()

    async def test_callback_from_non_admin_is_rejected_without_loading_analytics(self):
        callback = self._callback(40)
        with patch.object(admin, "ADMIN_IDS", {41}), patch.object(
            admin.admin_analytics, "get_report"
        ) as get_report:
            await admin.handle_analytics_callback(callback)
        callback.answer.assert_awaited_once_with("Недостаточно прав", show_alert=True)
        callback.message.edit_text.assert_not_awaited()
        get_report.assert_not_called()

    async def test_configured_admin_can_open_analytics_and_period_filter(self):
        callback = self._callback(41, "admin_analytics:view:activity:7")
        report = {
            "active_users": 2,
            "training_days": 3,
            "previous_active_users": 1,
            "days": 7,
        }
        with patch.object(admin, "ADMIN_IDS", {41}), patch.object(
            admin.admin_analytics, "get_report", return_value=report
        ) as get_report:
            await admin.handle_analytics_callback(callback)
        get_report.assert_called_once_with("activity", 7)
        callback.message.edit_text.assert_awaited_once()
        self.assertIn("Активные по тренировкам", callback.message.edit_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
