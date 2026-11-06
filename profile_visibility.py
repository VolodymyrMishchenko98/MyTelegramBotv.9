"""
Модуль для управления видимостью полей профиля пользователя.
Обеспечивает полный контроль над тем, какие данные показываются в профиле.
"""

from db_improved import get_db, fetch_one, execute_query

# Определение полей профиля с их метками
PROFILE_FIELDS = (
    ("height", "Зріст", "Height"),
    ("gender", "Стать", "Gender"),
    ("age", "Вік", "Age"),
    ("weight", "Вага", "Weight"),
    ("goal", "Мета", "Goal"),
)


# Whitelist mapping: field name → safe SQL column name
_VALID_COLUMNS = {
    name: f"show_{name}" for name, _, _ in PROFILE_FIELDS
}


def ensure_user_exists(user_id: int):
    """Убедиться, что пользователь существует в БД"""
    execute_query(
        "INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING",
        (user_id,)
    )


def get_profile_visibility(user_id: int) -> dict:
    """
    Получить состояние видимости всех полей профиля
    
    Args:
        user_id: ID пользователя
        
    Returns:
        dict: {field_name: bool, ...} где True = видимо, False = скрыто
    """
    ensure_user_exists(user_id)
    
    row = fetch_one(
        """
        SELECT show_height, show_gender, show_age, show_weight, show_goal
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    if not row:
        return {field: True for field, _, _ in PROFILE_FIELDS}

    return {
        "height": bool(row[0]) if row[0] is not None else True,
        "gender": bool(row[1]) if row[1] is not None else True,
        "age": bool(row[2]) if row[2] is not None else True,
        "weight": bool(row[3]) if row[3] is not None else True,
        "goal": bool(row[4]) if row[4] is not None else True,
    }


def set_field_visibility(user_id: int, field: str, visible: bool) -> bool:
    """
    Установить видимость конкретного поля профиля
    
    Args:
        user_id: ID пользователя
        field: Название поля (height, gender, age, weight, goal)
        visible: True для показа, False для скрытия
        
    Returns:
        bool: True если успешно, False если поле неизвестно
    """
    if field not in _VALID_COLUMNS:
        return False
    
    ensure_user_exists(user_id)
    
    column = _VALID_COLUMNS[field]
    value = 1 if visible else 0
    
    execute_query(f"UPDATE users SET {column}=? WHERE user_id=?", (value, user_id))
    return True


def toggle_field_visibility(user_id: int, field: str) -> bool:
    """
    Переключить видимость конкретного поля (показать <-> скрыть)
    
    Args:
        user_id: ID пользователя
        field: Название поля
        
    Returns:
        bool: Новое значение видимости (True = видимо, False = скрыто)
    """
    if field not in _VALID_COLUMNS:
        raise ValueError(f"Unknown field: {field}")
    
    ensure_user_exists(user_id)
    
    column = _VALID_COLUMNS[field]
    
    # Получаем текущее значение
    row = fetch_one(f"SELECT {column} FROM users WHERE user_id=?", (user_id,))
    current_value = bool(row[0]) if row and row[0] is not None else True
    new_value = 0 if current_value else 1
    
    # Обновляем - используем параметризованный запрос
    execute_query(f"UPDATE users SET {column}=? WHERE user_id=?", (new_value, user_id))
    
    return bool(new_value)


def set_all_visible(user_id: int):
    """Показать все поля профиля"""
    ensure_user_exists(user_id)
    
    for field, _, _ in PROFILE_FIELDS:
        set_field_visibility(user_id, field, True)


def hide_all_fields(user_id: int):
    """Скрыть все поля профиля"""
    ensure_user_exists(user_id)
    
    for field, _, _ in PROFILE_FIELDS:
        set_field_visibility(user_id, field, False)


def get_visible_fields(user_id: int) -> list[str]:
    """
    Получить список видимых полей
    
    Returns:
        list: Названия видимых полей
    """
    visibility = get_profile_visibility(user_id)
    return [field for field, visible in visibility.items() if visible]


def is_field_visible(user_id: int, field: str) -> bool:
    """Проверить, видимо ли конкретное поле"""
    visibility = get_profile_visibility(user_id)
    return visibility.get(field, True)


def get_field_label(field: str, lang: str = "uk") -> str:
    """
    Получить метку поля для отображения
    
    Args:
        field: Название поля
        lang: Язык (uk/en)
        
    Returns:
        str: Метка поля
    """
    for field_name, uk_label, en_label in PROFILE_FIELDS:
        if field_name == field:
            return uk_label if lang == "uk" else en_label
    return field
