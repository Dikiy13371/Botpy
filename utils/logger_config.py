"""Настройка логирования для бота."""

import logging
import os
from logging.handlers import RotatingFileHandler


# Флаг для предотвращения повторной инициализации
_logging_configured = False

def setup_logging(log_level: str = 'INFO', log_file: str = 'bot.log') -> None:
    """
    Настраивает логирование для бота.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов
    """
    global _logging_configured
    
    # Если логирование уже настроено, не настраиваем повторно
    if _logging_configured:
        return
    
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
    
    # Удаляем ВСЕ существующие обработчики
    # Важно: делаем это до добавления новых обработчиков
    while root_logger.handlers:
        handler = root_logger.handlers[0]
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    
    # Убеждаемся, что список обработчиков пуст
    root_logger.handlers = []
    
    # Проверяем, что обработчиков действительно нет
    if root_logger.handlers:
        # Если обработчики все еще есть, принудительно очищаем
        root_logger.handlers.clear()
    
    # Обработчик для файла (с ротацией)
    if log_file:
        # Убеждаемся, что нет файловых обработчиков перед добавлением
        # Удаляем все существующие RotatingFileHandler
        file_handlers_to_remove = []
        for handler in root_logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                file_handlers_to_remove.append(handler)
        
        for handler in file_handlers_to_remove:
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        
        # Теперь добавляем новый файловый обработчик
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
    # Убеждаемся, что нет консольных обработчиков перед добавлением
    # Удаляем все существующие StreamHandler (но не RotatingFileHandler)
    console_handlers_to_remove = []
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
            console_handlers_to_remove.append(handler)
    
    for handler in console_handlers_to_remove:
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    
    # Теперь добавляем новый консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Настраиваем уровень логирования для внешних библиотек
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telebot').setLevel(logging.WARNING)
    
    # Убеждаемся, что дочерние логгеры используют propagate=True (по умолчанию)
    # Это позволяет сообщениям проходить в root logger
    # НО важно: дочерние логгеры НЕ должны иметь своих обработчиков,
    # иначе будет дублирование
    
    # Помечаем, что логирование настроено
    _logging_configured = True
    
    # Финальная проверка: убеждаемся, что обработчики добавлены только один раз
    final_handlers_count = len(root_logger.handlers)
    file_handlers_count = sum(1 for h in root_logger.handlers if isinstance(h, RotatingFileHandler))
    console_handlers_count = sum(1 for h in root_logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler))
    
    # Если обработчиков больше чем нужно, удаляем дубликаты
    if file_handlers_count > 1:
        # Оставляем только первый файловый обработчик
        file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]
        for handler in file_handlers[1:]:  # Удаляем все кроме первого
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    
    if console_handlers_count > 1:
        # Оставляем только первый консольный обработчик
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)]
        for handler in console_handlers[1:]:  # Удаляем все кроме первого
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

