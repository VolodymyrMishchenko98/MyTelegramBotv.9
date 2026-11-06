"""
Модуль дедупликации команд для избежания повторного выполнения.
Некоторые Telegram клиенты могут отправлять одно обновление несколько раз.
"""

_duplicate_cmd_cache: dict[int, tuple[int, float]] = {}
_DUPLICATE_TTL_SEC = 10


def is_duplicate_command(user_id: int, message_id: int) -> bool:
    """
    Проверить, является ли это обновление дубликатом недавно полученного.
    
    Args:
        user_id: ID пользователя
        message_id: ID сообщения
        
    Returns:
        bool: True если это дубликат, False если новое сообщение
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
