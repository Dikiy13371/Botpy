"""Мониторинг статуса Bitrix24."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from config.config import BotConfig
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException

from services.bitrix_parser import BitrixStatusParser
from services.subscriber_manager import SubscriberManager
from services.metrics_collector import MetricsCollector
from services.incident_tracker import IncidentTracker
from services.alert_deduplicator import AlertDeduplicator
from utils.time_utils import get_msk_time, format_duration
from utils.message_formatter import format_status_message, create_status_button, create_alert_buttons
from time import time as current_time

logger = logging.getLogger(__name__)

# Константы
MONITORING_CHECK_INTERVAL_DISABLED = 60  # секунд - интервал проверки, когда мониторинг отключен
RECENT_INCIDENT_THRESHOLD_HOURS = 24  # часов - порог для "недавнего" инцидента
ADMIN_ALERT_ERROR_THRESHOLD = 5  # количество ошибок подряд для отправки алерта админу


class StatusMonitor:
    """Класс для мониторинга статуса Bitrix24."""
    
    def __init__(
        self,
        bot: TeleBot,
        parser: BitrixStatusParser,
        config: 'BotConfig',  # Forward reference для избежания циклического импорта
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
        
        # Инициализируем дедупликатор алертов
        self.deduplicator = AlertDeduplicator(
            dedup_window=self.config.DEDUP_WINDOW,
            group_interval=self.config.GROUP_INTERVAL
        )
        logger.info(
            f"Дедупликатор алертов инициализирован: "
            f"DEDUP_WINDOW={self.config.DEDUP_WINDOW}s, "
            f"GROUP_INTERVAL={self.config.GROUP_INTERVAL}s"
        )
        
        self.previous_status: Optional[Dict] = None
        self.alert_message_ids: Dict[int, Optional[int]] = {}  # {group_id: message_id}
        self.issue_start_time: Optional[datetime] = None
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.monitoring_enabled = True
        
        # Ошибки для мониторинга здоровья
        self.consecutive_errors = 0
        self.last_successful_check: Optional[datetime] = None
    
    def _send_or_edit_group_message(self, group_id: int, message_id: Optional[int] = None, message: str = "", is_new: bool = False) -> Optional[int]:
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
            # Если is_new=True, всегда отправляем новое сообщение, даже если message_id передан
            if message_id is None or is_new:
                # Используем create_alert_buttons для алертов, create_status_button для обычных сообщений
                is_alert = "АЛЕРТ" in message or "СБОЙ" in message
                markup = create_alert_buttons() if is_alert else create_status_button()
                
                sent = self.bot.send_message(
                    group_id,
                    message,
                    parse_mode='MarkdownV2',
                    reply_markup=markup
                )
                logger.info(f"📢 Сообщение с кнопкой отправлено в группу {group_id}")
                return sent.message_id
            else:
                # Используем create_alert_buttons для алертов
                is_alert = "АЛЕРТ" in message or "СБОЙ" in message or "ВОССТАНОВЛЕН" in message
                markup = create_alert_buttons() if is_alert else create_status_button()
                
                self.bot.edit_message_text(
                    chat_id=group_id,
                    message_id=message_id,
                    text=message,
                    parse_mode='MarkdownV2',
                    reply_markup=markup
                )
                logger.info(f"🔄 Сообщение в группе {group_id} обновлено")
                return message_id
        except ApiTelegramException as e:
            error_msg = str(e)
            # Специальная обработка ошибки преобразования группы в супергруппу
            if "group chat was upgraded to a supergroup chat" in error_msg or "chat not found" in error_msg.lower():
                logger.error(
                    f"❌ Группа {group_id} была преобразована в супергруппу или не найдена. "
                    f"Используйте команду /getid в новой группе для получения актуального ID."
                )
                # Пытаемся извлечь новый ID из ошибки (если Telegram его предоставляет)
                if "migrate_to_chat_id" in error_msg:
                    try:
                        import re
                        new_id_match = re.search(r'migrate_to_chat_id[":\s]+(-?\d+)', error_msg)
                        if new_id_match:
                            new_id = int(new_id_match.group(1))
                            logger.info(f"💡 Новый ID группы: {new_id}")
                    except (ValueError, AttributeError) as parse_error:
                        logger.debug(f"Не удалось извлечь новый ID группы: {parse_error}")
            else:
                logger.error(f"❌ Ошибка отправки/редактирования сообщения в группу {group_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при отправке сообщения в группу {group_id}: {e}")
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
            logger.debug(f"Отправка сообщения в группу {group_id}, is_new={is_new}, msg_id={msg_id}")
            new_msg_id = self._send_or_edit_group_message(group_id, msg_id, message, is_new=is_new)
            updated_dict[group_id] = new_msg_id
            if new_msg_id:
                logger.debug(f"✅ Сообщение успешно отправлено/обновлено в группу {group_id}, message_id={new_msg_id}")
            else:
                logger.warning(f"⚠️ Не удалось отправить/обновить сообщение в группу {group_id}")
        
        return updated_dict
    
    async def _handle_parse_error(self, current_status: Dict) -> None:
        """Обрабатывает ошибку парсинга статуса."""
        self.consecutive_errors += 1
        logger.warning(f"Ошибка при получении статуса: {current_status.get('message')}")
        
        # Отправляем предупреждение админу при множественных ошибках
        if self.consecutive_errors >= ADMIN_ALERT_ERROR_THRESHOLD and self.config.ADMIN_CHAT_ID:
            try:
                self.bot.send_message(
                    self.config.ADMIN_CHAT_ID,
                    f"⚠️ *Предупреждение:* Бот не может получить статус Bitrix24\\.\n"
                    f"Ошибок подряд: `{self.consecutive_errors}`\n"
                    f"Последняя ошибка: `{current_status.get('message')}`",
                    parse_mode='MarkdownV2'
                )
            except ApiTelegramException as e:
                logger.warning(f"Не удалось отправить предупреждение админу: {e}")
            except Exception as e:
                logger.warning(f"Неожиданная ошибка при отправке предупреждения админу: {e}")
    
    async def _handle_first_check_with_issues(
        self, 
        current_status: Dict, 
        active_incident: Optional[Dict]
    ) -> None:
        """Обрабатывает первую проверку при наличии проблем."""
        logger.info(f"[{get_msk_time()}] ✅ Обнаружен сбой при первом запуске, ALERT_ON_ISSUES={self.config.ALERT_ON_ISSUES}")
        
        if not active_incident:
            # Нет активного инцидента - создаем новый
            self.issue_start_time = get_msk_time()
            incident_id = await self.incident_tracker.start_incident(
                description=current_status.get('description', ''),
                region=current_status.get('region', ''),
                components=current_status.get('components', [])
            )
            if incident_id:
                logger.info(f"[{get_msk_time()}] Создан новый инцидент (ID: {incident_id})")
        else:
            # Есть активный инцидент - используем его время начала
            self.issue_start_time = datetime.fromisoformat(active_incident['start_time'])
            logger.info(f"[{get_msk_time()}] Используется существующий активный инцидент (ID: {active_incident['id']})")
        
        # Проверяем дедупликацию перед отправкой алерта
        region = current_status.get('region', '')
        components = current_status.get('components', [])
        should_send = await self.deduplicator.should_send_alert(
            components=components,
            status='down',
            region=region
        )
        
        if not should_send:
            logger.info(f"[{get_msk_time()}] Алерт пропущен (дубликат) при первой проверке")
            return
        
        # Отправляем алерт при первом запуске, если есть сбой
        message = format_status_message(
            current_status,
            self.config.URL,
            is_alert=True,
            start_time=self.issue_start_time
        )
        logger.info(f"[{get_msk_time()}] Подготовка к отправке алерта о проблемах в группы...")
        self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
        if self.alert_message_ids:
            self.metrics_collector.record_alert()
            logger.info(f"[{get_msk_time()}] ✅ Отправлен начальный алерт о проблемах в группы: {list(self.alert_message_ids.keys())}")
        else:
            logger.warning(f"[{get_msk_time()}] ⚠️ Не удалось отправить алерт в группы")
    
    async def _handle_first_check_recovery(self, current_status: Dict) -> None:
        """Обрабатывает восстановление при первой проверке."""
        incident = await self.incident_tracker.end_incident()
        if incident:
            self.issue_start_time = datetime.fromisoformat(incident['start_time'])
            duration = format_duration(self.issue_start_time)
            logger.info(f"[{get_msk_time()}] Завершен активный инцидент (ID: {incident['id']}), длительность: {duration}")
            
            # Отправляем алерт о восстановлении
            message = format_status_message(
                current_status,
                self.config.URL,
                is_alert=True,
                start_time=self.issue_start_time,
                duration=duration
            )
            self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
            self.metrics_collector.record_recovery()
            logger.info(f"[{get_msk_time()}] Отправлен алерт о восстановлении работы сервиса")
            self.alert_message_ids = {}
            self.issue_start_time = None
    
    async def _handle_first_check_recent_incident(self, current_status: Dict) -> None:
        """Обрабатывает недавний инцидент при первой проверке."""
        recent_incidents = await self.incident_tracker.get_recent_incidents(limit=1)
        logger.info(f"[{get_msk_time()}] Проверка недавних инцидентов: найдено {len(recent_incidents)}")
        
        if recent_incidents and recent_incidents[0].get('status') == 'resolved':
            incident_end_str = recent_incidents[0].get('end_time')
            if incident_end_str:
                incident_end = datetime.fromisoformat(incident_end_str)
                time_diff = get_msk_time() - incident_end
                logger.info(f"[{get_msk_time()}] Время с завершения инцидента: {time_diff}")
                
                threshold = timedelta(hours=RECENT_INCIDENT_THRESHOLD_HOURS)
                if time_diff < threshold and self.config.ALERT_ON_RECOVERY:
                    logger.info(f"[{get_msk_time()}] Обнаружен недавний завершенный инцидент (завершен {time_diff} назад), отправляем уведомление о восстановлении")
                    message = format_status_message(
                        current_status,
                        self.config.URL,
                        is_alert=True,
                        start_time=datetime.fromisoformat(recent_incidents[0]['start_time']),
                        duration=recent_incidents[0].get('duration', 'N/A')
                    )
                    self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
                    self.metrics_collector.record_recovery()
                    logger.info(f"[{get_msk_time()}] Отправлено уведомление о восстановлении работы сервиса")
                else:
                    logger.info(f"[{get_msk_time()}] Инцидент был завершен более {RECENT_INCIDENT_THRESHOLD_HOURS} часов назад ({time_diff}), уведомление не требуется")
            else:
                logger.info(f"[{get_msk_time()}] У завершенного инцидента нет end_time")
        else:
            logger.info(f"[{get_msk_time()}] Нет недавних завершенных инцидентов (найдено: {len(recent_incidents) if recent_incidents else 0})")
            # При первом запуске, если статус в норме, отправляем информационное сообщение
            if self.config.ALERT_ON_RECOVERY:
                logger.info(f"[{get_msk_time()}] Отправляем информационное сообщение о штатной работе сервиса")
                message = format_status_message(
                    current_status,
                    self.config.URL,
                    is_alert=False
                )
                self.alert_message_ids = self._send_to_all_groups({}, message, is_new=True)
                logger.info(f"[{get_msk_time()}] Отправлено информационное сообщение о штатной работе сервиса")
    
    async def _handle_status_change(self, current_status: Dict) -> None:
        """Обрабатывает изменение статуса (не первая проверка)."""
        if self.previous_status is None:
            return
        
        # Если появились проблемы (было OK, стало СБОЙ)
        if not self.previous_status.get('has_issues') and current_status.get('has_issues'):
            if self.config.ALERT_ON_ISSUES:
                # Проверяем дедупликацию перед отправкой алерта
                region = current_status.get('region', '')
                components = current_status.get('components', [])
                should_send = await self.deduplicator.should_send_alert(
                    components=components,
                    status='down',
                    region=region
                )
                
                if not should_send:
                    logger.info(f"[{get_msk_time()}] Алерт пропущен (дубликат) при изменении статуса")
                    # Все равно создаем инцидент в БД, но не отправляем алерт
                    await self.incident_tracker.start_incident(
                        description=current_status.get('description', ''),
                        region=region,
                        components=components
                    )
                    return
                
                self.issue_start_time = get_msk_time()
                await self.incident_tracker.start_incident(
                    description=current_status.get('description', ''),
                    region=region,
                    components=components
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
                incident = await self.incident_tracker.end_incident()
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
    
    async def _monitor_loop(self) -> None:
        """Основной цикл мониторинга."""
        first_check = True
        logger.info("Мониторинг статуса запущен")
        
        while self.is_running:
            if not self.monitoring_enabled:
                await asyncio.sleep(MONITORING_CHECK_INTERVAL_DISABLED)
                continue
            
            # При первой проверке не ждем интервал - проверяем сразу
            if not first_check:
                await asyncio.sleep(self.config.CHECK_INTERVAL)
            
            try:
                parse_start = current_time()
                current_status = await self.parser.parse_status()
                parse_duration = current_time() - parse_start
                
                # Записываем метрику проверки
                self.metrics_collector.record_check(parse_duration, not current_status.get('error'))
                
                if current_status.get('error'):
                    await self._handle_parse_error(current_status)
                    await asyncio.sleep(self.config.CHECK_INTERVAL)
                    continue
                
                # Успешная проверка
                self.consecutive_errors = 0
                self.last_successful_check = get_msk_time()
                logger.info(f"[{get_msk_time()}] Проверка статуса: has_issues={current_status.get('has_issues')}, error={current_status.get('error')}")
                
                if first_check:
                    logger.info(f"[{get_msk_time()}] 🔍 Первая проверка при запуске бота")
                    active_incident = await self.incident_tracker.get_active_incident()
                    logger.info(f"[{get_msk_time()}] Активный инцидент в БД: {active_incident is not None}")
                    
                    # Если есть сбой - отправляем алерт
                    if current_status.get('has_issues') and self.config.ALERT_ON_ISSUES:
                        await self._handle_first_check_with_issues(current_status, active_incident)
                    # Если нет сбоя, но есть активный инцидент - завершаем его
                    elif not current_status.get('has_issues') and active_incident and self.config.ALERT_ON_RECOVERY:
                        await self._handle_first_check_recovery(current_status)
                    # Если нет сбоя и нет активного инцидента - проверяем недавние инциденты
                    elif not current_status.get('has_issues'):
                        await self._handle_first_check_recent_incident(current_status)
                    elif not self.config.ALERT_ON_ISSUES:
                        logger.info(f"[{get_msk_time()}] Сбой обнаружен, но ALERT_ON_ISSUES=False, алерт не отправляется")
                    
                    self.previous_status = current_status
                    first_check = False
                else:
                    # Проверяем, изменился ли статус
                    await self._handle_status_change(current_status)
                    self.previous_status = current_status
                
            except Exception as e:
                logger.error(f"[{get_msk_time()}] Ошибка в мониторинге: {e}", exc_info=True)
                self.consecutive_errors += 1
            
            # После первой проверки ждем интервал перед следующей
            if not first_check:
                await asyncio.sleep(self.config.CHECK_INTERVAL)
    
    def start(self) -> None:
        """Запускает мониторинг в отдельном потоке с собственным event loop."""
        if self.is_running:
            logger.warning("Мониторинг уже запущен")
            return
        
        self.is_running = True
        # Всегда запускаем в отдельном потоке, т.к. bot.infinity_polling() блокирует event loop
        import threading
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._monitor_loop())
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}", exc_info=True)
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_loop, daemon=True, name="StatusMonitor")
        thread.start()
        logger.info("Мониторинг статуса запущен в отдельном потоке с event loop")
    
    async def stop_async(self) -> None:
        """Останавливает мониторинг (async версия)."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Мониторинг статуса остановлен")
    
    def stop(self) -> None:
        """Останавливает мониторинг (синхронная версия)."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
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
    
    async def get_health_status(self) -> Dict:
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
        
        # Проверяем доступность URL (async метод)
        url_available = False
        try:
            url_available = await self.parser._check_url_availability()
        except Exception as e:
            logger.debug(f"Ошибка проверки доступности URL: {e}")
        
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

