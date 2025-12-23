"""Управление подписчиками бота с использованием SQLite."""

import logging
from typing import Set, List
from services.database import Database

logger = logging.getLogger(__name__)
# Убеждаемся, что propagate включен (по умолчанию True)
# Это позволяет сообщениям проходить в root logger
logger.propagate = True


class SubscriberManager:
    """Класс для управления подписчиками бота с использованием SQLite."""
    
    def __init__(self, database: Database):
        """
        Инициализирует менеджер подписчиков.
        
        Args:
            database: Экземпляр базы данных
        """
        self.db = database
    
    async def add_subscriber(self, chat_id: int) -> bool:
        """
        Добавляет подписчика.
        
        Args:
            chat_id: ID чата подписчика
            
        Returns:
            bool: True если подписчик был добавлен, False если уже был подписан
        """
        try:
            # Проверяем, существует ли уже подписчик
            existing = await self.db.fetchone(
                'SELECT chat_id FROM subscribers WHERE chat_id = ?',
                (chat_id,)
            )
            
            if existing:
                return False
            
            # Добавляем нового подписчика
            await self.db.execute(
                'INSERT INTO subscribers (chat_id) VALUES (?)',
                (chat_id,)
            )
            await self.db.commit()
            logger.info(f"Добавлен подписчик: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления подписчика: {e}")
            return False
    
    async def remove_subscriber(self, chat_id: int) -> bool:
        """
        Удаляет подписчика.
        
        Args:
            chat_id: ID чата подписчика
            
        Returns:
            bool: True если подписчик был удален, False если не был подписан
        """
        try:
            cursor = await self.db.execute(
                'DELETE FROM subscribers WHERE chat_id = ?',
                (chat_id,)
            )
            await self.db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Удален подписчик: {chat_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления подписчика: {e}")
            return False
    
    async def is_subscribed(self, chat_id: int) -> bool:
        """
        Проверяет, подписан ли пользователь.
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если подписан
        """
        try:
            result = await self.db.fetchone(
                'SELECT chat_id FROM subscribers WHERE chat_id = ?',
                (chat_id,)
            )
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False
    
    async def get_count(self) -> int:
        """
        Возвращает количество подписчиков.
        
        Returns:
            int: Количество подписчиков
        """
        try:
            result = await self.db.fetchone('SELECT COUNT(*) as count FROM subscribers')
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Ошибка получения количества подписчиков: {e}")
            return 0
    
    async def get_all(self) -> Set[int]:
        """
        Возвращает множество всех подписчиков.
        
        Returns:
            Set[int]: Множество ID подписчиков
        """
        try:
            rows = await self.db.fetchall('SELECT chat_id FROM subscribers')
            return {row['chat_id'] for row in rows}
        except Exception as e:
            logger.error(f"Ошибка получения списка подписчиков: {e}")
            return set()
    
    async def load_subscribers(self) -> None:
        """Загружает список подписчиков (для совместимости)."""
        count = await self.get_count()
        logger.info(f"📋 Загружено {count} подписчиков из БД")
