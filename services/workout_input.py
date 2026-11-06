"""Pure parsing helpers for the workout input flow."""
from __future__ import annotations


def parse_workout_exercises(text: str) -> list[str]:
    """Split comma-separated workout input into non-empty trimmed names.

    The operation intentionally mirrors the legacy handler: whitespace around
    each comma-separated item is removed and empty items are ignored.
    """
    return [part.strip() for part in text.split(",") if part.strip()]
