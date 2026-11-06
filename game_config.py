"""
Global game configuration constants.

Imported by handlers/, services/, and game_config without creating circular
dependencies — only `bot.py` still creates the full user objects.
"""
from __future__ import annotations

from typing import Any

# ── XP rewards ────────────────────────────────────────────────────────────
WORKOUT_XP_REWARD      = 10   # per exercise in /workout
DAILY_TASK_XP_REWARD   = 15
SUGGESTED_WORKOUT_XP   = 20
CHALLENGE_XP_REWARD    = 15

# ── Coin rewards ──────────────────────────────────────────────────────────
WORKOUT_COIN_REWARD     = 10  # per exercise
SUGGESTED_WORKOUT_REWARD = 25
CHALLENGE_COIN_REWARD   = 35

# ── Streak bonuses (coins, bonus-xp) awarded ONCE per milestone ────────────
STREAK_BONUSES: dict[int, tuple[int, int]] = {
    3:  (15,  10),
    5:  (30,  25),
    7:  (50,  50),
    10: (80,  80),
    14: (120, 120),
    21: (200, 200),
    30: (350, 350),
}

# XP multipliers applied to every workout XP grant at given streak tiers
STREAK_XP_MULTIPLIERS: dict[int, float] = {
    7:  1.10,
    14: 1.20,
    21: 1.30,
    30: 1.50,
}
MAX_XP_MULTIPLIER = 1.50

