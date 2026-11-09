import asyncio
import aiohttp
import logging                 # standard library — always available
from aiogram import F
import sqlite3
import re
import html
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
import uuid
import sys
from functools import lru_cache
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BufferedInputFile, ErrorEvent
)
from aiogram.filters import Command
import os
from dotenv import load_dotenv
from db_improved import (
    DB_PATH,
    get_db, execute_query, fetch_one, fetch_all, execute_transaction,
    clear_user_all_data, verify_user_exists, get_user_data_safe,
    init_connection, get_db_context,
    get_user_streak,
    get_user_xp_level, add_xp_to_user, ensure_users_deleted_at
)
from utils.levels import get_rank, xp_for_next_level, total_xp_for_level, get_progress_in_level
from utils.streak import calculate_streak as _calculate_streak, calculate_best_streak, update_streak
from profile_visibility import (
    get_profile_visibility, set_field_visibility, toggle_field_visibility,
    get_visible_fields, is_field_visible, ensure_user_exists, PROFILE_FIELDS
)
from daily_tasks import DAILY_TASKS, DEFAULT_DAILY_TASK_ID
from backup_service import create_backup
from db_config import production_database_required, require_database_exists

# ── thin third-party / local ────────────────────────────────────────────────
from services.logging_config import get_logger
from services.workout_stats import summarize_workouts
from services.workout_service import save_workout_session
from services.workout_input import parse_workout_exercises
from services.achievements import check_and_award, get_user_stats
from services.reward_notifications import build_reward_summary
from services.reward_settlement import settle_action_rewards
from handlers.workouts import _workout_note_keyboard
from game_config import (
    WORKOUT_XP_REWARD, DAILY_TASK_XP_REWARD, SUGGESTED_WORKOUT_XP, CHALLENGE_XP_REWARD,
    WORKOUT_COIN_REWARD, SUGGESTED_WORKOUT_REWARD, CHALLENGE_COIN_REWARD,
    STREAK_BONUSES, STREAK_XP_MULTIPLIERS, MAX_XP_MULTIPLIER, LEVEL_UNLOCKS,
    SHOP_ITEMS,
)
from locales import t

log = get_logger("bot.main")

load_dotenv()
token = os.getenv("BOT_TOKEN")
API_NINJAS_KEY = os.getenv("API_NINJAS_KEY")

if not token:
    raise RuntimeError("BOT_TOKEN is not set. Add it to environment variables.")
if not API_NINJAS_KEY:
    raise RuntimeError("API_NINJAS_KEY is not set. Add it to environment variables.")

# Оптимизация для более быстрой отправки сообщений: timeout 10 секунд вместо 30
bot = Bot(token=token, timeout=aiohttp.ClientTimeout(total=10, connect=5, sock_read=5))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


@dp.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot) -> bool:
    log.exception(
        "Unhandled exception on update %s",
        event.update.update_id,
        exc_info=event.exception,
    )
    update = event.update
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id

    if chat_id:
        try:
            await bot.send_message(
                chat_id,
                f"❌ <code>{type(event.exception).__name__}: "
                f"{str(event.exception)[:400]}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    return True


calories_cache = {}
_manual_state_cache: dict[int, str] = {}
_pending_workouts: dict[int, dict] = {}
_pending_history_edits: dict[int, dict] = {}

# Shared HTTP session: one session handles ALL outgoing HTTP requests
# (avoids per-request TCP handovers / TLS negotiation overhead)
_http_session: aiohttp.ClientSession | None = None
_duplicate_cmd_cache: dict[int, tuple[int, float]] = {}
_DUPLICATE_TTL_SEC = 10
_instance_lock_handle = None


def is_duplicate_command(user_id: int, message_id: int) -> bool:
    """
    Проверить, является ли это обновление дубликатом недавно полученного.
    Некоторые Telegram клиенты отправляют одно обновление несколько раз.
    """
    import time
    current_time = time.time()
    cache_key = user_id
    
    if cache_key in _duplicate_cmd_cache:
        cached_msg_id, cached_time = _duplicate_cmd_cache[cache_key]
        
        # Если прошло больше TTL, очистить кэш
        if current_time - cached_time > _DUPLICATE_TTL_SEC:
            del _duplicate_cmd_cache[cache_key]
            return False
        
        # Если это тот же message_id, это дубликат
        if cached_msg_id == message_id:
            return True
    
    # Сохранить текущее сообщение в кэш
    _duplicate_cmd_cache[cache_key] = (message_id, current_time)
    return False


# ── Shared HTTP session ────────────────────────────────────────────────────────

def get_http_session() -> aiohttp.ClientSession:
    """Return a single shared :class:`aiohttp.ClientSession` for all outbound HTTP.

    The session is lazily created on first call and reused for the lifetime of the
    bot process so that TCP connections, TLS sessions, and connection limits are
    shared across every calorie lookup, reducing per-request latency.
    """
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
    return _http_session


async def close_http_session() -> None:
    """Gracefully close the shared HTTP session."""
    global _http_session
    if _http_session is not None and not _http_session.closed:
        await _http_session.close()


def acquire_single_instance_lock():
    """Prevent running two local polling copies from the same folder."""
    global _instance_lock_handle
    lock_path = os.path.join(os.getcwd(), ".bot.lock")
    _instance_lock_handle = open(lock_path, "w", encoding="utf-8")

    if os.name == "nt":
        import msvcrt
        try:
            msvcrt.locking(_instance_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError(
                "Another local bot instance is already running. Stop it before starting this one."
            )
    else:
        import fcntl
        try:
            fcntl.flock(_instance_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError(
                "Another local bot instance is already running. Stop it before starting this one."
            )

    _instance_lock_handle.write(str(os.getpid()))
    _instance_lock_handle.flush()


# ---------- UI ----------
def reminders_on_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t_pair(lang, "❌ Вимкнути", "❌ Disable"),
            callback_data="reminders_off"
        )
    ]])


def reminders_off_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t_pair(lang, "✅ Увімкнути", "✅ Enable"),
            callback_data="reminders_on"
        )
    ]])


def reset_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t_pair(lang, "✅ Так", "✅ Yes"), callback_data="reset_yes"),
        InlineKeyboardButton(text=t_pair(lang, "❌ Ні", "❌ No"), callback_data="reset_no")
    ]])


def suggest_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t_pair(lang, "✅ Виконав", "✅ Done"), callback_data="suggest_done"),
        InlineKeyboardButton(text=t_pair(lang, "🔁 Інша", "🔁 Another"), callback_data="suggest_retry")
    ]])


def challenge_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t_pair(lang, "✅ Зробив", "✅ Done"), callback_data="challenge_done"),
        InlineKeyboardButton(text=t_pair(lang, "🔁 Інший челендж", "🔁 Another challenge"), callback_data="challenge_next")
    ]])


def daily_task_keyboard(lang: str, task: dict, completed: bool, date_text: str = None) -> InlineKeyboardMarkup:
    date_text = date_text or datetime.now().strftime("%Y-%m-%d")
    if completed:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=t_pair(lang, "✅ Виконано", "✅ Completed"),
                callback_data=f"daily_done_{date_text}"
            )
        ]])

    unit = t_pair(lang, task["uk_unit"], task["en_unit"])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"+{task['step']} {unit}",
            callback_data=f"daily_add_{date_text}"
        )
    ]])


def shop_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Показує тільки категорії (шаг 1 після /shop)."""
    categories = sorted(
        {item.get("category", "Інше") for item in SHOP_ITEMS.values()}
    )

    rows: list[list[InlineKeyboardButton]] = []
    for category in categories:
        rows.append([
            InlineKeyboardButton(
                text=f"━━ {category} ━━",
                callback_data=f"shop_cat_{category}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_category_keyboard(lang: str, category: str, user_level: int = 1) -> InlineKeyboardMarkup:
    """Показує товари в конкретній категорії (шаг 2)."""
    rows: list[list[InlineKeyboardButton]] = []

    category_items = [
        (item_id, item)
        for item_id, item in SHOP_ITEMS.items()
        if item.get("category", "Інше") == category
    ]
    category_items.sort(key=lambda x: x[1].get("cost", 0))

    for item_id, item in category_items:
        icon  = item.get("icon", "🛍️")
        name  = t_pair(lang, item["uk_name"], item["en_name"])
        cost  = item.get("cost", 0)
        mlevel = item.get("min_level", 1)
        if user_level < mlevel:
            lock = t_pair(lang, f"🔒 Лвл {mlevel}", f"🔒 Lvl {mlevel}")
            text = f"{icon} {cost}🪙 · {name}\n   {lock}"
        else:
            text = f"{icon} {cost}🪙 · {name}"
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"shop_buy_{item_id}"
            )
        ])

    # Кнопка назад в список категорий
    rows.append([
        InlineKeyboardButton(
            text=t_pair(lang, "⬅️ Назад", "⬅️ Back"),
            callback_data="shop_back_to_categories"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# Константи для обмежень
MAX_POWER_PLANS = 3  # Макс преміум тренувань
MAX_MOTIVATION_PACKS = 2
MAX_COIN_BOOSTERS = 1
MAX_RESTORE_TOKENS = 2

# SHOP_ITEMS is defined centrally in game_config.py.
# XP rewards (pure account progress — no coins involved)
WORKOUT_XP_REWARD       = 10  # per exercise in manual /workout
DAILY_TASK_XP_REWARD    = 15
SUGGESTED_WORKOUT_XP    = 20
CHALLENGE_XP_REWARD     = 15

# Coin rewards (currency — can be spent in /shop)
WORKOUT_COIN_REWARD     = 10  # per exercise
SUGGESTED_WORKOUT_REWARD = 25
CHALLENGE_COIN_REWARD   = 35

# Streak bonuses: coins (currency) + XP (progress) — awarded once at each milestone
STREAK_BONUSES = {
    3:  (15,  10),
    5:  (30,  25),
    7:  (50,  50),
    10: (80,  80),
    14: (120, 120),
    21: (200, 200),
    30: (350, 350),
}

# Streak XP multiplier per 7-day streak tier: 7→1.10, 14→1.20, 21→1.30, 30→1.50
STREAK_XP_MULTIPLIERS = {
    7:  1.10,
    14: 1.20,
    21: 1.30,
    30: 1.50,
}
MAX_MULTIPLIER = 1.50  # cap


# Level unlocks: what the user GAINS when reaching the level
LEVEL_UNLOCKS = {
    3:  {  # Ukrainian / English descriptions
        "uk": "🔓 Рівень 3: Відкрито магазин бейджів!",
        "en": "🔓 Level 3: Badge shop unlocked!",
    },
    5:  {
        "uk": "🔓 Рівень 5: Рідкісні товари в магазині!",
        "en": "🔓 Level 5: Rare shop items unlocked!",
    },
    10: {
        "uk": "🔓 Рівень 10: Кастомізація профілю доступна!",
        "en": "🔓 Level 10: Profile customization unlocked!",
    },
    15: {
        "uk": "🔓 Рівень 15: Щоденні квести доступні!",
        "en": "🔓 Level 15: Daily quests unlocked!",
    },
}


def profile_visibility_keyboard(lang: str, visibility: dict) -> InlineKeyboardMarkup:
    rows = []
    for field, uk_label, en_label in PROFILE_FIELDS:
        enabled = bool(visibility.get(field, True))
        icon = "✅" if enabled else "🚫"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {t_pair(lang, uk_label, en_label)}",
                callback_data=f"profile_toggle_{field}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


language_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="English", callback_data="set_lang_en"),
        InlineKeyboardButton(text="Українська", callback_data="set_lang_uk")
    ]
])

MOTIVATION_QUOTES = [
    ("Маленькі кроки щодня = великі результати через місяць.", "Small steps every day = big results in a month."),
    ("Ти не завжди маєш бути мотивованим. Будь дисциплінованим.", "You don't always have to be motivated. Be disciplined."),
    ("Кожне тренування - це інвестиція у майбутнього себе.", "Every workout is an investment in your future self."),
    ("Не зупиняйся, коли втомився. Зупиняйся, коли завершив.", "Don't stop when you're tired. Stop when you're done."),
    ("Прогрес важливіший за ідеальність.", "Progress is more important than perfection.")
]

HEALTH_TIPS = [
    ("Після тренування випий склянку води протягом 15 хвилин.", "After training, drink a glass of water within 15 minutes."),
    ("Роби 5 хвилин розминки перед будь-яким навантаженням.", "Do 5 minutes of warm-up before any load."),
    ("Сон 7-8 годин пришвидшує відновлення м'язів.", "7-8 hours of sleep speeds up muscle recovery."),
    ("Додай білок до кожного основного прийому їжі.", "Add protein to every main meal."),
    ("Краще 20 хвилин руху щодня, ніж 2 години раз на тиждень.", "20 minutes of movement every day is better than 2 hours once a week.")
]

FITNESS_CHALLENGES = [
    ("30 присідань + 20 відтискувань + планка 40 сек", "30 squats + 20 push ups + 40 sec plank"),
    ("Швидка прогулянка 25 хв + розтяжка 5 хв", "25 min brisk walk + 5 min stretch"),
    ("3 кола: 15 випадів, 20 скручувань, планка 30 сек", "3 rounds: 15 lunges, 20 sit ups, 30 sec plank"),
    ("Біг або швидкий крок 20 хв без зупинок", "20 min run or fast walk without breaks"),
    ("100 стрибків на місці + 20 присідань + 20 випадів", "100 jumps in place + 20 squats + 20 lunges")
]


def get_localized_choice(lang: str, items):
    return random.choice(items)[1 if lang == "en" else 0]


def get_motivation_quote(lang: str) -> str:
    return get_localized_choice(lang, MOTIVATION_QUOTES)


def get_health_tip(lang: str) -> str:
    return get_localized_choice(lang, HEALTH_TIPS)


def get_fitness_challenge(lang: str) -> str:
    return get_localized_choice(lang, FITNESS_CHALLENGES)


def t_pair(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en  # default to English for any unknown/invalid language


def profile_input_prompt(lang: str) -> str:
    return t_pair(
        lang,
        "Введи профіль:\n"
        "Зріст, стать, вік, мета\n"
        "Приклад: 165, ч, 25, набрати масу\n\n"
        "Без віку теж можна: 165, ч, набрати масу",
        "Enter your profile:\n"
        "Height, gender, age, goal\n"
        "Example: 165, m, 25, gain muscle\n\n"
        "Without age also works: 165, m, gain muscle"
    )


def normalize_gender(value) -> str | None:
    v = str(value or "").strip().lower()
    male_values = {"ч", "m", "male", "man", "чоловік", "чоловик", "м", "хлопець"}
    female_values = {"ж", "f", "female", "woman", "жінка", "жинка", "дівчина"}

    if v in male_values:
        return "male"
    if v in female_values:
        return "female"

    if "чолов" in v or v.startswith("man"):
        return "male"
    if "жін" in v or "жин" in v or v.startswith("woman"):
        return "female"

    return None


def gender_display(lang: str, gender_value: str) -> str:
    normalized = normalize_gender(gender_value)
    if normalized == "male":
        return t_pair(lang, "чоловік👨", "man 👨")
    if normalized == "female":
        return t_pair(lang, "жінка👩", "woman 👩")

    return t_pair(lang, "не вказана", "not set")


def parse_profile_text(text: str):
    parts = [part.strip() for part in (text or "").split(",")]
    if len(parts) < 3:
        raise ValueError("format")

    try:
        height = int(parts[0])
    except ValueError as exc:
        raise ValueError("height") from exc
    if not 100 <= height <= 250:
        raise ValueError("height")

    gender = normalize_gender(parts[1])
    if not gender:
        raise ValueError("gender")

    age = None
    if len(parts) >= 4:
        try:
            age = int(parts[2])
        except ValueError as exc:
            raise ValueError("age") from exc
        if not 1 <= age <= 120:
            raise ValueError("age")
        goal = ",".join(parts[3:]).strip()
    else:
        goal = parts[2].strip()

    if len(goal) < 2:
        raise ValueError("goal")

    return height, gender, age, goal


_PROFILE_ROW_KEYS = (
    "height", "gender", "age", "goal", "current_weight",
    "show_height", "show_gender", "show_age", "show_weight", "show_goal",
)


def _coerce_profile_dict(profile_row) -> dict | None:
    """Normalize DB row / legacy tuple into a profile dict."""
    if not profile_row:
        return None
    if isinstance(profile_row, dict):
        return profile_row
    try:
        return dict(zip(_PROFILE_ROW_KEYS, profile_row))
    except TypeError:
        return None


def profile_is_filled(profile_row) -> bool:
    profile_row = _coerce_profile_dict(profile_row)
    if not profile_row:
        return False
    height = profile_row.get("height")
    gender = profile_row.get("gender")
    goal = profile_row.get("goal")
    return bool(height and normalize_gender(gender) and goal)


def migrate_profile_gender_values():
    """Normalize old stored profile genders to male/female."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT user_id, gender FROM users WHERE gender IS NOT NULL")
    rows = cur.fetchall()
    changed = 0

    for user_id, gender in rows:
        normalized = normalize_gender(gender)
        if normalized and gender != normalized:
            cur.execute(
                "UPDATE users SET gender=? WHERE user_id=?",
                (normalized, user_id)
            )
            changed += 1

    if changed:
        db.commit()
    db.close()
    return changed


def toggle_user_language(user_id: int) -> str:
    current = get_user_language(user_id)
    next_lang = "en" if current == "uk" else "uk"
    set_user_language(user_id, next_lang)
    return next_lang


def style_block(title: str, body: str, icon: str = "✨") -> str:
    safe_title = html.escape(title)
    safe_body = html.escape(body.strip())
    return (
        f"{icon} <b>{safe_title}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{safe_body}"
    )


def build_start_text(lang: str) -> str:
    menu_body = t_pair(
        lang,
        "/start — показати команди\n"
        "/profile — профіль\n"
        "/edit_profile — змінити профіль\n"
        "/profile_visibility — що показувати в профілі\n"
        "/workout — записати тренування\n"
        "/today — сьогодні\n"
        "/stats — статистика\n"
        "/weight — вага\n"
        "/reset — видалити все\n"
        "/weight_stats — статистика ваги\n"
        "/suggest — запропонувати тренування\n"
        "/set_goal — встановити мету на тиждень\n"
        "/change_language — змінити мову\n"
        "/reminders — нагадування\n"
        "/goal — показати мету на тиждень\n"
        "/daily — щоденне завдання\n"
        "/wallet — баланс монет\n"
        "/shop — магазин\n"
        "/level — рівень і ранг\n"
        "/chart — графіки прогресу\n"
        "/motivate — мотивація\n"
        "/tip — корисна порада\n"
        "/challenge — челендж дня\n"
        "/export — експорт даних\n"
        "/import — імпорт даних\n"
        "/use — використати предмет",
        "/start — show commands\n"
        "/profile — profile\n"
        "/edit_profile — edit profile\n"
        "/profile_visibility — profile fields visibility\n"
        "/workout — log workout\n"
        "/today — today\n"
        "/stats — statistics\n"
        "/weight — weight\n"
        "/reset — delete all data\n"
        "/weight_stats — weight statistics\n"
        "/suggest — suggest workout\n"
        "/set_goal — set weekly goal\n"
        "/change_language — change language\n"
        "/reminders — reminders\n"
        "/goal — show weekly goal\n"
        "/daily — daily task\n"
        "/wallet — coin balance\n"
        "/shop — shop\n"
        "/level — level & rank\n"
        "/chart — progress charts\n"
        "/motivate — motivation\n"
        "/tip — health tip\n"
        "/challenge — challenge of the day\n"
        "/export — export data\n"
        "/import — import data\n"
        "/use — use item"
    )
    return style_block(
        "SportBot",
        menu_body,
        icon="🏁"
    )


