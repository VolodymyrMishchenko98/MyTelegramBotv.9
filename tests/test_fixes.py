#!/usr/bin/env python3
"""
Тестирование исправленной логики profile_visibility и set_language
"""

import sys
from pathlib import Path

# Добавляем путь к проекту (parent directory)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем функции
from profile_visibility import (
    PROFILE_FIELDS, ensure_user_exists, get_profile_visibility,
    set_field_visibility, toggle_field_visibility, get_visible_fields,
    is_field_visible, set_all_visible, hide_all_fields
)
from db_improved import get_db, execute_query, fetch_one

print("=" * 60)
print("🧪 ТЕСТИРОВАНИЕ PROFILE_VISIBILITY")
print("=" * 60)

test_user_id = 999999

# Тест 1: ensure_user_exists
print("\n✅ Тест 1: ensure_user_exists")
try:
    ensure_user_exists(test_user_id)
    result = fetch_one("SELECT user_id FROM users WHERE user_id=?", (test_user_id,))
    if result:
        print("   ✅ Пользователь создан/найден")
    else:
        print("   ❌ Пользователь не создан")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 2: get_profile_visibility
print("\n✅ Тест 2: get_profile_visibility")
try:
    visibility = get_profile_visibility(test_user_id)
    print(f"   Видимость: {visibility}")
    expected_fields = {name for name, _, _ in PROFILE_FIELDS}
    actual_fields = set(visibility.keys())
    if expected_fields == actual_fields:
        print("   ✅ Все поля присутствуют")
    else:
        print(f"   ❌ Отсутствуют поля: {expected_fields - actual_fields}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 3: set_field_visibility
print("\n✅ Тест 3: set_field_visibility")
try:
    result = set_field_visibility(test_user_id, "height", False)
    if result:
        visibility = get_profile_visibility(test_user_id)
        if not visibility["height"]:
            print("   ✅ Поле height скрыто")
        else:
            print("   ❌ Поле height не скрыто")
    else:
        print("   ❌ Ошибка при установке видимости")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 4: toggle_field_visibility
print("\n✅ Тест 4: toggle_field_visibility")
try:
    # Переключим height (было скрыто, должно быть видимо)
    new_state = toggle_field_visibility(test_user_id, "height")
    print(f"   Новое состояние height: {new_state}")
    visibility = get_profile_visibility(test_user_id)
    if visibility["height"] == new_state:
        print(f"   ✅ Переключение работает (новое состояние: {new_state})")
    else:
        print("   ❌ Состояние не совпадает")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 5: get_visible_fields
print("\n✅ Тест 5: get_visible_fields")
try:
    visible = get_visible_fields(test_user_id)
    print(f"   Видимые поля: {visible}")
    if isinstance(visible, list) and len(visible) > 0:
        print("   ✅ Список видимых полей получен")
    else:
        print("   ❌ Пустой список видимых полей")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 6: is_field_visible
print("\n✅ Тест 6: is_field_visible")
try:
    for field in ["height", "gender", "age", "weight", "goal"]:
        is_visible = is_field_visible(test_user_id, field)
        print(f"   {field}: {is_visible}")
    print("   ✅ Проверка видимости работает")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 7: Обработка неизвестного поля
print("\n✅ Тест 7: Обработка неизвестного поля")
try:
    result = toggle_field_visibility(test_user_id, "unknown_field")
    print(f"   ❌ Должна была выброшена ошибка ValueError")
except ValueError as e:
    print(f"   ✅ ValueError выброшена правильно: {e}")
except Exception as e:
    print(f"   ❌ Неправильная ошибка: {e}")

# Тест 8: set_all_visible и hide_all_fields
print("\n✅ Тест 8: set_all_visible и hide_all_fields")
try:
    set_all_visible(test_user_id)
    visibility = get_profile_visibility(test_user_id)
    if all(visibility.values()):
        print("   ✅ set_all_visible работает")
    else:
        print("   ❌ Не все поля видимы после set_all_visible")
    
    hide_all_fields(test_user_id)
    visibility = get_profile_visibility(test_user_id)
    if not any(visibility.values()):
        print("   ✅ hide_all_fields работает")
    else:
        print("   ❌ Не все поля скрыты после hide_all_fields")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тест 9: Проверка PROFILE_FIELDS
print("\n✅ Тест 9: Проверка PROFILE_FIELDS")
try:
    print(f"   Поля профиля: {PROFILE_FIELDS}")
    for field, uk_label, en_label in PROFILE_FIELDS:
        if not (field and uk_label and en_label):
            print(f"   ❌ Некорректное поле: {field}, {uk_label}, {en_label}")
        else:
            print(f"   ✅ {field}: UK='{uk_label}' EN='{en_label}'")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("🧪 ТЕСТИРОВАНИЕ SET_LANGUAGE")
print("=" * 60)

# Для set_language нужно импортировать из bot.py
try:
    from bot import get_user_language, set_user_language, toggle_user_language, pick_lang
    
    # Тест 10: get_user_language
    print("\n✅ Тест 10: get_user_language")
    try:
        lang = get_user_language(test_user_id)
        if lang in ("uk", "en"):
            print(f"   ✅ Язык пользователя: {lang}")
        else:
            print(f"   ❌ Неправильный язык: {lang}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 11: set_user_language
    print("\n✅ Тест 11: set_user_language")
    try:
        set_user_language(test_user_id, "en")
        lang = get_user_language(test_user_id)
        if lang == "en":
            print("   ✅ Язык установлен на 'en'")
        else:
            print(f"   ❌ Язык остался {lang}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 12: toggle_user_language
    print("\n✅ Тест 12: toggle_user_language")
    try:
        initial_lang = get_user_language(test_user_id)
        toggled_lang = toggle_user_language(test_user_id)
        new_lang = get_user_language(test_user_id)
        expected = "uk" if initial_lang == "en" else "en"
        if new_lang == expected and toggled_lang == expected:
            print(f"   ✅ Язык переключен с {initial_lang} на {toggled_lang}")
        else:
            print(f"   ❌ Ошибка переключения: ожидалось {expected}, получено {new_lang}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 13: pick_lang
    print("\n✅ Тест 13: pick_lang")
    try:
        uk_result = pick_lang("uk", "Привіт", "Hello")
        en_result = pick_lang("en", "Привіт", "Hello")
        if uk_result == "Привіт" and en_result == "Hello":
            print("   ✅ pick_lang работает правильно")
        else:
            print(f"   ❌ pick_lang неправильно: uk={uk_result}, en={en_result}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
except ImportError as e:
    print(f"❌ Не удалось импортировать функции из bot.py: {e}")
except Exception as e:
    print(f"❌ Ошибка при тестировании set_language: {e}")

print("\n" + "=" * 60)
print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)

# Очистка тестовых данных
try:
    execute_query("DELETE FROM users WHERE user_id=?", (test_user_id,))
    print("\n✅ Тестовые данные удалены")
except:
    pass
