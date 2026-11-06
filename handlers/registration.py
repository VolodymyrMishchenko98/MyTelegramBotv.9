"""
Handler registrations.

Each function is a thin, dependency-injected wrapper that receives the
dispatcher and the handful of helpers it needs.  Nothing imports ``bot.py``.
"""
from __future__ import annotations

import logging

from aiogram import Dispatcher

from services.logging_config import get_logger

log = get_logger("handlers.__init__")


def register_all(dp: Dispatcher) -> None:
    pass  # delegated to sub-modules below
