"""Handler registration module for `handlers.register_all(dp)`."""
from __future__ import annotations

from aiogram import Dispatcher


def register(dp: Dispatcher) -> None:
    _reg_charts  (dp)
    _reg_general (dp)
    _reg_workouts(dp)
    _reg_tasks   (dp)
    _reg_shop    (dp)
    _reg_diet    (dp)
    _reg_profile (dp)
    _reg_level   (dp)
    _reg_challenge(dp)
    _reg_reset   (dp)