def generate_workout(goal: str, lang: str) -> str:
    goal_lower = goal.lower()

    if lang == "en":
        if any(keyword in goal_lower for keyword in ("gain", "mass", "muscle")):
            return random.choice([
                "💪 Muscle gain workout:\n"
                "• Push ups 4x15–20\n"
                "• Squats 4x25\n"
                "• Lunges 3x12\n"
                "• Plank 3x40 sec",
                "💪 Muscle gain workout:\n"
                "• Narrow push ups 4x12\n"
                "• Pause squats 4x20\n"
                "• Glute bridge 3x20\n"
                "• Plank 3x45 sec"
            ])
        elif any(keyword in goal_lower for keyword in ("lose", "fat", "diet", "slim")):
            return random.choice([
                "🔥 Fat burning workout:\n"
                "• Running 20–30 min\n"
                "• Burpees 3x12\n"
                "• Jumps 3x40 sec\n"
                "• Plank 3x30 sec",
                "🔥 Fat burning workout:\n"
                "• Jumping Jacks 4x40 sec\n"
                "• Mountain climbers 3x30 sec\n"
                "• Squats 3x25\n"
                "• Plank 3x35 sec"
            ])
        else:
            return random.choice([
                "🏋️ General workout:\n"
                "• Push ups 3x15\n"
                "• Squats 3x20\n"
                "• Plank 3x30 sec",
                "🏋️ General workout:\n"
                "• Push ups 3x12\n"
                "• Lunges 3x12\n"
                "• Bicycle 3x30 sec\n"
                "• Plank 3x40 sec"
            ])
    else:
        if "наб" in goal_lower:
            return random.choice([
                "💪 Тренування на набір маси:\n"
                "• Відтискування 4x15–20\n"
                "• Присідання 4x25\n"
                "• Випади 3x12\n"
                "• Планка 3x40 сек",
                "💪 Тренування на набір маси:\n"
                "• Відтискування вузькі 4x12\n"
                "• Присідання з паузою 4x20\n"
                "• Ягодичний міст 3x20\n"
                "• Планка 3x45 сек"
            ])
        elif "схуд" in goal_lower or "дієт" in goal_lower:
            return random.choice([
                "🔥 Тренування на спалювання жиру:\n"
                "• Біг 20–30 хвилин\n"
                "• Бьорпі 3x12\n"
                "• Стрибки 3x40 сек\n"
                "• Планка 3x30 сек",
                "🔥 Тренування на спалювання жиру:\n"
                "• Jumping Jack 4x40 сек\n"
                "• Альпініст 3x30 сек\n"
                "• Присідання 3x25\n"
                "• Планка 3x35 сек"
            ])
        else:
            return random.choice([
                "🏋️ Універсальне тренування:\n"
                "• Відтискування 3x15\n"
                "• Присідання 3x20\n"
                "• Планка 3x30 сек",
                "🏋️ Універсальне тренування:\n"
                "• Відтискування 3x12\n"
                "• Випади 3x12\n"
                "• Велосипед 3x30 сек\n"
                "• Планка 3x40 сек"
            ])





async def check_missed_days():
    db = get_db()
    cur = db.cursor()
    db = get_db()
    cur = db.cursor()

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Вибираємо користувачів з включеними нагадуваннями, які мають тренування за останні 7 днів
    cur.execute("""
                SELECT DISTINCT u.user_id
                FROM users u
                WHERE u.reminders_enabled = 1
                  AND u.user_id IN (
                    SELECT DISTINCT user_id FROM workouts 
                    WHERE date >= ?
                  )
                """, ((datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),))

    users = [row[0] for row in cur.fetchall()]

    for uid in users:
        # Використовуємо окремий курсор для уникнення конфліктів
        check_cur = db.cursor()
        check_cur.execute("SELECT 1 FROM workouts WHERE user_id=? AND date=?", (uid, yesterday))
        if not check_cur.fetchone():
            lang = get_user_language(uid)
            messages = get_missed_day_messages(lang)
            await bot.send_message(uid, random.choice(messages))
        check_cur.close()

    db.close()
    log.info("Check of missed days completed.")


def get_missed_day_messages(lang: str):
    return [
        t_pair(
            lang,
            "💪 Вчора пропустив тренування?\nСьогодні новий день! 🔥 /suggest",
            "💪 Missed a workout yesterday?\nToday is a new day! 🔥 /suggest"
        ),
        t_pair(
            lang,
            "😴 Відпочив вчора? Повертайся до строю! /today",
            "😴 Rested yesterday? Back to action! /today"
        ),
        t_pair(
            lang,
            "⚡ Швидкий тест: /suggest → ✅ Виконав!",
            "⚡ Quick test: /suggest → ✅ Done!"
        )
    ]


# ---------- DB ----------
# get_db() теперь импортируется из db_improved и использует глобальное соединение
# Оставляем здесь для совместимости с остальным кодом


def init_db():
    db = get_db()
    cur = db.cursor()

    # Создаем users БЕЗ reminders_enabled сначала
    cur.execute("""
                CREATE TABLE IF NOT EXISTS users
                (
                    user_id
                    INTEGER
                    PRIMARY
                    KEY,
                    height
                    INTEGER,
                    gender
                    TEXT,
                    age
                    INTEGER,
                    goal
                    TEXT,
                    weekly_goal
                    INTEGER,
                    current_weight
                    REAL
                    DEFAULT
                    0
                )
                """)

    # ПРОВЕРЯЕМ и добавляем колонку ТОЛЬКО если её нет
    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]

    if 'reminders_enabled' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN reminders_enabled INTEGER DEFAULT 1")
    if 'language' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'uk'")
    if 'age' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN age INTEGER")
    if 'coin_balance' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN coin_balance INTEGER DEFAULT 0")
    for column_name in (
        'show_height',
        'show_gender',
        'show_age',
        'show_weight',
        'show_goal',
        'streak_days',
        'last_workout_date',
        'xp',
        'level',
    ):
        if column_name not in columns:
            default = {
                'streak_days':        'INTEGER DEFAULT 0',
                'last_workout_date':  'TEXT',
                'xp':                 'INTEGER DEFAULT 0',
                'level':              'INTEGER DEFAULT 1',
            }.get(column_name, 'INTEGER DEFAULT 1')
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {default}")

    # Migrate databases created before soft-delete support was introduced.
    ensure_users_deleted_at(cur)

    cur.execute("""
                CREATE TABLE IF NOT EXISTS weights
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    user_id
                    INTEGER,
                    weight
                    REAL,
                    date
                    TEXT
                )
                """)

    cur.execute("""
                CREATE TABLE IF NOT EXISTS workouts
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    user_id
                    INTEGER,
                    text
                    TEXT,
                    date
                    TEXT,
                    is_challenge
                    INTEGER
                    DEFAULT
                    0
                )
                """)

    # Add is_challenge column if it doesn't exist
    cur.execute("PRAGMA table_info(workouts)")
    columns = [row[1] for row in cur.fetchall()]
    if 'is_challenge' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN is_challenge INTEGER DEFAULT 0")
    if 'recorded_at' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN recorded_at TEXT")
    cur.execute("""CREATE TABLE IF NOT EXISTS workout_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        date TEXT NOT NULL, note TEXT)""")
    cur.execute("PRAGMA table_info(workout_sessions)")
    session_columns = [row[1] for row in cur.fetchall()]
    if 'recorded_at' not in session_columns:
        cur.execute("ALTER TABLE workout_sessions ADD COLUMN recorded_at TEXT")
    cur.execute("PRAGMA table_info(workouts)")
    columns = [row[1] for row in cur.fetchall()]
    if 'session_id' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN session_id INTEGER")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_workouts_session_id ON workouts(session_id)")

    cur.execute("""
                CREATE TABLE IF NOT EXISTS user_items
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    user_id
                    INTEGER,
                    item_id
                    TEXT,
                    purchased_at
                    TEXT
                )
                """)

    cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_tasks
                (
                    user_id
                    INTEGER,
                    date
                    TEXT,
                    task_id
                    TEXT,
                    progress
                    INTEGER
                    DEFAULT
                    0,
                    completed
                    INTEGER
                    DEFAULT
                    0,
                    PRIMARY KEY
                    (user_id, date)
                )
                """)

    cur.execute("""
                CREATE TABLE IF NOT EXISTS coin_rewards
                (
                    user_id
                    INTEGER,
                    date
                    TEXT,
                    source
                    TEXT,
                    amount
                    INTEGER,
                    created_at
                    TEXT,
                    PRIMARY KEY
                    (user_id, date, source)
                )
                """)
    cur.execute("PRAGMA table_info(coin_rewards)")
    coin_columns = [row[1] for row in cur.fetchall()]
    if "idem_key" not in coin_columns:
        cur.execute("ALTER TABLE coin_rewards ADD COLUMN idem_key TEXT")
    cur.execute("""
                CREATE TABLE IF NOT EXISTS reward_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, source, action_key)
                )
                """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    achievement_key TEXT NOT NULL,
                    awarded_at TEXT NOT NULL,
                    UNIQUE(user_id, achievement_key)
                )
                """)

    db.commit()
    db.close()


# ---------- UTILS ----------
def set_user_state(user_id: int, state: str):
    _manual_state_cache[user_id] = state


def get_user_state(user_id: int):
    return _manual_state_cache.get(user_id)


def clear_user_state(user_id: int):
    _manual_state_cache.pop(user_id, None)


@lru_cache(maxsize=2048)
def _cached_language(user_id: int) -> str:
    """Cached language lookup; invalidate on language change."""
    row = fetch_one("SELECT language FROM users WHERE user_id=? AND deleted_at IS NULL", (user_id,))
    return row[0] if row and row[0] in ("uk", "en") else "uk"


def get_user_language(user_id: int) -> str:
    """Return the user's language with a bounded LRU cache."""
    return _cached_language(user_id)


def invalidate_language_cache(user_id: int | None = None) -> None:
    """Invalidate cached language values after a language update."""
    _cached_language.cache_clear()


def set_user_language(user_id: int, lang: str):
    """Set the user's language and invalidate the language cache."""
    if lang not in ("uk", "en"):
        lang = "uk"
    execute_query(
        """
        INSERT INTO users (user_id, language)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET language=excluded.language, deleted_at=NULL
        """,
        (user_id, lang)
    )
    invalidate_language_cache(user_id)


def get_user_profile(user_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT height, gender, age, goal, current_weight,
               show_height, show_gender, show_age, show_weight, show_goal
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )
    row = cur.fetchone()
    db.close()

    if not row:
        return None

    return {
        "height": row[0],
        "gender": row[1],
        "age": row[2],
        "goal": row[3],
        "current_weight": row[4],
        "show_height": bool(row[5]) if row[5] is not None else True,
        "show_gender": bool(row[6]) if row[6] is not None else True,
        "show_age": bool(row[7]) if row[7] is not None else True,
        "show_weight": bool(row[8]) if row[8] is not None else True,
        "show_goal": bool(row[9]) if row[9] is not None else True,
    }


def is_profile_complete(profile) -> bool:
    if not profile:
        return False
    return bool(
        profile.get("height") and
        profile.get("gender") and
        profile.get("goal")
    )


def ensure_user(user_id: int):
    """Алиас для ensure_user_exists() из profile_visibility модуля"""
    ensure_user_exists(user_id)


def get_coin_balance(user_id: int) -> int:
    row = fetch_one(
        """
        INSERT INTO users (user_id) VALUES (?)
        ON CONFLICT(user_id) DO UPDATE SET user_id=excluded.user_id
        RETURNING COALESCE(coin_balance, 0)
        """,
        (user_id,)
    )
    return int(row[0] or 0) if row else 0


def add_coins(user_id: int, amount: int) -> int:
    row = fetch_one(
        """
        INSERT INTO users (user_id, coin_balance)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE
        SET coin_balance = COALESCE(users.coin_balance, 0) + ?
            RETURNING COALESCE(coin_balance, 0)
        """,
        (user_id, amount)
    )
    return int(row[0] or 0) if row else 0


def claim_daily_coin_reward(user_id: int, source: str, amount: int):
    ensure_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            """
            INSERT OR IGNORE INTO coin_rewards
                (user_id, date, source, amount, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, today, source, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        awarded = cur.rowcount == 1
        if awarded:
            cur.execute(
                "UPDATE users SET coin_balance = COALESCE(coin_balance, 0) + ? WHERE user_id=?",
                (amount, user_id)
            )
        cur.execute("SELECT coin_balance FROM users WHERE user_id=?", (user_id,))
        balance = int((cur.fetchone() or [0])[0] or 0)
        db.commit()
        return awarded, balance
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def spend_coins(user_id: int, amount: int):
    ensure_user(user_id)
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            """
            UPDATE users
            SET coin_balance = COALESCE(coin_balance, 0) - ?
            WHERE user_id=? AND COALESCE(coin_balance, 0) >= ?
            """,
            (amount, user_id, amount)
        )
        paid = cur.rowcount == 1
        cur.execute("SELECT coin_balance FROM users WHERE user_id=?", (user_id,))
        balance = int((cur.fetchone() or [0])[0] or 0)
        db.commit()
        return paid, balance
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def buy_shop_item(user_id: int, item_id: str, cost: int):
    """
    Безопасная функция покупки товара с использованием транзакции
    Возвращает (success: bool, balance: int, status: str)
    """
    item = SHOP_ITEMS.get(item_id, {})
    max_count = item.get("max_count")

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (user_id,))
        #ddsfdsfsdf
        if max_count:
            cur.execute(
                "SELECT COUNT(*) FROM user_items WHERE user_id=? AND item_id=?",
                (user_id, item_id)
            )
            if (cur.fetchone() or [0])[0] >= max_count:
                cur.execute("SELECT COALESCE(coin_balance, 0) FROM users WHERE user_id=?", (user_id,))
                balance = int((cur.fetchone() or [0])[0] or 0)
                db.rollback()
                return False, balance, "limit_exceeded"

        cur.execute(
            """
            UPDATE users
            SET coin_balance = COALESCE(coin_balance, 0) - ?
                WHERE user_id=? AND COALESCE(coin_balance, 0) >= ?
            RETURNING COALESCE(coin_balance, 0)
            """,
            (cost, user_id, cost)
        )
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT COALESCE(coin_balance, 0) FROM users WHERE user_id=?", (user_id,))
            balance = int((cur.fetchone() or [0])[0] or 0)
            db.rollback()
            return False, balance, "insufficient_coins"

        balance = int(row[0] or 0)
        cur.execute(
            "INSERT INTO user_items (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
            (user_id, item_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        return True, balance, "success"
    except Exception as exc:
        db.rollback()
        log.error("buy_shop_item failed: %s", exc)
        return False, get_coin_balance(user_id), "error"
    finally:
        db.close()


def add_user_item(user_id: int, item_id: str):
    execute_query(
        "INSERT INTO user_items (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
        (user_id, item_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )


def get_user_items(user_id: int) -> dict:
    rows = fetch_all(
        "SELECT item_id, COUNT(*) FROM user_items WHERE user_id=? GROUP BY item_id",
        (user_id,)
    )
    return {item_id: count for item_id, count in rows} if rows else {}


def format_coin_reward(lang: str, amount: int, balance: int) -> str:
    return t_pair(
        lang,
        f"\n\n🪙 +{amount} монет\nБаланс: {balance}",
        f"\n\n🪙 +{amount} coins\nBalance: {balance}"
    )


def get_premium_workout(lang: str) -> str:
    workouts = [
        (
            "⚡ Преміум тренування:\n"
            "• Розминка 5 хв\n"
            "• Присідання 4x20\n"
            "• Відтискування 4x12\n"
            "• Альпініст 3x40 сек\n"
            "• Планка 3x45 сек",
            "⚡ Premium workout:\n"
            "• Warm-up 5 min\n"
            "• Squats 4x20\n"
            "• Push ups 4x12\n"
            "• Mountain climbers 3x40 sec\n"
            "• Plank 3x45 sec",
        ),
        (
            "⚡ Преміум тренування:\n"
            "• Швидкий крок 10 хв\n"
            "• Випади 4x12\n"
            "• Скручування 3x20\n"
            "• Бьорпі 3x10\n"
            "• Розтяжка 5 хв",
            "⚡ Premium workout:\n"
            "• Fast walk 10 min\n"
            "• Lunges 4x12\n"
            "• Sit ups 3x20\n"
            "• Burpees 3x10\n"
            "• Stretch 5 min",
        ),
    ]
    return get_localized_choice(lang, workouts)


def choose_daily_task_id(user_id: int, date_text: str) -> str:
    task_ids = list(DAILY_TASKS.keys())
    rng = random.Random(f"{user_id}:{date_text}")
    return rng.choice(task_ids)


def get_or_create_daily_task(user_id: int):
    ensure_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT task_id, progress, completed FROM daily_tasks WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = cur.fetchone()

    if not row:
        task_id = choose_daily_task_id(user_id, today)
        cur.execute(
            "INSERT INTO daily_tasks (user_id, date, task_id, progress, completed) VALUES (?, ?, ?, 0, 0)",
            (user_id, today, task_id)
        )
        db.commit()
        row = (task_id, 0, 0)

    db.close()
    task_id, progress, completed = row
    task = DAILY_TASKS.get(task_id, DAILY_TASKS[DEFAULT_DAILY_TASK_ID])
    return today, task_id, task, int(progress or 0), bool(completed)


def build_progress_bar(progress: int, target: int) -> tuple[str, int]:
    percent = min(int(progress / target * 100), 100) if target else 0
    filled = min(percent // 10, 10)
    return "█" * filled + "░" * (10 - filled), percent


def build_daily_task_text(lang: str, task: dict, progress: int, completed: bool) -> str:
    target = task["target"]
    progress = min(progress, target)
    bar, percent = build_progress_bar(progress, target)
    unit = t_pair(lang, task["uk_unit"], task["en_unit"])
    status = t_pair(lang, "✅ Завершено", "✅ Completed") if completed else t_pair(lang, "⏳ В процесі", "⏳ In progress")

    return t_pair(
        lang,
        f"🎯 Завдання: {task['uk_name']}\n"
        f"📈 Прогрес: {progress}/{target} {unit}\n"
        f"{bar} {percent}%\n"
        f"🪙 Нагорода: {task['reward']} монет\n"
        f"📌 {task['uk_hint']}\n\n"
        f"{status}",
        f"🎯 Task: {task['en_name']}\n"
        f"📈 Progress: {progress}/{target} {unit}\n"
        f"{bar} {percent}%\n"
        f"🪙 Reward: {task['reward']} coins\n"
        f"📌 {task['en_hint']}\n\n"
        f"{status}"
    )


def build_daily_today_text(lang: str, task: dict, progress: int, completed: bool) -> str:
    target = task["target"]
    progress = min(progress, target)
    unit = t_pair(lang, task["uk_unit"], task["en_unit"])
    name = t_pair(lang, task["uk_name"], task["en_name"])
    daily_label = t_pair(lang, "Щоденне", "Daily")
    reward_label = t_pair(lang, "монет", "coins")
    status = t_pair(lang, "виконано", "completed") if completed else f"{progress}/{target} {unit}"
    return t_pair(
        lang,
        f"🎮 {daily_label}: {name} — {status} · нагорода {task['reward']} {reward_label}",
        f"🎮 {daily_label}: {name} — {status} · reward {task['reward']} {reward_label}"
    )


# ── Streak XP multiplier helper ────────────────────────────────────

def get_streak_xp_multiplier(streak_days: int) -> float:
    """Return the XP multiplier from the user's current streak."""
    mult = 1.0
    for threshold in sorted(STREAK_XP_MULTIPLIERS):
        if streak_days >= threshold:
            mult = STREAK_XP_MULTIPLIERS[threshold]
        else:
            break
    return min(mult, MAX_MULTIPLIER)


