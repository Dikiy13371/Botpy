"""Утилиты для работы со временем."""

from datetime import datetime
import pytz


def get_msk_time() -> datetime:
    """
    Возвращает текущее время по московскому времени (МСК).
    
    Returns:
        datetime: Текущее время в таймзоне МСК
    """
    msk = pytz.timezone('Europe/Moscow')
    return datetime.now(msk)


def format_duration(start_time: datetime) -> str:
    """
    Форматирует длительность в формат ЧЧ:ММ:СС.
    
    Args:
        start_time: Время начала события
        
    Returns:
        str: Отформатированная длительность в формате ЧЧ:ММ:СС
    """
    now = get_msk_time()
    duration = now - start_time
    seconds = duration.total_seconds()
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


