import unittest
from datetime import date, timedelta
from pathlib import Path
import sqlite3

import db_improved
from services.workout_stats import summarize_workouts


class WorkoutStatsTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 11)  # Wednesday

    def d(self, offset):
        return (self.today + timedelta(days=offset)).isoformat()

    def test_sessions_and_exercises_are_separate(self):
        rows = [
            (self.d(0), "Run", 10),
            (self.d(0), "Push ups", 10),
            (self.d(-1), "Old one", None),
            (self.d(-2), "Old two", None),
        ]
        result = summarize_workouts(rows, self.today)
        self.assertEqual(result["total_sessions"], 3)
        self.assertEqual(result["total_exercises"], 4)

    def test_week_boundaries_do_not_overlap(self):
        rows = [
            (self.d(-2), "Current week", 1),  # Monday 2026-11-09
            (self.d(-7), "Previous week", 2),
            (self.d(-8), "Previous week", None),
            (self.d(-10), "Older", None),
        ]
        result = summarize_workouts(rows, self.today)
        self.assertEqual(result["current_week_sessions"], 1)
        self.assertEqual(result["previous_week_sessions"], 2)

    def test_month_boundary(self):
        rows = [
            (self.d(0), "This month", None),
            ("2026-10-31", "Last month", None),
        ]
        self.assertEqual(summarize_workouts(rows, self.today)["current_month_sessions"], 1)

    def test_popular_exercise_normalizes_case_and_spaces(self):
        rows = [
            (self.d(0), "  Push   Ups ", 1),
            (self.d(-1), "push ups", None),
            (self.d(-2), "Running", None),
        ]
        result = summarize_workouts(rows, self.today)
        self.assertEqual(result["popular_exercise"], "Push Ups")
        self.assertEqual(result["popular_exercise_count"], 2)

    def test_empty_and_isolated_users_are_data_independent(self):
        self.assertEqual(summarize_workouts([], self.today)["total_sessions"], 0)
        rows = [(self.d(0), "Only this user", 99)]
        self.assertEqual(summarize_workouts(rows, self.today)["total_sessions"], 1)

    def test_database_path_is_absolute_and_save_read_path_is_one_file(self):
        self.assertTrue(Path(db_improved.DB_PATH).is_absolute())
        db = sqlite3.connect(":memory:")
        db.executescript("""
            CREATE TABLE workout_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, note TEXT);
            CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, date TEXT, session_id INTEGER);
        """)
        db.execute("INSERT INTO workout_sessions VALUES (1, 42, '2026-11-11', NULL)")
        db.executemany("INSERT INTO workouts VALUES (?, 42, ?, '2026-11-11', 1)", [(1, "Run"), (2, "Push ups")])
        rows = db.execute("SELECT date, text, session_id FROM workouts WHERE user_id=?", (42,)).fetchall()
        self.assertEqual(summarize_workouts(rows, self.today)["total_sessions"], 1)
        self.assertEqual(summarize_workouts(rows, self.today)["total_exercises"], 2)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (7,)).fetchone()[0], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