# ── XP / Streak helpers ─────────────────────────────────────────────

def award_xp_and_streak(uid: int, workout_date: str, xp_amount: int) -> dict:
    """Award XP and update streak. XP is pure account progress; coins stay separate.
    Returns {xp, level, leveled_up, streak_days, streak_bonus_coins, streak_bonus_xp,
    new_level_unlock, streak_multiplier}."""
    from utils.streak import update_streak as _update_streak

    streak_result = _update_streak(uid, workout_date, earned_xp=xp_amount)
    streak_days = streak_result["streak_days"]

    # Apply streak XP multiplier
    multiplier = get_streak_xp_multiplier(streak_days)
    xp_with_mult = round(xp_amount * multiplier)

    # XP (progress only — no coins mixed in)
    xp_result = add_xp_to_user(uid, xp_with_mult)

    # Streak milestone bonus (coins + bonus XP, awarded once)
    streak_bonus_coins = 0
    streak_bonus_xp   = 0
    for threshold, (coins, xp_bonus) in STREAK_BONUSES.items():
        if streak_result.get("is_new") and streak_days == threshold:
            streak_bonus_coins = coins
            streak_bonus_xp   = xp_bonus
            break

    all_coins  = streak_bonus_coins
    bonus_xp_result = xp_result
    if streak_bonus_xp:
        bonus_xp_result = add_xp_to_user(uid, streak_bonus_xp)
        xp_result = bonus_xp_result  # latest state after bonus

    if all_coins:
        execute_query(
            "UPDATE users SET coin_balance=COALESCE(coin_balance,0)+? WHERE user_id=?",
            (all_coins, uid)
        )

    # Level unlock announcement
    new_level  = xp_result.get("level", 1)
    lvl_unlock = None
    if new_level in LEVEL_UNLOCKS:
        lvl_unlock = LEVEL_UNLOCKS[new_level]

    sync_info = {
        "user_id": uid,
        **xp_result,
        **streak_result,
        "base_xp_awarded": xp_with_mult,
        "total_xp_awarded": xp_with_mult + streak_bonus_xp,
        "streak_bonus_coins": streak_bonus_coins,
        "streak_bonus_xp":    streak_bonus_xp,
        "new_level_unlock":    lvl_unlock,
        "streak_multiplier":   multiplier,
    }
    return sync_info


def collect_new_achievements(user_id: int) -> list[dict]:
    """Check achievements once after a completed rewarding action."""
    try:
        return check_and_award(user_id, get_user_stats(user_id))
    except Exception as exc:
        log.warning("achievement check skipped user_id=%s: %s", user_id, exc)
        return []


def reward_summary(
    lang: str,
    action_uk: str,
    action_en: str,
    *,
    xp: int = 0,
    coins: int = 0,
    balance: int | None = None,
    sync_info: dict | None = None,
    achievements: list[dict] | None = None,
) -> str:
    """Build one localized reward message from persisted result values."""
    sync_info = sync_info or {}
    xp_info = get_user_xp_level(sync_info.get("user_id", 0)) if sync_info.get("user_id") else None
    level = sync_info.get("level")
    xp_total = sync_info.get("xp")
    level_up = bool(sync_info.get("leveled_up"))
    if xp_info:
        level_up = level_up or int(xp_info.get("level", 1)) > int(level or 1)
        level = xp_info.get("level", level)
        xp_total = xp_info.get("xp", xp_total)
    if level is not None:
        xp_next = total_xp_for_level(level) + (xp_for_next_level(level) or 0)
    else:
        xp_next = None
    return build_reward_summary(
        lang,
        action_uk=action_uk,
        action_en=action_en,
        xp=xp,
        coins=coins,
        balance=balance,
        streak_days=sync_info.get("streak_days"),
        level=level,
        level_up=level_up,
        xp_total=xp_total,
        xp_next=xp_next,
        achievements=achievements,
    )


def format_level_block(lang: str, xp_info: dict, streak_days: int = 0) -> str:
    """Build a progress-block text for XP / level display."""
    lvl   = xp_info.get("level", 1)
    xp    = xp_info.get("xp", 0)
    rank_uk, rank_en = get_rank(lvl)
    prev_total  = total_xp_for_level(lvl)
    cur_xp, xp_needed = get_progress_in_level(lvl, xp)
    pct = int(cur_xp / xp_needed * 100) if xp_needed else 100
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

    lines = [
        f"⭐ {t_pair(lang, 'Рівень', 'Level')}: {lvl}",
        f"🏅 {t_pair(lang, 'Ранг', 'Rank')}: {rank_uk if lang=='uk' else rank_en}",
        f"📊 XP: {xp} / {prev_total + xp_needed if xp_needed else xp}",
        f"{bar} {pct}%",
    ]
    if streak_days:
        lines.append(f"🔥 {t_pair(lang, 'Серія', 'Streak')}: {streak_days} {t_pair(lang, 'днів', 'days')}")
    return "\n".join(lines)


# ── Chart keyboards ─────────────────────────────────────────────────

def chart_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⚖️ Weight",       callback_data="chart_weight"),
         InlineKeyboardButton(text="🏋️ Workouts",    callback_data="chart_workouts")],
        [InlineKeyboardButton(text="🔥 Streak",       callback_data="chart_streak"),
         InlineKeyboardButton(text="📦 Volume",       callback_data="chart_volume")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _chart_fetch_all(query: str, params):
    """Thin adapter: chart layer calls this instead of db_improved.fetch_all directly."""
    return fetch_all(query, params)


def update_daily_progress(user_id: int):
    today, task_id, task, progress, completed = get_or_create_daily_task(user_id)

    if completed:
        return task, progress, True, False, get_coin_balance(user_id)

    new_progress = min(progress + task["step"], task["target"])
    completed_now = new_progress >= task["target"]

    balance = get_coin_balance(user_id)
    rewarded = False
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            """
            UPDATE daily_tasks
            SET progress=?, completed=?
            WHERE user_id=? AND date=? AND completed=0
            """,
            (new_progress, 1 if completed_now else 0, user_id, today)
        )
        changed = cur.rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if not changed:
        return task, progress, True, False, get_coin_balance(user_id)

    # Coins and XP are settled together by settle_action_rewards after the
    # task transition commits successfully.
    return task, new_progress, completed_now, False, balance


def parse_activity_and_duration(text: str):
    raw = text.lower()
    m = re.search(r'(\d+)\s*(хв|хвилин|мин|min)', raw)
    duration = int(m.group(1)) if m else 30

    activity_map = {
        "біг": "running",
        "run": "running",
        "ходьб": "walking",
        "прогулянк": "walking",
        "вело": "bicycling",
        "велосипед": "bicycling",
        "плав": "swimming",
        "відтиск": "push ups",
        "push": "push ups",
        "присідан": "squats",
        "squat": "squats",
        "планк": "plank",
        "випад": "lunges",
        "lunge": "lunges",
        "бурпі": "burpees",
        "бьорпі": "burpees",
        "burpee": "burpees",
        "jumping jack": "jumping jacks",
        "стрибк": "jumping jacks",
        "альпініст": "mountain climbers",
        "mountain": "mountain climbers",
        "скручуван": "sit ups",
        "прес": "sit ups"
    }

    for key, api_activity in activity_map.items():
        if key in raw:
            return api_activity, duration

    return "workout", duration


def calc_calories(text: str) -> int:  # DEPRECATED — use calc_calories_async instead
    """Sync estimate only.

    .. deprecated::
        Always calls :func:`calc_calories_async` from an async context.
        This wrapper is kept only for backward-compatible imports that do
        not yet support ``await``.  It never blocks the event loop.
    """
    log.warning("calc_calories (sync stub) called — switch to calc_calories_async")
    raise RuntimeError(
        "calc_calories is deprecated; call asyncio.run(calc_calories_async(text)) "
        "from an async context, or use services/calories_service directly."
    )


async def calc_calories_async(text: str) -> int:
    cache_key = text.strip().lower()
    if cache_key in calories_cache:
        return calories_cache[cache_key]

    activity, duration = parse_activity_and_duration(text)

    # Use the shared HTTP session (one TCP/TLS handshake per process; per-request timeout still applies).
    session = get_http_session()
    timeout = aiohttp.ClientTimeout(total=2.5, connect=1.0, sock_read=1.5)
    try:
        async with session.get(
            "https://api.api-ninjas.com/v1/caloriesburned",
            params={"activity": activity, "duration": duration},
            headers={"X-Api-Key": API_NINJAS_KEY},
            timeout=timeout,
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list) and data:
                    total = data[0].get("total_calories")
                    if total is not None:
                        value = int(round(float(total)))
                        calories_cache[cache_key] = value
                        return value
    except Exception:
        # fallback below
        pass

    # Fallback estimate when API is unavailable or activity wasn't matched
    text_lower = cache_key
    m = re.search(r'(\d+)\s*(хв|хвилин|мин|min)', text_lower)
    if m:
        value = int(m.group(1)) * 8  # rough estimate
        calories_cache[cache_key] = value
        return value

    if 'x' in text_lower or 'х' in text_lower:
        calories_cache[cache_key] = 30
        return 30

    calories_cache[cache_key] = 0
    return 0


def calculate_streak(dates):
    """Backward-compatible wrapper around the shared streak calculation."""
    return _calculate_streak(None, dates)


