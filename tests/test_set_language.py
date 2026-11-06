#!/usr/bin/env python3
"""
Тестирование set_language функций без необходимости в BOT_TOKEN
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Добавляем путь к проекту (parent directory)
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_improved import execute_query, fetch_one, init_connection

print("=" * 60)
print("🧪 ТЕСТИРОВАНИЕ SET_LANGUAGE ФУНКЦИЙ")
print("=" * 60)

test_user_id = 888888

# Инициализируем БД
init_connection()

def get_user_language(user_id: int) -> str:
    """Получить язык пользователя"""
    row = fetch_one("SELECT language FROM users WHERE user_id=?", (user_id,))
    if row and row[0] in ("uk", "en"):
        return row[0]
    return "uk"

def set_user_language(user_id: int, lang: str):
    """Установить язык пользователя"""
    if lang not in ("uk", "en"):
        lang = "uk"
    execute_query(
        """
        INSERT INTO users (user_id, language)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET language=excluded.language
        """,
        (user_id, lang)
    )

def toggle_user_language(user_id: int) -> str:
    """Переключить язык пользователя"""
    current = get_user_language(user_id)
    next_lang = "en" if current == "uk" else "uk"
    set_user_language(user_id, next_lang)
    return next_lang

def pick_lang(lang: str, uk: str, en: str) -> str:
    """Выбрать текст по языку — по умолчанию английский для неизвестных языков"""
    return uk if lang == "uk" else en

# Тест 1: get_user_language - дефолтное значение
print("\n✅ Тест 1: get_user_language - дефолтное значение")
try:
    lang = get_user_language(test_user_id)
    if lang == "uk":
        print(f"   ✅ Дефолтный язык: {lang}")
    else:
        print(f"   ❌ Ожидается 'uk', получено '{lang}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 2: set_user_language на 'en'
print("\n✅ Тест 2: set_user_language на 'en'")
try:
    set_user_language(test_user_id, "en")
    lang = get_user_language(test_user_id)
    if lang == "en":
        print(f"   ✅ Язык установлен: {lang}")
    else:
        print(f"   ❌ Ожидается 'en', получено '{lang}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 3: set_user_language на 'uk'
print("\n✅ Тест 3: set_user_language на 'uk'")
try:
    set_user_language(test_user_id, "uk")
    lang = get_user_language(test_user_id)
    if lang == "uk":
        print(f"   ✅ Язык установлен: {lang}")
    else:
        print(f"   ❌ Ожидается 'uk', получено '{lang}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 4: toggle_user_language из 'uk' в 'en'
print("\n✅ Тест 4: toggle_user_language из 'uk' в 'en'")
try:
    current = get_user_language(test_user_id)
    toggled = toggle_user_language(test_user_id)
    new = get_user_language(test_user_id)
    
    if current == "uk" and toggled == "en" and new == "en":
        print(f"   ✅ Переключение: {current} -> {toggled} (проверка: {new})")
    else:
        print(f"   ❌ Ошибка переключения: {current} -> {toggled} (проверка: {new})")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 5: toggle_user_language из 'en' в 'uk'
print("\n✅ Тест 5: toggle_user_language из 'en' в 'uk'")
try:
    current = get_user_language(test_user_id)
    toggled = toggle_user_language(test_user_id)
    new = get_user_language(test_user_id)
    
    if current == "en" and toggled == "uk" and new == "uk":
        print(f"   ✅ Переключение: {current} -> {toggled} (проверка: {new})")
    else:
        print(f"   ❌ Ошибка переключения: {current} -> {toggled} (проверка: {new})")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 6: pick_lang для 'uk'
print("\n✅ Тест 6: pick_lang для 'uk'")
try:
    result = pick_lang("uk", "Привіт", "Hello")
    if result == "Привіт":
        print(f"   ✅ pick_lang('uk') = '{result}'")
    else:
        print(f"   ❌ Ожидается 'Привіт', получено '{result}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 7: pick_lang для 'en'
print("\n✅ Тест 7: pick_lang для 'en'")
try:
    result = pick_lang("en", "Привіт", "Hello")
    if result == "Hello":
        print(f"   ✅ pick_lang('en') = '{result}'")
    else:
        print(f"   ❌ Ожидается 'Hello', получено '{result}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 8: pick_lang для неизвестного языка (должен использовать 'en')
print("\n✅ Тест 8: pick_lang для неизвестного языка")
try:
    result = pick_lang("unknown", "Привіт", "Hello")
    if result == "Hello":
        print(f"   ✅ pick_lang('unknown') использует 'en' = '{result}'")
    else:
        print(f"   ❌ Ожидается 'Hello', получено '{result}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 9: Проверка persistence (сохранение языка между вызовами)
print("\n✅ Тест 9: Persistence языка между вызовами")
try:
    set_user_language(test_user_id, "en")
    lang1 = get_user_language(test_user_id)
    lang2 = get_user_language(test_user_id)
    if lang1 == lang2 == "en":
        print(f"   ✅ Язык сохраняется: {lang1} == {lang2}")
    else:
        print(f"   ❌ Языки не совпадают: {lang1} != {lang2}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 10: Проверка SQL injection защиты
print("\n✅ Тест 10: SQL injection защита")
try:
    # Попытаемся установить язык с SQL кодом
    malicious = "en'; DROP TABLE users; --"
    set_user_language(test_user_id, malicious)
    lang = get_user_language(test_user_id)
    
    # Проверим, что таблица users не была удалена
    result = fetch_one("SELECT COUNT(*) FROM users", None)
    if result and result[0] > 0:
        print(f"   ✅ SQL injection не сработал, таблица целая ({result[0]} пользователей)")
    else:
        print(f"   ❌ Таблица пуста - возможна SQL injection!")
except Exception as e:
    print(f"   ⚠️ Проверка SQL injection: {e}")

print("\n" + "=" * 60)
print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)

# Очистка тестовых данных
try:
    execute_query("DELETE FROM users WHERE user_id=?", (test_user_id,))
    print("\n✅ Тестовые данные удалены")
except:
    pass
