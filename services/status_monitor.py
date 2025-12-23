"""Мониторинг статуса Bitrix24."""

import time
import threading
import logging
from datetime import datetime
from typing import Optional, Dict
from telebot import TeleBot

from services.bitrix_parser import BitrixStatusParser
from services.subscriber_manager import SubscriberManager
from services.metrics_collector import MetricsCollector
from services.incident_tracker import IncidentTracker
from utils.time_utils import get_msk_time, format_duration
from utils.message_formatter import format_status_message, create_status_button
from time import time as current_time

logger = logging.getLogger(__name__)


class StatusMonitor:
    """Класс для мониторинга статуса Bitrix24."""
    
    def __init__(
        self,
        bot: TeleBot,
        parser: BitrixStatusParser,
        config,
        subscriber_manager: SubscriberManager,
        metrics_collector: MetricsCollector,
        incident_tracker: IncidentTracker
    ):
        """
        Инициализирует монитор статуса.
        
        Args:
            bot: Экземпляр Telegram бота
            parser: Парсер статуса Bitrix24
            config: Конфигурация бота
            subscriber_manager: Менеджер подписчиков
            metrics_collector: Сборщик метрик
            incident_tracker: Трекер инцидентов
        """
        self.bot = bot
        self.parser = parser
        self.config = config
        self.subscriber_manager = subscriber_manager
        self.metrics_collector = metrics_collector
        self.incident_tracker = incident_tracker
        
        self.previous_status: Optional[Dict] = None
        self.alert_message_ids: Dict[int, Optional[int]] = {}  # {group_id: message_id}
        self.issue_start_time: Optional[datetime] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.monitoring_enabled = True
        
        # Ошибки для мониторинга здоровья
        self.consecutive_errors = 0
        self.last_successful_check: Optional[datetime] = None
    
    def _send_or_edit_group_message(self, group_id: int, message_id: Optional[int] = None, message: str = "") -> Optional[int]:
        """
        Отправляет новое сообщение или редактирует существующее в группе.
        
        Args:
            group_id: ID группы для отправки
            message_id: ID сообщения для редактирования (None для нового)
            message: Текст сообщения
            
        Returns:
            Optional[int]: ID отправленного/отредактированного сообщения или None при ошибке
        """
        try:
            if message_id is None:
                sent = self.bot.send_message(
                    group_id,
                    message,
                    parse_mode='MarkdownV2',
                    reply_markup=create_status_button()
                )
                logger.info(f"📢 Сообщение с кнопкой отправлено в группу {group_id}")
                return sent.message_id
            else:
                self.bot.edit_message_text(
                    chat_id=group_id,
                    message_id=message_id,
                    text=message,
                    parse_mode='MarkdownV2',
                    reply_markup=create_status_button()
                )
                logger.info(f"🔄 Сообщение в группе {group_id} обновлено")
                return message_id
        except Exception as e:
            logger.error(f"❌ Ошибка отправки/редактирования сообщения в группу {group_id}: {e}")
            return None
    
    def _send_to_all_groups(self, message_id_dict: Dict[int, Optional[int]], message: str, is_new: bool = False) -> Dict[int, Optional[int]]:
        """
        Отправляет сообщение во все группы.
        
        Args:
            message_id_dict: Словарь {group_id: message_id}
            message: Текст сообщения
            is_new: Новое сообщение или обновление
            
        Returns:
            Dict[int, Optional[int]]: Обновленный словарь message_id
        """
        groups = self.config.get_alert_groups()
        updated_dict = {}
        
        for group_id in groups:
            msg_id = message_id_dict.get(group_id) if not is_new else None
            new_msg_id = self._send_or_edit_group_message(group_id, msg_id, message)
            updated_dict[group_id] = new_msg_id
        
        return updated_dict
    
    def _monitor_loop(self) -> None:
        """Основной цикл мониторинга."""
        first_check = True
        
        logger.info("Мониторинг статуса запущен")
        
        while self.is_running:
            if not self.monitoring_enabled:
                time.sleep(60)  # Проверяем каждую минуту, если мониторинг отключен
                continue
            
            try:
                parse_start = current_time()
                current_status = self.parser.parse_status()
                parse_duration = current_time() - parse_start
                
                # Записываем метрику проверки
                self.metrics_collector.record_check(parse_duration, not current_status.get('error'))
                
                if current_status.get('error'):
                    self.consecutive_errors += 1
                    logger.warning(f"Ошибка при получении статуса: {current_status.get('message')}")
                    
                    # Отправляем предупреждение админу при множественных ошибках
                    if self.consecutive_errors >= 5 and self.config.ADMIN_CHAT_ID:
                        try:
                            self.bot.send_message(
                                self.config.ADMIN_CHAT_ID,
                                f"⚠️ *Предупреждение:* Бот не может получить статус Bitrix24\\.\n"
                                f"Ошибок подряд: `{self.consecutive_errors}`\n"
                                f"Последняя ошибка: `{current_status.get('message')}`",
                                parse_mode='MarkdownV2'
                            )
                        except:
                            pass
                    
                    time.sleep(self.config.CHECK_INTERVAL)
                    continue
                
                # Успешная проверка
                self.consecutive_errors = 0
                self.last_successful_check = get_msk_time()
                
                if first_check:
                    # При первом запуске отправляем алерт только если есть сбой
                    if current_status.get('has_issues') and self.config.ALERT_ON_ISSUES:
                        self.issue_start_time = get_msk_time()
                        self.incident_tracker.start_incident(
                            description=current_status.get('description', ''),
                            region=current_status.get('region', '')
                        )
                        message = format_status_message(
                            current_status,
                            self.config.URL,
                            is_alert=True,
                            start_time=self.issue_start_time
                        )
                        self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
                        self.metrics_collector.record_alert()
                        logger.info(f"[{get_msk_time()}] Отправлен начальный алерт о проблемах")
                    else:
                        logger.info(f"[{get_msk_time()}] Статус в норме, алерт не требуется")
                    
                    self.previous_status = current_status
                    first_check = False
                else:
                    # Проверяем, изменился ли статус
                    if self.previous_status is not None:
                        # Если появились проблемы (было OK, стало СБОЙ)
                        if not self.previous_status.get('has_issues') and current_status.get('has_issues'):
                            if self.config.ALERT_ON_ISSUES:
                                self.issue_start_time = get_msk_time()
                                self.incident_tracker.start_incident(
                                    description=current_status.get('description', ''),
                                    region=current_status.get('region', '')
                                )
                                message = format_status_message(
                                    current_status,
                                    self.config.URL,
                                    is_alert=True,
                                    start_time=self.issue_start_time
                                )
                                self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
                                self.metrics_collector.record_alert()
                                logger.info(f"[{get_msk_time()}] Отправлен алерт о проблемах")
                        
                        # Если проблемы устранены (было СБОЙ, стало OK)
                        elif self.previous_status.get('has_issues') and not current_status.get('has_issues'):
                            if self.config.ALERT_ON_RECOVERY:
                                incident = self.incident_tracker.end_incident()
                                duration = format_duration(self.issue_start_time) if self.issue_start_time else None
                                message = format_status_message(
                                    current_status,
                                    self.config.URL,
                                    is_alert=True,
                                    start_time=self.issue_start_time,
                                    duration=duration
                                )
                                self.alert_message_ids = self._send_to_all_groups(
                                    self.alert_message_ids,
                                    message,
                                    is_new=False
                                )
                                self.metrics_collector.record_recovery()
                                logger.info(f"[{get_msk_time()}] Отправлен алерт о восстановлении")
                            self.alert_message_ids = {}
                            self.issue_start_time = None
                        
                        # Если всё ещё сбой - обновляем сообщение с таймером
                        elif self.previous_status.get('has_issues') and current_status.get('has_issues'):
                            if self.alert_message_ids and self.issue_start_time:
                                duration = format_duration(self.issue_start_time)
                                message = format_status_message(
                                    current_status,
                                    self.config.URL,
                                    is_alert=True,
                                    start_time=self.issue_start_time,
                                    duration=duration
                                )
                                self.alert_message_ids = self._send_to_all_groups(
                                    self.alert_message_ids,
                                    message,
                                    is_new=False
                                )
                    
                    self.previous_status = current_status
                
            except Exception as e:
                logger.error(f"[{get_msk_time()}] Ошибка в мониторинге: {e}", exc_info=True)
                self.consecutive_errors += 1
            
            time.sleep(self.config.CHECK_INTERVAL)
    
    def start(self) -> None:
        """Запускает мониторинг в отдельном потоке."""
        if self.is_running:
            logger.warning("Мониторинг уже запущен")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Мониторинг статуса запущен в отдельном потоке")
    
    def stop(self) -> None:
        """Останавливает мониторинг."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Мониторинг статуса остановлен")
    
    def get_metrics(self) -> Dict:
        """
        Возвращает метрики мониторинга.
        
        Returns:
            dict: Словарь с метриками
        """
        return self.metrics_collector.get_metrics()
    
    def toggle_monitoring(self, enabled: bool) -> None:
        """
        Включает/выключает мониторинг.
        
        Args:
            enabled: Включить мониторинг
        """
        self.monitoring_enabled = enabled
        logger.info(f"Мониторинг {'включен' if enabled else 'выключен'}")
    
    def get_health_status(self) -> Dict:
        """
        Возвращает статус здоровья бота.
        
        Returns:
            dict: Словарь со статусом здоровья
        """
        try:
            # Проверяем подключение к Telegram API
            bot_info = self.bot.get_me()
            telegram_status = "✅ OK" if bot_info else "❌ Ошибка"
        except Exception as e:
            telegram_status = f"❌ Ошибка: {str(e)[:50]}"
        
        # Проверяем доступность URL
        url_available = self.parser._check_url_availability()
        url_status = "✅ Доступен" if url_available else "❌ Недоступен"
        
        metrics = self.metrics_collector.get_metrics()
        
        return {
            'telegram_api': telegram_status,
            'bitrix_url': url_status,
            'last_successful_check': self.last_successful_check.isoformat() if self.last_successful_check else None,
            'errors_last_hour': metrics.get('errors_last_hour', 0),
            'consecutive_errors': self.consecutive_errors,
            'monitoring_enabled': self.monitoring_enabled
        }