# ---------- RESET ----------
@dp.message(Command("reset"))
async def reset_profile(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(
        t_pair(lang, "Видалити профіль і всі дані?", "Delete profile and all data?"),
        reply_markup=reset_keyboard(lang)
    )


@dp.callback_query(lambda c: c.data == "reset_yes")
async def reset_yes(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    
    # Используем новую безопасную функцию
    success = clear_user_all_data(uid)
    
    if success:
        await callback.message.edit_text(
            t_pair(lang, "✅ Профіль повністю видалено. Дані очищені.", 
                     "✅ Profile completely deleted. All data cleared.")
        )
    else:
        await callback.message.edit_text(
            t_pair(lang, "❌ Помилка при видаленні. Спробуйте пізніше.", 
                     "❌ Error during deletion. Try again later.")
        )


@dp.callback_query(lambda c: c.data == "reset_no")
async def reset_no(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t_pair(lang, "Скасування.", "Canceled."))


# ── EXPORT / IMPORT ----------
def get_user_export_data(user_id: int) -> dict:
    """Collect all user data for export."""
    import re
    from collections import defaultdict
    
    db = get_db()
    cur = db.cursor()
    # Keep export compatible with databases created before the reward ledger.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reward_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            action_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, source, action_key)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            awarded_at TEXT NOT NULL,
            UNIQUE(user_id, achievement_key)
        )
    """)
    cur.execute("PRAGMA table_info(coin_rewards)")
    if not any(row[1] == "idem_key" for row in cur.fetchall()):
        cur.execute("ALTER TABLE coin_rewards ADD COLUMN idem_key TEXT")
    
    # Profile data
    cur.execute(
        """SELECT height, gender, age, goal, current_weight, weekly_goal,
                  streak_days, xp, level, coin_balance, language,
                  show_height, show_gender, show_age, show_weight, show_goal
           FROM users WHERE user_id=?""",
        (user_id,)
    )
    profile = cur.fetchone()
    
    # Workouts
    cur.execute(
        "SELECT text, date, is_challenge, session_id, recorded_at FROM workouts WHERE user_id=? ORDER BY date",
        (user_id,)
    )
    workouts = cur.fetchall()
    cur.execute("SELECT id, date, note, recorded_at FROM workout_sessions WHERE user_id=? ORDER BY id", (user_id,))
    workout_sessions = cur.fetchall()
    
    # Weights
    cur.execute(
        "SELECT weight, date FROM weights WHERE user_id=? ORDER BY date",
        (user_id,)
    )
    weights = cur.fetchall()
    
    # Daily tasks
    cur.execute(
        "SELECT date, task_id, progress, completed FROM daily_tasks WHERE user_id=?",
        (user_id,)
    )
    daily_tasks = cur.fetchall()
    
    # Coin rewards
    cur.execute(
        "SELECT date, source, amount, idem_key, created_at FROM coin_rewards WHERE user_id=?",
        (user_id,)
    )
    coin_rewards = cur.fetchall()

    cur.execute(
        "SELECT source, action_key, created_at FROM reward_events WHERE user_id=? ORDER BY id",
        (user_id,)
    )
    reward_events = cur.fetchall()

    cur.execute(
        "SELECT achievement_key, awarded_at FROM achievements WHERE user_id=? ORDER BY id",
        (user_id,)
    )
    achievements = cur.fetchall()
    
    # User items
    cur.execute(
        "SELECT item_id, purchased_at FROM user_items WHERE user_id=?",
        (user_id,)
    )
    user_items = cur.fetchall()
    
    db.close()
    
    # Calculate chart statistics
    # Weight statistics
    weight_stats = []
    if weights:
        weight_values = [w[0] for w in weights]
        weight_stats = {
            "min": min(weight_values),
            "max": max(weight_values),
            "current": weight_values[-1],
            "start": weight_values[0],
            "change": round(weight_values[-1] - weight_values[0], 2),
            "entries_count": len(weights),
            "first_date": weights[0][1],
            "last_date": weights[-1][1],
        }
    
    # Workout statistics
    workout_dates = [w[1] for w in workouts]
    workout_dates_set = set(workout_dates)
    total_workouts = len(workouts)
    unique_days = len(workout_dates_set)
    
    # Calculate streak stats
    streak_stats = {"current_streak": 0, "longest_streak": 0, "streak_history": []}
    if workout_dates_set:
        from datetime import datetime as dt, timedelta
        sorted_dates = sorted(workout_dates_set)
        
        # Current streak
        today = dt.now().strftime("%Y-%m-%d")
        current_streak = 0
        check_date = dt.now()
        while check_date.strftime("%Y-%m-%d") in workout_dates_set:
            current_streak += 1
            check_date -= timedelta(days=1)
        streak_stats["current_streak"] = current_streak
        
        # Longest streak
        if sorted_dates:
            longest = 1
            current = 1
            streak_history = [(sorted_dates[0], 1)]
            for i in range(1, len(sorted_dates)):
                prev = dt.strptime(sorted_dates[i-1], "%Y-%m-%d")
                curr = dt.strptime(sorted_dates[i], "%Y-%m-%d")
                if (curr - prev).days == 1:
                    current += 1
                    if current > longest:
                        longest = current
                        streak_history.append((sorted_dates[i], current))
                else:
                    current = 1
                    streak_history.append((sorted_dates[i], 1))
            streak_stats["longest_streak"] = longest
            streak_stats["streak_history"] = streak_history
    
    # Volume statistics (extract numbers from workout text)
    volume_by_date = defaultdict(int)
    for w_text, w_date, _, _, _ in workouts:
        numbers = re.findall(r'(\d+)', w_text)
        for num in numbers:
            volume_by_date[w_date] += int(num)
    
    volume_stats = {
        "by_date": dict(sorted(volume_by_date.items())),
        "total": sum(volume_by_date.values()),
        "avg_per_workout": round(sum(volume_by_date.values()) / max(len(workouts), 1), 2),
    }
    
    # Workout frequency by date
    workout_count_by_date = defaultdict(int)
    for _, w_date, _, _, _ in workouts:
        workout_count_by_date[w_date] += 1
    
    workout_freq_stats = {
        "by_date": dict(sorted(workout_count_by_date.items())),
        "total_workouts": total_workouts,
        "unique_days": unique_days,
    }
    
    data = {
        "version": "3.0",  # Preserved legacy version field
        "backup_version": 3,
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": {
            "height": profile[0] if profile else None,
            "gender": profile[1] if profile else None,
            "age": profile[2] if profile else None,
            "goal": profile[3] if profile else None,
            "current_weight": profile[4] if profile else None,
            "weekly_goal": profile[5] if profile else None,
            "streak_days": profile[6] if profile else None,
            "xp": profile[7] if profile else None,
            "level": profile[8] if profile else None,
            "coin_balance": profile[9] if profile else None,
            "language": profile[10] if profile else None,
            "show_height": profile[11] if profile else None,
            "show_gender": profile[12] if profile else None,
            "show_age": profile[13] if profile else None,
            "show_weight": profile[14] if profile else None,
            "show_goal": profile[15] if profile else None,
        } if profile else None,
        "workout_sessions": [{"id": s[0], "date": s[1], "note": s[2], "recorded_at": s[3]} for s in workout_sessions],
        "workouts": [{"text": w[0], "date": w[1], "is_challenge": w[2], "session_id": w[3], "recorded_at": w[4]} for w in workouts],
        "weights": [{"weight": w[0], "date": w[1]} for w in weights],
        "daily_tasks": [{"date": d[0], "task_id": d[1], "progress": d[2], "completed": d[3]} for d in daily_tasks],
        "coin_rewards": [{"date": c[0], "source": c[1], "amount": c[2], "idem_key": c[3], "created_at": c[4]} for c in coin_rewards],
        "reward_events": [{"source": r[0], "action_key": r[1], "created_at": r[2]} for r in reward_events],
        "achievements": [{"achievement_key": a[0], "awarded_at": a[1]} for a in achievements],
        "user_items": [{"item_id": i[0], "purchased_at": i[1]} for i in user_items],
        # Chart statistics
        "chart_stats": {
            "weight": weight_stats,
            "streak": streak_stats,
            "volume": volume_stats,
            "workout_frequency": workout_freq_stats,
        }
    }
    # ``get_db().close()`` commits compatibility DDL on the shared DB proxy
    # without physically closing the pooled connection.
    db.close()
    return data


def _validate_backup_payload(data: dict) -> tuple[bool, int, bool, str]:
    """Validate v3 and legacy backup shapes without evaluating old rewards."""
    if not isinstance(data, dict):
        return False, 0, False, "Invalid data format"

    raw_version = data.get("backup_version", data.get("version", 1))
    try:
        version = int(float(raw_version))
    except (TypeError, ValueError):
        return False, 0, False, "Invalid backup version"
    if version < 1 or version > 3:
        return False, version, False, "Unsupported backup version"

    required = ("profile", "workouts", "weights", "daily_tasks", "coin_rewards", "user_items")
    missing = [key for key in required if key not in data]
    if missing:
        return False, version, False, f"Missing key: {missing[0]}"
    for key in required:
        if not isinstance(data[key], list) and key != "profile":
            return False, version, False, f"Invalid type for {key}"
    if data.get("profile") is not None and not isinstance(data["profile"], dict):
        return False, version, False, "Invalid profile"

    has_ledger = "reward_events" in data and "achievements" in data
    if version >= 3 and not has_ledger:
        return False, version, False, "Backup v3 requires reward ledger fields"
    if has_ledger and (not isinstance(data["reward_events"], list) or not isinstance(data["achievements"], list)):
        return False, version, False, "Invalid reward ledger"

    if "workout_sessions" in data and not isinstance(data["workout_sessions"], list):
        return False, version, has_ledger, "Invalid type for workout_sessions"
    row_lists = required[1:] + (("workout_sessions",) if "workout_sessions" in data else ()) + (("reward_events", "achievements") if has_ledger else ())
    for list_key in row_lists:
        if any(not isinstance(row, dict) for row in data[list_key]):
            return False, version, has_ledger, f"Invalid row in {list_key}"
    for row in data.get("reward_events", []):
        if not isinstance(row.get("source"), str) or not isinstance(row.get("action_key"), str):
            return False, version, has_ledger, "Invalid reward event fields"
    for row in data.get("achievements", []):
        if not isinstance(row.get("achievement_key"), str):
            return False, version, has_ledger, "Invalid achievement fields"

    return True, version, has_ledger, ""


def import_user_data(user_id: int, data: dict) -> tuple[bool, str]:
    """Import user data from export format.
    
    Supports both v1.0 (basic data) and v2.0 (with chart statistics) formats.
    Chart statistics are automatically recalculated from raw data on import.
    """
    valid, version, has_ledger, error = _validate_backup_payload(data)
    if not valid:
        return False, error
    
    db = get_db()
    cur = db.cursor()
    
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reward_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                action_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, source, action_key)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_key TEXT NOT NULL,
                awarded_at TEXT NOT NULL,
                UNIQUE(user_id, achievement_key)
            )
        """)
        cur.execute("PRAGMA table_info(coin_rewards)")
        if not any(row[1] == "idem_key" for row in cur.fetchall()):
            cur.execute("ALTER TABLE coin_rewards ADD COLUMN idem_key TEXT")
        cur.execute("PRAGMA table_info(users)")
        if not any(row[1] == "deleted_at" for row in cur.fetchall()):
            cur.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT DEFAULT NULL")
        
        # Clear existing data first
        cur.execute("DELETE FROM workouts WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM workout_sessions WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM weights WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM daily_tasks WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM coin_rewards WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM reward_events WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM achievements WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM user_items WHERE user_id=?", (user_id,))
        
        # Import profile
        profile = data.get("profile")
        if profile:
            cur.execute(
                """INSERT INTO users (user_id, height, gender, age, goal, current_weight,
                          weekly_goal, streak_days, xp, level, coin_balance, language,
                          show_height, show_gender, show_age, show_weight, show_goal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                      height=excluded.height, gender=excluded.gender, age=excluded.age,
                      goal=excluded.goal, current_weight=excluded.current_weight,
                      weekly_goal=excluded.weekly_goal, streak_days=excluded.streak_days,
                      xp=excluded.xp, level=excluded.level, coin_balance=excluded.coin_balance,
                      language=excluded.language, show_height=excluded.show_height,
                      show_gender=excluded.show_gender, show_age=excluded.show_age,
                      show_weight=excluded.show_weight, show_goal=excluded.show_goal""",
                (user_id, profile.get("height"), profile.get("gender"), profile.get("age"),
                 profile.get("goal"), profile.get("current_weight"), profile.get("weekly_goal"),
                 profile.get("streak_days"), profile.get("xp"), profile.get("level"),
                 profile.get("coin_balance"), profile.get("language"),
                 profile.get("show_height"), profile.get("show_gender"),
                 profile.get("show_age"), profile.get("show_weight"), profile.get("show_goal"))
            )

        # /reset uses a soft-delete marker.  Reactivate the account as part of
        # this same transaction so a failed import restores the old marker.
        cur.execute("UPDATE users SET deleted_at=NULL WHERE user_id=?", (user_id,))
        
        session_map = {}
        for s in data.get("workout_sessions", []):
            cur.execute("INSERT INTO workout_sessions (user_id, date, note, recorded_at) VALUES (?, ?, ?, ?)",
                        (user_id, s.get("date"), s.get("note"), s.get("recorded_at")))
            session_map[s.get("id")] = cur.lastrowid

        # Import workouts
        for w in data.get("workouts", []):
            cur.execute(
                "INSERT INTO workouts (user_id, text, date, is_challenge, session_id, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, w.get("text"), w.get("date"), w.get("is_challenge", 0), session_map.get(w.get("session_id")), w.get("recorded_at"))
            )
        
        # Import weights
        for w in data.get("weights", []):
            cur.execute(
                "INSERT INTO weights (user_id, weight, date) VALUES (?, ?, ?)",
                (user_id, w.get("weight"), w.get("date"))
            )
        
        # Import daily tasks
        for d in data.get("daily_tasks", []):
            cur.execute(
                "INSERT INTO daily_tasks (user_id, date, task_id, progress, completed) VALUES (?, ?, ?, ?, ?)",
                (user_id, d.get("date"), d.get("task_id"), d.get("progress", 0), d.get("completed", 0))
            )
        
        # Import coin rewards
        for c in data.get("coin_rewards", []):
            cur.execute(
                "INSERT INTO coin_rewards (user_id, date, source, amount, idem_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, c.get("date"), c.get("source"), c.get("amount"), c.get("idem_key"), c.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )

        if has_ledger:
            for event in data.get("reward_events", []):
                cur.execute(
                    "INSERT INTO reward_events (user_id, source, action_key, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, event["source"], event["action_key"], event.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
            for achievement in data.get("achievements", []):
                cur.execute(
                    "INSERT INTO achievements (user_id, achievement_key, awarded_at) VALUES (?, ?, ?)",
                    (user_id, achievement["achievement_key"], achievement.get("awarded_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
        else:
            # Legacy backups have no reward ledger. Restore XP/coins as-is and
            # fence achievements implied by history without paying them again.
            from services.achievements import ACHIEVEMENTS
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (user_id,))
            workout_count = int(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(streak_days,0), COALESCE(level,1) FROM users WHERE user_id=?", (user_id,))
            streak_days, level = cur.fetchone()
            legacy_stats = {"workout_count": workout_count, "max_streak": int(streak_days or 0), "level": int(level or 1), "early_workouts": 0, "late_workouts": 0}
            for key, achievement in ACHIEVEMENTS.items():
                if achievement["check"](legacy_stats):
                    cur.execute(
                        "INSERT OR IGNORE INTO achievements (user_id, achievement_key, awarded_at) VALUES (?, ?, ?)",
                        (user_id, key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    )
            # Deterministic sources can be fenced even in old backups. Manual
            # workout UUIDs are intentionally not reconstructed.
            for coin_reward in data.get("coin_rewards", []):
                source = coin_reward.get("source")
                date_text = coin_reward.get("date")
                action_key = None
                if source == "suggest":
                    action_key = f"suggest:{date_text}"
                elif source == "challenge":
                    action_key = f"challenge:{date_text}"
                elif source == "daily":
                    task_row = next((item for item in data.get("daily_tasks", []) if item.get("date") == date_text), None)
                    if task_row and task_row.get("task_id"):
                        action_key = f"daily:{date_text}:{task_row['task_id']}"
                if action_key:
                    cur.execute(
                        "INSERT OR IGNORE INTO reward_events (user_id, source, action_key, created_at) VALUES (?, ?, ?, ?)",
                        (user_id, source, action_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    )
        
        # Import user items
        for i in data.get("user_items", []):
            cur.execute(
                "INSERT INTO user_items (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
                (user_id, i.get("item_id"), i.get("purchased_at"))
            )
        
        db.commit()
        db.close()
        
        # Note: chart_stats are not imported directly - they are recalculated
        # automatically when exporting, based on the raw data (workouts, weights, etc.)
        return True, "Data imported successfully"
    except Exception as e:
        db.rollback()
        db.close()
        return False, f"Import error: {str(e)}"


@dp.message(Command("export"))
async def export_data(message: Message):
    """Export user data as JSON file."""
    uid = message.from_user.id
    lang = get_user_language(uid)
    
    data = get_user_export_data(uid)
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    # Send file to user
    filename = f"export_{uid}.json"
    file_data = json_str.encode('utf-8')
    document = BufferedInputFile(file_data, filename=filename)
    
    await message.answer_document(
        document=document,
        caption=t_pair(lang, 
            "✅ Ваші дані для резервної копії. Збережіть цей файл.\n\nДля відновлення використайте /import", 
            "✅ Your backup data. Save this file.\n\nUse /import to restore"
        )
    )


@dp.message(Command("import"))
async def import_prompt(message: Message):
    """Prompt user to send JSON file for import."""
    lang = get_user_language(message.from_user.id)
    await message.answer(
        t_pair(lang,
            "📥 Надішліть файл JSON для імпорту даних\n\n⚠️ Увага: це перезапише ваші поточні дані!",
            "📥 Send a JSON file to import data\n\n⚠️ Warning: this will overwrite your current data!"
        )
    )


@dp.message(F.document)
async def handle_import_file(message: Message):
    """Handle JSON file import."""
    uid = message.from_user.id
    lang = get_user_language(uid)
    
    if not message.document or not message.document.file_name:
        return
    
    if not message.document.file_name.endswith(".json"):
        await message.answer(t_pair(lang, "❌ Файл має бути JSON", "❌ File must be JSON"))
        return
    
    # Download file
    file = await bot.download(message.document.file_id)
    content = file.read().decode("utf-8")
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        await message.answer(t_pair(lang, "❌ Невірний JSON файл", "❌ Invalid JSON file"))
        return
    
    # Confirm before import
    await message.answer(
        t_pair(lang,
            "⚠️ Це перезапише всі ваші дані. Продовжити?", 
            "⚠️ This will overwrite all your data. Continue?"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_pair(lang, "✅ Так", "✅ Yes"), callback_data="import_confirm")],
            [InlineKeyboardButton(text=t_pair(lang, "❌ Ні", "❌ No"), callback_data="import_cancel")]
        ])
    )
    
    # Store temp data
    set_user_state(uid, f"import_data:{content}")


@dp.callback_query(F.data == "import_confirm")
async def import_confirm(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    
    state = get_user_state(uid)
    if not state or not state.startswith("import_data:"):
        await callback.message.edit_text(t_pair(lang, "❌ Дані не знайдено", "❌ Data not found"))
        return
    
    try:
        data = json.loads(state.replace("import_data:", ""))
    except json.JSONDecodeError:
        await callback.message.edit_text(t_pair(lang, "❌ Невірний формат даних", "❌ Invalid data format"))
        clear_user_state(uid)
        return
    
    success, msg = import_user_data(uid, data)
    if success:
        await callback.message.edit_text(
            t_pair(lang, "✅ Дані успішно імпортовано!", "✅ Data imported successfully!")
        )
    else:
        await callback.message.edit_text(
            t_pair(lang, f"❌ Помилка імпорту: {msg}", f"❌ Import error: {msg}")
        )
    clear_user_state(uid)


@dp.callback_query(F.data == "import_cancel")
async def import_cancel(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    clear_user_state(uid)
    await callback.message.edit_text(t_pair(lang, "❌ Імпорт скасовано", "❌ Import cancelled"))


# ── USE ITEM ----------
def use_item_from_inventory(user_id: int, item_id: str) -> tuple[bool, str, str]:
    """Use an item from user's inventory. Returns (success, message, result_text)."""
    items = get_user_items(user_id)
    if item_id not in items:
        return False, "Item not found", ""
    
    item = SHOP_ITEMS.get(item_id, {})
    item_type = item.get("type", "unknown")
    lang = get_user_language(user_id)
    
    if item_type == "consumable":
        # Remove one from inventory
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "DELETE FROM user_items WHERE user_id=? AND item_id=? LIMIT 1",
            (user_id, item_id)
        )
        db.commit()
        db.close()
    
    result_text = ""
    
    if item_id == "motivation_pack":
        quotes = "\n".join(f"• {get_motivation_quote(lang)}" for _ in range(3))
        result_text = f"{t_pair(lang, '💪 Мотивація дня:', '💪 Motivation:')}\n{quotes}"
        # Add XP bonus
        add_xp_to_user(user_id, 10)
        
    elif item_id == "energy_drink":
        result_text = t_pair(
            lang,
            "🥤 Ви почутили енергією! +20% до наступних трьох тренувань (на сьогодні)",
            "🥤 Powered up! +20% bonus for next 3 workouts today"
        )
        
    elif item_id == "sleep_guide":
        result_text = t_pair(
            lang,
            "😴 Тривала якістьний сон = краща регенерація. Ваші тренування будуть ефективнішими!",
            "😴 Quality sleep = better recovery. Your workouts will be more effective!"
        )
        
    elif item_id == "power_plan":
        result_text = get_premium_workout(lang)
        add_xp_to_user(user_id, 15)
        
    elif item_id == "monthly_program":
        result_text = t_pair(
            lang,
            "📅 Програма активована! Перегляньте тренування в /today. Нові випусти кожен тиждень!",
            "📅 Program activated! Check workouts in /today. New releases weekly!"
        )
        
    elif item_id == "home_gym":
        result_text = t_pair(
            lang,
            "🏠 Гайд активовано! Ви отримали доступ до 40+ вправ без обладнання. Використовуйте /workout",
            "🏠 Guide activated! Access to 40+ bodyweight exercises. Use /workout"
        )
        
    elif item_id == "hiit_protocol":
        result_text = t_pair(
            lang,
            "🔥 HIIT протокол активовано! Короткі інтенсивні тренування для спалювання жиру.",
            "🔥 HIIT protocol activated! Short intense workouts for fat burning."
        )
        
    elif item_id == "coin_booster_x2":
        result_text = t_pair(
            lang,
            "🪙 Бустер активовано! На 7 днів всі тренування дають x2 монети!",
            "🪙 Booster activated! For 7 days all workouts give x2 coins!"
        )
        
    elif item_id == "restore_stamina":
        result_text = t_pair(
            lang,
            "⚡ Енергію відновлено! Ще 4 години активності без обмежень.",
            "⚡ Energy restored! 4 more hours of activity without limits."
        )
        
    elif item_id == "skip_daily_task":
        db = get_db()
        cur = db.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            "UPDATE daily_tasks SET completed=1, progress=(SELECT target FROM daily_tasks WHERE user_id=? AND date=?) WHERE user_id=? AND date=?",
            (user_id, today, user_id, today)
        )
        db.commit()
        db.close()
        result_text = t_pair(
            lang,
            "⏭️ Щоденне завдання пропущено без штрафу!",
            "⏭️ Daily task skipped without penalty!"
        )
    else:
        result_text = t_pair(lang, "Предмет використано.", "Item used.")
    
    return True, "success", result_text


@dp.message(Command("use"))
async def use_item(message: Message):
    """Show inventory to use items."""
    uid = message.from_user.id
    lang = get_user_language(uid)
    items = get_user_items(uid)
    
    if not items:
        await message.answer(t_pair(lang, "У вас немає предметів для використання. Купіть в /shop", "No items to use. Buy in /shop"))
        return
    
    rows = []
    for item_id, count in items.items():
        item = SHOP_ITEMS.get(item_id)
        if item:
            name = t_pair(lang, item["uk_name"], item["en_name"])
            icon = item.get("icon", "📦")
            rows.append([
                InlineKeyboardButton(
                    text=f"{icon} {name} ({count})",
                    callback_data=f"use_item_{item_id}"
                )
            ])
    
    await message.answer(
        t_pair(lang, "Оберіть предмет для використання:", "Choose an item to use:"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(F.data.startswith("use_item_"))
async def use_item_callback(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    item_id = callback.data.replace("use_item_", "", 1)
    
    success, msg, result = use_item_from_inventory(uid, item_id)
    
    if success:
        item = SHOP_ITEMS.get(item_id, {})
        name = t_pair(lang, item.get("uk_name", ""), item.get("en_name", ""))
        await callback.message.edit_text(
            f"✅ {name} використано!\n\n{result}",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            t_pair(lang, f"❌ {msg}", f"❌ {msg}")
        )


# ---------- COMMANDS ----------
def welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Записати тренування" if lang == "uk" else "💪 Record workout", callback_data="welcome_workout")],
        [InlineKeyboardButton(text="📊 Моя статистика" if lang == "uk" else "📊 My stats", callback_data="welcome_stats"),
         InlineKeyboardButton(text="📅 Історія тренувань" if lang == "uk" else "📅 Workout history", callback_data="welcome_history")],
        [InlineKeyboardButton(text="❓ Як користуватися" if lang == "uk" else "❓ How to use", callback_data="welcome_help")],
        [InlineKeyboardButton(text="🇬🇧 English" if lang == "uk" else "🇺🇦 Українська", callback_data="welcome_lang_en" if lang == "uk" else "welcome_lang_uk")],
    ])


def help_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Записати тренування" if lang == "uk" else "💪 Record workout", callback_data="welcome_workout")],
        [InlineKeyboardButton(text="🏠 Головне меню" if lang == "uk" else "🏠 Main menu", callback_data="welcome_menu")],
    ])


def first_workout_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Відкрити статистику" if lang == "uk" else "📊 Open stats", callback_data="welcome_stats")],
        [InlineKeyboardButton(text="🏠 Головне меню" if lang == "uk" else "🏠 Main menu", callback_data="welcome_menu")],
    ])


@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    ensure_user(uid)
    lang = get_user_language(uid)
    await message.answer(t("welcome", lang), parse_mode="HTML", reply_markup=welcome_keyboard(lang))


@dp.message(Command("help"))
async def help_command(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(t("help", lang), parse_mode="HTML", reply_markup=help_keyboard(lang))


@dp.callback_query(F.data == "welcome_workout")
async def welcome_workout(callback: CallbackQuery):
    await callback.answer()
    # ``workout`` was moved to handlers.workouts during the split. Importing
    # it at module scope would create a cycle: bot.py imports bot_legacy first
    # and only then configures/includes the new routers.
    callback_user = getattr(callback, "from_user", None)
    if callback_user is None:  # compatibility with older callback test doubles
        from handlers.workouts import workout as start_workout
        await start_workout(callback.message)
        return
    from handlers.workouts import start_workout_for_user
    await start_workout_for_user(callback.message, callback_user.id, get_user_language(callback_user.id))


@dp.callback_query(F.data == "welcome_stats")
async def welcome_stats(callback: CallbackQuery):
    await callback.answer()
    await stats(callback.message, callback.from_user.id)


@dp.callback_query(F.data == "welcome_history")
async def welcome_history(callback: CallbackQuery):
    await callback.answer()
    await history(callback.message, callback.from_user.id)


@dp.callback_query(F.data == "welcome_help")
async def welcome_help(callback: CallbackQuery):
    await callback.answer()
    lang = get_user_language(callback.from_user.id)
    await callback.message.answer(t("help", lang), parse_mode="HTML", reply_markup=help_keyboard(lang))


@dp.callback_query(F.data == "welcome_menu")
async def welcome_menu(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.answer()
    try:
        await callback.message.edit_text(t("welcome", lang), parse_mode="HTML", reply_markup=welcome_keyboard(lang))
    except Exception:
        await callback.message.answer(t("welcome", lang), parse_mode="HTML", reply_markup=welcome_keyboard(lang))


@dp.callback_query(F.data.startswith("welcome_lang_"))
async def welcome_language(callback: CallbackQuery):
    lang = callback.data.rsplit("_", 1)[-1]
    if lang not in ("uk", "en"):
        await callback.answer("Outdated request", show_alert=True)
        return
    set_user_language(callback.from_user.id, lang)
    await callback.answer("Збережено" if lang == "uk" else "Saved")
    try:
        await callback.message.edit_text(t("welcome", lang), parse_mode="HTML", reply_markup=welcome_keyboard(lang))
    except Exception:
        await callback.message.answer(t("welcome", lang), parse_mode="HTML", reply_markup=welcome_keyboard(lang))


@dp.message(Command("change_language"))
async def change_language_command(message: Message):
    uid = message.from_user.id

    # Требование: любой вызов /change_language должен переключать UA <-> EN
    lang = toggle_user_language(uid)

    await message.answer(
        t_pair(lang, "Мову змінено на Українську ✅", "Language changed to English ✅"),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data in ("set_lang_en", "set_lang_uk"))
async def set_language(callback: CallbackQuery):
    lang = "en" if callback.data == "set_lang_en" else "uk"
    set_user_language(callback.from_user.id, lang)
    await callback.answer(t_pair(lang, "Збережено", "Saved"))
    await callback.message.edit_text(build_start_text(lang), parse_mode="HTML")


@dp.message(Command("profile"))
async def profile(message: Message):
    uid = message.from_user.id
    if is_duplicate_command(uid, message.message_id):
        return
    lang = get_user_language(uid)
    profile_row = _coerce_profile_dict(get_user_data_safe(uid))

    if not profile_is_filled(profile_row):
        ensure_user(uid)
        set_user_state(uid, "profile")
        await message.answer(profile_input_prompt(lang))
        return

    clear_user_state(uid)
    h = profile_row.get("height")
    g = profile_row.get("gender")
    age = profile_row.get("age")
    goal = profile_row.get("goal")
    current_weight = profile_row.get("current_weight")
    show_height = profile_row.get("show_height")
    show_gender = profile_row.get("show_gender")
    show_age = profile_row.get("show_age")
    show_weight = profile_row.get("show_weight")
    show_goal = profile_row.get("show_goal")

    try:
        weight_value = float(current_weight) if current_weight not in (None, "") else 0.0
    except (TypeError, ValueError):
        weight_value = 0.0
    weight_text = (
        f"{weight_value:.1f} кг"
        if weight_value > 0
        else t_pair(lang, "не вказана", "not set")
    )
    age_text = str(age) if age else t_pair(lang, "не вказаний", "not set")

    profile_lines = []
    if show_height and h:
        profile_lines.append(t_pair(lang, f"📏 Зріст: {h} см", f"📏 Height: {h} cm"))
    if show_gender and normalize_gender(g):
        gd = gender_display(lang, g)
        profile_lines.append(t_pair(lang, f"🧍 Стать: {gd}", f"🧍 Gender: {gd}"))
    if show_age and age:
        profile_lines.append(t_pair(lang, f"🎂 Вік: {age_text}", f"🎂 Age: {age_text}"))
    if show_weight:
        profile_lines.append(t_pair(lang, f"⚖️ Вага: {weight_text}", f"⚖️ Weight: {weight_text}"))
    if show_goal and goal:
        profile_lines.append(t_pair(lang, f"🎯 Мета: {goal}", f"🎯 Goal: {goal}"))

    if not profile_lines:
        profile_lines.append(
            t_pair(
                lang,
                "Усі поля приховані. Налаштувати: /profile_visibility",
                "All fields are hidden. Configure: /profile_visibility"
            )
        )

    await message.answer(
        style_block(
            t_pair(lang, "Профіль", "Profile"),
            "\n".join(profile_lines),
            icon="👤"
        ),
        parse_mode="HTML"
    )


@dp.message(Command("edit_profile"))
async def edit_profile(message: Message):
    uid = message.from_user.id
    if is_duplicate_command(uid, message.message_id):
        return
    lang = get_user_language(uid)
    set_user_state(uid, "profile")
    await message.answer(profile_input_prompt(lang))


@dp.message(Command("profile_visibility"))
async def profile_visibility(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)
    ensure_user_exists(uid)
    visibility = get_profile_visibility(uid)
    await message.answer(
        t_pair(
            lang,
            "Обери, які поля показувати в /profile:",
            "Choose which fields to show in /profile:"
        ),
        reply_markup=profile_visibility_keyboard(lang, visibility)
    )


@dp.callback_query(F.data.startswith("profile_toggle_"))
async def profile_toggle(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    field = callback.data.replace("profile_toggle_", "", 1)

    if field not in {name for name, _, _ in PROFILE_FIELDS}:
        await callback.answer(t_pair(lang, "❌ Невідоме поле", "❌ Unknown field"))
        return

    try:
        await callback.answer()
        # Используем новый модуль для переключения видимости
        toggle_field_visibility(uid, field)
        
        visibility = get_profile_visibility(uid)
        await callback.message.edit_reply_markup(
            reply_markup=profile_visibility_keyboard(lang, visibility)
        )
    except ValueError as e:
        await callback.message.answer(t_pair(lang, f"❌ Помилка: {str(e)}", f"❌ Error: {str(e)}"))
    except Exception as e:
        await callback.message.answer(t_pair(lang, f"❌ Помилка БД", f"❌ Database error"))
        log.error("Profile toggle error: %s", e)


@dp.message(Command("set_goal"))
async def set_goal(message: Message):
    lang = get_user_language(message.from_user.id)
    set_user_state(message.from_user.id, "weekly_goal")
    await message.answer(
        t_pair(lang, "Введи мету на тиждень (кількість днів тренувань)\nПриклад: 4", "Enter weekly goal (number of workout days)\nExample: 4")
    )


@dp.message(Command("goal"))
async def goal(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT weekly_goal FROM users WHERE user_id=?",
        (uid,)
    )
    row = cur.fetchone()

    if not row or not row[0] or row[0] < 1:
        db.close()
        await message.answer(t_pair(lang, "Мета не задана. Використовуй /set_goal", "Goal is not set. Use /set_goal"))
        return

    weekly_goal = int(row[0])

    week_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    cur.execute(
        "SELECT COUNT(DISTINCT date) FROM workouts WHERE user_id=? AND date>=?",
        (uid, week_ago)
    )
    done = cur.fetchone()[0] or 0
    db.close()

    progress = min(int(done / weekly_goal * 100), 100)

    blocks_total = 10
    blocks_done = int(progress / 10)
    bar = "█" * blocks_done + "░" * (blocks_total - blocks_done)

    status = t_pair(lang, "🔥 Чудово", "🔥 Great") if done >= weekly_goal else t_pair(lang, "⏳ Продовжуй", "⏳ Keep going")

    await message.answer(
        style_block(
            t_pair(lang, "Мета на тиждень", "Weekly goal"),
            t_pair(
                lang,
                f"🎯 Ціль: {weekly_goal}\n✅ Виконано: {done}\n📈 Прогрес: {progress}% {bar}\n{status}",
                f"🎯 Goal: {weekly_goal}\n✅ Done: {done}\n📈 Progress: {progress}% {bar}\n{status}"
            ),
            icon="🗓️"
        ),
        parse_mode="HTML"
    )


@dp.message(Command("daily"))
async def daily(message: Message):
    try:
        uid = message.from_user.id
        lang = get_user_language(uid)
        date_text, _, task, progress, completed = get_or_create_daily_task(uid)

        await message.answer(
            style_block(
                t_pair(lang, "Щоденне завдання", "Daily task"),
                build_daily_task_text(lang, task, progress, completed),
                icon="🎮"
            ),
            parse_mode="HTML",
            reply_markup=daily_task_keyboard(lang, task, completed, date_text)
        )
    except Exception as exc:
        log.error("/daily handler error: %s", exc, exc_info=True)
        await message.answer("❌ Error in daily command")
    return


@dp.callback_query(lambda c: c.data and c.data.startswith("daily_"))
async def daily_progress(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    callback_date = None

    if callback.data.startswith("daily_add_"):
        callback_date = callback.data.replace("daily_add_", "", 1)
    elif callback.data.startswith("daily_done_"):
        callback_date = callback.data.replace("daily_done_", "", 1)
    elif callback.data.startswith("daily_finish_"):
        callback_date = callback.data.replace("daily_finish_", "", 1)

    if callback_date and callback_date != today:
        await callback.answer(
            t_pair(lang, "Це старе завдання. Відкрий /daily", "This is an old task. Open /daily"),
            show_alert=True
        )
        return

    if callback.data.startswith("daily_done"):
        await callback.answer(t_pair(lang, "Завдання вже виконано", "Task already completed"))
        return

    date_text, task_id, task, progress, completed = get_or_create_daily_task(uid)
    was_completed = completed
    xp_amount   = 0
    if not completed:
        _, progress, completed, rewarded, balance = update_daily_progress(uid)
    else:
        rewarded, balance = False, get_coin_balance(uid)

    completed_now = completed
    just_completed = not was_completed and completed_now
    reward_info = {}
    if just_completed:
        reward_info = settle_action_rewards(
            uid, today, DAILY_TASK_XP_REWARD, task["reward"], "daily",
            update_streak=False, action_key=f"daily:{today}:{task_id}"
        )
        xp_info = reward_info
        xp_amount = DAILY_TASK_XP_REWARD
        rewarded = reward_info.get("coins_awarded", 0) > 0
        balance = reward_info.get("balance", balance)

    if completed_now is True and progress >= task["target"]:
        completed_now = True
    elif completed_now is None:
        completed_now = progress >= task["target"]

    text = build_daily_task_text(lang, task, progress, completed_now or completed)
    achievements = reward_info.get("achievements", [])
    if xp_amount or rewarded or achievements:
        daily_sync = {
            **(xp_info if xp_amount else {}),
            "user_id": uid,
            "streak_days": None,
            "leveled_up": bool(xp_amount and xp_info.get("leveled_up")),
        }
        text += "\n\n" + reward_summary(
            lang,
            "Щоденне завдання виконано",
            "Daily task completed",
            xp=reward_info.get("xp_awarded", xp_amount),
            coins=reward_info.get("coins_awarded", task["reward"] if rewarded else 0),
            balance=reward_info.get("balance", balance),
            sync_info=daily_sync,
            achievements=achievements,
        )

    await callback.message.edit_text(
        style_block(
            t_pair(lang, "Щоденне завдання", "Daily task"),
            text,
            icon="🎮"
        ),
        parse_mode="HTML",
        reply_markup=daily_task_keyboard(lang, task, completed_now or completed, date_text)
    )
    if rewarded or xp_amount or achievements:
        await callback.answer(t_pair(lang, "Нагороди нараховано", "Rewards granted"))
    else:
        await callback.answer(t_pair(lang, "Прогрес оновлено", "Progress updated"))


@dp.message(Command("wallet"))
async def wallet(message: Message):
    try:
        uid = message.from_user.id
        lang = get_user_language(uid)
        balance = get_coin_balance(uid)
        items = get_user_items(uid)

        if items:
            item_lines = []
            for item_id, count in items.items():
                item = SHOP_ITEMS.get(item_id)
                if item:
                    item_lines.append(f"• {t_pair(lang, item['uk_name'], item['en_name'])}: {count}")
            inventory = "\n".join(item_lines)
        else:
            inventory = t_pair(lang, "Покупок ще немає.", "No purchases yet.")

        await message.answer(
            style_block(
                t_pair(lang, "Гаманець", "Wallet"),
                t_pair(
                    lang,
                    f"🪙 Баланс: {balance}\n\n🎒 Покупки:\n{inventory}\n\nМагазин: /shop",
                    f"🪙 Balance: {balance}\n\n🎒 Purchases:\n{inventory}\n\nShop: /shop"
                ),
                icon="💰"
            ),
            parse_mode="HTML"
        )
    except Exception as exc:
        log.error("/wallet handler error: %s", exc, exc_info=True)
        await message.answer("❌ Error in wallet command")
    return


@dp.message(Command("shop"))
async def shop(message: Message):
    try:
        uid = message.from_user.id
        lang = get_user_language(uid)
        
        # Обеспечиваем существование пользователя
        ensure_user(uid)
        
        # Безопасно получаем баланс
        balance = get_coin_balance(uid)
        
        # Формируем текст со структурированной информацией
        header = t_pair(
            lang,
            f"🛒 Магазин Спортсмена\n\n🪙 Баланс: {balance} монет\n\nОберіть категорію товара:",
            f"🛒 Sports Shop\n\n🪙 Balance: {balance} coins\n\nChoose a category:"
        )
        
        try:
            # Отправляем сообщение с клавиатурой категорий
            await message.answer(
                header,
                parse_mode=None,
                reply_markup=shop_keyboard(lang)
            )
        except Exception as exc:
            log.error("/shop inner handler error: %s", exc, exc_info=True)
            # Fallback ответ
            await message.answer(
                t_pair(
                    lang,
                    f"🛒 Магазин\n\n🪙 Баланс: {balance} монет\n\nИспользуйте кнопки для навигации.",
                    f"🛒 Shop\n\n🪙 Balance: {balance} coins\n\nUse buttons to navigate."
                )
            )
    except Exception as exc:
        log.error("/shop handler error: %s", exc, exc_info=True)
        await message.answer("❌ Error in shop command")
    return


@dp.callback_query(lambda c: c.data == "shop_noop")
async def shop_noop(callback: CallbackQuery):
    """Обработчик для кликов на заголовки категорий - ничего не делает"""
    await callback.answer()



@dp.callback_query(F.data.startswith("shop_cat_"))
async def shop_cat(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    await callback.answer()
    ensure_user(uid)

    category = callback.data.replace("shop_cat_", "", 1)
    lvl      = get_user_xp_level(uid).get("level", 1)
    text = t_pair(lang, "📦 Магазин: оберіть товар", "📦 Shop: pick an item")

    try:
        await callback.message.edit_text(
            text,
            reply_markup=shop_category_keyboard(lang, category, user_level=lvl),
            parse_mode=None,
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=shop_category_keyboard(lang, category, user_level=lvl),
        )


@dp.callback_query(F.data == "shop_back_to_categories")
async def shop_back_to_categories(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    await callback.answer()

    text = t_pair(lang, "📦 Магазин: категорії", "📦 Shop: categories")

    try:
        await callback.message.edit_text(
            text,
            reply_markup=shop_keyboard(lang),
            parse_mode=None,
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=shop_keyboard(lang),
        )


@dp.callback_query(F.data.startswith("shop_buy_"))
async def shop_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    ensure_user(uid)
    item_id = callback.data.replace("shop_buy_", "", 1)
    item = SHOP_ITEMS.get(item_id)

    if not item:
        await callback.answer(t_pair(lang, "Товар не знайдено", "Item not found"), show_alert=True)
        return

    # Level-gate check
    min_lvl = item.get("min_level", 1)
    user_lvl = get_user_xp_level(uid).get("level", 1)
    if user_lvl < min_lvl:
        await callback.answer(
            t_pair(
                lang,
                f"🔒 Потрібен рівень {min_lvl}. Твій рівень: {user_lvl}. Підвищуй XP тренуваннями!",
                f"🔒 Level {min_lvl} required. Your level: {user_lvl}. Train more to earn XP!",
            ),
            show_alert=True
        )
        return

    paid, balance, status = buy_shop_item(uid, item_id, item["cost"])
    
    if status == "limit_exceeded":
        max_count = item.get('max_count', 1)
        await callback.answer(
            t_pair(
                lang,
                f"Макс куплено: {max_count} шт. Вижраних: /wallet",
                f"Maximum purchased: {max_count}. View: /wallet"
            ),
            show_alert=True
        )
        return
    
    if status == "insufficient_coins":
        await callback.answer(
            t_pair(
                lang,
                f"Не вистачає монет. Баланс: {balance}",
                f"Not enough coins. Balance: {balance}"
            ),
            show_alert=True
        )
        return

    # При успешной покупке генерируем разные отговеты в зависимости от типа
    item_name = t_pair(lang, item['uk_name'], item['en_name'])
    item_desc = t_pair(lang, item['uk_desc'], item['en_desc'])
    item_type = item.get('type', 'unknown')

    # Основное сообщение
    base_msg = t_pair(
        lang,
        f"✅ {item_name}\n🪙 Баланс: {balance}",
        f"✅ {item_name}\n🪙 Balance: {balance}"
    )

    # Генерируем содержимое в зависимости от типа
    if item_type == "functional":
        if item_id == "power_plan":
            body = f"{base_msg}\n\n{get_premium_workout(lang)}"
        elif item_id == "monthly_program":
            body = t_pair(
                lang,
                f"{base_msg}\n\n📅 30 днів модуля:\n• Тиждень 1: Основа\n• Тиждень 2-3: Настроювання\n• Тиждень 4: Пік\n\nВицавлено наовна в /магазині",
                f"{base_msg}\n\n📅 30-day progression:\n• Week 1: Foundation\n• Week 2-3: Building\n• Week 4: Peak\n\nStart now: /profile"
            )
        elif item_id == "home_gym":
            body = t_pair(
                lang,
                f"{base_msg}\n\n🏠 40+ вправ без обладнання!\nУсо в /wallet",
                f"{base_msg}\n\n🏠 40+ bodyweight exercises!\nOpen: /wallet"
            )
        elif item_id == "hiit_protocol":
            body = t_pair(
                lang,
                f"{base_msg}\n\n🔥 HIIT - 20 мін для максимального ефекту калорій",
                f"{base_msg}\n\n🔥 20-min intervals for max calorie burn"
            )
        elif item_id == "sleep_guide":
            body = t_pair(
                lang,
                f"{base_msg}\n\n😴 Таємниці сну атлета: Оптимальна температура, час сну",
                f"{base_msg}\n\n😴 Athlete's sleep formula: temp, timing, duration"
            )
        else:
            body = f"{base_msg}\n\n{item_desc}"

    elif item_type == "consumable":
        if item_id == "motivation_pack":
            quotes = "\n".join(f"• {get_motivation_quote(lang)}" for _ in range(3))
            body = f"{base_msg}\n\n{quotes}"
        elif item_id == "energy_drink":
            body = t_pair(
                lang,
                f"{base_msg}\n\n🥤 Зарядився! 🤸\nТепер рязва пітти води і тренуватися!",
                f"{base_msg}\n\n🥤 Powered up! 🤸\nTime to crush it!"
            )
        else:
            body = f"{base_msg}\n\n✨ {item_desc}"

    elif item_type == "booster":
        if item_id == "coin_booster_x2":
            body = t_pair(
                lang,
                f"{base_msg}\n\n🪙 × 2 МОНЕТ на 7 днів!\nВсі тренування = 2x рівардс",
                f"{base_msg}\n\n🪙 × 2 COINS for 7 days!\nAll workouts = 2x rewards"
            )
        elif item_id == "restore_stamina":
            body = t_pair(
                lang,
                f"{base_msg}\n\n⚡ Відновлено!\nКільканка чотири години активності.",
                f"{base_msg}\n\n⚡ Restored!\n4 hours of active energy."
            )
        elif item_id == "skip_daily_task":
            body = t_pair(
                lang,
                f"{base_msg}\n\n⏭️ Топ (день) випало!",
                f"{base_msg}\n\n⏭️ Daily task skipped penalty-free!"
            )
        else:
            body = f"{base_msg}\n\n⚡ {item_desc}"

    else:  # collectible + exclusive
        if item_id == "legendary_pack":
            body = t_pair(
                lang,
                f"{base_msg}\n\n🌟 ЛЕГЕНДА! 🌟\nОвдточено всі доступні бонуси!\nОбмежено кілька годин.",
                f"{base_msg}\n\n🌟 LEGENDARY! 🌟\nUnlocked all available bonuses!\nHurry - limited time offer."
            )
        elif item_id == "vip_membership":
            body = t_pair(
                lang,
                f"{base_msg}\n\n👑 VIP доступ 👑\nНа місяць: +50% знижка, екскльузив\nОтримати графік 1 ра неділя.",
                f"{base_msg}\n\n👑 VIP ACCESS 👑\n1 Month: 50% discount + exclusive\ntraining schedule unlock."
            )
        else:
            body = f"{base_msg}\n\n🌟 {item_desc}"

    await callback.message.answer(
        style_block(t_pair(lang, "📖 Умвовання в /wallet", "📖 Unlocked in /wallet"), body, icon="✅"),
        parse_mode="HTML"
    )
    await callback.answer(t_pair(lang, "🌟 Отмено!", "🌟 Awesome!"))


@dp.message(Command("reminders"))
async def reminders(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT reminders_enabled FROM users WHERE user_id=?",
        (uid,)
    )
    row = cur.fetchone()
    
    if not row or row[0] is None:
        # Новый пользователь или неизвестный статус — включаем напоминания по умолчанию
        cur.execute(
            "INSERT INTO users (user_id, reminders_enabled) VALUES (?, 1)",
            (uid,)
        )
        db.commit()
        status = True
    else:
        status = bool(row[0])
    
    db.close()

    if status:
        await message.answer(
            t_pair(lang, "🔔 Нагадування вже увімкнені.\n\nХочеш вимкнути?", "🔔 Reminders are already enabled.\n\nDo you want to disable them?"),
            reply_markup=reminders_on_keyboard(lang)
        )
    else:
        await message.answer(
            t_pair(lang, "🔕 Нагадування вже вимкнені.\n\nХочеш увімкнути?", "🔕 Reminders are already disabled.\n\nDo you want to enable them?"),
            reply_markup=reminders_off_keyboard(lang)
        )


@dp.callback_query(lambda c: c.data == "reminders_on")
async def reminders_on(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    await callback.answer()
    db = get_db()
    cur = db.cursor()

    cur.execute(
        """
        INSERT INTO users (user_id, reminders_enabled)
        VALUES (?, 1)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (uid,)
    )
    cur.execute(
        "UPDATE users SET reminders_enabled=1 WHERE user_id=?",
        (uid,)
    )
    db.commit()
    db.close()

    try:
        await callback.message.edit_text(
            t_pair(
                lang,
                "🔔 Нагадування УВІМКНЕНІ!\n\nОтримувати мотивацію щодня при пропуску тренування? 💪",
                "🔔 Reminders are ENABLED!\n\nGet daily motivation if you skip a workout? 💪"
            ),
            reply_markup=None
        )
    except Exception as exc:
        log.debug("reminders_on callback: edit_text failed (harmless): %s", exc)


@dp.callback_query(lambda c: c.data == "reminders_off")
async def reminders_off(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    await callback.answer()
    db = get_db()
    cur = db.cursor()

    cur.execute(
        """
        INSERT INTO users (user_id, reminders_enabled)
        VALUES (?, 0)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (uid,)
    )
    cur.execute(
        "UPDATE users SET reminders_enabled=0 WHERE user_id=?",
        (uid,)
    )
    db.commit()
    db.close()

    try:
        await callback.message.edit_text(
            t_pair(
                lang,
                "🔕 Нагадування ВИМКНЕНІ\n\nТи босс, тренуйся за настроєм! 😎",
                "🔕 Reminders are DISABLED\n\nYou're the boss, train by your mood! 😎"
            ),
            reply_markup=None
        )
    except Exception as exc:
        log.debug("reminders_off callback: edit_text failed (harmless): %s", exc)


@dp.message(Command("suggest"))
async def suggest(message: Message):
    lang = get_user_language(message.from_user.id)
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT goal FROM users WHERE user_id=?", (message.from_user.id,))
    row = cur.fetchone()
    db.close()

    if not row or not row[0]:
        await message.answer(t_pair(lang, "Спочатку задай мету в профілі (/profile).", "Set a goal in your profile first (/profile)."))
        return

    text = generate_workout(row[0], lang)
    await message.answer(text, reply_markup=suggest_keyboard(lang))


@dp.message(Command("motivate"))
async def motivate(message: Message):
    lang = get_user_language(message.from_user.id)
    quote = get_motivation_quote(lang)
    title = t_pair(lang, "Мотивація", "Motivation")
    await message.answer(
        style_block(title, f"💬 {quote}", icon="🚀"),
        parse_mode="HTML"
    )


@dp.message(Command("tip"))
async def tip(message: Message):
    lang = get_user_language(message.from_user.id)
    tip_text = get_health_tip(lang)
    title = t_pair(lang, "Порада дня", "Tip of the day")
    await message.answer(
        style_block(title, f"💡 {tip_text}", icon="🧠"),
        parse_mode="HTML"
    )


@dp.message(Command("challenge"))
async def challenge(message: Message):
    lang = get_user_language(message.from_user.id)
    challenge_text = get_fitness_challenge(lang)
    title = t_pair(lang, "Челендж дня", "Challenge of the day")
    await message.answer(
        style_block(title, f"🔥 {challenge_text}", icon="🏆"),
        parse_mode="HTML",
        reply_markup=challenge_keyboard(lang)
    )


@dp.callback_query(F.data == "suggest_retry")
async def suggest_retry(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.answer()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT goal FROM users WHERE user_id=?", (callback.from_user.id,))
    row = cur.fetchone()
    db.close()

    if not row or not row[0]:
        await callback.message.answer(t_pair(lang, "Немає мети", "No goal set"))
        return

    text = generate_workout(row[0], lang)
    await callback.message.answer(text, reply_markup=suggest_keyboard(lang))


@dp.callback_query(F.data == "suggest_done")
async def suggest_done(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    uid = callback.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")

    workout_text = callback.message.text or ""

    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT 1 FROM workouts WHERE user_id=? AND date=?",
        (uid, today)
    )
    if cur.fetchone():
        db.close()
        await callback.answer(t_pair(lang, "Сьогодні вже зараховано", "Already counted today"))
        return

    saved_count = 0
    for line in workout_text.split("\n"):
        if line.startswith("•"):
            cur.execute(
                "INSERT INTO workouts (user_id, text, date, recorded_at) VALUES (?, ?, ?, ?)",
                (uid, line[2:], today, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            saved_count += 1

    db.commit()
    db.close()

    reward = SUGGESTED_WORKOUT_REWARD if saved_count else 0
    xp_amount = SUGGESTED_WORKOUT_XP if saved_count else 0
    sync_inf = settle_action_rewards(
        uid, today, xp_amount, reward, "suggest", action_key=f"suggest:{today}"
    ) if saved_count else {}
    achievements = sync_inf.get("achievements", [])
    reward_text = reward_summary(
        lang, "Тренування збережено", "Workout saved",
        xp=sync_inf.get("xp_awarded", 0),
        coins=sync_inf.get("coins_awarded", 0),
        balance=sync_inf.get("balance"), sync_info=sync_inf, achievements=achievements,
    )

    edit_text = (
        callback.message.text
        + "\n\n" + reward_text
    )

    await callback.message.edit_text(edit_text)
    await callback.answer(t_pair(lang, "Нагороди нараховано", "Rewards granted"))


@dp.callback_query(F.data == "challenge_next")
async def challenge_next(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.answer()
    challenge_text = get_fitness_challenge(lang)
    await callback.message.edit_text(
        style_block(t_pair(lang, "Челендж дня", "Challenge of the day"), f"🔥 {challenge_text}", icon="🏆"),
        parse_mode="HTML",
        reply_markup=challenge_keyboard(lang)
    )


@dp.callback_query(F.data == "challenge_done")
async def challenge_done(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Extract challenge text from the message (it's between 🔥 markers)
    message_text = callback.message.text or ""
    # Find the challenge text that starts with 🔥
    lines = message_text.split("\n")
    challenge_text = None
    for line in lines:
        if line.startswith("🔥"):
            challenge_text = line[1:].strip()  # Remove 🔥 emoji
            break
    
    if not challenge_text:
        challenge_text = message_text

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT 1 FROM workouts WHERE user_id=? AND date=? AND is_challenge=1",
        (uid, today)
    )
    if cur.fetchone():
        db.close()
        await callback.answer(t_pair(lang, "Сьогодні вже зараховано", "Already counted today"))
        return

    cur.execute(
        "INSERT INTO workouts (user_id, text, date, is_challenge, recorded_at) VALUES (?, ?, ?, 1, ?)",
        (uid, challenge_text, today, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    db.close()

    sync_inf = settle_action_rewards(
        uid, today, CHALLENGE_XP_REWARD, CHALLENGE_COIN_REWARD, "challenge",
        action_key=f"challenge:{today}"
    )
    achievements = sync_inf.get("achievements", [])
    reward_text = reward_summary(
        lang, "Челендж зараховано", "Challenge counted",
        xp=sync_inf.get("xp_awarded", CHALLENGE_XP_REWARD),
        coins=sync_inf.get("coins_awarded", CHALLENGE_COIN_REWARD),
        balance=sync_inf.get("balance"), sync_info=sync_inf, achievements=achievements,
    )

    edit_text = (
        callback.message.text
        + "\n\n" + reward_text
    )
    await callback.message.edit_text(edit_text, parse_mode="HTML")
    await callback.answer(t_pair(lang, "Нагороди нараховано", "Rewards granted"))


async def _save_workout_with_note(
    message: Message,
    exercises: list[str],
    note: str | None,
    user_id: int,
    action_key: str | None = None,
):
    """Persist one workout atomically for the explicitly supplied owner.

    ``message`` can be either a user's message or the bot message attached to
    a callback query, so it must never be used to infer ownership here.
    """
    uid = user_id
    today = datetime.now().strftime("%Y-%m-%d")
    verify_db = get_db()
    verify_cur = verify_db.cursor()
    verify_cur.execute("SELECT 1 FROM workout_sessions WHERE user_id=? LIMIT 1", (uid,))
    is_first_workout = verify_cur.fetchone() is None
    verify_db.close()
    session_id = save_workout_session(uid, exercises, note, today)
    verify_db = get_db(); verify_cur = verify_db.cursor()
    verify_cur.execute("SELECT COUNT(*) FROM workout_sessions WHERE user_id=?", (uid,))
    session_count = verify_cur.fetchone()[0]
    verify_cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (uid,))
    workout_count = verify_cur.fetchone()[0]
    verify_db.close()
    log.info(
        "workout_saved db=%s cwd=%s user_id=%s session_id=%s sessions=%s workouts=%s",
        os.path.abspath(DB_PATH), os.getcwd(), uid, session_id, session_count, workout_count,
    )
    reward = min(len(exercises) * WORKOUT_COIN_REWARD, 50)
    sync_inf = settle_action_rewards(
        uid, today, min(len(exercises) * WORKOUT_XP_REWARD, 20), reward, "workout",
        action_key=action_key or f"session:{session_id}"
    )
    lang = get_user_language(uid)
    achievements = sync_inf.get("achievements", [])
    notification = reward_summary(
        lang,
        "Тренування збережено!",
        "Workout saved!",
        xp=sync_inf.get("xp_awarded", 0),
        coins=sync_inf.get("coins_awarded", 0),
        balance=sync_inf.get("balance"),
        sync_info=sync_inf,
        achievements=achievements,
    )
    await message.answer(notification +
                         (t_pair(lang, f"\nНотатка: {note}", f"\nNote: {note}") if note else ""))
    if is_first_workout:
        first_save_text = t_pair(
            lang,
            "🎉 Перше тренування збережено! Воно вже в історії. Переглянь статистику, щоб побачити свій прогрес.",
            "🎉 Your first workout is saved! It is now in your history. Open stats to see your progress.",
        )
        try:
            await message.answer(first_save_text, reply_markup=first_workout_keyboard(lang))
        except TypeError:  # lightweight message doubles used by integrations/tests
            await message.answer(first_save_text)
    clear_user_state(uid)


@dp.callback_query(lambda c: c.data == "workout_note_skip")
async def workout_note_skip(callback: CallbackQuery):
    uid = callback.from_user.id
    pending = _pending_workouts.get(uid)
    if not pending:
        await callback.answer(t_pair(get_user_language(uid), "Введення вже завершено", "Input already finished"))
        return
    await _save_workout_with_note(
        callback.message, pending["exercises"], None, uid, pending["action_key"]
    )
    _pending_workouts.pop(uid, None)
    await callback.answer()


@dp.message(Command("weight"))
async def weight(message: Message):
    lang = get_user_language(message.from_user.id)
    set_user_state(message.from_user.id, "weight")
    await message.answer(t_pair(lang, "Введи вагу (кг)", "Enter weight (kg)"))


@dp.message(Command("weight_stats"))
async def weight_stats(message: Message):
    lang = get_user_language(message.from_user.id)
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT weight, date FROM weights WHERE user_id=? ORDER BY date DESC LIMIT 7",
        (message.from_user.id,)
    )
    rows = cur.fetchall()
    db.close()

    if not rows:
        await message.answer(t_pair(lang, "Вага ще не записувалася.", "No weight entries yet."))
        return

    text = t_pair(lang, "⚖️ Вага (останні записи):\n", "⚖️ Weight (latest entries):\n")
    for w, d in rows:
        text += f"{d}: {w} кг\n"

    await message.answer(text)


# ---------- TODAY ----------
@dp.message(Command("today"))
async def today(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)
    _, _, daily_task, daily_progress_value, daily_completed = get_or_create_daily_task(uid)
    db = get_db()
    cur = db.cursor()

    today_date = datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        """SELECT w.text, w.is_challenge, w.session_id, s.note
           FROM workouts w LEFT JOIN workout_sessions s ON s.id=w.session_id
           WHERE w.user_id=? AND w.date=? ORDER BY w.id""",
        (uid, today_date)
    )
    rows = cur.fetchall()
    db.close()

    workouts_text_list: list[str] = [
        build_daily_today_text(lang, daily_task, daily_progress_value, daily_completed)
    ]
    # Считаем калории параллельно, чтобы не блокировать event loop
    calories = await asyncio.gather(*(calc_calories_async(row[0]) for row in rows))

    total_cal = 0
    displayed_sessions = set()
    for (text, is_challenge, session_id, note), cal in zip(rows, calories):
        total_cal += cal
        if session_id is not None and session_id not in displayed_sessions:
            if note:
                workouts_text_list.append(t_pair(lang, f"📝 Нотатка: {note}", f"📝 Note: {note}"))
            displayed_sessions.add(session_id)
        if is_challenge:
            workouts_text_list.append(f"🏆 {text}")
        else:
            workouts_text_list.append(f"• {text}")

    text = "\n".join(workouts_text_list)
    if not rows:
        text += t_pair(lang, "\n\nТренувань поки немає. Запиши через /workout.", "\n\nNo workouts yet. Log one with /workout.")

    await message.answer(
        style_block(
            t_pair(lang, "Сьогоднішні тренування", "Today's workouts"),
            t_pair(lang, f"{text}\n\n🔥 Витрачено: ~{total_cal} ккал", f"{text}\n\n🔥 Burned: ~{total_cal} kcal"),
            icon="🏋️"
        ),
        parse_mode="HTML"
    )


# ---------- STATS ----------
@dp.message(Command("stats"))
async def stats(message: Message, user_id: int | None = None):
    db = get_db()
    cur = db.cursor()
    uid = user_id or message.from_user.id
    lang = get_user_language(uid)

    cur.execute("SELECT COUNT(*) FROM workout_sessions WHERE user_id=?", (uid,))
    session_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (uid,))
    workout_count = cur.fetchone()[0]
    log.info(
        "stats_read_start db=%s cwd=%s user_id=%s sessions=%s workouts=%s",
        os.path.abspath(DB_PATH), os.getcwd(), uid, session_count, workout_count,
    )

    cur.execute(
        """SELECT w.date, w.text, w.is_challenge, w.session_id, s.note
           FROM workouts w LEFT JOIN workout_sessions s ON s.id=w.session_id
           WHERE w.user_id=? ORDER BY w.date DESC, w.id DESC""",
        (uid,)
    )
    rows = cur.fetchall()
    db.close()
    log.info(
        "stats_read_result db=%s user_id=%s rows=%s",
        os.path.abspath(DB_PATH), uid, len(rows),
    )

    if not rows:
        await message.answer(t_pair(lang, "Тренувань немає.", "No workouts yet."))
        return

    dates = [row[0] for row in rows]
    streak = _calculate_streak(None, dates)
    best_streak = calculate_best_streak(dates)
    activity = summarize_workouts(
        [(row[0], row[1], row[3]) for row in rows],
        today=datetime.now().date(),
    )
    week_delta = activity["current_week_sessions"] - activity["previous_week_sessions"]
    if week_delta > 0:
        week_comparison_uk = f"Зростання на {week_delta}"
        week_comparison_en = f"Up by {week_delta}"
    elif week_delta < 0:
        week_comparison_uk = f"Зниження на {abs(week_delta)}"
        week_comparison_en = f"Down by {abs(week_delta)}"
    else:
        week_comparison_uk = "Без змін"
        week_comparison_en = "No change"

    week_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")

    # Параллельно считаем калории ( entirely async, no event-loop blocking )
    all_texts = [row[1] for row in rows]
    calories = await asyncio.gather(*(calc_calories_async(t) for t in all_texts))

    total_cal = sum(calories)
    week_cal = sum(cal for row, cal in zip(rows, calories) if row[0] >= week_ago)

    # XP / Level
    xp_info = get_user_xp_level(uid)
    lvl     = xp_info.get("level", 1)
    xp      = xp_info.get("xp", 0)
    rank_uk, rank_en = get_rank(lvl)
    prev_total  = total_xp_for_level(lvl)
    cur_xp, xp_needed = get_progress_in_level(lvl, xp)
    pct   = int(cur_xp / xp_needed * 100) if xp_needed else 100
    xp_bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

    level_block = format_level_block(lang, xp_info) if True else (
        f"\n\n⭐ {t_pair(lang, 'Рівень', 'Level')}: {lvl}  "
        f"🏅 {t_pair(lang, rank_uk, rank_en)}\n"
        f"📊 XP: {xp}\n"
        f"{xp_bar} {pct}%"
    )

    activity_block = t_pair(
        lang,
        f"🏋️ Тренувань: {activity['total_sessions']}\n"
        f"💪 Вправ: {activity['total_exercises']}\n"
        f"📅 Цього тижня: {activity['current_week_sessions']}\n"
        f"📅 Попереднього тижня: {activity['previous_week_sessions']} ({week_comparison_uk})\n"
        f"🗓 Цього місяця: {activity['current_month_sessions']}\n"
        f"⭐ Найчастіша вправа: {activity['popular_exercise'] or '—'} ({activity['popular_exercise_count']})",
        f"🏋️ Workouts: {activity['total_sessions']}\n"
        f"💪 Exercises: {activity['total_exercises']}\n"
        f"📅 This week: {activity['current_week_sessions']}\n"
        f"📅 Previous week: {activity['previous_week_sessions']} ({week_comparison_en})\n"
        f"🗓 This month: {activity['current_month_sessions']}\n"
        f"⭐ Most frequent exercise: {activity['popular_exercise'] or '—'} ({activity['popular_exercise_count']})",
    )

    body_lines = [
        t_pair(
            lang,
            f"📊 Статистика\n"
            f"Днів тренування: {len(set(dates))}\n"
            f"🔥 Серія: {streak} {t_pair(lang, 'днів', 'days')}\n"
            f"🏆 Найкраща серія: {best_streak} {t_pair(lang, 'днів', 'days')}\n"
            f"🔥 Калорій всього: ~{total_cal}\n"
            f"🔥 За 7 днів: ~{week_cal}",
            f"📊 Statistics\n"
            f"Workout days: {len(set(dates))}\n"
            f"🔥 Streak: {streak} days\n"
            f"🏆 Best streak: {best_streak} days\n"
            f"🔥 Calories total: ~{total_cal}\n"
            f"🔥 Last 7 days: ~{week_cal}"
        ),
        activity_block,
        level_block,
        t_pair(lang, "Останні:", "Recent:"),
    ]

    displayed_sessions = set()
    for d, t, is_ch, session_id, note in rows[:5]:
        prefix = "🏆 " if is_ch else ""
        body_lines.append(f"{d}: {prefix}{t}")
        if session_id is not None and session_id not in displayed_sessions and note:
            body_lines.append(f"📝 {note}")
        if session_id is not None:
            displayed_sessions.add(session_id)

    body_lines.append(t_pair(lang, "\n↕️ Прогрес: /weight_stats   |   📊 Графіки: /chart",
                                  "\n↕️ Progress: /weight_stats   |   📊 Charts: /chart"))

    await message.answer(
        style_block(
            t_pair(lang, "Статистика", "Statistics"),
            "\n".join(body_lines).strip(),
            icon="📊"
        ),
        parse_mode="HTML"
    )


# ---------- LEVEL ----------
HISTORY_PAGE_SIZE = 5
HISTORY_MAX_TEXT = 3500


def _history_clip(value: str, limit: int = HISTORY_MAX_TEXT) -> str:
    value = html.escape(str(value or ""), quote=False)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _history_sessions(user_id: int) -> list[dict]:
    """Return real sessions plus legacy workouts without a session_id."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT s.id, s.date, s.note, COUNT(w.id)
           FROM workout_sessions s
           LEFT JOIN workouts w ON w.session_id=s.id AND w.user_id=s.user_id
           WHERE s.user_id=?
           GROUP BY s.id, s.date, s.note""",
        (user_id,),
    )
    sessions = [
        {"key": f"s:{row[0]}", "id": row[0], "date": row[1], "note": row[2], "count": row[3], "legacy": False}
        for row in cur.fetchall()
    ]
    cur.execute(
        """SELECT id, date, text FROM workouts
           WHERE user_id=? AND session_id IS NULL
           ORDER BY date DESC, id DESC""",
        (user_id,),
    )
    sessions.extend(
        {"key": f"l:{row[0]}", "id": row[0], "date": row[1], "note": None, "count": 1,
         "legacy": True, "text": row[2]}
        for row in cur.fetchall()
    )
    db.close()
    return sorted(sessions, key=lambda item: (item["date"] or "", item["id"]), reverse=True)


def _history_keyboard(lang: str, page: int, page_count: int, sessions: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"{item['date']} · {item['count']}" + (" 📝" if item["note"] else ""),
        callback_data=f"history_open_{item['key']}_{page}"
    )] for item in sessions]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"history_page_{page - 1}"))
    if page + 1 < page_count:
        navigation.append(InlineKeyboardButton(text=t_pair(lang, "Вперед ➡️", "Next ➡️"), callback_data=f"history_page_{page + 1}"))
    if navigation:
        rows.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _history_list_message(target, page: int = 0, user_id: int | None = None):
    uid = user_id or target.from_user.id
    lang = get_user_language(uid)
    sessions = _history_sessions(uid)
    if not sessions:
        text = t_pair(lang, "📚 Історія тренувань порожня.", "📚 Workout history is empty.")
        markup = None
        page = 0
    else:
        page_count = (len(sessions) + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE
        page = max(0, min(page, page_count - 1))
        current = sessions[page * HISTORY_PAGE_SIZE:(page + 1) * HISTORY_PAGE_SIZE]
        lines = [t_pair(lang, "📚 Історія тренувань", "📚 Workout history"), ""]
        for index, item in enumerate(current, page * HISTORY_PAGE_SIZE + 1):
            marker = " 📝" if item["note"] else ""
            unit = t_pair(lang, "вправа" if item["count"] == 1 else "вправи", "exercise" if item["count"] == 1 else "exercises")
            lines.append(f"{index}. {_history_clip(item['date'])} — {item['count']} {unit}{marker}")
        text = "\n".join(lines)
        markup = _history_keyboard(lang, page, page_count, current)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@dp.message(Command("history"))
async def history(message: Message, user_id: int | None = None):
    await _history_list_message(message, 0, user_id)


@dp.callback_query(F.data.startswith("history_page_"))
async def history_page(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except (AttributeError, ValueError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True)
        return
    await _history_list_message(callback, page)
    await callback.answer()


def _history_detail_keyboard(lang: str, key: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t_pair(lang, "✏️ Редагувати", "✏️ Edit"), callback_data=f"history_edit_{key}_{page}"),
         InlineKeyboardButton(text=t_pair(lang, "🗑 Видалити", "🗑 Delete"), callback_data=f"history_delete_menu_{key}_{page}")],
        [InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"history_back_{page}")],
    ])


def _history_edit_keyboard(lang: str, key: str, page: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t_pair(lang, "✏️ Змінити вправу", "✏️ Edit exercise"),
                                  callback_data=f"history_choose_ex_{key}_{page}")]]
    if key.startswith("s:"):
        rows.append([InlineKeyboardButton(text=t_pair(lang, "📝 Змінити нотатку", "📝 Edit note"),
                                          callback_data=f"history_edit_note_{key}_{page}")])
    rows.append([InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"),
                                      callback_data=f"history_open_{key}_{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _history_detail_payload(user_id: int, key: str, page: int):
    db = get_db(); cur = db.cursor(); session = None; exercises = []
    if key.startswith("s:") and key[2:].isdigit():
        session_id = int(key[2:])
        cur.execute("SELECT id, date, note FROM workout_sessions WHERE id=? AND user_id=?", (session_id, user_id)); session = cur.fetchone()
        if session:
            cur.execute("SELECT id, text, is_challenge FROM workouts WHERE session_id=? AND user_id=? ORDER BY id", (session_id, user_id)); exercises = cur.fetchall()
    elif key.startswith("l:") and key[2:].isdigit():
        workout_id = int(key[2:])
        cur.execute("SELECT id, date, NULL FROM workouts WHERE id=? AND user_id=? AND session_id IS NULL", (workout_id, user_id)); session = cur.fetchone()
        if session:
            cur.execute("SELECT id, text, is_challenge FROM workouts WHERE id=? AND user_id=? AND session_id IS NULL", (workout_id, user_id)); exercises = cur.fetchall()
    db.close()
    if not session:
        return None
    lang = get_user_language(user_id)
    lines = [t_pair(lang, f"🏋️ Тренування: {_history_clip(session[1])}", f"🏋️ Workout: {_history_clip(session[1])}"), ""]
    for _, text_value, is_challenge in exercises:
        lines.append(("🏆 " if is_challenge else "• ") + _history_clip(text_value, 800))
    if session[2]:
        lines.extend(["", t_pair(lang, "📝 Нотатка:", "📝 Note:"), _history_clip(session[2], 1200)])
    return _history_clip("\n".join(lines)), _history_detail_keyboard(lang, key, page)


@dp.callback_query(lambda c: c.data.startswith("history_edit_") and not c.data.startswith(("history_edit_ex_", "history_edit_note_")))
async def history_edit_menu(callback: CallbackQuery):
    value = callback.data[len("history_edit_"):]
    try:
        key, page_text = value.rsplit("_", 1); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True)
        return
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t_pair(lang, "Оберіть, що змінити:", "Choose what to edit:"), reply_markup=_history_edit_keyboard(lang, key, page))
    await callback.answer()


@dp.callback_query(F.data.startswith("history_choose_ex_"))
async def history_choose_exercise(callback: CallbackQuery):
    value = callback.data[len("history_choose_ex_"):]
    try:
        key, page_text = value.rsplit("_", 1); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True)
        return
    uid = callback.from_user.id; lang = get_user_language(uid)
    db = get_db(); cur = db.cursor()
    if key.startswith("s:"):
        try: item_id = int(key[2:])
        except ValueError: item_id = -1
        cur.execute("SELECT id, text FROM workouts WHERE session_id=? AND user_id=? ORDER BY id", (item_id, uid))
    elif key.startswith("l:"):
        try: item_id = int(key[2:])
        except ValueError: item_id = -1
        cur.execute("SELECT id, text FROM workouts WHERE id=? AND user_id=? AND session_id IS NULL", (item_id, uid))
    else:
        cur.execute("SELECT id, text FROM workouts WHERE 1=0")
    exercises = cur.fetchall(); db.close()
    if not exercises:
        await callback.answer(t_pair(lang, "Тренування не знайдено.", "Workout not found."), show_alert=True); return
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{index}. {_history_clip(text, 80)}", callback_data=f"history_edit_ex_{exercise_id}_{key}_{page}")
    ] for index, (exercise_id, text) in enumerate(exercises, 1)] + [[
        InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"history_edit_{key}_{page}")
    ]])
    await callback.message.edit_text(t_pair(lang, "Оберіть вправу:", "Choose an exercise:"), reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("history_edit_ex_"))
