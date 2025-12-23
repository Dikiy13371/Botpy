"""Обработчики команд Telegram бота."""

import logging
import io
from datetime import datetime
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

from services.subscriber_manager import SubscriberManager
from services.bitrix_parser import BitrixStatusParser
from services.metrics_collector import MetricsCollector
from services.incident_tracker import IncidentTracker
from services.status_monitor import StatusMonitor
from utils.message_formatter import format_status_message, create_status_button, escape_url
from utils.time_utils import get_msk_time

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Класс для обработки команд бота."""
    
    def __init__(
        self,
        bot: TeleBot,
        subscriber_manager: SubscriberManager,
        parser: BitrixStatusParser,
        config,
        status_monitor: StatusMonitor,
        metrics_collector: MetricsCollector,
        incident_tracker: IncidentTracker
    ):
        """
        Инициализирует обработчики команд.
        
        Args:
            bot: Экземпляр Telegram бота
            subscriber_manager: Менеджер подписчиков
            parser: Парсер статуса Bitrix24
            config: Конфигурация бота
            status_monitor: Монитор статуса
            metrics_collector: Сборщик метрик
            incident_tracker: Трекер инцидентов
        """
        self.bot = bot
        self.subscriber_manager = subscriber_manager
        self.parser = parser
        self.config = config
        self.status_monitor = status_monitor
        self.metrics_collector = metrics_collector
        self.incident_tracker = incident_tracker
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Регистрирует все обработчики команд."""
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message: Message):
            """Обработчик команды /start"""
            self.handle_start(message)
        
        @self.bot.message_handler(commands=['help'])
        def send_help(message: Message):
            """Обработчик команды /help"""
            self.handle_help(message)
        
        @self.bot.message_handler(commands=['subscribe'])
        def subscribe(message: Message):
            """Обработчик команды /subscribe"""
            self.handle_subscribe(message)
        
        @self.bot.message_handler(commands=['unsubscribe'])
        def unsubscribe(message: Message):
            """Обработчик команды /unsubscribe"""
            self.handle_unsubscribe(message)
        
        @self.bot.message_handler(commands=['stats'])
        def show_stats(message: Message):
            """Обработчик команды /stats"""
            self.handle_stats(message)
        
        @self.bot.message_handler(commands=['status'])
        def check_status(message: Message):
            """Обработчик команды /status"""
            self.handle_status(message)
        
        @self.bot.message_handler(commands=['getid'])
        def get_id(message: Message):
            """Обработчик команды /getid"""
            self.handle_getid(message)
        
        @self.bot.message_handler(commands=['metrics'])
        def show_metrics(message: Message):
            """Обработчик команды /metrics"""
            self.handle_metrics(message)
        
        @self.bot.message_handler(commands=['incidents'])
        def show_incidents(message: Message):
            """Обработчик команды /incidents"""
            self.handle_incidents(message)
        
        @self.bot.message_handler(commands=['health'])
        def show_health(message: Message):
            """Обработчик команды /health"""
            self.handle_health(message)
        
        @self.bot.message_handler(commands=['export'])
        def export_data(message: Message):
            """Обработчик команды /export"""
            self.handle_export(message)
        
        @self.bot.message_handler(commands=['monitoring'])
        def toggle_monitoring(message: Message):
            """Обработчик команды /monitoring"""
            self.handle_monitoring(message)
        
        @self.bot.callback_query_handler(func=lambda call: call.data == "check_status")
        def callback_status(call: CallbackQuery):
            """Обработчик callback для кнопки проверки статуса"""
            self.handle_callback_status(call)
    
    def handle_start(self, message: Message) -> None:
        """Обработчик команды /start"""
        chat_id = message.chat.id
        self.subscriber_manager.add_subscriber(chat_id)
        
        welcome_text = (
            "👋 *Привет\\!* Я бот для мониторинга статуса Битрикс24\\.\n\n"
            "✅ Вы подписаны на уведомления\\!\n\n"
            "*Доступные команды:*\n"
            "• `/status` \\- Проверить текущий статус\n"
            "• `/subscribe` \\- Подписаться на уведомления\n"
            "• `/unsubscribe` \\- Отписаться от уведомлений\n"
            "• `/stats` \\- Статистика бота\n"
            "• `/metrics` \\- Подробные метрики\n"
            "• `/incidents` \\- История инцидентов\n"
            "• `/health` \\- Статус здоровья бота\n"
            "• `/export` \\- Экспорт данных в CSV\n"
            "• `/help` \\- Показать это сообщение\n\n"
            "🔔 Я автоматически буду уведомлять вас о любых сбоях и их устранении\\."
        )
        try:
            self.bot.reply_to(
                message,
                welcome_text,
                parse_mode='MarkdownV2',
                reply_markup=create_status_button()
            )
        except Exception as e:
            logger.error(f"Ошибка отправки приветственного сообщения: {e}")
    
    def handle_help(self, message: Message) -> None:
        """Обработчик команды /help"""
        self.handle_start(message)
    
    def handle_subscribe(self, message: Message) -> None:
        """Обработчик команды /subscribe"""
        chat_id = message.chat.id
        was_new = self.subscriber_manager.add_subscriber(chat_id)
        
        if was_new:
            response = "✅ Вы подписаны на уведомления о статусе Битрикс24\\!"
        else:
            response = "ℹ️ Вы уже подписаны на уведомления\\!"
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения подписки: {e}")
    
    def handle_unsubscribe(self, message: Message) -> None:
        """Обработчик команды /unsubscribe"""
        chat_id = message.chat.id
        if self.subscriber_manager.remove_subscriber(chat_id):
            response = "❌ Вы отписались от уведомлений\\."
        else:
            response = "ℹ️ Вы не были подписаны на уведомления\\."
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения отписки: {e}")
    
    def handle_stats(self, message: Message) -> None:
        """Обработчик команды /stats"""
        escaped_url = escape_url(self.config.URL)
        stats_text = (
            f"📊 *Статистика бота*\n\n"
            f"👥 Подписчиков: `{self.subscriber_manager.get_count()}`\n"
            f"⏰ Интервал проверки: `{self.config.CHECK_INTERVAL}` сек\n"
            f"🌐 Мониторинг: [status\\.bitrix24\\.ru]({escaped_url})"
        )
        try:
            self.bot.reply_to(message, stats_text, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки статистики: {e}")
    
    def handle_status(self, message: Message) -> None:
        """Обработчик команды /status"""
        try:
            self.bot.reply_to(message, "🔍 Проверяю статус Битрикс24\\.\\.\\.", parse_mode='MarkdownV2')
            
            status_info = self.parser.parse_status()
            status_message = format_status_message(status_info, self.config.URL)
            
            self.bot.send_message(
                message.chat.id,
                status_message,
                parse_mode='MarkdownV2',
                reply_markup=create_status_button()
            )
        except Exception as e:
            logger.error(f"Ошибка проверки статуса: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при проверке статуса\\. Попробуйте позже\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_getid(self, message: Message) -> None:
        """Обработчик команды /getid"""
        chat_id = message.chat.id
        chat_type = message.chat.type
        chat_title = getattr(message.chat, 'title', 'Личный чат')
        
        response = (
            f"📊 *Информация о чата:*\n\n"
            f"🆔 *ID:* `{chat_id}`\n"
            f"📝 *Тип:* `{chat_type}`\n"
            f"🏷️ *Название:* `{chat_title}`\n\n"
            f"💡 *Скопируйте ID и вставьте в конфигурацию*"
        )
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
            logger.info(f"Запрос ID: {chat_id} ({chat_title})")
        except Exception as e:
            logger.error(f"Ошибка отправки ID: {e}")
    
    def handle_callback_status(self, call: CallbackQuery) -> None:
        """Обработчик callback для кнопки проверки статуса"""
        try:
            self.bot.answer_callback_query(call.id, "🔍 Проверяю статус Битрикс24...")
            status_info = self.parser.parse_status()
            status_message = format_status_message(status_info, self.config.URL)
            self.bot.send_message(
                call.message.chat.id,
                status_message,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Ошибка обработки callback статуса: {e}")
    
    def handle_metrics(self, message: Message) -> None:
        """Обработчик команды /metrics"""
        try:
            metrics = self.metrics_collector.get_metrics()
            uptime = self.metrics_collector.get_uptime_formatted()
            
            last_check = "Никогда"
            if metrics.get('last_check_time'):
                try:
                    last_check_dt = datetime.fromisoformat(metrics['last_check_time'])
                    last_check = last_check_dt.strftime('%H:%M:%S')
                except:
                    pass
            
            avg_parse = f"{metrics.get('average_parse_time', 0):.2f}" if metrics.get('average_parse_time') else "N/A"
            
            metrics_text = (
                f"📊 *Подробные метрики бота*\n\n"
                f"⏱️ *Время работы:* `{uptime}`\n"
                f"🚨 *Алертов отправлено:* `{metrics.get('alerts_sent', 0)}`\n"
                f"✅ *Восстановлений:* `{metrics.get('recoveries_sent', 0)}`\n"
                f"🔍 *Всего проверок:* `{metrics.get('total_checks', 0)}`\n"
                f"✅ *Успешных:* `{metrics.get('successful_checks', 0)}`\n"
                f"❌ *Ошибок:* `{metrics.get('failed_checks', 0)}`\n"
                f"⏰ *Последняя проверка:* `{last_check}`\n"
                f"⚡ *Среднее время парсинга:* `{avg_parse}` сек\n"
                f"⚠️ *Ошибок за час:* `{metrics.get('errors_last_hour', 0)}`\n"
                f"👥 *Подписчиков:* `{self.subscriber_manager.get_count()}`"
            )
            
            self.bot.reply_to(message, metrics_text, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки метрик: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении метрик\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_incidents(self, message: Message) -> None:
        """Обработчик команды /incidents"""
        try:
            recent = self.incident_tracker.get_recent_incidents(10)
            active = self.incident_tracker.get_active_incident()
            
            if not recent and not active:
                self.bot.reply_to(message, "📋 *История инцидентов*\n\nНет зарегистрированных инцидентов\\.", parse_mode='MarkdownV2')
                return
            
            incidents_text = "📋 *Последние инциденты:*\n\n"
            
            if active:
                start_dt = datetime.fromisoformat(active['start_time'])
                incidents_text += (
                    f"🔴 *АКТИВНЫЙ ИНЦИДЕНТ*\n"
                    f"⏰ Начало: `{start_dt.strftime('%d.%m.%Y %H:%M:%S')}`\n"
                )
                if active.get('region'):
                    incidents_text += f"🌍 Регион: `{active['region']}`\n"
                if active.get('description'):
                    desc = active['description'][:100] + "..." if len(active['description']) > 100 else active['description']
                    incidents_text += f"📝 Описание: `{desc}`\n"
                incidents_text += "\n"
            
            for incident in reversed(recent[-5:]):  # Последние 5
                start_dt = datetime.fromisoformat(incident['start_time'])
                end_dt = datetime.fromisoformat(incident['end_time']) if incident.get('end_time') else None
                
                incidents_text += f"• `{start_dt.strftime('%d.%m %H:%M')}`"
                if end_dt:
                    incidents_text += f" \\- `{end_dt.strftime('%H:%M')}`"
                    incidents_text += f" \\(`{incident.get('duration', 'N/A')}`\\)"
                incidents_text += "\n"
            
            incidents_text += f"\n📊 Всего инцидентов: `{self.incident_tracker.get_incidents_count()}`"
            
            self.bot.reply_to(message, incidents_text, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки инцидентов: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении инцидентов\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_health(self, message: Message) -> None:
        """Обработчик команды /health"""
        try:
            health = self.status_monitor.get_health_status()
            
            last_check = "Никогда"
            if health.get('last_successful_check'):
                try:
                    last_check_dt = datetime.fromisoformat(health['last_successful_check'])
                    last_check = last_check_dt.strftime('%d.%m.%Y %H:%M:%S')
                except:
                    pass
            
            health_text = (
                f"🏥 *Статус здоровья бота*\n\n"
                f"📱 *Telegram API:* {health.get('telegram_api', 'N/A')}\n"
                f"🌐 *Bitrix24 URL:* {health.get('bitrix_url', 'N/A')}\n"
                f"✅ *Последняя успешная проверка:* `{last_check}`\n"
                f"⚠️ *Ошибок за час:* `{health.get('errors_last_hour', 0)}`\n"
                f"🔄 *Ошибок подряд:* `{health.get('consecutive_errors', 0)}`\n"
                f"🔔 *Мониторинг:* {'✅ Включен' if health.get('monitoring_enabled') else '❌ Выключен'}"
            )
            
            self.bot.reply_to(message, health_text, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки статуса здоровья: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении статуса здоровья\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_export(self, message: Message) -> None:
        """Обработчик команды /export"""
        try:
            csv_data = self.incident_tracker.export_to_csv_format()
            
            if not csv_data or csv_data == "Дата,Время начала,Время конца,Длительность,Регион,Описание":
                self.bot.reply_to(message, "📊 *Экспорт данных*\n\nНет данных для экспорта\\.", parse_mode='MarkdownV2')
                return
            
            # Создаем файл в памяти
            csv_file = io.BytesIO(csv_data.encode('utf-8'))
            csv_file.name = f'bitrix24_incidents_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            self.bot.send_document(
                message.chat.id,
                csv_file,
                caption="📊 Экспорт истории инцидентов"
            )
        except Exception as e:
            logger.error(f"Ошибка экспорта данных: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при экспорте данных\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_monitoring(self, message: Message) -> None:
        """Обработчик команды /monitoring (переключение мониторинга)"""
        try:
            # Простая проверка - если сообщение содержит "off" или "выкл", выключаем
            text = message.text.lower() if message.text else ""
            enabled = "off" not in text and "выкл" not in text and "stop" not in text
            
            self.status_monitor.toggle_monitoring(enabled)
            
            status = "включен" if enabled else "выключен"
            response = f"🔔 Мониторинг {status}\\."
            
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка переключения мониторинга: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при переключении мониторинга\\.", parse_mode='MarkdownV2')
            except:
                pass

