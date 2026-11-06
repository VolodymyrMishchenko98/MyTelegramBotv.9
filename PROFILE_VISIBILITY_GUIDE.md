# Profile Visibility - Управление видимостью полей профиля

## Описание

Модуль `profile_visibility` позволяет пользователям управлять видимостью полей их профиля. Каждый пользователь может выбрать, какие информационные поля показывать в профиле:

- **Зріст (Height)** - 📏
- **Стать (Gender)** - 🧍
- **Вік (Age)** - 🎂
- **Вага (Weight)** - ⚖️
- **Мета (Goal)** - 🎯

## Использование

### Для пользователей

#### Команда `/profile_visibility`

Открывает интерактивное меню для управления видимостью полей профиля.

```
/profile_visibility
```

Бот покажет кнопки для каждого поля:

- ✅ поле видимо (показывается в профиле)
- 🚫 поле скрыто (не показывается в профиле)

Нажмите на кнопку поля, чтобы переключить его видимость.

#### Команда `/profile`

Показывает профиль пользователя с учетом настроек видимости.

```
/profile
```

Будут показаны только те поля, для которых включена видимость.

#### Команда `/edit_profile`

Позволяет обновить данные профиля.

```
/edit_profile
```

**Форматы ввода:**

- С возрастом: `165, м, 25, набрать мышцы`
- Без возраста: `165, м, набрать мышцы`

**Параметры:**

- **Зріст**: числа от 100 до 250 см
- **Стать**: ч/м/male (мужчина) или ж/f/female (женщина)
- **Вік** (опционально): числа от 1 до 120
- **Мета**: любой текст

### Для разработчиков

#### Импорт функций

```python
from profile_visibility import (
    get_profile_visibility,
    set_field_visibility,
    toggle_field_visibility,
    get_visible_fields,
    is_field_visible,
    get_field_label,
    PROFILE_FIELDS
)
```

#### Основные функции

##### `get_profile_visibility(user_id: int) -> dict`

Получить состояние видимости всех полей профиля.

```python
visibility = get_profile_visibility(123456)
# {'height': True, 'gender': True, 'age': False, 'weight': True, 'goal': True}
```

##### `toggle_field_visibility(user_id: int, field: str) -> bool`

Переключить видимость поля (показать ↔ скрыть).

```python
# Если поле было видимо, оно будет скрыто, и наоборот
new_state = toggle_field_visibility(123456, 'age')  # True если видимо, False если скрыто
```

##### `set_field_visibility(user_id: int, field: str, visible: bool) -> bool`

Установить видимость поля на определенное значение.

```python
set_field_visibility(123456, 'weight', False)  # Скрыть вес
set_field_visibility(123456, 'goal', True)     # Показать мету
```

##### `is_field_visible(user_id: int, field: str) -> bool`

Проверить, видимо ли конкретное поле.

```python
if is_field_visible(123456, 'weight'):
    # Показать вес в профиле
    pass
```

##### `get_visible_fields(user_id: int) -> list[str]`

Получить список видимых полей.

```python
visible = get_visible_fields(123456)
# ['height', 'gender', 'weight', 'goal']
```

##### `get_field_label(field: str, lang: str = "uk") -> str`

Получить метку поля для отображения.

```python
label = get_field_label('height', 'uk')  # 'Зріст'
label = get_field_label('height', 'en')  # 'Height'
```

## Структура БД

Таблица `users` содержит следующие колонки видимости:

| Колонка       | Тип     | Описание               |
| ------------- | ------- | ---------------------- |
| `show_height` | INTEGER | 1 = видимо, 0 = скрыто |
| `show_gender` | INTEGER | 1 = видимо, 0 = скрыто |
| `show_age`    | INTEGER | 1 = видимо, 0 = скрыто |
| `show_weight` | INTEGER | 1 = видимо, 0 = скрыто |
| `show_goal`   | INTEGER | 1 = видимо, 0 = скрыто |

Все колонки имеют значение по умолчанию `1` (видимо).

## Примеры использования

### Пример 1: Скрыть личные данные

```python
from profile_visibility import set_field_visibility

user_id = 123456

# Скрыть возраст и вес
set_field_visibility(user_id, 'age', False)
set_field_visibility(user_id, 'weight', False)

# Показать только цель и пол
set_field_visibility(user_id, 'goal', True)
set_field_visibility(user_id, 'gender', True)
```

### Пример 2: Показать профиль с учетом видимости

```python
from profile_visibility import is_field_visible, get_field_label

def display_profile(user_id: int, profile_data: dict, lang: str = 'uk'):
    """Показать профиль с учетом видимости полей"""
    lines = []

    for field, uk_label, en_label in PROFILE_FIELDS:
        if is_field_visible(user_id, field):
            value = profile_data.get(field)
            label = get_field_label(field, lang)
            lines.append(f"{label}: {value}")

    return "\n".join(lines)
```

## Улучшения в обработчике ввода профиля

Обновленный обработчик ввода профиля включает:

✅ **Лучшая валидация**

- Проверка диапазонов (зріст, возраст)
- Поддержка разных форматов ввода пола
- Проверка на пустые значения

✅ **Информативные сообщения об ошибках**

- Указание причины ошибки
- Подсказки по исправлению
- Примеры правильного формата

✅ **Автоматическое управление видимостью**

- При создании профиля все поля видимы по умолчанию
- Предложение настроить видимость после создания профиля

✅ **Подтверждение и итоги**

- Показ сохраненных данных
- Рекомендация по дальнейшей настройке

## Интеграция с остальным ботом

Новый модуль интегрирован с:

- **`/profile`** - отображает только видимые поля
- **`/edit_profile`** - обновленный обработчик с лучшей валидацией
- **`/profile_visibility`** - управление видимостью
- **`profile_visibility_keyboard()`** - UI для управления видимостью
- **`profile_toggle` callback** - обработчик переключения видимости

## Файлы

- `profile_visibility.py` - основной модуль управления видимостью
- `bot.py` - интеграция с обработчиками команд

## Версия

Версия: 1.0
Дата: 11 мая 2026