async def history_edit_exercise_start(callback: CallbackQuery):
    value = callback.data[len("history_edit_ex_"):]
    try:
        exercise_id_text, key, page_text = value.split("_", 2); exercise_id = int(exercise_id_text); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True); return
    _pending_history_edits[callback.from_user.id] = {"kind": "exercise", "id": exercise_id, "key": key, "page": page,
                                                     "chat_id": callback.message.chat.id, "message_id": callback.message.message_id}
    set_user_state(callback.from_user.id, "history_edit_exercise")
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t_pair(lang, "Введіть нову назву вправи:", "Send the new exercise name:"))
    await callback.answer()


@dp.callback_query(F.data.startswith("history_edit_note_"))
async def history_edit_note_start(callback: CallbackQuery):
    value = callback.data[len("history_edit_note_"):]
    try:
        key, page_text = value.rsplit("_", 1); page = int(page_text); session_id = int(key[2:])
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True); return
    if not key.startswith("s:"):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Для старого запису нотатка недоступна.", "Notes are unavailable for legacy records."), show_alert=True); return
    _pending_history_edits[callback.from_user.id] = {"kind": "note", "id": session_id, "key": key, "page": page,
                                                     "chat_id": callback.message.chat.id, "message_id": callback.message.message_id}
    set_user_state(callback.from_user.id, "history_edit_note")
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t_pair(lang, "Введіть нову нотатку. Порожній текст видалить її:", "Send the new note. Empty text removes it:"))
    await callback.answer()


