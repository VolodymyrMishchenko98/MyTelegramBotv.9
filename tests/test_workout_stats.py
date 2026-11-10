import unittest
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from unittest.mock import patch

import db_improved
import services.workout_stats as workout_stats
from services.workout_stats import (
    build_activity_calendar,
    format_activity_calendar,
    summarize_activity,
    summarize_workouts,
)


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
            (self.d(-7), "Previous Wednesday", 2),
            (self.d(-8), "Previous Tuesday", None),
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

    def test_activity_counts_sessions_not_training_days(self):
        sessions = [
            (self.d(-2), "s:1"),
            (self.d(0), "s:2"),
            (self.d(0), "s:3"),
        ]
        result = summarize_activity(sessions, self.today)
        self.assertEqual(result["current_week_sessions"], 3)
        self.assertEqual(result["days_28"], 2)

    def test_current_and_previous_weeks_have_exact_monday_boundaries(self):
        sessions = [
            (self.d(-2), "s:current-monday"),
            (self.d(0), "s:current-wednesday"),
            (self.d(-9), "s:previous-monday"),
            (self.d(-7), "s:previous-wednesday"),
            (self.d(-3), "s:previous-sunday"),
            (self.d(-10), "s:older-sunday"),
        ]
        result = summarize_activity(sessions, self.today)
        self.assertEqual(result["current_week_sessions"], 2)
        self.assertEqual(result["previous_week_sessions"], 2)

    def test_week_comparison_on_monday_compares_only_mondays(self):
        monday = date(2026, 11, 9)
        sessions = [
            (monday.isoformat(), "s:current"),
            ("2026-11-02", "s:previous"),
            ("2026-11-03", "s:previous-tuesday"),
            ("2026-11-10", "s:future"),
        ]
        result = summarize_activity(sessions, monday)
        self.assertEqual(result["current_week_sessions"], 1)
        self.assertEqual(result["previous_week_sessions"], 1)
        self.assertEqual(result["total_sessions"], 3)

    def test_week_comparison_midweek_compares_equal_elapsed_days(self):
        wednesday = date(2026, 11, 11)
        sessions = [
            ("2026-11-09", "s:current-monday"),
            ("2026-11-11", "s:current-wednesday"),
            ("2026-11-02", "s:previous-monday"),
            ("2026-11-04", "s:previous-wednesday"),
            ("2026-11-05", "s:previous-thursday"),
        ]
        result = summarize_activity(sessions, wednesday)
        self.assertEqual(result["current_week_sessions"], 2)
        self.assertEqual(result["previous_week_sessions"], 2)

    def test_week_comparison_on_sunday_compares_complete_weeks(self):
        sunday = date(2026, 11, 15)
        sessions = [
            ("2026-11-09", "s:current-monday"),
            ("2026-11-15", "s:current-sunday"),
            ("2026-11-02", "s:previous-monday"),
            ("2026-11-08", "s:previous-sunday"),
            ("2026-11-16", "s:future"),
        ]
        result = summarize_activity(sessions, sunday)
        self.assertEqual(result["current_week_sessions"], 2)
        self.assertEqual(result["previous_week_sessions"], 2)
        self.assertEqual(result["total_sessions"], 4)

    def test_empty_activity_has_zero_metrics(self):
        self.assertEqual(
            summarize_activity([], self.today),
            {
                "total_sessions": 0,
                "current_week_sessions": 0,
                "previous_week_sessions": 0,
                "days_28": 0,
                "current_streak": 0,
                "best_streak": 0,
            },
        )

    def test_calendar_is_exactly_four_weeks_and_marks_days_once(self):
        dates = [self.d(-27), self.d(-27), self.d(-14), self.d(0), self.d(1)]
        weeks = build_activity_calendar(dates, self.today)
        self.assertEqual(len(weeks), 4)
        self.assertTrue(all(len(week) == 7 for week in weeks))
        self.assertEqual(sum(trained for week in weeks for _, trained in week), 3)
        self.assertEqual(weeks[0][0][0], self.today - timedelta(days=27))
        self.assertEqual(weeks[-1][-1][0], self.today)

    def test_calendar_localizes_and_marks_unrecorded_days_neutrally(self):
        uk = format_activity_calendar([self.d(0)], self.today, "uk")
        en = format_activity_calendar([self.d(0)], self.today, "en")
        self.assertIn("Пн", uk)
        self.assertIn("Тиждень 1", uk)
        self.assertIn("день без запису", uk)
        self.assertIn("Mon", en)
        self.assertIn("Week 1", en)
        self.assertIn("no workout recorded", en)
        week_rows = [line for line in uk.splitlines() if line.startswith("Тиждень ")]
        self.assertEqual(sum(line.count("●") for line in week_rows), 1)

    def test_calendar_labels_month_transition_and_bolds_today(self):
        today = date(2026, 11, 3)
        rendered = format_activity_calendar(["2026-11-03"], today, "en")
        rows = [line for line in rendered.splitlines() if line.startswith("Week ")]
        self.assertEqual(len(rows), 4)
        self.assertIn("28 Oct–03 Nov", rows[-1])
        self.assertIn("<b>03●</b>", rows[-1])
        self.assertIn("Wed", rendered)

    def test_calendar_bolds_today_even_without_a_workout(self):
        rendered = format_activity_calendar([], date(2026, 11, 3), "en")
        self.assertIn("<b>03·</b>", rendered)
        self.assertIn("no workout recorded", rendered)

    def test_streak_uses_unique_dates_and_ends_on_today_or_yesterday(self):
        sessions = [
            (self.d(-2), "s:1"),
            (self.d(-1), "s:2"),
            (self.d(-1), "s:3"),
            (self.d(0), "legacy:4"),
            (self.d(2), "future:5"),
        ]
        result = summarize_activity(sessions, self.today)
        self.assertEqual(result["current_streak"], 3)
        self.assertEqual(result["best_streak"], 3)
        self.assertEqual(result["days_28"], 3)

        old = summarize_activity([(self.d(-3), "s:old")], self.today)
        self.assertEqual(old["current_streak"], 0)

    def test_database_session_rows_do_not_double_count_exercises(self):
        db = sqlite3.connect(":memory:")
        db.executescript("""
            CREATE TABLE workout_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT);
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, session_id INTEGER
            );
        """)
        db.executemany("INSERT INTO workout_sessions VALUES (?, ?, ?)", [
            (1, 7, self.d(0)),
            (2, 7, self.d(0)),
        ])
        db.executemany("INSERT INTO workouts VALUES (?, ?, ?, ?)", [
            (1, 7, self.d(0), 1),
            (2, 7, self.d(0), 1),
            (3, 7, self.d(0), 2),
            (4, 7, self.d(-1), None),
            (5, 7, self.d(-1), None),
            (6, 7, self.d(-2), 99),
            (7, 7, self.d(-2), 99),
            (8, 8, self.d(0), None),
        ])

        with patch.object(
            workout_stats,
            "fetch_all",
            side_effect=lambda query, params: db.execute(query, params).fetchall(),
        ):
            rows = workout_stats.load_workout_sessions(7)
        result = summarize_activity(rows, self.today)

        self.assertEqual(result["total_sessions"], 5)
        self.assertEqual(result["current_week_sessions"], 5)
        self.assertEqual(result["days_28"], 3)
        db.close()


if __name__ == "__main__":
    unittest.main()
