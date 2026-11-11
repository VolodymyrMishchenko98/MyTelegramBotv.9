"""All keyboard builders used across the bot.

These are pure functions — they hold no state and depend only on strings.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from locales import t

MOTIVATION_QUOTES = [
    ("Маленькі кроки щодня = великі результати через місяць.",
     "Small steps every day = big results in a month."),
    ("Ти не завжди маєш бути мотивованим. Будь дисциплінованим.",
     "You don't always have to be motivated. Be disciplined."),
    ("Кожне тренування - це інвестиція у майбутнього себе.",
     "Every workout is an investment in your future self."),
]

HEALTH_TIPS = [
    ("Після тренування випий склянку води протягом 15 хвилин.",
     "After training, drink a glass of water within 15 minutes."),
    ("Роби 5 хвилин розминки перед будь-яким навантаженням.",
     "Do 5 minutes of warm-up before any load."),
    ("Сон 7-8 годин пришвидшує відновлення м'язів.",
     "7-8 hours of sleep speeds up muscle recovery."),
]

FITNESS_CHALLENGES = [
    ("30 присідань + 20 відтискувань + планка 40 сек",
     "30 squats + 20 push ups + 40 sec plank"),
    ("Швидка прогулянка 25 хв + розтяжка 5 хв",
     "25 min brisk walk + 5 min stretch"),
]


# ── style helper ───────────────────────────────────────────────────────────

import html as _html_mod


def style_block(title: str, body: str, icon: str = "✨") -> str:
    safe_title = _html_mod.escape(title)
    safe_body  = _html_mod.escape(body.strip())
    return f"{icon} <b>{safe_title}</b>\n━━━━━━━━━━━━━━\n{safe_body}"


def add_home_button(
    markup: InlineKeyboardMarkup | None,
    lang: str,
) -> InlineKeyboardMarkup:
    """Keep the current screen's actions and append a consistent home action."""
    home_label = "🏠 Головне меню" if lang == "uk" else "🏠 Main menu"
    rows = []
    home_found = False
    for row in markup.inline_keyboard if markup else ():
        copied_row = []
        for button in row:
            if button.callback_data == "welcome_menu":
                copied_row.append(InlineKeyboardButton(
                    text=home_label,
                    callback_data="welcome_menu",
                ))
                home_found = True
            else:
                copied_row.append(button)
        rows.append(copied_row)
    if not home_found:
        rows.append([InlineKeyboardButton(
            text=home_label,
            callback_data="welcome_menu",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_navigation_button(
    markup: InlineKeyboardMarkup | None,
    lang: str,
    label_key: str,
    callback_data: str,
) -> InlineKeyboardMarkup:
    rows = [list(row) for row in markup.inline_keyboard] if markup else []
    if not any(
        button.callback_data == callback_data
        for row in rows
        for button in row
    ):
        navigation_row = [InlineKeyboardButton(
            text=t(label_key, lang),
            callback_data=callback_data,
        )]
        home_index = next(
            (
                index
                for index, row in enumerate(rows)
                if any(button.callback_data == "welcome_menu" for button in row)
            ),
            len(rows),
        )
        rows.insert(home_index, navigation_row)
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=rows), lang)


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("settings_profile", lang), callback_data="settings_profile")],
        [InlineKeyboardButton(text=t("settings_language", lang), callback_data="settings_language")],
        [InlineKeyboardButton(text=t("settings_reminders", lang), callback_data="settings_reminders")],
        [InlineKeyboardButton(text=t("settings_data", lang), callback_data="settings_data")],
    ]), lang)


def sections_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("sections_economy", lang), callback_data="economy_home")],
        [InlineKeyboardButton(text=t("sections_activities", lang), callback_data="activities_home")],
        [InlineKeyboardButton(text=t("sections_inspiration", lang), callback_data="inspiration_home")],
    ]), lang)


def economy_home_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("economy_shop_button", lang), callback_data="economy_shop")],
        [InlineKeyboardButton(text=t("economy_inventory_button", lang), callback_data="economy_inventory")],
        [InlineKeyboardButton(text=t("economy_use_button", lang), callback_data="economy_use")],
    ]), lang)


def activities_home_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("activities_daily_button", lang), callback_data="activities_daily")],
        [InlineKeyboardButton(text=t("activities_challenge_button", lang), callback_data="activities_challenge")],
    ]), lang)


def inspiration_home_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("inspiration_suggest_button", lang), callback_data="inspiration_suggest")],
        [InlineKeyboardButton(text=t("inspiration_motivate_button", lang), callback_data="inspiration_motivate")],
        [InlineKeyboardButton(text=t("inspiration_tip_button", lang), callback_data="inspiration_tip")],
    ]), lang)


def profile_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_home_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("settings_profile_edit", lang), callback_data="profile_edit_open")],
        [InlineKeyboardButton(text=t("settings_profile_visibility", lang), callback_data="profile_visibility_open")],
        [InlineKeyboardButton(text=t("settings_back", lang), callback_data="settings_home")],
    ]), lang)


def language_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_navigation_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if lang == 'uk' else ''}{t('settings_language_ukrainian', lang)}",
            callback_data="settings_language_uk",
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if lang == 'en' else ''}{t('settings_language_english', lang)}",
            callback_data="settings_language_en",
        )],
    ]), lang, "settings_back", "settings_home")


def reminders_settings_keyboard(lang: str, enabled: bool) -> InlineKeyboardMarkup:
    label_key = "settings_reminders_disable" if enabled else "settings_reminders_enable"
    callback_data = "settings_reminders_disable" if enabled else "settings_reminders_enable"
    return add_navigation_button(InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(label_key, lang), callback_data=callback_data)
    ]]), lang, "settings_back", "settings_home")


