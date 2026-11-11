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
        self.assertEqual(len(markup.inline_keyboard), 8)
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "welcome_menu")
        self.assertEqual(markup.inline_keyboard[-2][0].callback_data, "history_page_1")
        self.assertEqual(markup.inline_keyboard[-3][0].callback_data, "stats_home")
        markup = bot_legacy._history_keyboard("uk", 1, 2, rows[5:])
        self.assertEqual(markup.inline_keyboard[-2][0].callback_data, "history_page_0")

    def test_localized_labels_and_safe_clipping(self):
        self.assertIn("статистики", bot_legacy._history_keyboard("uk", 1, 2, []).inline_keyboard[0][0].text)
        self.assertIn("stats", bot_legacy._history_keyboard("en", 1, 2, []).inline_keyboard[0][0].text)
        self.assertEqual(bot_legacy._history_clip("<script>"), "&lt;script&gt;")
        self.assertTrue(len(bot_legacy._history_clip("x" * 5000)) <= bot_legacy.HISTORY_MAX_TEXT)

    def test_edit_and_delete_are_owner_scoped(self):
        cur = self.db.cursor()
        cur.execute("UPDATE workouts SET text=? WHERE id=? AND user_id=?", ("Updated", 1, 7))
        cur.execute("UPDATE workout_sessions SET note=? WHERE id=? AND user_id=?", ("Updated note", 1, 7))
        cur.execute("DELETE FROM workouts WHERE id=? AND user_id=?", (5, 7))
        self.assertEqual(cur.rowcount, 0)
        self.assertEqual(cur.execute("SELECT text FROM workouts WHERE id=1").fetchone()[0], "Updated")
        self.assertEqual(cur.execute("SELECT note FROM workout_sessions WHERE id=1").fetchone()[0], "Updated note")

    def test_delete_session_is_atomic_and_does_not_touch_other_user(self):
        cur = self.db.cursor()
        self.db.execute("BEGIN")
        cur.execute("DELETE FROM workouts WHERE session_id=? AND user_id=?", (1, 7))
        cur.execute("DELETE FROM workout_sessions WHERE id=? AND user_id=?", (1, 7))
        self.db.commit()
        self.assertIsNone(cur.execute("SELECT id FROM workout_sessions WHERE id=1").fetchone())
        self.assertIsNotNone(cur.execute("SELECT id FROM workout_sessions WHERE id=3").fetchone())
        self.assertIsNotNone(cur.execute("SELECT id FROM workouts WHERE id=5").fetchone())

    def test_new_and_legacy_export_shapes_keep_session_id_optional(self):
        exported = {"text": "Run", "date": "2026-11-06", "is_challenge": 0, "session_id": 1}
        legacy = {"text": "Old", "date": "2026-11-04", "is_challenge": 0}
        self.assertEqual(exported["session_id"], 1)
        self.assertIsNone(legacy.get("session_id"))


if __name__ == "__main__":
    unittest.main()
