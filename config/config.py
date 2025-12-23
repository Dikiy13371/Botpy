"""Configuration management with environment variables support."""

import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


class BotConfig:
    """Класс для управления конфигурацией бота."""
    
    def __init__(self):
        """Инициализирует конфигурацию из переменных окружения или значений по умолчанию."""
        self.BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
        self.URL: str = os.getenv('URL', 'https://status.bitrix24.ru/')
        self.CHECK_INTERVAL: int = int(os.getenv('CHECK_INTERVAL', '300'))
        self.GROUP_ID: Optional[int] = self._parse_group_id(os.getenv('GROUP_ID'))
        self.GROUP_IDS: List[int] = self._parse_group_ids(os.getenv('GROUP_IDS'))
        # По умолчанию используем data/ и logs/ для Docker, но можно переопределить через .env
        self.SUBSCRIBERS_FILE: str = os.getenv('SUBSCRIBERS_FILE', 'data/subscribers.json')
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')
        self.REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', '10'))
        self.RETRY_ATTEMPTS: int = int(os.getenv('RETRY_ATTEMPTS', '3'))
        self.RETRY_DELAY: int = int(os.getenv('RETRY_DELAY', '5'))
        
        # Фильтры алертов
        self.ALERT_ON_ISSUES: bool = os.getenv('ALERT_ON_ISSUES', 'true').lower() == 'true'
        self.ALERT_ON_RECOVERY: bool = os.getenv('ALERT_ON_RECOVERY', 'true').lower() == 'true'
        
        # Кэширование
        self.CACHE_TTL: int = int(os.getenv('CACHE_TTL', '30'))
        
        # Мониторинг здоровья
        self.HEALTH_CHECK_INTERVAL: int = int(os.getenv('HEALTH_CHECK_INTERVAL', '3600'))
        self.ADMIN_CHAT_ID: Optional[int] = self._parse_group_id(os.getenv('ADMIN_CHAT_ID'))
        
    def _parse_group_id(self, value: Optional[str]) -> Optional[int]:
        """Парсит GROUP_ID из строки в int."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except ValueError:
            return None
    
    def _parse_group_ids(self, value: Optional[str]) -> List[int]:
        """Парсит список GROUP_IDS из строки (разделенные запятыми)."""
        if value is None or value == '':
            return []
        try:
            return [int(x.strip()) for x in value.split(',') if x.strip()]
        except ValueError:
            return []
    
    def get_alert_groups(self) -> List[int]:
        """
        Возвращает список групп для отправки алертов.
        
        Returns:
            List[int]: Список ID групп
        """
        groups = []
        if self.GROUP_ID:
            groups.append(self.GROUP_ID)
        groups.extend(self.GROUP_IDS)
        return list(set(groups))  # Убираем дубликаты
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Валидирует конфигурацию.
        
        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not self.BOT_TOKEN:
            return False, "BOT_TOKEN не установлен. Установите его в .env файле или переменной окружения."
        
        # Проверяем базовый формат токена (должен содержать двоеточие)
        if ':' not in self.BOT_TOKEN:
            return False, "BOT_TOKEN имеет неверный формат. Должен содержать двоеточие (например: 123456:ABC-DEF...)."
        
        if self.CHECK_INTERVAL < 60:
            return False, "CHECK_INTERVAL должен быть не менее 60 секунд."
        
        if self.GROUP_ID is None and not self.GROUP_IDS:
            return False, "GROUP_ID или GROUP_IDS не установлены. Установите их в .env файле или переменной окружения."
        
        return True, None
    
    def __repr__(self) -> str:
        """Строковое представление конфигурации (без токена)."""
        return (
            f"BotConfig("
            f"URL={self.URL}, "
            f"CHECK_INTERVAL={self.CHECK_INTERVAL}, "
            f"GROUP_ID={self.GROUP_ID}, "
            f"SUBSCRIBERS_FILE={self.SUBSCRIBERS_FILE}, "
            f"LOG_LEVEL={self.LOG_LEVEL}"
            f")"
        )

