"""
Logging configuration for SportBot.

Centralises all loggers so that:

* library noise from aiohttp / asyncio is hidden by default,
* application code emits at WARNING INFO/ERROR as appropriate,
* tracebacks are never swallowed silently.
"""
import logging
import sys

# ── root logger ──────────────────────────────────────────────────────────
log = logging.getLogger("sportbot")
log.setLevel(logging.DEBUG)          # let everything in; handlers filter


class _PkgFilter(logging.Filter):
    """Drop noisy library loggers unless explicitly enabled."""
    def filter(self, record):
        return record.name not in (
            "aiohttp", "aiohttp.access",
            "aiogram", "aiogram.event",
            "slash COMMAND",
            "apscheduler",
        )


_STDERR = logging.StreamHandler(sys.stderr)
_STDERR.setLevel(logging.INFO)
_STDERR.addFilter(_PkgFilter())
_STDERR.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    "%H:%M:%S"
))
log.addHandler(_STDERR)

# ── file handler (rotating, always at DEBUG) ──────────────────────────────
try:
    from logging.handlers import RotatingFileHandler
    _file = RotatingFileHandler("sportbot.log", maxBytes=2_000_000, backupCount=3,
                                encoding="utf-8")
    _file.setLevel(logging.DEBUG)
    _file.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    ))
    log.addHandler(_file)
except Exception:
    pass


def get_logger(name: str = "sportbot") -> logging.Logger:  # noqa: A001
    """Return a child logger, e.g. ``get_logger("handlers.shop")``."""
    return logging.getLogger(name)
