"""Explicit, non-destructive SQLite relocation using the online backup API."""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
from pathlib import Path

from backup_service import create_backup
from db_config import database_path, require_database_exists


def migrate(source: str | Path, target: str | Path) -> Path:
    source = require_database_exists(source)
    target = Path(target).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing target database: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    create_backup(source=source)

    with tempfile.NamedTemporaryFile(prefix="sportbot-migration-", suffix=".db", dir=target.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        src = sqlite3.connect(source)
        dst = sqlite3.connect(temporary)
        try:
            src.backup(dst, pages=100, sleep=0.05)
            dst.commit()
        finally:
            dst.close()
            src.close()
        check = sqlite3.connect(temporary)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Migrated database failed PRAGMA integrity_check")
        finally:
            check.close()
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely relocate SportBot SQLite database")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", default=str(database_path()))
    args = parser.parse_args()
    print(migrate(args.source, args.target))