@dp.callback_query(F.data.startswith("history_delete_menu_"))
async def history_delete_menu(callback: CallbackQuery):
    value = callback.data[len("history_delete_menu_"):]
    try: key, page_text = value.rsplit("_", 1); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True); return
    lang = get_user_language(callback.from_user.id)
    rows = []
    if key.startswith("s:"):
        rows.append([InlineKeyboardButton(text=t_pair(lang, "🗑 Видалити всю сесію", "🗑 Delete whole session"), callback_data=f"history_confirm_session_{key}_{page}")])
        rows.append([InlineKeyboardButton(text=t_pair(lang, "🗑 Видалити вправу", "🗑 Delete exercise"), callback_data=f"history_choose_del_{key}_{page}")])
    else:
        rows.append([InlineKeyboardButton(text=t_pair(lang, "🗑 Видалити запис", "🗑 Delete record"), callback_data=f"history_confirm_exercise_{key}_{page}")])
    rows.append([InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"history_open_{key}_{page}")])
    await callback.message.edit_text(t_pair(lang, "Оберіть тип видалення:", "Choose deletion type:"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data.startswith("history_choose_del_"))
async def history_choose_delete_exercise(callback: CallbackQuery):
    value = callback.data[len("history_choose_del_"):]
    try: key, page_text = value.rsplit("_", 1); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True); return
    uid = callback.from_user.id; lang = get_user_language(uid); db = get_db(); cur = db.cursor()
    session_id = int(key[2:]) if key.startswith("s:") and key[2:].isdigit() else -1
    cur.execute("SELECT id, text FROM workouts WHERE session_id=? AND user_id=? ORDER BY id", (session_id, uid)); exercises = cur.fetchall(); db.close()
    if not exercises:
        await callback.answer(t_pair(lang, "Вправи не знайдено.", "Exercises not found."), show_alert=True); return
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{index}. {_history_clip(text, 80)}", callback_data=f"history_confirm_exercise_e:{exercise_id}_{page}")
    ] for index, (exercise_id, text) in enumerate(exercises, 1)] + [[InlineKeyboardButton(text=t_pair(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"history_delete_menu_{key}_{page}")]])
    await callback.message.edit_text(t_pair(lang, "Оберіть вправу для видалення:", "Choose an exercise to delete:"), reply_markup=markup); await callback.answer()


