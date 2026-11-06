import sqlite3
import unittest

from db_improved import ensure_users_deleted_at


class DatabaseMigrationTests(unittest.TestCase):
    def test_deleted_at_is_added_to_legacy_users_table_and_is_idempotent(self):
        db = sqlite3.connect(":memory:")
        db.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, language TEXT)"
        )
        db.execute("INSERT INTO users (user_id, language) VALUES (1, 'uk')")
        db.commit()

        ensure_users_deleted_at(db.cursor())
        db.commit()
        columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        self.assertIn("deleted_at", columns)
        self.assertIsNone(
            db.execute("SELECT deleted_at FROM users WHERE user_id=1").fetchone()[0]
        )

        ensure_users_deleted_at(db.cursor())
        db.commit()
        self.assertEqual(
            sum(name == "deleted_at" for (name,) in db.execute(
                "SELECT name FROM pragma_table_info('users')"
            )),
            1,
        )
        db.close()


if __name__ == "__main__":
    unittest.main()
