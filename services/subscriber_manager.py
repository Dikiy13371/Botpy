"""Управление подписчиками бота."""

import json
import os
import logging
from typing import Set

logger = logging.getLogger(__name__)


class SubscriberManager:
    """Класс для управления подписчиками бота."""
    
    def __init__(self, subscribers_file: str):
        """
        Инициализирует менеджер подписчиков.
        
        Args:
            subscribers_file: Путь к файлу с подписчиками
        """
        self.subscribers_file = subscribers_file
        self.subscribers: Set[int] = set()
        self.load_subscribers()
    
    def load_subscribers(self) -> None:
        """Загружает список подписчиков из файла."""
        # Создаем директорию если нужно
        subscribers_dir = os.path.dirname(self.subscribers_file)
        if subscribers_dir and not os.path.exists(subscribers_dir):
            os.makedirs(subscribers_dir, exist_ok=True)
            logger.info(f"Создана директория для подписчиков: {subscribers_dir}")
        
        if os.path.exists(self.subscribers_file):
            try:
                with open(self.subscribers_file, 'r', encoding='utf-8') as f:
                    self.subscribers = set(json.load(f))
                logger.info(f"📋 Загружено {len(self.subscribers)} подписчиков")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON файла подписчиков: {e}")
                self.subscribers = set()
            except Exception as e:
                logger.error(f"Ошибка загрузки подписчиков: {e}")
                self.subscribers = set()
        else:
            logger.info("Файл подписчиков не найден, создан новый список")
            self.subscribers = set()
    
    def save_subscribers(self) -> None:
        """Сохраняет список подписчиков в файл."""
        try:
            with open(self.subscribers_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.subscribers), f, ensure_ascii=False, indent=2)
            logger.debug(f"Сохранено {len(self.subscribers)} подписчиков")
        except Exception as e:
            logger.error(f"Ошибка сохранения подписчиков: {e}")
    
    def add_subscriber(self, chat_id: int) -> bool:
        """
        Добавляет подписчика.
        
        Args:
            chat_id: ID чата подписчика
            
        Returns:
            bool: True если подписчик был добавлен, False если уже был подписан
        """
        if chat_id not in self.subscribers:
            self.subscribers.add(chat_id)
            self.save_subscribers()
            logger.info(f"Добавлен подписчик: {chat_id}")
            return True
        return False
    
    def remove_subscriber(self, chat_id: int) -> bool:
        """
        Удаляет подписчика.
        
        Args:
            chat_id: ID чата подписчика
            
        Returns:
            bool: True если подписчик был удален, False если не был подписан
        """
        if chat_id in self.subscribers:
            self.subscribers.remove(chat_id)
            self.save_subscribers()
            logger.info(f"Удален подписчик: {chat_id}")
            return True
        return False
    
    def is_subscribed(self, chat_id: int) -> bool:
        """
        Проверяет, подписан ли пользователь.
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если подписан
        """
        return chat_id in self.subscribers
    
    def get_count(self) -> int:
        """
        Возвращает количество подписчиков.
        
        Returns:
            int: Количество подписчиков
        """
        return len(self.subscribers)
    
    def get_all(self) -> Set[int]:
        """
        Возвращает множество всех подписчиков.
        
        Returns:
            Set[int]: Множество ID подписчиков
        """
        return self.subscribers.copy()