@dp.callback_query(F.data.startswith("history_confirm_"))
async def history_confirm_prompt(callback: CallbackQuery):
    value = callback.data[len("history_confirm_"):]
    lang = get_user_language(callback.from_user.id)
    if value.startswith("session_"):
        kind, rest = "session", value[len("session_"):]
    elif value.startswith("exercise_"):
        kind, rest = "exercise", value[len("exercise_"):]
    else:
        await callback.answer(t_pair(lang, "Застарілий запит", "Outdated request"), show_alert=True); return
    try: target, page_text = rest.rsplit("_", 1); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(lang, "Застарілий запит", "Outdated request"), show_alert=True); return
    cancel_target = target if target.startswith("s:") else None
    cancel_callback = f"history_open_{cancel_target}_{page}" if cancel_target else f"history_back_{page}"
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t_pair(lang, "✅ Так, видалити", "✅ Yes, delete"), callback_data=f"history_do_delete_{kind}_{target}_{page}"),
        InlineKeyboardButton(text=t_pair(lang, "❌ Скасувати", "❌ Cancel"), callback_data=cancel_callback)
    ]])
    await callback.message.edit_text(t_pair(lang, "Підтвердити видалення?", "Confirm deletion?"), reply_markup=markup); await callback.answer()


@dp.callback_query(F.data.startswith("history_do_delete_"))
async def history_do_delete(callback: CallbackQuery):
    value = callback.data[len("history_do_delete_"):]
    try: kind, target, page_text = value.split("_", 2); page = int(page_text)
    except (ValueError, AttributeError):
        await callback.answer(t_pair(get_user_language(callback.from_user.id), "Застарілий запит", "Outdated request"), show_alert=True); return
    uid = callback.from_user.id; lang = get_user_language(uid); db = get_db(); cur = db.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        if kind == "session" and target.startswith("s:"):
            session_id = int(target[2:])
            cur.execute("DELETE FROM workouts WHERE session_id=? AND user_id=?", (session_id, uid))
            deleted = cur.rowcount
            cur.execute("DELETE FROM workout_sessions WHERE id=? AND user_id=?", (session_id, uid))
            deleted += cur.rowcount
        elif kind == "exercise":
            exercise_id = int(target[2:]) if target.startswith(("e:", "l:")) else int(target)
            cur.execute("SELECT session_id FROM workouts WHERE id=? AND user_id=?", (exercise_id, uid))
            session_row = cur.fetchone()
            session_id = session_row[0] if session_row else None
            cur.execute("DELETE FROM workouts WHERE id=? AND user_id=?", (exercise_id, uid)); deleted = cur.rowcount
            if deleted and session_id is not None:
                cur.execute("SELECT COUNT(*) FROM workouts WHERE session_id=? AND user_id=?", (session_id, uid))
                if cur.fetchone()[0] == 0:
                    cur.execute("DELETE FROM workout_sessions WHERE id=? AND user_id=?", (session_id, uid))
        else:
            deleted = 0
        db.commit()
    except (ValueError, sqlite3.Error):
        db.rollback(); deleted = 0
    finally:
        db.close()
    if not deleted:
        await callback.answer(t_pair(lang, "Запис уже видалено або доступ заборонено.", "Record already deleted or access denied."), show_alert=True); return
    if kind == "session":
        page = max(0, page)
    await _history_list_message(callback, page)
    await callback.answer(t_pair(lang, "Видалено", "Deleted"))


@dp.callback_query(F.data.startswith("history_open_"))
async def history_open(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = get_user_language(uid)
    open_value = callback.data[len("history_open_"):]
    try:
        key, page_text = open_value.rsplit("_", 1)
        return_page = int(page_text)
    except (ValueError, AttributeError):
        key, return_page = open_value, 0
    db = get_db(); cur = db.cursor()
    if key.startswith("s:"):
        try:
            session_id = int(key[2:])
        except ValueError:
            session_id = -1
        cur.execute("SELECT id, date, note FROM workout_sessions WHERE id=? AND user_id=?", (session_id, uid))
        session = cur.fetchone()
        if session:
            cur.execute("SELECT text, is_challenge FROM workouts WHERE session_id=? AND user_id=? ORDER BY id", (session_id, uid))
            exercises = cur.fetchall()
    elif key.startswith("l:"):
        try:
            workout_id = int(key[2:])
        except ValueError:
            workout_id = -1
        cur.execute("SELECT id, date, NULL FROM workouts WHERE id=? AND user_id=? AND session_id IS NULL", (workout_id, uid))
        session = cur.fetchone()
        if session:
            cur.execute("SELECT text, is_challenge FROM workouts WHERE id=? AND user_id=?", (workout_id, uid))
            exercises = cur.fetchall()
    else:
        session = None
    db.close()
    if not session:
        await callback.answer(t_pair(lang, "Тренування не знайдено або доступ заборонено.", "Workout not found or access denied."), show_alert=True)
        return
    lines = [t_pair(lang, f"🏋️ Тренування: {_history_clip(session[1])}", f"🏋️ Workout: {_history_clip(session[1])}"), ""]
    for text_value, is_challenge in exercises:
        prefix = "🏆 " if is_challenge else "• "
        lines.append(prefix + _history_clip(text_value, 800))
    if session[2]:
        lines.extend(["", t_pair(lang, "📝 Нотатка:", "📝 Note:"), _history_clip(session[2], 1200)])
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t_pair(lang, "⬅️ До історії", "⬅️ Back to history"), callback_data=f"history_back_{return_page}"
    )]])
    markup = _history_detail_keyboard(lang, key, return_page)
    await callback.message.edit_text(_history_clip("\n".join(lines)), reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("history_back_"))
