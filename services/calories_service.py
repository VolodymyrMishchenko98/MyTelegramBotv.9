"""
Async calorie-burn lookup via api-ninjas.com.

Uses ``aiohttp`` (non-blocking) instead of ``requests`` and caches results
with an in-process time-to-live to avoid repeated network calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import Any

import aiohttp

from services.logging_config import get_logger

log = get_logger("services.calories")

_API_NINJAS_URL = "https://api.api-ninjas.com/v1/caloriesburned"

# ── TTL cache ────────────────────────────────────────────────────────────

_CACHE: dict[str, tuple[float, int]] = {}
_CACHE_TTL   = 60 * 30          # 30 minutes
_CACHE_LIMIT = 1024             # max entries to prevent unbounded growth
_SWEEP_INTERVAL = 300           # seconds between janitor runs


def _cache_key(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def _cache_get(key: str) -> int | None:
    if key in _CACHE:
        ts, value = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return value
        del _CACHE[key]
    return None


def _cache_set(key: str, value: int) -> None:
    if len(_CACHE) >= _CACHE_LIMIT:
        _sweep_cache()
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (time.time(), value)


def _sweep_cache() -> None:
    now = time.time()
    expired = [k for k, (ts, _) in _CACHE.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _CACHE[k]


async def _sweep_loop() -> None:
    """Background task that periodically evicts stale cache entries."""
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL)
        _sweep_cache()


# Start sweep task on module load
_janitor: asyncio.Task[None] | None = None


def start_janitor(loop: asyncio.AbstractEventLoop | None = None) -> None:
    global _janitor
    if _janitor is None:
        loop = loop or asyncio.get_event_loop()
        _janitor = loop.create_task(_sweep_loop())


# ── activity parser ──────────────────────────────────────────────────────

_ACTIVITY_MAP: dict[str, str] = {
    "біг": "running", "run": "running",
    "ходьб": "walking", "прогулянк": "walking",
    "вело": "bicycling", "велосипед": "bicycling",
    "плав": "swimming",
    "відтиск": "push ups", "push": "push ups",
    "присідан": "squats", "squat": "squats",
    "планк": "plank",
    "випад": "lunges", "lunge": "lunges",
    "бурпі": "burpees", "бьорпі": "burpees", "burpee": "burpees",
    "jumping jack": "jumping jacks", "стрибк": "jumping jacks",
    "альпініст": "mountain climbers", "mountain": "mountain climbers",
    "скручуван": "sit ups", "прес": "sit ups",
}


def _parse_activity_duration(text: str) -> tuple[str, int]:
    raw = text.lower()
    m = re.search(r'(\d+)\s*(хв|хвилин|мин|min)', raw)
    duration = int(m.group(1)) if m else 30

    for key, api_activity in _ACTIVITY_MAP.items():
        if key in raw:
            return api_activity, duration
    return "workout", duration


# ── public API ────────────────────────────────────────────────────────────

async def fetch_calories(
    text: str,
    session: aiohttp.ClientSession,
    api_key: str,
    timeout: float = 2.5,
) -> int:
    """Return estimated calories burned for *text*.

    1. Check in-process TTL cache.
    2. Call api-ninjas.com on cache miss.
    3. Fall back to heuristic estimate on any failure.
    """
    cache_key = _cache_key(text)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    activity, duration = _parse_activity_duration(text)
    short_timeout = aiohttp.ClientTimeout(total=timeout, connect=1.0, sock_read=1.5)

    try:
        async with session.get(
            _API_NINJAS_URL,
            params={"activity": activity, "duration": duration},
            headers={"X-Api-Key": api_key},
            timeout=short_timeout,
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list) and data:
                    total = data[0].get("total_calories")
                    if total is not None:
                        value = int(round(float(total)))
                        _cache_set(cache_key, value)
                        log.debug("Calories API hit: %s → %d kcal", text, value)
                        return value
    except Exception as exc:
        log.debug("Calories API error for %r: %s", text, exc)

    # ── heuristic fallback ───────────────────────────────────────────────
    fallback = _heuristic_fallback(text)
    if fallback:
        _cache_set(cache_key, fallback)
        log.debug("Calories heuristic: %s → %d kcal", text, fallback)
        return fallback

    _cache_set(cache_key, 0)
    return 0


def _heuristic_fallback(text: str) -> int | None:
    lower = text.lower()
    m = re.search(r'(\d+)\s*(хв|хвилин|мин|min)', lower)
    if m:
        return int(m.group(1)) * 8
    if 'x' in lower or 'х' in lower:
        return 30
    return None
