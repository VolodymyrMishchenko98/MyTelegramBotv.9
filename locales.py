"""Centralized translations for SportBot."""
from __future__ import annotations

TEXTS = {
    "welcome": {
        "uk": "🔥 <b>Ласкаво просимо до SportBot!</b>\n\nТвій щоденник тренувань — тепер у Telegram.\n\n💪 Записуй свої тренування.\n📊 Відстежуй активність і статистику.\n🏆 Отримуй XP, монети та досягнення.\n📅 Переглядай історію тренувань.\n\n<b>Почни прямо зараз!</b>\n\nНатисни кнопку нижче, щоб записати перше тренування.\n\nТренуйся. Записуй. Рости! 🚀",
        "en": "🔥 <b>Welcome to SportBot!</b>\n\nYour workout journal — right inside Telegram.\n\n💪 Record your workouts.\n📊 Track your activity and statistics.\n🏆 Earn XP, coins and achievements.\n📅 Explore your workout history.\n\n<b>Let's get started!</b>\n\nTap the button below to record your first workout.\n\nTrain. Track. Grow! 🚀",
    },
    "help": {
        "uk": "<b>Як користуватися SportBot?</b>\n\n1️⃣ Натисни /workout або кнопку запису тренування.\n2️⃣ Введи вправи через кому.\n3️⃣ Додай нотатку або пропусти цей крок.\n4️⃣ Переглядай результати через /stats та /history.\n\nКорисні команди:\n/today — активність за сьогодні\n/stats — статистика тренувань\n/history — історія тренувань\n/weight — запис ваги\n/goal — цілі\n/daily — щоденні завдання\n/help — допомога",
        "en": "<b>How to use SportBot?</b>\n\n1️⃣ Tap /workout or the record workout button.\n2️⃣ Enter exercises separated by commas.\n3️⃣ Add a note or skip this step.\n4️⃣ View results with /stats and /history.\n\nUseful commands:\n/today — today's activity\n/stats — workout statistics\n/history — workout history\n/weight — record weight\n/goal — goals\n/daily — daily tasks\n/help — help",
    },
}

def t(key: str, lang: str = "uk") -> str:
    entry = TEXTS.get(key, {})
    return entry.get(lang) or entry.get("en") or f"[{key}]"

def t_pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en

def pick_lang(lang: str, uk: str, en: str) -> str:
    return t_pair(lang, uk, en)