async def history_back(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except (AttributeError, ValueError):
        page = 0
    await _history_list_message(callback, page)
    await callback.answer()


@dp.message(Command("level"))
async def level_cmd(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)
    ensure_user(uid)
    xp_info  = get_user_xp_level(uid)
    streak_i = get_user_streak(uid)
    balance  = get_coin_balance(uid)
    lvl      = xp_info.get("level", 1)
    xp       = xp_info.get("xp", 0)
    streak_days = streak_i.get("streak_days", 0)
    rank_uk, rank_en = get_rank(lvl)

    xp_needed = xp_for_next_level(lvl)
    if xp_needed:
        progress_note = t_pair(
            lang,
            f"Потрібно ще {xp_needed - (xp - total_xp_for_level(lvl))} XP для наступного рівня",
            f"Need {xp_needed - (xp - total_xp_for_level(lvl))} more XP for next level",
        )
    else:
        progress_note = t_pair(lang, "Досягнуто максимальний рівень!", "MAX LEVEL reached!")

    # Streak multiplier status
    multiplier = get_streak_xp_multiplier(streak_days)
    mult_line = ""
    if streak_days >= 3 and multiplier > 1.0:
        mult_line = t_pair(
            lang,
            f"\n🔥 Множник XP від серії: ×{multiplier:.0%}",
            f"\n🔥 Streak XP multiplier: ×{multiplier:.0%}",
        )

    # Level unlock status (what's unlocked + what's next)
    unlocked_lines, next_line = [], ""
    next_level = lvl + 1
    for threshold in sorted(LEVEL_UNLOCKS):
        if lvl >= threshold:
            txt = LEVEL_UNLOCKS[threshold]["uk"] if lang == "uk" else LEVEL_UNLOCKS[threshold]["en"]
            unlocked_lines.append(txt.replace(f"Рівень {threshold}", f"Рівень {threshold}"
                ).replace(f"Level {threshold}", f"Level {threshold}"))
    for threshold in sorted(LEVEL_UNLOCKS):
        if lvl < threshold:
            txt = LEVEL_UNLOCKS[threshold]["uk"] if lang == "uk" else LEVEL_UNLOCKS[threshold]["en"]
            next_line = f"\n🔒 {txt.replace(f'Рівень {threshold}', f'Рівень {threshold} ⬅').replace(f'Level {threshold}', f'Level {threshold} ←')}"
            break

    lines = [
        f"{format_level_block(lang, xp_info, streak_days)}",
        f"💡 {progress_note}",
        mult_line,
    ]
    if unlocked_lines:
        lines.append("")
        lines.append(t_pair(lang, "🔓 Розблоковано:", "🔓 Unlocked:"))
        lines.extend(unlocked_lines)
    if next_line:
        lines.append(next_line)

    lines.append(f"\n🪙 {t_pair(lang, 'Монети', 'Coins')}: {balance}")

    body = "\n".join(lines)

    await message.answer(
        style_block(
            t_pair(lang, "Рівень гравця", "Player Level"),
            body,
            icon="🏆"
        ),
        parse_mode="HTML"
    )


# ---------- CHARTS ----------
@dp.message(Command("chart"))
async def chart_cmd(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(
        t_pair(
            lang,
            "📊 Оберіть графік:",
            "📊 Pick a chart:"
        ),
        reply_markup=chart_keyboard(lang)
    )


@dp.callback_query(F.data == "chart_weight")
async def chart_weight(cb: CallbackQuery):
    from services.charts import weight_chart as _weight_chart_fn
    from aiogram.types import BufferedInputFile
    lang = get_user_language(cb.from_user.id)
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    try:
        buf = await asyncio.to_thread(_weight_chart_fn, cb.from_user.id, _chart_fetch_all)
        photo = BufferedInputFile(buf.read(), filename="weight_chart.png")
        await cb.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=t_pair(lang, "⚖️ Зміна ваги", "⚖️ Weight change"),
        )
    except Exception as exc:
        log.error(
            "chart_weight failed uid=%s chat=%s: %s",
            cb.from_user.id, chat_id, exc, exc_info=True,
        )
        try:
            await cb.message.answer(
                t_pair(lang, "❌ Не вдалося згенерувати графік ваги.", "❌ Failed to generate weight chart.")
            )
        except Exception:
            pass
    finally:
        await cb.answer()


@dp.callback_query(F.data == "chart_workouts")
async def chart_workouts(cb: CallbackQuery):
    from services.charts import workout_chart as _workout_chart_fn
    from aiogram.types import BufferedInputFile
    lang = get_user_language(cb.from_user.id)
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    try:
        buf = await asyncio.to_thread(_workout_chart_fn, cb.from_user.id, _chart_fetch_all)
        photo = BufferedInputFile(buf.read(), filename="workout_chart.png")
        await cb.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=t_pair(lang, "🏋️ Тренування", "🏋️ Workouts"),
        )
    except Exception as exc:
        log.error("chart_workouts failed uid=%s chat=%s: %s",
                  cb.from_user.id, chat_id, exc, exc_info=True)
        try:
            await cb.message.answer(
                t_pair(lang, "❌ Не вдалося згенерувати графік тренувань.", "❌ Failed to generate workout chart.")
            )
        except Exception:
            pass
    finally:
        await cb.answer()


@dp.callback_query(F.data == "chart_streak")
async def chart_streak(cb: CallbackQuery):
    from services.charts import streak_chart as _streak_chart_fn
    from aiogram.types import BufferedInputFile
    lang = get_user_language(cb.from_user.id)
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    try:
        buf = await asyncio.to_thread(_streak_chart_fn, cb.from_user.id, _chart_fetch_all)
        photo = BufferedInputFile(buf.read(), filename="streak_chart.png")
        await cb.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=t_pair(lang, "🔥 Серія днів", "🔥 Training streak"),
        )
    except Exception as exc:
        log.error("chart_streak failed uid=%s chat=%s: %s",
                  cb.from_user.id, chat_id, exc, exc_info=True)
        try:
            await cb.message.answer(
                t_pair(lang, "❌ Не вдалося згенерувати графік серії.", "❌ Failed to generate streak chart.")
            )
        except Exception:
            pass
    finally:
        await cb.answer()


@dp.callback_query(F.data == "chart_volume")
async def chart_volume(cb: CallbackQuery):
    from services.charts import volume_chart as _volume_chart_fn
    from aiogram.types import BufferedInputFile
    lang = get_user_language(cb.from_user.id)
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    try:
        buf = await asyncio.to_thread(_volume_chart_fn, cb.from_user.id, _chart_fetch_all)
        photo = BufferedInputFile(buf.read(), filename="volume_chart.png")
        await cb.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=t_pair(lang, "📦 Обсяг тренувань", "📦 Training volume"),
        )
    except Exception as exc:
        log.error("chart_volume failed uid=%s chat=%s: %s",
                  cb.from_user.id, chat_id, exc, exc_info=True)
        try:
            await cb.message.answer(
                t_pair(lang, "❌ Не вдалося згенерувати графік обсягу.", "❌ Failed to generate volume chart.")
            )
        except Exception:
            pass
    finally:
        await cb.answer()


# ---------- INPUT ----------
def _is_non_command_message(message: Message) -> bool:
    """Keep the legacy text-state handler from swallowing registered commands."""
    return not (message.text and message.text.startswith("/"))


@dp.message(_is_non_command_message)
async def handle_input(message: Message):
    uid = message.from_user.id
    lang = get_user_language(uid)

    if not message.text:
        await message.answer(t_pair(lang, "Поки що працюю лише з текстом. Спробуй команду /start", "I currently work with text only. Try /start"))
        return

    if message.text.startswith("/"):
        return

    state = get_user_state(uid)

    if not state:
        await message.answer(t_pair(lang, "Я на зв'язку 👋 Використай /start, щоб побачити команди.", "I'm here 👋 Use /start to see commands."))
        return

    if state in ("history_edit_exercise", "history_edit_note"):
        pending = _pending_history_edits.get(uid)
        if not pending:
            clear_user_state(uid)
            await message.answer(t_pair(lang, "Редагування вже завершено.", "Editing has already finished."))
            return
        value = message.text.strip()
        if state == "history_edit_exercise":
            if not value:
                await message.answer(t_pair(lang, "Назва вправи не може бути порожньою.", "Exercise name cannot be empty.")); return
            if len(value) > 500:
                await message.answer(t_pair(lang, "Назва надто довга (максимум 500 символів).", "Name is too long (maximum 500 characters).")); return
            db = get_db(); cur = db.cursor()
            cur.execute("UPDATE workouts SET text=? WHERE id=? AND user_id=?", (value, pending["id"], uid)); changed = cur.rowcount
            db.commit(); db.close()
        else:
            if len(value) > 2000:
                await message.answer(t_pair(lang, "Нотатка надто довга (максимум 2000 символів).", "Note is too long (maximum 2000 characters).")); return
            db = get_db(); cur = db.cursor()
            cur.execute("UPDATE workout_sessions SET note=? WHERE id=? AND user_id=?", (value or None, pending["id"], uid)); changed = cur.rowcount
            db.commit(); db.close()
        meta = _pending_history_edits.pop(uid)
        clear_user_state(uid)
        payload = _history_detail_payload(uid, meta["key"], meta["page"])
        if changed and payload:
            await bot.edit_message_text(chat_id=meta["chat_id"], message_id=meta["message_id"], text=payload[0], reply_markup=payload[1])
            await message.answer(t_pair(lang, "Зміни збережено.", "Changes saved."))
        else:
            await message.answer(t_pair(lang, "Запис не знайдено або доступ заборонено.", "Record not found or access denied."))
        return

    if state == "weekly_goal":
        try:
            goal = int(message.text)
            if goal < 1:
                raise ValueError("invalid goal")

            db = get_db()
            cur = db.cursor()

            cur.execute(
                """
                INSERT INTO users (user_id, weekly_goal)
                VALUES (?, ?) ON CONFLICT(user_id)
                DO
                UPDATE SET weekly_goal=excluded.weekly_goal
                """,
                (uid, goal)
            )

            db.commit()
            db.close()

            await message.answer(t_pair(lang, "Мета тижня збережена.", "Weekly goal saved."))
            clear_user_state(uid)
        except ValueError:
            await message.answer(t_pair(lang, "Введи число.", "Enter a number."))
        except Exception as exc:
            log.error("weekly_goal DB error uid=%s: %s", uid, exc, exc_info=True)
        return

    # WEIGHT
    if state == "weight":
        try:
            w = float(message.text)
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING",
                (uid,)
            )
            cur.execute(
                "INSERT INTO weights (user_id, weight, date) VALUES (?, ?, ?)",
                (uid, w, datetime.now().strftime("%Y-%m-%d"))
            )

            cur.execute(
                "UPDATE users SET current_weight = ? WHERE user_id = ?",
                (w, uid)
            )
            db.commit()
            db.close()

            await message.answer(t_pair(lang, "Вагу збережено.", "Weight saved."))
            clear_user_state(uid)
        except ValueError:
            await message.answer(t_pair(lang, "Введи число.", "Enter a number."))
        except Exception as exc:
            log.error("weight input error uid=%s: %s", uid, exc, exc_info=True)
        return

    # PROFILE
    if state == "profile":
        try:
            h, g, age, goal = parse_profile_text(message.text)

            # Збереження профіля
            db = get_db()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO users (user_id, height, gender, age, goal)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO
                UPDATE SET
                    height=excluded.height,
                    gender=excluded.gender,
                    age=excluded.age,
                    goal=excluded.goal
                """,
                (uid, h, g, age, goal)
            )
            
            # Встановити видимість за замовчуванням (усі поля видимі)
            cur.execute(
                """
                UPDATE users 
                SET show_height=1, show_gender=1, show_age=1, show_weight=1, show_goal=1
                WHERE user_id=?
                """,
                (uid,)
            )
            
            db.commit()
            db.close()

            # Успішне повідомлення з деталями профіля
            profile_summary = t_pair(
                lang,
                f"👤 Профіль збережено!\n\n📏 Зріст: {h} см\n🧍 Стать: {gender_display(lang, g)}\n🎯 Мета: {goal}",
                f"👤 Profile saved!\n\n📏 Height: {h} cm\n🧍 Gender: {gender_display(lang, g)}\n🎯 Goal: {goal}"
            )
            if age:
                profile_summary += t_pair(lang, f"\n🎂 Вік: {age}", f"\n🎂 Age: {age}")
            
            await message.answer(profile_summary)
            
            # Пропозиція налаштувати видимість профіля
            await message.answer(
                t_pair(
                    lang,
                    "Налаштувати видимість полів профіля? /profile_visibility",
                    "Configure profile field visibility? /profile_visibility"
                )
            )
            
            clear_user_state(uid)
        except ValueError as e:
            reason = str(e)
            error_texts = {
                "height": ("❌ Зріст має бути числом від 100 до 250 см", "❌ Height must be a number between 100 and 250 cm"),
                "gender": ("❌ Стать: ч/чоловік або ж/жінка", "❌ Gender: m/male or f/female"),
                "age": ("❌ Вік має бути числом від 1 до 120", "❌ Age must be a number between 1 and 120"),
                "goal": ("❌ Мета не може бути пустою", "❌ Goal cannot be empty"),
            }
            uk, en = error_texts.get(
                reason,
                (
                    "❌ Помилка в форматі профіля\n\n📋 Формати:\n• З віком: 165, ч, 25, набрати масу\n• Без віку: 165, ч, набрати масу",
                    "❌ Invalid profile format\n\n📋 Formats:\n• With age: 165, m, 25, gain muscle\n• Without age: 165, m, gain muscle",
                )
            )
            await message.answer(t_pair(lang, uk, en))
        except Exception as exc:
            log.exception("Profile parsing / save error uid=%s: %s", uid, exc)
            await message.answer(
                t_pair(
                    lang,
                    "❌ Помилка при збереженні профіля. Спробуй ще раз.",
                    "❌ Error saving profile. Try again."
                )
            )
        return

    # WORKOUT
    if state == "workout":
        exercises = parse_workout_exercises(message.text)
        if not exercises:
            await message.answer(
                t_pair(
                    lang,
                    "Введи хоча б одну вправу.",
                    "Enter at least one exercise."
                )
            )
            return

        _pending_workouts[uid] = {
            "exercises": exercises,
            "action_key": f"manual:{uuid.uuid4().hex}",
        }
        set_user_state(uid, "workout_note")
        await message.answer(t_pair(lang, "Хочеш додати нотатку? Напиши її або натисни «Пропустити».",
                                     "Add a note? Send it or press Skip."),
                              reply_markup=_workout_note_keyboard(lang))
        return

    if state == "workout_note":
        pending = _pending_workouts.pop(uid, None)
        if pending:
            await _save_workout_with_note(
                message, pending["exercises"], message.text.strip() or None, uid, pending["action_key"]
            )
            _pending_workouts.pop(uid, None)
        else:
            clear_user_state(uid)
        return

        reward = min(len(exercises) * WORKOUT_COIN_REWARD, 50)
        xp_amount = min(len(exercises) * WORKOUT_XP_REWARD, 20)
        rewarded, balance = claim_daily_coin_reward(uid, "workout", reward) if reward else (False, get_coin_balance(uid))

        today_str = datetime.now().strftime("%Y-%m-%d")
        sync_inf = award_xp_and_streak(uid, today_str, xp_amount)
        balance += sync_inf.get("streak_bonus_coins", 0)

        level_text = ""
        if xp_amount:
            level_text = (
                f"\n⭐ +{xp_amount} XP"
                + (t_pair(lang,
                             f"\n🏆 LEVEL UP! Рівень {sync_inf['level']}",
                             f"\n🏆 LEVEL UP! Level {sync_inf['level']}") if sync_inf["leveled_up"] else "")
                + (t_pair(lang,
                             f"\n🔥 Бонус серії: +{sync_inf['streak_bonus_coins']}🪙",
                             f"\n🔥 Streak bonus: +{sync_inf['streak_bonus_coins']}🪙") if sync_inf["streak_bonus_coins"] else "")
            )

        reward_text = (
            t_pair(lang, f"\n🪙 +{reward} монет\nБаланс: {balance}", f"\n🪙 +{reward} coins\nBalance: {balance}")
            if rewarded else
            t_pair(lang, f"\n🪙 Нагорода за /workout сьогодні вже отримана\nБаланс: {balance}", f"\n🪙 Today's /workout reward is already claimed\nBalance: {balance}")
        )

        await message.answer(
            t_pair(
                lang,
                f"Збережено: {len(exercises)}{reward_text}{level_text}",
                f"Saved: {len(exercises)}{reward_text}{level_text}"
            )
        )
        clear_user_state(uid)
        return


# ---------- RUN ----------
async def _scheduled_database_backup() -> None:
    admin_ids = [int(value.strip()) for value in os.getenv("ADMIN_IDS", "").split(",")
                 if value.strip().isdigit()]
    try:
        manifest = await asyncio.to_thread(create_backup)
        log.info("Scheduled database backup completed: %s", manifest["file"])
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, f"✅ Backup OK: {manifest['file']}\nSHA-256: {manifest['sha256']}")
            except Exception:
                log.exception("Could not send backup success notification to admin %s", admin_id)
    except Exception as exc:
        log.exception("Scheduled database backup failed")
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, f"❌ Backup failed: {type(exc).__name__}")
            except Exception:
                log.exception("Could not send backup failure notification to admin %s", admin_id)


async def main():
    acquire_single_instance_lock()
    if production_database_required():
        require_database_exists(DB_PATH)
    init_db()
    # Protect the pre-migration state.  This is a normal verified snapshot;
    # the original database is never copied over or modified.
    try:
        await asyncio.to_thread(create_backup)
    except Exception:
        log.exception("Pre-migration database backup failed")
        raise
    migrated_profiles = migrate_profile_gender_values()
    if migrated_profiles:
        log.info("Normalized profile gender values: %d", migrated_profiles)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_missed_days, 'cron', hour=9, minute=0)  # 9:00 кожноденно
    scheduler.add_job(lambda: asyncio.create_task(_scheduled_database_backup()), "interval", hours=6,
                      id="database_backup", replace_existing=True, coalesce=True, max_instances=1)
    scheduler.start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск"),
        BotCommand(command="change_language", description="Змінити мову"),
        BotCommand(command="profile", description="Профіль"),
        BotCommand(command="edit_profile", description="Змінити профіль"),
        BotCommand(command="profile_visibility", description="Поля профілю"),
        BotCommand(command="workout", description="Тренування"),
        BotCommand(command="today", description="Сьогодні"),
        BotCommand(command="history", description="Історія тренувань"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="weight", description="Вага"),
        BotCommand(command="reset", description="Видалити все"),
        BotCommand(command="weight_stats", description="Статистика ваги"),
        BotCommand(command="suggest", description="Запропонувати тренування"),
        BotCommand(command="set_goal", description="Встановити мету на тиждень"),
        BotCommand(command="goal", description="Показати мету на тиждень"),
        BotCommand(command="daily", description="Щоденне завдання"),
        BotCommand(command="wallet", description="Баланс монет"),
        BotCommand(command="shop", description="Магазин"),
        BotCommand(command="level", description="Рівень і ранг"),
        BotCommand(command="chart", description="Графіки прогресу"),
        BotCommand(command="reminders", description="Нагадування"),
        BotCommand(command="motivate", description="Мотивація"),
        BotCommand(command="tip", description="Корисна порада"),
        BotCommand(command="challenge", description="Челендж дня"),
        BotCommand(command="export", description="Експорт даних"),
        BotCommand(command="import", description="Імпорт даних"),
        BotCommand(command="use", description="Використати предмет"),
        BotCommand(command="backup", description="Резервна копія (адмін)"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    # Оптимизация polling: меньший timeout для быстрого отклика
    await dp.start_polling(bot, timeout=30)
    await close_http_session()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