# ── Level unlocks ──────────────────────────────────────────────────────────
LEVEL_UNLOCKS: dict[int, dict[str, str]] = {
    3:  {
        "uk": "🔓 Рівень 3: Відкрито бейдж-магазин!",
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

# ── Shop items ─────────────────────────────────────────────────────────────
SHOP_ITEMS: dict[str, dict[str, Any]] = {
    # ── Тренувальні програми ──────────────────────────────────────────────
    "power_plan": {
        "cost": 60, "category": "Тренування", "type": "functional", "min_level": 5,
        "uk_name": "Преміум тренування",
        "en_name": "Premium workout",
        "uk_desc": "Посилене тренування з вулу.",
        "en_desc": "Get a random stronger workout.",
        "icon": "⚡",
    },
    "monthly_program": {
        "cost": 150, "category": "Тренування", "type": "functional", "min_level": 5,
        "uk_name": "Програма на місяць",
        "en_name": "Monthly program",
        "uk_desc": "30 днів прогресивного навчання.",
        "en_desc": "30 days of progressive training.",
        "icon": "📅",
    },
    "home_gym": {
        "cost": 120, "category": "Тренування", "type": "functional", "min_level": 5,
        "uk_name": "Домашній спортзал",
        "en_name": "Home gym guide",
        "uk_desc": "Тренування без обладнання. 40+ вправ.",
        "en_desc": "Bodyweight exercises guide. 40+ exercises.",
        "icon": "🏠",
    },
    "hiit_protocol": {
        "cost": 100, "category": "Тренування", "type": "functional", "min_level": 5,
        "uk_name": "HIIT протокол",
        "en_name": "HIIT protocol",
        "uk_desc": "Інтенсивні інтервальні тренування.",
        "en_desc": "High-intensity interval training for fat loss.",
        "icon": "🔥",
    },
    # ── Підтримка ─────────────────────────────────────────────────────────
    "motivation_pack": {
        "cost": 35, "category": "Підтримка", "type": "functional", "min_level": 1,
        "uk_name": "Пак мотивації",
        "en_name": "Motivation pack",
        "uk_desc": "3 мотиваційні цитати.",
        "en_desc": "3 motivational quotes.",
        "icon": "💪",
    },
    "energy_drink": {
        "cost": 45, "category": "Підтримка", "type": "consumable", "min_level": 1,
        "uk_name": "Енергетичний напій",
        "en_name": "Energy drink",
        "uk_desc": "Посиль перед тренуванням.",
        "en_desc": "Boost before workout.",
        "icon": "🥤",
    },
    "sleep_guide": {
        "cost": 50, "category": "Підтримка", "type": "functional", "min_level": 1,
        "uk_name": "Гід здорового сну",
        "en_name": "Sleep guide",
        "uk_desc": "Оптимізуй відновлення.",
        "en_desc": "Optimize recovery with quality sleep tips.",
        "icon": "😴",
    },
    # ── Аксесуари ─────────────────────────────────────────────────────────
    "gym_towel": {
        "cost": 25, "category": "Аксесуари", "type": "collectible", "min_level": 1,
        "uk_name": "Рушник для спортзалу",
        "en_name": "Gym towel",
        "uk_desc": "Якісний мікрофібровий рушник.",
        "en_desc": "Premium microfiber gym towel.",
        "icon": "🧣",
    },
    "water_bottle": {
        "cost": 40, "category": "Аксесуари", "type": "collectible", "min_level": 1,
        "uk_name": "Спортивна пляшка",
        "en_name": "Sports bottle",
        "uk_desc": "Залишайся гідратованим. 1.5 л.",
        "en_desc": "Stay hydrated. 1.5L capacity.",
        "icon": "🍾",
    },
    "training_gloves": {
        "cost": 55, "category": "Аксесуари", "type": "collectible", "min_level": 3,
        "uk_name": "Тренувальні рукавиці",
        "en_name": "Training gloves",
        "uk_desc": "Захист при силових вправах.",
        "en_desc": "Protection for heavy lifts.",
        "icon": "🧤",
    },
    "yoga_mat": {
        "cost": 60, "category": "Аксесуари", "type": "collectible", "min_level": 3,
        "uk_name": "Килимок для йоги",
        "en_name": "Yoga mat",
        "uk_desc": "Комфортна поверхня для вправ.",
        "en_desc": "Comfort mat for exercises.",
        "icon": "🧘",
    },
    "headphones": {
        "cost": 70, "category": "Аксесуари", "type": "collectible", "min_level": 5,
        "uk_name": "Спортивні навушники",
        "en_name": "Sports headphones",
        "uk_desc": "Водостійкі, з гарною музикою.",
        "en_desc": "Waterproof with great sound.",
        "icon": "🎧",
    },
    # ── Харчування ────────────────────────────────────────────────────────
    "protein_powder": {
        "cost": 80, "category": "Харчування", "type": "consumable", "min_level": 3,
        "uk_name": "Протеїновий порошок",
        "en_name": "Protein powder",
        "uk_desc": "Якісний сироватковий білок. 500г.",
        "en_desc": "Quality whey protein. 500g.",
        "icon": "🥛",
    },
    "creatine": {
        "cost": 65, "category": "Харчування", "type": "consumable", "min_level": 3,
        "uk_name": "Креатин моногідрат",
        "en_name": "Creatine monohydrate",
        "uk_desc": "Для більшої сили і м'язевої маси.",
        "en_desc": "Boost strength and muscle growth.",
        "icon": "💊",
    },
    "bcaa": {
        "cost": 75, "category": "Харчування", "type": "consumable", "min_level": 5,
        "uk_name": "BCAA амінокислоти",
        "en_name": "BCAA amino acids",
        "uk_desc": "Для відновлення м'язів. 200 порцій.",
        "en_desc": "Muscle recovery. 200 servings.",
        "icon": "⚗️",
    },
    "multivitamin": {
        "cost": 70, "category": "Харчування", "type": "consumable", "min_level": 3,
        "uk_name": "Мультивітамін",
        "en_name": "Multivitamin",
        "uk_desc": "Повні вітаміни і мінерали.",
        "en_desc": "Full spectrum vitamins & minerals.",
        "icon": "🔬",
    },
    "weight_gainer": {
        "cost": 90, "category": "Харчування", "type": "consumable", "min_level": 10,
        "uk_name": "Вейт-гейнер",
        "en_name": "Weight gainer",
        "uk_desc": "Для набору маси. 1 кг, 10 порцій.",
        "en_desc": "Mass gainer. 1kg, 10 servings.",
        "icon": "🍫",
    },
    # ── Бейджі ────────────────────────────────────────────────────────────
    "rest_badge": {
        "cost": 80, "category": "Бейджі", "type": "collectible", "min_level": 3,
        "uk_name": "Бейдж Відновлення 🏆",
        "en_name": "Recovery badge 🏆",
        "uk_desc": "Рідкісний бейдж за баланс у тренуванні.",
        "en_desc": "Rare badge for training balance.",
        "icon": "🎖️",
    },
    "champion_badge": {
        "cost": 100, "category": "Бейджі", "type": "collectible", "min_level": 10,
        "uk_name": "Чемпіон 👑",
        "en_name": "Champion 👑",
        "uk_desc": "Престижний бейдж для переможців.",
        "en_desc": "Prestige badge for champions.",
        "icon": "👑",
    },
    "endurance_badge": {
        "cost": 85, "category": "Бейджі", "type": "collectible", "min_level": 5,
        "uk_name": "Витривалість 💯",
        "en_name": "Endurance 💯",
        "uk_desc": "За 100 днів безперервних тренувань.",
        "en_desc": "For 100 consecutive training days.",
        "icon": "💯",
    },
    "strength_badge": {
        "cost": 90, "category": "Бейджі", "type": "collectible", "min_level": 5,
        "uk_name": "Сила 💪",
        "en_name": "Strength 💪",
        "uk_desc": "За подолання власних меж.",
        "en_desc": "For pushing your limits.",
        "icon": "💪",
    },
    "speed_badge": {
        "cost": 85, "category": "Бейджі", "type": "collectible", "min_level": 3,
        "uk_name": "Швидкість ⚡",
        "en_name": "Speed ⚡",
        "uk_desc": "За швидкі інтенсивні тренування.",
        "en_desc": "For high-intensity cardio.",
        "icon": "⚡",
    },
    # ── Бусти ─────────────────────────────────────────────────────────────
    "coin_booster_x2": {
        "cost": 150, "category": "Бусти", "type": "booster", "min_level": 10,
        "uk_name": "Бустер монет ×2 (1 тиждень)",
        "en_name": "Coin booster ×2 (1 week)",
        "uk_desc": "Отримуй в 2 рази більше монет за тренування.",
        "en_desc": "Earn 2x coins for 7 days.",
        "icon": "🪙",
        "max_count": 1,
    },
    "restore_stamina": {
        "cost": 120, "category": "Бусти", "type": "booster", "min_level": 5,
        "uk_name": "Відновити енергію",
        "en_name": "Restore stamina",
        "uk_desc": "Перезагрузи свою енергію.",
        "en_desc": "Restore your energy for new challenges.",
        "icon": "⚡",
        "max_count": 2,
    },
    "skip_daily_task": {
        "cost": 90, "category": "Бусти", "type": "booster", "min_level": 5,
        "uk_name": "Пропустити завдання",
        "en_name": "Skip daily task",
        "uk_desc": "Пропусти щоденне завдання без штрафу.",
        "en_desc": "Skip daily task without penalty.",
        "icon": "⏭️",
    },
    # ── Ексклюзив ────────────────────────────────────────────────────────
    "legendary_pack": {
        "cost": 200, "category": "Ексклюзив", "type": "collectible", "min_level": 15,
        "uk_name": "Легендарний набір 🌟",
        "en_name": "Legendary pack 🌟",
        "uk_desc": "Всі програми + бейджі + бусти. Обмежено!",
        "en_desc": "All programs + badges + boosters. Limited!",
        "icon": "🌟",
    },
    "vip_membership": {
        "cost": 250, "category": "Ексклюзив", "type": "collectible", "min_level": 15,
        "uk_name": "VIP членство (1 місяць)",
        "en_name": "VIP membership (1 month)",
        "uk_desc": "Ексклюзивні тренування + 50% знижка.",
        "en_desc": "Exclusive workouts + 50% discount on all items.",
        "icon": "👑",
    },
}
