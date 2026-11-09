import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db_config


class DatabasePathTests(unittest.TestCase):
    def test_database_path_override_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / "existing.db"
            with patch.dict(os.environ, {"DATABASE_PATH": str(selected)}, clear=False):
                self.assertEqual(db_config.database_path(), selected.resolve())
            self.assertFalse(selected.exists())

    def test_data_dir_selects_persistent_database(self):
        with patch.dict(os.environ, {"DATA_DIR": "/app/data"}, clear=True):
            self.assertEqual(db_config.database_path(), Path("/app/data/sportbot.db").resolve())
            self.assertTrue(db_config.production_database_required())

    def test_missing_production_database_fails_without_creating_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.db"
            with self.assertRaises(FileNotFoundError):
                db_config.require_database_exists(missing)
            self.assertFalse(missing.exists())

    def test_backup_service_resolves_same_configured_path(self):
        import backup_service

        with tempfile.TemporaryDirectory() as tmp:
            selected = Path(tmp) / "configured.db"
            conn = sqlite3.connect(selected)
            conn.execute("CREATE TABLE marker(value TEXT)")
            conn.commit()
            conn.close()
            with patch.dict(os.environ, {"DATABASE_PATH": str(selected)}, clear=False):
                manifest = backup_service.create_backup(directory=Path(tmp) / "backups")
            self.assertTrue((Path(tmp) / "backups" / manifest["file"]).exists())


if __name__ == "__main__":
    unittest.main()
