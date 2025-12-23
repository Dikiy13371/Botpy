"""Дедупликация алертов для предотвращения спама одинаковых уведомлений."""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from time import time as current_time

logger = logging.getLogger(__name__)


class AlertDeduplicator:
    """Предотвращает отправку дублирующихся алертов."""
    
    def __init__(self, dedup_window: int = 300, group_interval: int = 30):
        """
        Инициализирует дедупликатор алертов.
        
        Args:
            dedup_window: Окно дедупликации в секундах (не отправлять одинаковые алерты чаще)
            group_interval: Интервал группировки компонентов в секундах
        """
        self.dedup_window = dedup_window
        self.group_interval = group_interval
        
        # Хранилище последних алертов: {alert_hash: (timestamp, count)}
        self._alert_history: Dict[str, Tuple[float, int]] = {}
        
        # Очистка старых записей каждые 10 минут
        self._last_cleanup = current_time()
        self._cleanup_interval = 600  # 10 минут
    
    def _generate_alert_hash(
        self, 
        region: str, 
        status: str, 
        components: List[str]
    ) -> str:
        """
        Генерирует хеш для идентификации алерта.
        
        Args:
            region: Регион инцидента (ru, com, eu и т.д.)
            status: Статус ('down' для сбоя, 'up' для восстановления)
            components: Список затронутых компонентов
        
        Returns:
            str: Хеш алерта
        """
        # Сортируем компоненты для консистентности
        sorted_components = sorted(components) if components else []
        components_str = ','.join(sorted_components)
        
        # Создаем уникальный ключ
        alert_key = f"{region}|{status}|{components_str}"
        
        # Генерируем хеш
        return hashlib.md5(alert_key.encode('utf-8')).hexdigest()
    
    async def should_send_alert(
        self,
        components: List[str],
        status: str,
        region: str
    ) -> bool:
        """
        Проверяет, нужно ли отправлять алерт.
        
        Правила:
        - Не отправлять если идентичный алерт был менее DEDUP_WINDOW секунд назад
        - Сравнивать: регион + статус + отсортированные компоненты
        - Для восстановления (status="up") всегда отправлять
        
        Args:
            components: Список затронутых компонентов
            status: Статус ('down' для сбоя, 'up' для восстановления)
            region: Регион инцидента
        
        Returns:
            bool: True если нужно отправить алерт, False если это дубликат
        """
        try:
            # Всегда отправляем уведомления о восстановлении
            if status == 'up':
                logger.debug(f"Alert allowed (recovery): region={region}, status={status}")
                return True
            
            # Очищаем старые записи периодически
            await self._cleanup_old_alerts()
            
            # Генерируем хеш алерта
            alert_hash = self._generate_alert_hash(region, status, components)
            
            # Проверяем историю
            now = current_time()
            if alert_hash in self._alert_history:
                last_time, count = self._alert_history[alert_hash]
                time_diff = now - last_time
                
                if time_diff < self.dedup_window:
                    # Это дубликат
                    self._alert_history[alert_hash] = (last_time, count + 1)
                    logger.info(
                        f"Alert skipped (duplicate): region={region}, "
                        f"status={status}, components={components}, "
                        f"last_sent={time_diff:.1f}s ago, count={count + 1}"
                    )
                    return False
            
            # Новый алерт или прошло достаточно времени
            self._alert_history[alert_hash] = (now, 1)
            logger.info(
                f"Alert allowed: region={region}, status={status}, "
                f"components={components}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error in should_send_alert: {e}", exc_info=True)
            # В случае ошибки разрешаем отправку (graceful degradation)
            return True
    
    async def _cleanup_old_alerts(self) -> None:
        """Удаляет старые записи из истории алертов."""
        try:
            now = current_time()
            
            # Очищаем только если прошло достаточно времени
            if now - self._last_cleanup < self._cleanup_interval:
                return
            
            # Удаляем записи старше dedup_window * 2
            cutoff_time = now - (self.dedup_window * 2)
            keys_to_remove = [
                key for key, (timestamp, _) in self._alert_history.items()
                if timestamp < cutoff_time
            ]
            
            for key in keys_to_remove:
                del self._alert_history[key]
            
            if keys_to_remove:
                logger.debug(f"Cleaned up {len(keys_to_remove)} old alert records")
            
            self._last_cleanup = now
            
        except Exception as e:
            logger.error(f"Error cleaning up alert history: {e}", exc_info=True)
    
    async def get_alert_summary(self, alert_hash: str) -> Optional[str]:
        """
        Возвращает информацию о том, сколько раз был этот алерт.
        
        Args:
            alert_hash: Хеш алерта
        
        Returns:
            Optional[str]: Информация об алерте или None если не найден
        """
        try:
            if alert_hash not in self._alert_history:
                return None
            
            timestamp, count = self._alert_history[alert_hash]
            time_diff = current_time() - timestamp
            time_str = f"{int(time_diff)}s ago" if time_diff < 60 else f"{int(time_diff / 60)}m ago"
            
            return f"Alert sent {count} time(s), last: {time_str}"
            
        except Exception as e:
            logger.error(f"Error getting alert summary: {e}", exc_info=True)
            return None
    
    def get_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику дедупликатора.
        
        Returns:
            Dict[str, int]: Статистика (total_alerts, unique_alerts)
        """
        try:
            total_count = sum(count for _, count in self._alert_history.values())
            unique_count = len(self._alert_history)
            
            return {
                'total_alerts': total_count,
                'unique_alerts': unique_count,
                'duplicates_prevented': total_count - unique_count
            }
        except Exception as e:
            logger.error(f"Error getting deduplicator stats: {e}", exc_info=True)
            return {'total_alerts': 0, 'unique_alerts': 0, 'duplicates_prevented': 0}