def data_management_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_navigation_button(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("settings_data_export", lang), callback_data="settings_data_export")],
        [InlineKeyboardButton(text=t("settings_data_import", lang), callback_data="settings_data_import")],
        [InlineKeyboardButton(text=t("settings_data_reset", lang), callback_data="settings_data_reset")],
    ]), lang, "settings_back", "settings_home")


def settings_return_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_navigation_button(None, lang, "settings_back", "settings_home")


def profile_return_keyboard(lang: str) -> InlineKeyboardMarkup:
    return add_navigation_button(None, lang, "settings_profile_back", "profile_screen")


# ── inline keyboards ───────────────────────────────────────────────────────

INLINE_LANGUAGE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="English",  callback_data="set_lang_en"),
     InlineKeyboardButton(text="Українська", callback_data="set_lang_uk")],
])


def reminders_on_keyboard(lang: str) -> InlineKeyboardMarkup:
    uk, en = "❌ Вимкнути", "❌ Disable"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=uk if lang == "uk" else en, callback_data="reminders_off")]
    ])


def reminders_off_keyboard(lang: str) -> InlineKeyboardMarkup:
    uk, en = "✅ Увімкнути", "✅ Enable"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=uk if lang == "uk" else en, callback_data="reminders_on")]
    ])


def reset_keyboard(lang: str) -> InlineKeyboardMarkup:
    uk_yes, uk_no = "✅ Так", "❌ Ні"
    en_yes, en_no = "✅ Yes", "❌ No"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
             text=(uk_yes if lang == "uk" else en_yes), callback_data="reset_yes"),
         InlineKeyboardButton(
             text=(uk_no  if lang == "uk" else en_no),  callback_data="reset_no")],
    ])


def suggest_keyboard(lang: str) -> InlineKeyboardMarkup:
    uk1, uk2 = "✅ Виконав", "🔁 Інша"
    en1, en2 = "✅ Done",   "🔁 Another"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=uk1 if lang == "uk" else en1, callback_data="suggest_done"),
         InlineKeyboardButton(text=uk2 if lang == "uk" else en2, callback_data="suggest_retry")],
    ])


def challenge_keyboard(lang: str) -> InlineKeyboardMarkup:
    uk1, uk2 = "✅ Зробив", "🔁 Інший челендж"
    en1, en2 = "✅ Done",   "🔁 Another challenge"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=uk1 if lang == "uk" else en1, callback_data="challenge_done"),
         InlineKeyboardButton(text=uk2 if lang == "uk" else en2, callback_data="challenge_next")],
    ])


def daily_task_keyboard(lang: str, task: dict, completed: bool,
                        date_text: str | None = None) -> InlineKeyboardMarkup:
    date_text = date_text or ""
    unit = task["uk_unit"] if lang == "uk" else task["en_unit"]
    if completed:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ {('Виконано' if lang=='uk' else 'Completed')}",
                callback_data=f"daily_done_{date_text}",
            )]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"+{task['step']} {unit}",
            callback_data=f"daily_add_{date_text}",
        )]
    ])


def chart_keyboard(lang: str) -> InlineKeyboardMarkup:
    labels = (
        ("⚖️ Вага", "🏋️ Тренування", "🔥 Серія", "📦 Обсяг")
        if lang == "uk"
        else ("⚖️ Weight", "🏋️ Workouts", "🔥 Streak", "📦 Volume")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels[0], callback_data="chart_weight"),
         InlineKeyboardButton(text=labels[1], callback_data="chart_workouts")],
        [InlineKeyboardButton(text=labels[2], callback_data="chart_streak"),
         InlineKeyboardButton(text=labels[3], callback_data="chart_volume")],
    ])


def shop_keyboard(lang: str) -> InlineKeyboardMarkup:
    from game_config import SHOP_ITEMS               # lazy to avoid circular
    categories = sorted({item.get("category", "Інше") for item in SHOP_ITEMS.values()})
    rows = []
    for category in categories:
        rows.append([InlineKeyboardButton(
            text=f"━━ {category} ━━",
            callback_data=f"shop_cat_{category}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_category_keyboard(
    lang: str, category: str, user_level: int = 1
) -> InlineKeyboardMarkup:
    from game_config import SHOP_ITEMS
    rows: list[list[InlineKeyboardButton]] = []
    category_items = sorted(
        ((iid, it) for iid, it in SHOP_ITEMS.items()
         if it.get("category", "Інше") == category),
        key=lambda x: x[1].get("cost", 0),
    )
    for iid, item in category_items:
        icon  = item.get("icon", "🛍️")
        name  = item["uk_name"] if lang == "uk" else item["en_name"]
        cost  = item.get("cost", 0)
        ml    = item.get("min_level", 1)
        if user_level < ml:
            lock = f"{'🔒 Лвл ' if lang=='uk' else '🔒 Lvl '}{ml}"
            btn_text = f"{icon} {cost}🪙 · {name}\n   {lock}"
        else:
            btn_text = f"{icon} {cost}🪙 · {name}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"shop_buy_{iid}")])

    rows.append([InlineKeyboardButton(
        text=("⬅️ Назад" if lang == "uk" else "⬅️ Back"),
        callback_data="shop_back_to_categories",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── lang helpers ───────────────────────────────────────────────────────────

_pick_fns = {}       # cache per lang; populated on first call


def t_pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en
