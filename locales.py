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
        "uk": ("<b>Команди SportBot</b>\n/help — цей список команд\n\n"
               "<b>Тренування</b>\n/workout — записати тренування\n/today — активність за сьогодні\n/history — історія тренувань\n\n"
               "<b>Статистика та прогрес</b>\n/stats — статистика тренувань\n/weight — записати вагу\n/weight_stats — останні записи ваги\n/level — рівень і XP\n/chart — графіки прогресу\n\n"
               "<b>Профіль і цілі</b>\n/profile — переглянути профіль\n/edit_profile — змінити профіль\n/profile_visibility — налаштувати видимість полів\n/set_goal — задати тижневу ціль\n/goal — переглянути ціль\n/suggest — запропонувати тренування (потрібна мета в профілі)\n\n"
               "<b>Завдання та нагороди</b>\n/daily — щоденне завдання\n/challenge — челендж дня\n/reminders — налаштувати нагадування\n/motivate — мотивація\n/tip — порада дня\n/wallet — монети та інвентар\n/shop — магазин\n/use — використати предмет з інвентарю\n\n"
               "<b>Дані та налаштування</b>\n/export — завантажити копію даних\n/import — імпортувати JSON (замінює поточні дані)\n/reset — видалити дані профілю після підтвердження\n/change_language — перемкнути українську й англійську\n\n"
               "<b>Лише для адміністраторів з ADMIN_IDS</b>\n/admin — статистика бота\n/backup — створити резервну копію\n\n"
               "Введи /start, щоб відкрити головне меню."),
        "en": ("<b>SportBot commands</b>\n/help — this command list\n\n"
               "<b>Workouts</b>\n/workout — record a workout\n/today — today's activity\n/history — workout history\n\n"
               "<b>Stats and progress</b>\n/stats — workout statistics\n/weight — record body weight\n/weight_stats — recent weight entries\n/level — level and XP\n/chart — progress charts\n\n"
               "<b>Profile and goals</b>\n/profile — view your profile\n/edit_profile — edit your profile\n/profile_visibility — manage visible profile fields\n/set_goal — set a weekly goal\n/goal — view your goal\n/suggest — suggest a workout (requires a profile goal)\n\n"
               "<b>Tasks and rewards</b>\n/daily — daily task\n/challenge — daily challenge\n/reminders — manage reminders\n/motivate — motivation\n/tip — tip of the day\n/wallet — coins and inventory\n/shop — shop\n/use — use an inventory item\n\n"
               "<b>Data and settings</b>\n/export — download a copy of your data\n/import — import JSON (replaces current data)\n/reset — delete profile data after confirmation\n/change_language — switch between Ukrainian and English\n\n"
               "<b>Admins configured in ADMIN_IDS only</b>\n/admin — bot statistics\n/backup — create a database backup\n\n"
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
