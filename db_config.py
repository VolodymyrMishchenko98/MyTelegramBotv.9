"""Single source of truth for the SportBot SQLite location."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
LOCAL_DATABASE_PATH = PROJECT_DIR / "sportbot.db"
BOT_HOSTING_DATABASE_PATH = Path("/app/data/sportbot.db")


def database_path() -> Path:
    """Return the configured database path without creating any files.

    ``DATABASE_PATH`` wins.  On Bothosting, ``DATA_DIR`` is supplied as
    ``/app/data``; locally, the existing project database remains the default.
    """
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        return (Path(data_dir).expanduser() / "sportbot.db").resolve()
    if Path("/app/data").is_dir():
        return BOT_HOSTING_DATABASE_PATH
    return LOCAL_DATABASE_PATH


def production_database_required() -> bool:
    """Whether startup must refuse to create a missing database."""
    return bool(os.getenv("DATABASE_PATH") or os.getenv("DATA_DIR") or Path("/app/data").is_dir())


def require_database_exists(path: str | Path | None = None) -> Path:
    """Fail clearly instead of allowing SQLite to create an empty production DB."""
    selected = Path(path) if path is not None else database_path()
    selected = selected.expanduser().resolve()
    if not selected.is_file() or selected.stat().st_size == 0:
        raise FileNotFoundError(
            "SQLite database was not found or is empty: "
            f"{selected}. Set DATABASE_PATH to the existing database before starting. "
            "No new database was created."
        )
    return selected
