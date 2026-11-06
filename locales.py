"""Centralized translations for SportBot.

New code should prefer ``t(key, lang)``. During the migration from inline
translation pairs, ``t_pair`` and ``pick_lang`` keep existing dynamic strings
working without changing business logic.
"""
from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "welcome": {
        "uk": "Ласкаво просимо до SportBot! 🏋️",
        "en": "Welcome to SportBot! 🏋️",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Return translated string for key in given language, fallback to English."""
    entry = TEXTS.get(key, {})
    return entry.get(lang) or entry.get("en") or f"[{key}]"


def t_pair(lang: str, uk: str, en: str) -> str:
    """Return the Ukrainian or English text from an inline translation pair."""
    return uk if lang == "uk" else en


def pick_lang(lang: str, uk: str, en: str) -> str:
    """Deprecated compatibility alias for old call sites."""
    return t_pair(lang, uk, en)
