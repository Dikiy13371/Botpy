"""Сбор и хранение метрик бота."""

import json
import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional
from utils.time_utils import get_msk_time

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Класс для сбора и хранения метрик бота."""
    
    def __init__(self, metrics_file: str = 'data/metrics.json'):
        """
        Инициализирует сборщик метрик.
        
        Args:
            metrics_file: Путь к файлу с метриками
        """
        self.metrics_file = metrics_file
        self.start_time = get_msk_time()
        self.metrics = self._load_metrics()
        
        # Создаем директорию если нужно
        metrics_dir = os.path.dirname(self.metrics_file)
        if metrics_dir and not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir, exist_ok=True)
    
    def _load_metrics(self) -> Dict:
        """Загружает метрики из файла."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
                logger.info("Метрики загружены из файла")
                return metrics
            except Exception as e:
                logger.error(f"Ошибка загрузки метрик: {e}")
        
        # Инициализация метрик по умолчанию
        return {
            'start_time': self.start_time.isoformat(),
            'uptime_seconds': 0,
            'alerts_sent': 0,
            'recoveries_sent': 0,
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'last_check_time': None,
            'last_check_duration': None,
            'average_parse_time': 0,
            'parse_times': [],
            'errors_last_hour': 0,
            'errors_timestamps': [],
            'last_error_time': None
        }
    
    def _save_metrics(self) -> None:
        """Сохраняет метрики в файл."""
        try:
            # Обновляем uptime
            uptime = get_msk_time() - self.start_time
            self.metrics['uptime_seconds'] = int(uptime.total_seconds())
            
            # Очищаем старые ошибки (старше часа)
            self._clean_old_errors()
            
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
            logger.debug("Метрики сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик: {e}")
    
    def _clean_old_errors(self) -> None:
        """Удаляет ошибки старше часа."""
        now = time.time()
        hour_ago = now - 3600
        self.metrics['errors_timestamps'] = [
            ts for ts in self.metrics['errors_timestamps'] if ts > hour_ago
        ]
        self.metrics['errors_last_hour'] = len(self.metrics['errors_timestamps'])
    
    def record_check(self, duration: float, success: bool = True) -> None:
        """
        Записывает информацию о проверке статуса.
        
        Args:
            duration: Время парсинга в секундах
            success: Успешна ли проверка
        """
        self.metrics['total_checks'] += 1
        self.metrics['last_check_time'] = get_msk_time().isoformat()
        self.metrics['last_check_duration'] = duration
        
        if success:
            self.metrics['successful_checks'] += 1
            # Сохраняем время парсинга для расчета среднего
            self.metrics['parse_times'].append(duration)
            # Оставляем только последние 100 значений
            if len(self.metrics['parse_times']) > 100:
                self.metrics['parse_times'] = self.metrics['parse_times'][-100:]
            
            # Рассчитываем среднее время
            if self.metrics['parse_times']:
                self.metrics['average_parse_time'] = sum(self.metrics['parse_times']) / len(self.metrics['parse_times'])
        else:
            self.metrics['failed_checks'] += 1
            self.metrics['errors_timestamps'].append(time.time())
            self.metrics['last_error_time'] = get_msk_time().isoformat()
            self._clean_old_errors()
        
        self._save_metrics()
    
    def record_alert(self) -> None:
        """Записывает отправку алерта о проблеме."""
        self.metrics['alerts_sent'] += 1
        self._save_metrics()
    
    def record_recovery(self) -> None:
        """Записывает отправку уведомления о восстановлении."""
        self.metrics['recoveries_sent'] += 1
        self._save_metrics()
    
    def get_metrics(self) -> Dict:
        """
        Возвращает текущие метрики.
        
        Returns:
            dict: Словарь с метриками
        """
        uptime = get_msk_time() - self.start_time
        self.metrics['uptime_seconds'] = int(uptime.total_seconds())
        self._clean_old_errors()
        
        return self.metrics.copy()
    
    def get_uptime_formatted(self) -> str:
        """
        Возвращает отформатированное время работы.
        
        Returns:
            str: Время работы в формате "X дней, Y часов, Z минут"
        """
        uptime = get_msk_time() - self.start_time
        total_seconds = int(uptime.total_seconds())
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} дн.")
        if hours > 0:
            parts.append(f"{hours} ч.")
        if minutes > 0 or not parts:
            parts.append(f"{minutes} мин.")
        
        return ", ".join(parts)

