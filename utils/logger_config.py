"""Настройка логирования для бота."""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str = 'INFO', log_file: str = 'bot.log') -> None:
    """
    Настраивает логирование для бота.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов
    """
    # Создаем директорию для логов если нужно
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Настраиваем формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Получаем уровень логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Удаляем существующие обработчики
    root_logger.handlers.clear()
    
    # Обработчик для файла (с ротацией)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Настраиваем уровень логирования для внешних библиотек
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telebot').setLevel(logging.WARNING)

