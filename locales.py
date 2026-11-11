"""Centralized translations for SportBot."""
from __future__ import annotations

TEXTS = {
    "welcome": {
        "uk": ("💪 <b>SportBot — твій щоденник тренувань у Telegram.</b>\n\n"
                "<b>Почни з тренування:</b> натисни кнопку нижче та введи вправи через кому, "
                "наприклад: Біг 30 хвилин, Відтискування 4x20.\n\n"
                "Після збереження побачиш підтвердження та лише фактично нараховані нагороди."),
        "en": ("💪 <b>SportBot is your workout journal in Telegram.</b>\n\n"
                "<b>Start with a workout:</b> tap the button below and enter exercises separated by commas, "
                "for example: Running 30 min, Push-ups 4x20.\n\n"
                "After saving, you'll see a confirmation and only the rewards actually granted."),
    },
    "help": {
        "uk": ("<b>Команди SportBot</b>\n/help — цей список команд\n\n"
               "<b>Тренування</b>\n/workout — записати тренування\n/today — активність за сьогодні\n/history — історія тренувань\n\n"
               "<b>Статистика та прогрес</b>\n/stats — статистика тренувань\n/weight — записати вагу\n/weight_stats — останні записи ваги\n/level — рівень і XP\n/chart — графіки прогресу\n\n"
               "<b>Профіль і цілі</b>\n/profile — переглянути профіль\n/edit_profile — змінити профіль\n/profile_visibility — налаштувати видимість полів\n/set_goal — задати тижневу ціль\n/goal — переглянути ціль\n/suggest — запропонувати тренування (потрібна мета в профілі)\n\n"
               "<b>Завдання та нагороди</b>\n/daily — щоденне завдання\n/challenge — челендж дня\n/reminders — налаштувати нагадування\n/motivate — мотивація\n/tip — порада дня\n/wallet — монети та інвентар\n/shop — магазин\n/use — використати предмет з інвентарю\n\n"
               "<b>Дані та налаштування</b>\n/export — завантажити копію даних\n/import — імпортувати JSON (замінює поточні дані)\n/reset — видалити дані профілю після підтвердження\n/change_language — перемкнути українську й англійську\n\n"
               "/developer — зв’язатися з розробником\n\n"
               "<b>Лише для адміністраторів з ADMIN_IDS</b>\n/admin — статистика бота\n/backup — створити резервну копію\n\n"
               "Введи /start, щоб відкрити головне меню."),
        "en": ("<b>SportBot commands</b>\n/help — this command list\n\n"
               "<b>Workouts</b>\n/workout — record a workout\n/today — today's activity\n/history — workout history\n\n"
               "<b>Stats and progress</b>\n/stats — workout statistics\n/weight — record body weight\n/weight_stats — recent weight entries\n/level — level and XP\n/chart — progress charts\n\n"
               "<b>Profile and goals</b>\n/profile — view your profile\n/edit_profile — edit your profile\n/profile_visibility — manage visible profile fields\n/set_goal — set a weekly goal\n/goal — view your goal\n/suggest — suggest a workout (requires a profile goal)\n\n"
               "<b>Tasks and rewards</b>\n/daily — daily task\n/challenge — daily challenge\n/reminders — manage reminders\n/motivate — motivation\n/tip — tip of the day\n/wallet — coins and inventory\n/shop — shop\n/use — use an inventory item\n\n"
               "<b>Data and settings</b>\n/export — download a copy of your data\n/import — import JSON (replaces current data)\n/reset — delete profile data after confirmation\n/change_language — switch between Ukrainian and English\n\n"
               "/developer — contact the developer\n\n"
               "<b>Admins configured in ADMIN_IDS only</b>\n/admin — bot statistics\n/backup — create a database backup\n\n"
               "Send /start to open the main menu."),
    },
    "developer_card": {
        "uk": ("👨‍💻 <b>Зв'язок із розробником SportBot</b>\n\n"
               "Маєш ідею, питання або знайшов помилку?\n"
               "Напиши повідомлення прямо тут — я його прочитаю.\n\n"
               "Ти можеш надіслати повідомлення анонімно або від свого імені."),
        "en": ("👨‍💻 <b>Contact the SportBot developer</b>\n\n"
               "Have an idea, a question, or found a bug?\n"
               "Send a message right here — I'll read it.\n\n"
               "You can send it anonymously or with your name."),
    },
    "developer_contact_button": {
        "uk": "✉️ Написати розробнику",
        "en": "✉️ Message the developer",
    },
    "developer_contact_unavailable": {
        "uk": "Надсилання повідомлень тимчасово недоступне.",
        "en": "Sending feedback is temporarily unavailable.",
    },
    "developer_feedback_choose_mode": {
        "uk": "Як надіслати повідомлення?",
        "en": "How would you like to send your message?",
    },
    "developer_feedback_anonymous": {
        "uk": "🕵️ Анонімно",
        "en": "🕵️ Anonymous",
    },
    "developer_feedback_identified": {
        "uk": "👤 Від свого імені",
        "en": "👤 With my name",
    },
    "developer_feedback_back": {
        "uk": "↩️ Назад",
        "en": "↩️ Back",
    },
    "developer_feedback_cancel": {
        "uk": "✖️ Скасувати",
        "en": "✖️ Cancel",
    },
    "developer_feedback_cancelled": {
        "uk": "Надсилання звернення скасовано.",
        "en": "Feedback submission cancelled.",
    },
    "developer_feedback_anonymity_note": {
        "uk": "Анонімно для розробника. Telegram і бот технічно знають твій ID.",
        "en": "Anonymous to the developer. Telegram and the bot technically know your ID.",
    },
    "developer_feedback_choose_category": {
        "uk": "Обери категорію звернення:",
        "en": "Choose a feedback category:",
    },
    "developer_feedback_category_idea": {
        "uk": "💡 Пропозиція",
        "en": "💡 Suggestion",
    },
    "developer_feedback_category_bug": {
        "uk": "🐛 Помилка",
        "en": "🐛 Bug",
    },
    "developer_feedback_category_question": {
        "uk": "❓ Питання",
        "en": "❓ Question",
    },
    "developer_feedback_category_other": {
        "uk": "💬 Інше",
        "en": "💬 Other",
    },
    "developer_feedback_write_message": {
        "uk": "Напиши повідомлення текстом (до 1800 символів).",
        "en": "Write your message as text (up to 1800 characters).",
    },
    "developer_feedback_empty": {
        "uk": "Повідомлення не може бути порожнім. Напиши текст або скасуй звернення.",
        "en": "The message can't be empty. Enter text or cancel the request.",
    },
    "developer_feedback_too_long": {
        "uk": "Повідомлення задовге. Максимум — 1800 символів.",
        "en": "The message is too long. Maximum length is 1800 characters.",
    },
    "developer_feedback_text_only": {
        "uk": "Поки що можна надіслати лише текстове повідомлення.",
        "en": "Only text messages are supported for now.",
    },
    "developer_feedback_rate_limited": {
        "uk": "Можна надіслати не більше 3 звернень за 10 хвилин. Спробуй пізніше.",
        "en": "You can send up to 3 requests every 10 minutes. Please try again later.",
    },
    "developer_feedback_saved": {
        "uk": "✅ Звернення #{ticket_id} надіслано. Дякую!",
        "en": "✅ Feedback #{ticket_id} has been sent. Thank you!",
    },
    "developer_feedback_delivery_failed": {
        "uk": "Звернення #{ticket_id} збережено, але зараз його не вдалося доставити розробнику. Воно не загубилося.",
        "en": "Feedback #{ticket_id} was saved, but couldn't be delivered to the developer right now. It has not been lost.",
    },
    "developer_feedback_save_error": {
        "uk": "Не вдалося зберегти звернення. Спробуй ще раз пізніше.",
        "en": "Couldn't save your feedback. Please try again later.",
    },
    "developer_feedback_dev_notification": {
        "uk": ("📩 <b>Нове звернення до розробника</b>\n\n"
               "ID: #{ticket_id}\nКатегорія: {category}\nРежим: {mode}\n{identity}"
               "Повідомлення:\n{message}"),
        "en": ("📩 <b>New developer feedback</b>\n\n"
               "ID: #{ticket_id}\nCategory: {category}\nMode: {mode}\n{identity}"
               "Message:\n{message}"),
    },
    "developer_feedback_mode_anonymous": {
        "uk": "🕵️ Анонімно",
        "en": "🕵️ Anonymous",
    },
    "developer_feedback_mode_identified": {
        "uk": "👤 Від свого імені",
        "en": "👤 Identified",
    },
    "developer_feedback_identity_name": {
        "uk": "Ім'я: {name}\n",
        "en": "Name: {name}\n",
    },
    "developer_feedback_identity_username": {
        "uk": "Username: @{username}\n",
        "en": "Username: @{username}\n",
    },
    "developer_feedback_reply": {
        "uk": "↩️ Відповісти",
        "en": "↩️ Reply",
    },
    "developer_feedback_close": {
        "uk": "✅ Закрити звернення",
        "en": "✅ Close request",
    },
    "developer_feedback_reopen": {
        "uk": "🔓 Відкрити знову",
        "en": "🔓 Reopen",
    },
    "developer_feedback_user_reply": {
        "uk": "✉️ Відповісти SportBot",
        "en": "✉️ Reply to SportBot",
    },
    "developer_feedback_reply_prompt": {
        "uk": "Напиши відповідь користувачу. Максимум — 1800 символів.",
        "en": "Write your reply to the user. Maximum length is 1800 characters.",
    },
    "developer_feedback_reply_saved": {
        "uk": "Відповідь на звернення #{ticket_id} надіслано.",
        "en": "Reply to feedback #{ticket_id} has been delivered.",
    },
    "developer_feedback_reply_history_failed": {
        "uk": "Відповідь на звернення #{ticket_id} доставлена, але не вдалося оновити її історію.",
        "en": "Reply to feedback #{ticket_id} was delivered, but its history could not be updated.",
    },
    "developer_feedback_reply_failed": {
        "uk": "Не вдалося доставити відповідь на звернення #{ticket_id}. Звернення залишилося відкритим.",
        "en": "Couldn't deliver the reply to feedback #{ticket_id}. The request remains open.",
    },
    "developer_feedback_reply_error": {
        "uk": "Не вдалося зберегти відповідь. Звернення залишилося відкритим.",
        "en": "Couldn't save the reply. The request remains open.",
    },
    "developer_feedback_reply_body": {
        "uk": "💬 <b>Відповідь SportBot:</b>\n\n{message}",
        "en": "💬 <b>Reply from SportBot:</b>\n\n{message}",
    },
    "developer_feedback_user_followup": {
        "uk": "📩 <b>Нове повідомлення у зверненні #{ticket_id}</b>\n\n"
               "Категорія: {category}\nРежим: {mode}\n{identity}Повідомлення:\n{message}",
        "en": "📩 <b>New message in feedback #{ticket_id}</b>\n\n"
               "Category: {category}\nMode: {mode}\n{identity}Message:\n{message}",
    },
    "developer_feedback_followup_sent": {
        "uk": "✅ Повідомлення додано до звернення #{ticket_id}.",
        "en": "✅ Your message was added to feedback #{ticket_id}.",
    },
    "developer_feedback_followup_delivery_failed": {
        "uk": "Повідомлення додано до звернення #{ticket_id}, але не вдалося сповістити розробника. Воно не загубилося.",
        "en": "Your message was added to feedback #{ticket_id}, but the developer couldn't be notified. It has not been lost.",
    },
    "developer_feedback_closed": {
        "uk": "Звернення закрито.",
        "en": "Feedback closed.",
    },
    "developer_feedback_reopened": {
        "uk": "Звернення знову відкрите.",
        "en": "Feedback reopened.",
    },
    "developer_feedback_closed_user": {
        "uk": "Це звернення закрите. Створи нове через /developer, якщо маєш додаткові питання.",
        "en": "This request is closed. Start a new one with /developer if you have more questions.",
    },
    "developer_feedback_not_found": {
        "uk": "Звернення не знайдено або воно вже недоступне.",
        "en": "Feedback wasn't found or is no longer available.",
    },
    "developer_feedback_unauthorized": {
        "uk": "Ця дія доступна лише розробнику.",
        "en": "This action is available to the developer only.",
    },
}

def t(key: str, lang: str = "uk") -> str:
    entry = TEXTS.get(key, {})
    return entry.get(lang) or entry.get("en") or f"[{key}]"

def t_pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en

def pick_lang(lang: str, uk: str, en: str) -> str:
    return t_pair(lang, uk, en)
