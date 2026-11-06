import sqlite3
import unittest
from unittest.mock import patch

import bot_legacy


class HistoryHelpersTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE workout_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, note TEXT);
            CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, date TEXT,
                                   is_challenge INTEGER DEFAULT 0, session_id INTEGER);
        """)
        self.db.executemany("INSERT INTO workout_sessions VALUES (?, ?, ?, ?)", [
            (1, 7, "2026-11-06", "Good session"),
            (2, 7, "2026-11-05", None),
            (3, 8, "2026-11-07", "Private"),
        ])
        self.db.executemany("INSERT INTO workouts VALUES (?, ?, ?, ?, ?, ?)", [
            (1, 7, "Run", "2026-11-06", 0, 1),
            (2, 7, "Push-ups", "2026-11-06", 0, 1),
            (3, 7, "Squats", "2026-11-05", 0, 2),
            (4, 7, "Legacy", "2026-11-04", 0, None),
            (5, 8, "Other user", "2026-11-07", 0, 3),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_empty_history(self):
        with patch.object(bot_legacy, "get_db", return_value=self.db):
            self.assertEqual(bot_legacy._history_sessions(999), [])

    def test_sessions_notes_counts_and_legacy_records(self):
        with patch.object(bot_legacy, "get_db", return_value=self.db):
            rows = bot_legacy._history_sessions(7)
        self.assertEqual([row["key"] for row in rows], ["s:1", "s:2", "l:4"])
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["note"], "Good session")
        self.assertIsNone(rows[1]["note"])

    def test_other_user_is_not_returned(self):
        with patch.object(bot_legacy, "get_db", return_value=self.db):
            rows = bot_legacy._history_sessions(7)
        self.assertNotIn("s:3", [row["key"] for row in rows])

    def test_pagination_is_five_items_and_bounds_are_safe(self):
        rows = [{"key": f"l:{i}", "id": i, "date": "2026-01-01", "note": None, "count": 1} for i in range(7)]
        markup = bot_legacy._history_keyboard("en", 0, 2, rows[:5])
        self.assertEqual(len(markup.inline_keyboard), 6)
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "history_page_1")
        markup = bot_legacy._history_keyboard("uk", 1, 2, rows[5:])
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "history_page_0")

    def test_localized_labels_and_safe_clipping(self):
        self.assertIn("Назад", bot_legacy._history_keyboard("uk", 1, 2, []).inline_keyboard[0][0].text)
        self.assertIn("Back", bot_legacy._history_keyboard("en", 1, 2, []).inline_keyboard[0][0].text)
        self.assertEqual(bot_legacy._history_clip("<script>"), "&lt;script&gt;")
        self.assertTrue(len(bot_legacy._history_clip("x" * 5000)) <= bot_legacy.HISTORY_MAX_TEXT)


if __name__ == "__main__":
    unittest.main()
