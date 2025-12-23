"""Управление базой данных SQLite."""

import aiosqlite
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    """Класс для управления базой данных SQLite."""
    
    def __init__(self, db_path: str = 'data/bot.db'):
        """
        Инициализирует подключение к базе данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        
        # Создаем директорию если нужно
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Создана директория для БД: {db_dir}")
    
    async def connect(self) -> None:
        """Устанавливает подключение к базе данных."""
        if self.connection is None:
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row
            await self.init_tables()
            logger.info("Подключение к БД установлено")
    
    async def close(self) -> None:
        """Закрывает подключение к базе данных."""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("Подключение к БД закрыто")
    
    async def init_tables(self) -> None:
        """Инициализирует таблицы в базе данных."""
        if not self.connection:
            await self.connect()
        
        # Таблица подписчиков
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id INTEGER PRIMARY KEY,
                subscribed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        
        # Таблица инцидентов
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration TEXT,
                description TEXT,
                region TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                components TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        
        # Индексы для быстрого поиска
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_incidents_start_time 
            ON incidents(start_time DESC)
        ''')
        
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_incidents_status 
            ON incidents(status)
        ''')
        
        await self.connection.commit()
        logger.info("Таблицы БД инициализированы")
    
    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """
        Выполняет SQL запрос.
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            Cursor: Курсор с результатами
        """
        if not self.connection:
            await self.connect()
        
        return await self.connection.execute(query, params)
    
    async def executemany(self, query: str, params_list: list) -> None:
        """
        Выполняет SQL запрос с множественными параметрами.
        
        Args:
            query: SQL запрос
            params_list: Список параметров
        """
        if not self.connection:
            await self.connect()
        
        await self.connection.executemany(query, params_list)
        await self.connection.commit()
    
    async def commit(self) -> None:
        """Сохраняет изменения в базе данных."""
        if self.connection:
            await self.connection.commit()
    
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """
        Выполняет запрос и возвращает одну строку.
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            Optional[Row]: Строка результата или None
        """
        cursor = await self.execute(query, params)
        return await cursor.fetchone()
    
    async def fetchall(self, query: str, params: tuple = ()) -> list:
        """
        Выполняет запрос и возвращает все строки.
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            list: Список строк результатов
        """
        cursor = await self.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


