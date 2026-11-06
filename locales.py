"""Centralized translations for SportBot."""
from __future__ import annotations

TEXTS = {
    "welcome": {
        "uk": ("💪 <b>SportBot — твій особистий щоденник тренувань у Telegram.</b>\n\n"
                "Записуй заняття, переглядай статистику та історію, отримуй XP, монети й досягнення.\n\n"
                "<b>Почни з першого тренування:</b> натисни кнопку нижче та введи вправи через кому.\n\n"
                "Наступні кроки: переглянь статистику, історію або відкрий коротку інструкцію."),
        "en": ("💪 <b>SportBot is your personal workout journal in Telegram.</b>\n\n"
                "Record sessions, review your stats and history, and earn XP, coins, and achievements.\n\n"
                "<b>Start with your first workout:</b> tap the button below and enter exercises separated by commas.\n\n"
                "Next: check your stats, history, or open the short guide."),
    },
    "help": {
        "uk": ("<b>Як користуватися SportBot</b>\n\n"
               "<b>Тренування</b>\n/workout — записати тренування\n/today — активність за сьогодні\n/history — історія тренувань\n\n"
               "<b>Статистика та прогрес</b>\n/stats — статистика тренувань\n/weight_stats — історія ваги\n/level — рівень, XP і серія\n/chart — графіки\n\n"
               "<b>Профіль і цілі</b>\n/profile — профіль\n/edit_profile — змінити профіль\n/set_goal — встановити тижневу ціль\n/goal — переглянути ціль\n\n"
               "<b>Нагороди та завдання</b>\n/daily — щоденне завдання\n/wallet — монети та інвентар\n/shop — магазин\n\n"
               "Введи /start, щоб відкрити головне меню."),
        "en": ("<b>How to use SportBot</b>\n\n"
               "<b>Workouts</b>\n/workout — record a workout\n/today — today's activity\n/history — workout history\n\n"
               "<b>Stats and progress</b>\n/stats — workout statistics\n/weight_stats — weight history\n/level — level, XP, and streak\n/chart — charts\n\n"
               "<b>Profile and goals</b>\n/profile — profile\n/edit_profile — edit profile\n/set_goal — set a weekly goal\n/goal — view your goal\n\n"
               "<b>Rewards and tasks</b>\n/daily — daily task\n/wallet — coins and inventory\n/shop — shop\n\n"
               "Send /start to open the main menu."),
    },
}

def t(key: str, lang: str = "uk") -> str:
    entry = TEXTS.get(key, {})
    return entry.get(lang) or entry.get("en") or f"[{key}]"

def t_pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en

def pick_lang(lang: str, uk: str, en: str) -> str:
    return t_pair(lang, uk, en)
