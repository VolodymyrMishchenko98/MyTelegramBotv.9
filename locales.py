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
    "settings_open_button": {
        "uk": "⚙️ Налаштування",
        "en": "⚙️ Settings",
    },
    "sections_open_button": {
        "uk": "🧭 Інші розділи",
        "en": "🧭 More sections",
    },
    "sections_title": {
        "uk": "Розділи SportBot",
        "en": "SportBot sections",
    },
    "sections_description": {
        "uk": "Обери, чим хочеш зайнятися.",
        "en": "Choose what you'd like to do.",
    },
    "sections_economy": {
        "uk": "🛍 Магазин та інвентар",
        "en": "🛍 Shop and inventory",
    },
    "sections_activities": {
        "uk": "🎮 Активності",
        "en": "🎮 Activities",
    },
    "sections_inspiration": {
        "uk": "💡 Натхнення та тренування",
        "en": "💡 Inspiration and workouts",
    },
    "economy_title": {
        "uk": "Магазин та інвентар",
        "en": "Shop and inventory",
    },
    "economy_description": {
        "uk": "Баланс: {balance} монет. Переглядай товари або керуй своїми предметами.",
        "en": "Balance: {balance} coins. Browse items or manage your inventory.",
    },
    "economy_shop_button": {
        "uk": "🛒 Відкрити магазин",
        "en": "🛒 Open shop",
    },
    "economy_inventory_button": {
        "uk": "🎒 Гаманець та інвентар",
        "en": "🎒 Wallet and inventory",
    },
    "economy_use_button": {
        "uk": "✨ Використати предмет",
        "en": "✨ Use an item",
    },
    "economy_back_button": {
        "uk": "⬅️ До магазину та інвентарю",
        "en": "⬅️ Back to shop and inventory",
    },
    "economy_inventory_empty": {
        "uk": "У вас ще немає предметів.",
        "en": "You don't have any items yet.",
    },
    "economy_use_empty": {
        "uk": "Немає предметів для використання.",
        "en": "There are no items to use.",
    },
    "economy_use_prompt": {
        "uk": "Оберіть предмет для використання:",
        "en": "Choose an item to use:",
    },
    "economy_item_used": {
        "uk": "використано",
        "en": "used",
    },
    "economy_item_missing": {
        "uk": "Предмет не знайдено.",
        "en": "Item not found.",
    },
    "economy_purchase_duplicate": {
        "uk": "Цю покупку вже оброблено.",
        "en": "This purchase has already been processed.",
    },
    "economy_purchase_failed": {
        "uk": "Не вдалося завершити покупку. Монети не списано.",
        "en": "The purchase could not be completed. No coins were charged.",
    },
    "economy_shop_error": {
        "uk": "Не вдалося відкрити магазин. Спробуйте ще раз.",
        "en": "The shop could not be opened. Please try again.",
    },
    "activities_title": {
        "uk": "Активності",
        "en": "Activities",
    },
    "activities_description": {
        "uk": "Щоденне завдання та прогрес на сьогодні:",
        "en": "Today's daily task and progress:",
    },
    "activities_daily_button": {
        "uk": "🎯 Відкрити щоденне завдання",
        "en": "🎯 Open daily task",
    },
    "activities_today_button": {
        "uk": "📅 Активність за сьогодні",
        "en": "📅 Today's activity",
    },
    "activities_challenge_button": {
        "uk": "🔥 Челенджі",
        "en": "🔥 Challenges",
    },
    "activities_back_button": {
        "uk": "⬅️ До активностей",
        "en": "⬅️ Back to activities",
    },
    "activities_challenge_title": {
        "uk": "Челендж дня",
        "en": "Challenge of the day",
    },
    "activities_error": {
        "uk": "Не вдалося завантажити активність. Спробуйте ще раз.",
        "en": "The activity could not be loaded. Please try again.",
    },
    "inspiration_title": {
        "uk": "Натхнення та тренування",
        "en": "Inspiration and workouts",
    },
    "inspiration_description": {
        "uk": "Запропоновані тренування, мотивація та корисні поради.",
        "en": "Suggested workouts, motivation, and helpful tips.",
    },
    "inspiration_suggest_button": {
        "uk": "💪 Запропонувати тренування",
        "en": "💪 Suggest a workout",
    },
    "inspiration_motivate_button": {
        "uk": "🚀 Мотивація",
        "en": "🚀 Motivation",
    },
    "inspiration_tip_button": {
        "uk": "🧠 Порада",
        "en": "🧠 Tip",
    },
    "inspiration_back_button": {
        "uk": "⬅️ До натхнення та тренувань",
        "en": "⬅️ Back to inspiration and workouts",
    },
    "inspiration_motivation_title": {
        "uk": "Мотивація",
        "en": "Motivation",
    },
    "inspiration_tip_title": {
        "uk": "Порада дня",
        "en": "Tip of the day",
    },
    "inspiration_goal_required": {
        "uk": "Спочатку задай мету в профілі (/profile).",
        "en": "Set a goal in your profile first (/profile).",
    },
    "settings_title": {
        "uk": "Налаштування SportBot",
        "en": "SportBot settings",
    },
    "settings_description": {
        "uk": "Керуй профілем, мовою, нагадуваннями та своїми даними.",
        "en": "Manage your profile, language, reminders, and personal data.",
    },
    "settings_profile": {
        "uk": "👤 Профіль",
        "en": "👤 Profile",
    },
    "settings_language": {
        "uk": "🌐 Мова",
        "en": "🌐 Language",
    },
    "settings_reminders": {
        "uk": "🔔 Нагадування",
        "en": "🔔 Reminders",
    },
    "settings_data": {
        "uk": "🗂 Керування даними",
        "en": "🗂 Manage data",
    },
    "settings_back": {
        "uk": "⬅️ До налаштувань",
        "en": "⬅️ Back to settings",
    },
    "settings_profile_edit": {
        "uk": "✏️ Редагувати профіль і мету",
        "en": "✏️ Edit profile and goal",
    },
    "settings_profile_visibility": {
        "uk": "👁 Видимість полів",
        "en": "👁 Field visibility",
    },
    "settings_profile_back": {
        "uk": "⬅️ До профілю",
        "en": "⬅️ Back to profile",
    },
    "settings_language_title": {
        "uk": "Мова інтерфейсу",
        "en": "Interface language",
    },
    "settings_language_current": {
        "uk": "Поточна мова: {language}",
        "en": "Current language: {language}",
    },
    "settings_language_ukrainian": {
        "uk": "Українська",
        "en": "Українська",
    },
    "settings_language_english": {
        "uk": "English",
        "en": "English",
    },
    "settings_language_saved": {
        "uk": "Мову збережено ✅",
        "en": "Language saved ✅",
    },
    "settings_reminders_enabled": {
        "uk": "Нагадування увімкнені.",
        "en": "Reminders are enabled.",
    },
    "settings_reminders_disabled": {
        "uk": "Нагадування вимкнені.",
        "en": "Reminders are disabled.",
    },
    "settings_reminders_enabled_title": {
        "uk": "🔔 Стан нагадувань",
        "en": "🔔 Reminder status",
    },
    "settings_reminders_enable": {
        "uk": "✅ Увімкнути нагадування",
        "en": "✅ Enable reminders",
    },
    "settings_reminders_disable": {
        "uk": "🔕 Вимкнути нагадування",
        "en": "🔕 Disable reminders",
    },
    "settings_data_title": {
        "uk": "Керування даними",
        "en": "Manage your data",
    },
    "settings_data_description": {
        "uk": "Експортуй або імпортуй свої дані чи скинь профіль. Це не резервна копія бази даних.",
        "en": "Export or import your data, or reset your profile. This is not a database backup.",
    },
    "settings_data_export": {
        "uk": "📤 Експортувати дані",
        "en": "📤 Export data",
    },
    "settings_data_import": {
        "uk": "📥 Імпортувати дані",
        "en": "📥 Import data",
    },
    "settings_data_reset": {
        "uk": "🗑 Скинути профіль",
        "en": "🗑 Reset profile",
    },
    "settings_export_caption": {
        "uk": "✅ Ваші дані для резервної копії. Збережіть цей файл.\n\nДля відновлення використайте /import",
        "en": "✅ Your backup data. Save this file.\n\nUse /import to restore",
    },
    "settings_import_prompt": {
        "uk": "📥 Надішліть файл JSON для імпорту даних\n\n⚠️ Увага: це перезапише ваші поточні дані!",
        "en": "📥 Send a JSON file to import data\n\n⚠️ Warning: this will overwrite your current data!",
    },
    "settings_import_confirmation": {
        "uk": "⚠️ Це перезапише всі ваші дані. Продовжити?",
        "en": "⚠️ This will overwrite all your data. Continue?",
    },
    "settings_import_missing": {
        "uk": "❌ Дані не знайдено",
        "en": "❌ Data not found",
    },
    "settings_import_invalid": {
        "uk": "❌ Невірний формат даних",
        "en": "❌ Invalid data format",
    },
    "settings_import_success": {
        "uk": "✅ Дані успішно імпортовано!",
        "en": "✅ Data imported successfully!",
    },
    "settings_import_failure": {
        "uk": "❌ Помилка імпорту: {message}",
        "en": "❌ Import error: {message}",
    },
    "settings_import_cancelled": {
        "uk": "❌ Імпорт скасовано",
        "en": "❌ Import cancelled",
    },
    "settings_reset_prompt": {
        "uk": "Видалити профіль і всі дані?",
        "en": "Delete profile and all data?",
    },
    "settings_reset_success": {
        "uk": "✅ Профіль повністю видалено. Дані очищені.",
        "en": "✅ Profile completely deleted. All data cleared.",
    },
    "settings_reset_failure": {
        "uk": "❌ Помилка при видаленні. Спробуйте пізніше.",
        "en": "❌ Error during deletion. Try again later.",
    },
    "settings_reset_cancelled": {
        "uk": "Скасування.",
        "en": "Canceled.",
    },
    "help": {
        "uk": ("<b>Основні команди</b>\n"
               "/start — відкрити головне меню\n/help — ця довідка\n/workout — записати тренування\n"
               "/today — активність за сьогодні\n/stats — статистика й прогрес\n/history — історія тренувань\n"
               "/program — тренувальні програми\n\n"
               "<b>Розділи головного меню</b>\n"
               "Статистика: графіки, рівень і XP, досягнення, активність, вага та тижнева ціль.\n"
               "Налаштування: профіль, редагування, видимість, мова, нагадування й керування даними.\n"
               "Магазин та інвентар: баланс, покупки й використання предметів.\n"
               "Активності: щоденні завдання та окремі челенджі.\n"
               "Натхнення: запропоновані тренування, мотивація та поради.\n"
               "Зв’язок з розробником доступний із головного меню.\n\n"
               "<b>Додаткові можливості</b>\n"
               "Зберігай і переглядай вагу, змінюй цілі профілю й тижня, налаштовуй нагадування. "
               "Дані можна експортувати, імпортувати після підтвердження або скинути після підтвердження. "
               "Старі команди цих функцій продовжують працювати; вибір мови та зворотний зв’язок доступні в меню.\n\n"
               "Відкрий /start, щоб перейти до розділів."),
        "en": ("<b>Main commands</b>\n"
               "/start — open the main menu\n/help — this guide\n/workout — record a workout\n"
               "/today — today's activity\n/stats — stats and progress\n/history — workout history\n"
               "/program — training plans\n\n"
               "<b>Main menu sections</b>\n"
               "Stats: charts, level and XP, achievements, activity, weight, and weekly goal.\n"
               "Settings: profile, editing, visibility, language, reminders, and data management.\n"
               "Shop and inventory: balance, purchases, and item use.\n"
               "Activities: daily tasks and separate challenges.\n"
               "Inspiration: suggested workouts, motivation, and tips.\n"
               "Contact the developer from the main menu.\n\n"
               "<b>More features</b>\n"
               "Track and review weight, update profile and weekly goals, and manage reminders. "
               "You can export data, import it after confirmation, or reset it after confirmation. "
               "Legacy commands for these features still work; language selection and feedback are in the menu.\n\n"
               "Send /start to open the sections."),
    },
    "help_admin": {
        "uk": "\n\n<b>Адміністраторські команди</b>\n/admin — статистика бота\n/backup — резервна копія бази даних",
        "en": "\n\n<b>Admin commands</b>\n/admin — bot statistics\n/backup — database backup",
    },
    "program_create": {
        "uk": "📝 Створити програму",
        "en": "📝 Create a program",
    },
    "program_empty": {
        "uk": "🏋️ <b>Персональна програма</b>\n\nУ тебе ще немає активної програми. Відповідай на кілька коротких запитань — і я складу помірний план на тиждень.",
        "en": "🏋️ <b>Personal training plan</b>\n\nYou don't have an active plan yet. Answer a few quick questions and I'll build a moderate weekly plan.",
    },
    "program_archive": {
        "uk": "📦 Архівувати програму",
        "en": "📦 Archive plan",
    },
    "program_archives": {
        "uk": "🗂 Архів програм",
        "en": "🗂 Archived plans",
    },
    "program_back": {
        "uk": "↩️ Назад",
        "en": "↩️ Back",
    },
    "program_cancel": {
        "uk": "✖️ Скасувати",
        "en": "✖️ Cancel",
    },
    "program_continue": {
        "uk": "Далі",
        "en": "Continue",
    },
    "program_skip": {
        "uk": "Пропустити",
        "en": "Skip",
    },
    "program_generate": {
        "uk": "✅ Створити програму",
        "en": "✅ Generate plan",
    },
    "program_to_menu": {
        "uk": "До програми",
        "en": "Back to plan",
    },
    "program_archive_confirm": {
        "uk": "Так, архівувати",
        "en": "Yes, archive",
    },
    "program_back_to_plan": {
        "uk": "↩️ До програми",
        "en": "↩️ Back to plan",
    },
    "program_invalid_choice": {
        "uk": "Цей крок застарів. Відкрий /program і продовж.",
        "en": "This step has expired. Open /program to continue.",
    },
    "program_choose_button": {
        "uk": "Обери варіант кнопкою нижче.",
        "en": "Choose an option using the buttons below.",
    },
    "program_select_equipment": {
        "uk": "Обери принаймні один варіант обладнання.",
        "en": "Select at least one equipment option.",
    },
    "program_not_found": {
        "uk": "Програму не знайдено або вона більше недоступна.",
        "en": "The plan wasn't found or is no longer available.",
    },
    "program_no_archives": {
        "uk": "Архівованих програм поки немає.",
        "en": "There are no archived plans yet.",
    },
    "program_archive_item": {
        "uk": "Програма #{program_id} · {created}",
        "en": "Plan #{program_id} · {created}",
    },
    "program_question_goal": {
        "uk": "1/7. Яка твоя мета тренувань?",
        "en": "1/7. What is your training goal?",
    },
    "program_question_location": {
        "uk": "2/7. Де плануєш тренуватися?",
        "en": "2/7. Where do you plan to train?",
    },
    "program_question_frequency": {
        "uk": "3/7. Скільки тренувань на тиждень тобі підходить?",
        "en": "3/7. How many workouts per week work for you?",
    },
    "program_question_duration": {
        "uk": "4/7. Скільки часу маєш на одне заняття?",
        "en": "4/7. How much time do you have for each session?",
    },
    "program_question_level": {
        "uk": "5/7. Як оціниш свій рівень підготовки?",
        "en": "5/7. How would you describe your current level?",
    },
    "program_question_equipment": {
        "uk": "6/7. Обери все доступне обладнання. «Без обладнання» не поєднується з іншими варіантами.",
        "en": "6/7. Select all available equipment. “No equipment” can't be combined with other options.",
    },
    "program_question_other_equipment": {
        "uk": "Переліч інше доступне обладнання через кому (до 120 символів). Відомі назви можна врахувати; незнайоме обладнання не буде автоматично додане до вправ.",
        "en": "List other available equipment separated by commas (up to 120 characters). Recognized items can be used; unknown equipment won't be added to exercises automatically.",
    },
    "program_question_notes": {
        "uk": "7/7. Додаткові побажання чи обмеження? Напиши текстом (до 500 символів) або пропусти. Для підготовки до спорту вкажи його назву.",
        "en": "7/7. Any extra preferences or limitations? Enter up to 500 characters or skip. If preparing for a sport, include its name.",
    },
    "program_goal_general": {
        "uk": "Загальна фізична підготовка",
        "en": "General fitness",
    },
    "program_goal_strength": {
        "uk": "Розвиток сили",
        "en": "Strength",
    },
    "program_goal_endurance": {
        "uk": "Витривалість",
        "en": "Endurance",
    },
    "program_goal_mobility": {
        "uk": "Гнучкість і мобільність",
        "en": "Flexibility and mobility",
    },
    "program_goal_sport": {
        "uk": "Підготовка до спорту",
        "en": "Sport preparation",
    },
    "program_location_home": {
        "uk": "Дім",
        "en": "Home",
    },
    "program_location_gym": {
        "uk": "Тренажерний зал",
        "en": "Gym",
    },
    "program_location_outdoors": {
        "uk": "Вулиця",
        "en": "Outdoors",
    },
    "program_frequency_2_3": {
        "uk": "2–3 на тиждень",
        "en": "2–3 per week",
    },
    "program_frequency_4": {
        "uk": "4 на тиждень",
        "en": "4 per week",
    },
    "program_frequency_5": {
        "uk": "5 на тиждень",
        "en": "5 per week",
    },
    "program_duration_15_20": {
        "uk": "15–20 хвилин",
        "en": "15–20 minutes",
    },
    "program_duration_30": {
        "uk": "30 хвилин",
        "en": "30 minutes",
    },
    "program_duration_45": {
        "uk": "45 хвилин",
        "en": "45 minutes",
    },
    "program_duration_60": {
        "uk": "60 хвилин",
        "en": "60 minutes",
    },
    "program_level_beginner": {
        "uk": "Початковий",
        "en": "Beginner",
    },
    "program_level_intermediate": {
        "uk": "Середній",
        "en": "Intermediate",
    },
    "program_level_advanced": {
        "uk": "Просунутий",
        "en": "Advanced",
    },
    "program_equipment_none": {
        "uk": "Без обладнання",
        "en": "No equipment",
    },
    "program_equipment_dumbbells": {
        "uk": "Гантелі",
        "en": "Dumbbells",
    },
    "program_equipment_pullup_bar": {
        "uk": "Турнік",
        "en": "Pull-up bar",
    },
    "program_equipment_machines": {
        "uk": "Тренажери",
        "en": "Machines",
    },
    "program_equipment_other": {
        "uk": "Інше",
        "en": "Other",
    },
    "program_not_selected": {
        "uk": "не вибрано",
        "en": "not selected",
    },
    "program_parameter_goal": {
        "uk": "Мета: {value}",
        "en": "Goal: {value}",
    },
    "program_parameter_location": {
        "uk": "Місце: {value}",
        "en": "Location: {value}",
    },
    "program_parameter_frequency": {
        "uk": "Частота: {value}",
        "en": "Frequency: {value}",
    },
    "program_parameter_duration": {
        "uk": "Тривалість: {value}",
        "en": "Session length: {value}",
    },
    "program_parameter_level": {
        "uk": "Рівень: {value}",
        "en": "Level: {value}",
    },
    "program_parameter_equipment": {
        "uk": "Обладнання: {value}",
        "en": "Equipment: {value}",
    },
    "program_parameter_notes": {
        "uk": "Побажання/обмеження: {value}",
        "en": "Preferences/limitations: {value}",
    },
    "program_confirmation": {
        "uk": "Перевір параметри програми:\n\n{parameters}\n\nПісля підтвердження збережу нову програму.",
        "en": "Review your plan settings:\n\n{parameters}\n\nConfirm to save the new plan.",
    },
    "program_replace_notice": {
        "uk": "Поточна програма буде архівована, а нова стане активною. Історія тренувань не зміниться.",
        "en": "Your current plan will be archived and the new one will become active. Workout history won't change.",
    },
    "program_saved_title": {
        "uk": "🏋️ <b>Тижнева програма #{program_id}</b>",
        "en": "🏋️ <b>Weekly plan #{program_id}</b>",
    },
    "program_weekly_schedule": {
        "uk": "<b>Заняття:</b>\n{days}",
        "en": "<b>Sessions:</b>\n{days}",
    },
    "program_recovery_notice": {
        "uk": "Дні без занять — для відновлення; за потреби перенеси тренування або відпочинь.",
        "en": "Days without sessions are for recovery; reschedule a workout or rest when needed.",
    },
    "program_two_day_option_note": {
        "uk": "Для варіанта 2–3 на тиждень у плані є три заняття; якщо обираєш два, пропусти одне й залиш день для відновлення.",
        "en": "The 2–3 per week option schedules three sessions; if you prefer two, skip one and keep a recovery day.",
    },
    "program_five_day_note": {
        "uk": "Для частоти 5 разів два заняття зроблено легкими сесіями мобільності; середа й субота залишаються днями відновлення.",
        "en": "For five sessions per week, two are lighter mobility sessions; Wednesday and Saturday remain recovery days.",
    },
    "program_schedule_line": {
        "uk": "• {day} — {title}",
        "en": "• {day} — {title}",
    },
    "program_progression": {
        "uk": "<b>Поступове навантаження:</b>\n{steps}",
        "en": "<b>Gradual progression:</b>\n{steps}",
    },
    "program_progression_week_1": {
        "uk": "Тиждень 1: відпрацюй техніку у комфортному темпі.",
        "en": "Week 1: learn the movements at a comfortable pace.",
    },
    "program_progression_week_2": {
        "uk": "Тиждень 2: за доброго самопочуття додай 1 повторення або 1–2 хвилини.",
        "en": "Week 2: if you feel well, add 1 repetition or 1–2 minutes.",
    },
    "program_progression_week_3": {
        "uk": "Тиждень 3: повтори невелике збільшення лише за повного відновлення.",
        "en": "Week 3: repeat a small increase only if you're fully recovered.",
    },
    "program_progression_week_4": {
        "uk": "Тиждень 4: збережи навантаження або зроби легший тиждень.",
        "en": "Week 4: maintain the load or take an easier week.",
    },
    "program_safety_general": {
        "uk": "План загальний, а тривалість орієнтовна. Не тренуйся через біль чи до виснаження; зупинись, якщо стає зле.",
        "en": "This is a general plan and durations are estimates. Don't train through pain or to exhaustion; stop if you feel unwell.",
    },
    "program_safety_minor": {
        "uk": "План адаптовано для неповнолітнього: помірні вправи, акцент на техніці, без максимальних ваг. Тренуйся з наглядом дорослого або тренера.",
        "en": "This plan is adjusted for a minor: moderate exercises, technique first, no maximum weights. Train with an adult or coach supervising.",
    },
    "program_notes_caution": {
        "uk": "Важливо: побажання й обмеження збережені, але система не може оцінити травми чи медичні стани. Узгодь план із фахівцем перед тренуванням, якщо маєш такі обмеження.",
        "en": "Important: your notes are saved, but the bot can't assess injuries or medical conditions. Consult a qualified professional before using this plan if you have such limitations.",
    },
    "program_sport_caution": {
        "uk": "Це загальна фізична підготовка, не спеціалізований план для конкретного виду спорту.",
        "en": "This is general conditioning, not a sport-specific training plan.",
    },
    "program_day_title": {
        "uk": "📅 <b>{day} · {title}</b>",
        "en": "📅 <b>{day} · {title}</b>",
    },
    "program_objective": {
        "uk": "<b>Мета:</b> {value}",
        "en": "<b>Focus:</b> {value}",
    },
    "program_warmup": {
        "uk": "<b>Розминка:</b> {value}",
        "en": "<b>Warm-up:</b> {value}",
    },
    "program_warmup_detail": {
        "uk": "5–7 хв легкої ходьби та плавних рухів суглобами.",
        "en": "5–7 min of easy walking and gentle joint movements.",
    },
    "program_exercises": {
        "uk": "<b>Вправи:</b>",
        "en": "<b>Exercises:</b>",
    },
    "program_prescription_reps": {
        "uk": "{sets} підх. × {reps} повт.",
        "en": "{sets} sets × {reps} reps",
    },
    "program_prescription_minutes": {
        "uk": "{sets} × {minutes} хв у легкому темпі",
        "en": "{sets} × {minutes} min at an easy pace",
    },
    "program_rest": {
        "uk": "<b>Відпочинок:</b> приблизно {seconds} с між підходами.",
        "en": "<b>Rest:</b> about {seconds} sec between sets.",
    },
    "program_cooldown": {
        "uk": "<b>Заминка:</b> {value}",
        "en": "<b>Cool-down:</b> {value}",
    },
    "program_cooldown_detail": {
        "uk": "3–5 хв спокійного руху й м'якого розтягування без болю.",
        "en": "3–5 min of easy movement and gentle, pain-free stretching.",
    },
    "program_duration_estimate": {
        "uk": "<b>Тривалість:</b> приблизно {minutes} хв.",
        "en": "<b>Duration:</b> about {minutes} min.",
    },
    "program_effort_note": {
        "uk": "Залишай запас сил і виконуй рухи контрольовано.",
        "en": "Keep some energy in reserve and move with control.",
    },
    "program_objective_general": {
        "uk": "помірна робота на все тіло",
        "en": "moderate full-body work",
    },
    "program_objective_strength": {
        "uk": "контрольована силова робота без максимальних ваг",
        "en": "controlled strength work without maximum weights",
    },
    "program_objective_endurance": {
        "uk": "розвиток витривалості у комфортному темпі",
        "en": "build endurance at a comfortable pace",
    },
    "program_objective_mobility": {
        "uk": "м'яка рухливість і контроль руху",
        "en": "gentle mobility and movement control",
    },
    "program_objective_sport": {
        "uk": "загальна фізична підготовка до спорту",
        "en": "general conditioning for sport",
    },
    "program_session_full_a": {
        "uk": "Все тіло A",
        "en": "Full body A",
    },
    "program_session_full_b": {
        "uk": "Все тіло B",
        "en": "Full body B",
    },
    "program_session_full_c": {
        "uk": "Все тіло C",
        "en": "Full body C",
    },
    "program_session_strength_a": {
        "uk": "Сила A",
        "en": "Strength A",
    },
    "program_session_strength_b": {
        "uk": "Сила B",
        "en": "Strength B",
    },
    "program_session_endurance_a": {
        "uk": "Витривалість A",
        "en": "Endurance A",
    },
    "program_session_endurance_b": {
        "uk": "Витривалість B",
        "en": "Endurance B",
    },
    "program_session_mobility_a": {
        "uk": "Мобільність A",
        "en": "Mobility A",
    },
    "program_session_mobility_b": {
        "uk": "Мобільність B",
        "en": "Mobility B",
    },
    "program_session_sport_a": {
        "uk": "Загальна підготовка A",
        "en": "General preparation A",
    },
    "program_session_sport_b": {
        "uk": "Загальна підготовка B",
        "en": "General preparation B",
    },
    "program_session_cardio": {
        "uk": "Кардіо та корпус",
        "en": "Cardio and core",
    },
    "program_session_mobility": {
        "uk": "Мобільність і легка активність",
        "en": "Mobility and light activity",
    },
    "program_day_monday": {"uk": "Понеділок", "en": "Monday"},
    "program_day_tuesday": {"uk": "Вівторок", "en": "Tuesday"},
    "program_day_wednesday": {"uk": "Середа", "en": "Wednesday"},
    "program_day_thursday": {"uk": "Четвер", "en": "Thursday"},
    "program_day_friday": {"uk": "П'ятниця", "en": "Friday"},
    "program_day_saturday": {"uk": "Субота", "en": "Saturday"},
    "program_day_sunday": {"uk": "Неділя", "en": "Sunday"},
    "program_exercise_squat": {
        "uk": "Присідання до комфортної глибини",
        "en": "Comfortable-range squats",
    },
    "program_exercise_push": {
        "uk": "Жимова вправа з доступним обладнанням",
        "en": "Pressing exercise with available equipment",
    },
    "program_exercise_pull": {
        "uk": "Тягова вправа з доступним обладнанням",
        "en": "Pulling exercise with available equipment",
    },
    "program_exercise_glute_bridge": {
        "uk": "Сідничний місток",
        "en": "Glute bridge",
    },
    "program_exercise_dead_bug": {
        "uk": "Dead bug (контроль корпусу)",
        "en": "Dead bug (core control)",
    },
    "program_exercise_bird_dog": {
        "uk": "Птах-собака",
        "en": "Bird dog",
    },
    "program_exercise_step_back": {
        "uk": "Крок назад із підтримкою за потреби",
        "en": "Step-back with support if needed",
    },
    "program_exercise_brisk_walk": {
        "uk": "Швидка ходьба",
        "en": "Brisk walk",
    },
    "program_exercise_march": {
        "uk": "Марш на місці",
        "en": "March in place",
    },
    "program_exercise_cat_cow": {
        "uk": "Плавна мобілізація спини «кішка-корова»",
        "en": "Gentle cat-cow spinal mobility",
    },
    "program_exercise_hip_mobility": {
        "uk": "М'яка рухливість кульшових суглобів",
        "en": "Gentle hip mobility",
    },
    "program_exercise_shoulder_mobility": {
        "uk": "Плавні кола плечима",
        "en": "Gentle shoulder circles",
    },
    "program_stationary_bike": {
        "uk": "Велотренажер у легкому темпі",
        "en": "Stationary bike at an easy pace",
    },
    "program_machine_leg_press": {
        "uk": "Жим ногами в тренажері з легким опором",
        "en": "Leg press with light resistance",
    },
    "program_dumbbell_squat": {
        "uk": "Присідання з легкими гантелями",
        "en": "Squat with light dumbbells",
    },
    "program_machine_chest_press": {
        "uk": "Жим від грудей у тренажері з легким опором",
        "en": "Machine chest press with light resistance",
    },
    "program_dumbbell_press": {
        "uk": "Жим гантелей лежачи на підлозі",
        "en": "Dumbbell floor press",
    },
    "program_wall_pushup": {
        "uk": "Відтискання від стіни",
        "en": "Wall push-ups",
    },
    "program_incline_pushup": {
        "uk": "Відтискання від стійкої підвищеної опори",
        "en": "Incline push-ups against a stable surface",
    },
    "program_machine_row": {
        "uk": "Тяга в тренажері з легким опором",
        "en": "Machine row with light resistance",
    },
    "program_dumbbell_row": {
        "uk": "Тяга гантелі з опорою",
        "en": "Supported dumbbell row",
    },
    "program_band_press": {
        "uk": "Жим еластичної стрічки з легким натягом",
        "en": "Resistance-band press with light tension",
    },
    "program_band_row": {
        "uk": "Тяга еластичної стрічки з легким натягом",
        "en": "Resistance-band row with light tension",
    },
    "program_supported_hang": {
        "uk": "Вис на турніку з опорою ногами",
        "en": "Supported bar hang with feet on the floor",
    },
    "program_prone_w_raise": {
        "uk": "Підйом рук лежачи у формі W",
        "en": "Prone W raise",
    },
    "program_text_only": {
        "uk": "Надішли текст або скористайся кнопкою пропуску.",
        "en": "Send text or use the skip button.",
    },
    "program_empty_input": {
        "uk": "Поле порожнє. Напиши текст або пропусти цей крок.",
        "en": "The field is empty. Enter text or skip this step.",
    },
    "program_equipment_too_long": {
        "uk": "Занадто довго. Максимум — 120 символів.",
        "en": "That's too long. Maximum is 120 characters.",
    },
    "program_notes_too_long": {
        "uk": "Занадто довго. Максимум — 500 символів.",
        "en": "That's too long. Maximum is 500 characters.",
    },
    "program_save_error": {
        "uk": "Не вдалося створити програму. Твої відповіді збережені — спробуй ще раз.",
        "en": "Couldn't create the plan. Your answers are still available—please try again.",
    },
    "program_archives_title": {
        "uk": "🗂 Архівовані програми",
        "en": "🗂 Archived plans",
    },
    "program_archive_confirmation": {
        "uk": "Архівувати поточну програму? Вона залишиться доступною в архіві.",
        "en": "Archive the current plan? It will remain available in your archive.",
    },
    "program_archived": {
        "uk": "Програму перенесено до архіву.",
        "en": "The plan has been archived.",
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
