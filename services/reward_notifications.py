"""Localized, user-facing summaries for rewards granted by one action."""
from __future__ import annotations

from typing import Any


def _pick(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en


def build_reward_summary(
    lang: str,
    *,
    action_uk: str,
    action_en: str,
    xp: int = 0,
    coins: int = 0,
    balance: int | None = None,
    streak_days: int | None = None,
    level: int | None = None,
    level_up: bool = False,
    xp_total: int | None = None,
    xp_next: int | None = None,
    achievements: list[dict[str, Any]] | None = None,
) -> str:
    """Return one compact summary containing only actually granted rewards."""
    achievements = achievements or []
    lines = [_pick(lang, f"🏋️ {action_uk}", f"🏋️ {action_en}")]

    if xp:
        lines.append(f"✨ XP: +{xp}")
    if coins:
        coin_line = _pick(lang, f"🪙 Монети: +{coins}", f"🪙 Coins: +{coins}")
        if balance is not None:
            coin_line += _pick(lang, f" (баланс: {balance})", f" (balance: {balance})")
        lines.append(coin_line)
    if streak_days is not None:
        lines.append(_pick(lang, f"🔥 Серія: {streak_days} днів", f"🔥 Streak: {streak_days} days"))

    if level is not None:
        if level_up:
            lines.extend([
                _pick(lang, f"🎉 НОВИЙ РІВЕНЬ! Ти досягнув рівня {level}!", f"🎉 NEW LEVEL! You reached level {level}!"),
            ])
        progress = _pick(lang, "📊 Рівень", "📊 Level")
        if xp_total is not None and xp_next is not None:
            progress += f": {level} · XP {xp_total} / {xp_next}"
        else:
            progress += f": {level}"
        lines.append(progress)

    for achievement in achievements:
        title = achievement.get("title_uk") if lang == "uk" else achievement.get("title_en")
        desc = achievement.get("desc_uk") if lang == "uk" else achievement.get("desc_en")
        reward_parts = []
        if achievement.get("xp"):
            reward_parts.append(f"+{achievement['xp']} XP")
        if achievement.get("coins"):
            reward_parts.append(_pick(lang, f"+{achievement['coins']} монет", f"+{achievement['coins']} coins"))
        lines.extend([
            _pick(lang, "🏆 НОВЕ ДОСЯГНЕННЯ!", "🏆 NEW ACHIEVEMENT!"),
            f"{achievement.get('icon', '🏆')} {title}",
            str(desc or ""),
        ])
        if reward_parts:
            lines.append(_pick(lang, "Нагорода: ", "Reward: ") + " / ".join(reward_parts))

    return "\n".join(line for line in lines if line)
