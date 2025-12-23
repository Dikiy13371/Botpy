"""Обработчики команд Telegram бота."""

import logging
import io
import os
from datetime import datetime
from typing import TYPE_CHECKING
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup
from telebot.apihelper import ApiTelegramException

if TYPE_CHECKING:
    from config.config import BotConfig

from services.subscriber_manager import SubscriberManager
from services.bitrix_parser import BitrixStatusParser
from services.metrics_collector import MetricsCollector
from services.incident_tracker import IncidentTracker
from services.status_monitor import StatusMonitor
from utils.message_formatter import format_status_message, create_status_button, escape_url
from utils.menu_builder import MenuBuilder
from utils.time_utils import get_msk_time

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Класс для обработки команд бота."""
    
    def __init__(
        self,
        bot: TeleBot,
        subscriber_manager: SubscriberManager,
        parser: BitrixStatusParser,
        config: 'BotConfig',  # Forward reference
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
    
    @staticmethod
    def _extract_retry_after(error_str: str) -> str:
        """Извлекает retry_after из строки ошибки Telegram API"""
        import re
        # Ищем паттерн "retry after X" где X - число
        match = re.search(r'retry after (\d+)', error_str.lower())
        if match:
            return match.group(1)
        return 'unknown'
    
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
        
        # Старые callback обработчики оставлены для совместимости, но теперь обрабатываются через handle_callback_menu
        
        @self.bot.message_handler(commands=['history'])
        def show_history(message: Message):
            """Обработчик команды /history"""
            self.handle_history(message)
        
        @self.bot.message_handler(commands=['logs'])
        def show_logs(message: Message):
            """Обработчик команды /logs"""
            self.handle_logs(message)
        
        @self.bot.message_handler(commands=['menu'])
        def show_menu(message: Message):
            """Обработчик команды /menu"""
            self.handle_menu(message)
        
        # Универсальный обработчик callback для всех кнопок меню
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_all_callbacks(call: CallbackQuery):
            """Обработчик всех callback кнопок"""
            self.handle_callback_menu(call)
    
    async def handle_start_async(self, message: Message) -> None:
        """Обработчик команды /start (async)"""
        chat_id = message.chat.id
        user_name = message.from_user.first_name if message.from_user else "Друг"
        is_subscribed = await self.subscriber_manager.is_subscribed(chat_id)
        
        if not is_subscribed:
            await self.subscriber_manager.add_subscriber(chat_id)
        
        # Проверяем, является ли пользователь администратором
        is_admin = self.config.ADMIN_CHAT_ID is not None and chat_id == self.config.ADMIN_CHAT_ID
        
        welcome_text = (
            f"👋 *Привет, {user_name}\\!* Я бот для мониторинга статуса Битрикс24\\.\n\n"
            f"✅ Вы {'подписаны' if is_subscribed else 'автоматически подписаны'} на уведомления\\!\n\n"
            "🎯 *Выберите что вам нужно:*"
        )
        
        try:
            keyboard = MenuBuilder.get_main_menu(is_admin=is_admin)
            self.bot.reply_to(
                message,
                welcome_text,
                parse_mode='MarkdownV2',
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки приветственного сообщения: {e}")
    
    def handle_start(self, message: Message) -> None:
        """Обработчик команды /start (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_start_async(message))
        except RuntimeError:
            # Если уже есть event loop, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_start_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_start: {e}", exc_info=True)
    
    async def handle_menu_async(self, message: Message) -> None:
        """Обработчик команды /menu (async)"""
        chat_id = message.chat.id
        is_admin = self.config.ADMIN_CHAT_ID is not None and chat_id == self.config.ADMIN_CHAT_ID
        
        menu_text = (
            "🤖 *Главное меню бота для мониторинга Bitrix24*\n\n"
            "Выберите раздел:"
        )
        
        try:
            keyboard = MenuBuilder.get_main_menu(is_admin=is_admin)
            self.bot.reply_to(
                message,
                menu_text,
                parse_mode='MarkdownV2',
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки меню: {e}")
    
    def handle_menu(self, message: Message) -> None:
        """Обработчик команды /menu (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_menu_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_menu_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_menu: {e}", exc_info=True)
    
    def handle_help(self, message: Message) -> None:
        """Обработчик команды /help"""
        self.handle_menu(message)
    
    async def handle_subscribe_async(self, message: Message) -> None:
        """Обработчик команды /subscribe (async)"""
        chat_id = message.chat.id
        was_new = await self.subscriber_manager.add_subscriber(chat_id)
        
        if was_new:
            response = "✅ Вы подписаны на уведомления о статусе Битрикс24\\!"
        else:
            response = "ℹ️ Вы уже подписаны на уведомления\\!"
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения подписки: {e}")
    
    def handle_subscribe(self, message: Message) -> None:
        """Обработчик команды /subscribe (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_subscribe_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_subscribe_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_subscribe: {e}", exc_info=True)
    
    async def handle_unsubscribe_async(self, message: Message) -> None:
        """Обработчик команды /unsubscribe (async)"""
        chat_id = message.chat.id
        if await self.subscriber_manager.remove_subscriber(chat_id):
            response = "❌ Вы отписались от уведомлений\\."
        else:
            response = "ℹ️ Вы не были подписаны на уведомления\\."
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения отписки: {e}")
    
    def handle_unsubscribe(self, message: Message) -> None:
        """Обработчик команды /unsubscribe (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_unsubscribe_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_unsubscribe_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_unsubscribe: {e}", exc_info=True)
    
    async def handle_stats_async(self, message: Message) -> None:
        """Обработчик команды /stats (async)"""
        escaped_url = escape_url(self.config.URL)
        subscriber_count = await self.subscriber_manager.get_count()
        stats_text = (
            f"📊 *Статистика бота*\n\n"
            f"👥 Подписчиков: `{subscriber_count}`\n"
            f"⏰ Интервал проверки: `{self.config.CHECK_INTERVAL}` сек\n"
            f"🌐 Мониторинг: [status\\.bitrix24\\.ru]({escaped_url})"
        )
        try:
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, stats_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки статистики: {e}")
    
    def handle_stats(self, message: Message) -> None:
        """Обработчик команды /stats (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_stats_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_stats_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_stats: {e}", exc_info=True)
    
    async def handle_status_async(self, message: Message) -> None:
        """Обработчик команды /status (async)"""
        try:
            self.bot.reply_to(message, "🔍 Проверяю статус Битрикс24\\.\\.\\.", parse_mode='MarkdownV2')
            
            status_info = await self.parser.parse_status()
            status_message = format_status_message(status_info, self.config.URL)
            keyboard = MenuBuilder.get_quick_action_buttons()
            
            self.bot.send_message(
                message.chat.id,
                status_message,
                parse_mode='MarkdownV2',
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка проверки статуса: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при проверке статуса\\. Попробуйте позже\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_status(self, message: Message) -> None:
        """Обработчик команды /status (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_status_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_status_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_status: {e}", exc_info=True)
    
    def handle_getid(self, message: Message) -> None:
        """Обработчик команды /getid"""
        chat_id = message.chat.id
        chat_type = message.chat.type
        chat_title = getattr(message.chat, 'title', 'Личный чат')
        
        # Проверяем, является ли это супергруппой
        is_supergroup = chat_type == 'supergroup'
        note = ""
        if is_supergroup:
            note = "\n\n⚠️ *Важно:* Это супергруппа\\. Если группа была преобразована из обычной группы, используйте этот новый ID\\."
        
        response = (
            f"📊 *Информация о чата:*\n\n"
            f"🆔 *ID:* `{chat_id}`\n"
            f"📝 *Тип:* `{chat_type}`\n"
            f"🏷️ *Название:* `{chat_title}`\n"
            f"{note}\n"
            f"💡 *Скопируйте ID и вставьте в GROUP_ID в файле \\.env*"
        )
        
        try:
            self.bot.reply_to(message, response, parse_mode='MarkdownV2')
            logger.info(f"Запрос ID: {chat_id} ({chat_title}, тип: {chat_type})")
        except Exception as e:
            logger.error(f"Ошибка отправки ID: {e}")
    
    async def handle_callback_status_async(self, call: CallbackQuery) -> None:
        """Обработчик callback для кнопки проверки статуса (async)"""
        try:
            self.bot.answer_callback_query(call.id, "🔍 Проверяю статус Битрикс24...")
            status_info = await self.parser.parse_status()
            status_message = format_status_message(status_info, self.config.URL)
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.send_message(
                call.message.chat.id,
                status_message,
                parse_mode='MarkdownV2',
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка обработки callback статуса: {e}")
    
    def handle_callback_status(self, call: CallbackQuery) -> None:
        """Обработчик callback для кнопки проверки статуса (синхронная обертка)"""
        import asyncio
        # pyTelegramBotAPI работает в worker threads без event loop
        # Создаем новый event loop для каждого вызова
        try:
            asyncio.run(self.handle_callback_status_async(call))
        except RuntimeError as e:
            # Если уже есть event loop (маловероятно в worker thread)
            logger.warning(f"Event loop уже существует: {e}, используем новый")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_callback_status_async(call))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_callback_status: {e}", exc_info=True)
    
    async def handle_callback_incidents_async(self, call: CallbackQuery) -> None:
        """Обработчик callback для кнопки показа инцидентов (async)"""
        try:
            self.bot.answer_callback_query(call.id, "📊 Загружаю историю инцидентов...")
            # Используем прямой вызов через callback меню для единообразия
            call.data = "cmd_incidents"
            await self.handle_callback_menu_async(call)
        except Exception as e:
            logger.error(f"Ошибка обработки callback инцидентов: {e}")
    
    def handle_callback_incidents(self, call: CallbackQuery) -> None:
        """Обработчик callback для кнопки показа инцидентов (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_callback_incidents_async(call))
        except RuntimeError as e:
            logger.warning(f"Event loop уже существует: {e}, используем новый")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_callback_incidents_async(call))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_callback_incidents: {e}", exc_info=True)
    
    async def handle_metrics_async(self, message: Message) -> None:
        """Обработчик команды /metrics (async)"""
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
            subscriber_count = await self.subscriber_manager.get_count()
            
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
                f"👥 *Подписчиков:* `{subscriber_count}`"
            )
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, metrics_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки метрик: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении метрик\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_metrics(self, message: Message) -> None:
        """Обработчик команды /metrics (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_metrics_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_metrics_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_metrics: {e}", exc_info=True)
    
    async def handle_incidents_async(self, message: Message) -> None:
        """Обработчик команды /incidents (async)"""
        try:
            # Получаем активный инцидент и последние завершенные
            active = await self.incident_tracker.get_active_incident()
            recent = await self.incident_tracker.get_recent_incidents(limit=5)
            
            if not active and not recent:
                self.bot.reply_to(
                    message,
                    "📋 *История инцидентов*\n\nНет зарегистрированных инцидентов\\.",
                    parse_mode='MarkdownV2'
                )
                return
            
            incidents_text = "📋 *Последние инциденты:*\n\n"
            
            # Показываем активный инцидент первым
            if active:
                start_dt = datetime.fromisoformat(active['start_time'])
                start_str = start_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.')
                
                incidents_text += (
                    f"🔴 *АКТИВНЫЙ ИНЦИДЕНТ*\n"
                    f"⏰ Начало: `{start_str}`\n"
                )
                if active.get('region'):
                    incidents_text += f"🌍 Регион: `{active['region']}`\n"
                if active.get('components'):
                    components = active['components']
                    if isinstance(components, str):
                        components_str = components
                    else:
                        components_str = ', '.join(components) if isinstance(components, list) else str(components)
                    if components_str:
                        incidents_text += f"🔧 Компоненты: `{components_str}`\n"
                incidents_text += "\n"
            
            # Показываем последние завершенные инциденты
            for incident in recent[-5:]:  # Последние 5
                if incident.get('status') == 'active':
                    continue  # Пропускаем активный, он уже показан выше
                
                start_dt = datetime.fromisoformat(incident['start_time'])
                end_dt = datetime.fromisoformat(incident['end_time']) if incident.get('end_time') else None
                
                start_str = start_dt.strftime('%d.%m %H:%M').replace('.', '\\.')
                incidents_text += f"• `{start_str}`"
                if end_dt:
                    end_str = end_dt.strftime('%H:%M').replace('.', '\\.')
                    incidents_text += f" \\- `{end_str}`"
                    if incident.get('duration'):
                        incidents_text += f" \\(`{incident['duration']}`\\)"
                incidents_text += "\n"
            
            total_count = await self.incident_tracker.get_incidents_count()
            incidents_text += f"\n📊 Всего инцидентов: `{total_count}`"
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, incidents_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки инцидентов: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении инцидентов\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_incidents(self, message: Message) -> None:
        """Обработчик команды /incidents (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_incidents_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_incidents_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_incidents: {e}", exc_info=True)
    
    def handle_health(self, message: Message) -> None:
        """Обработчик команды /health (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_health_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_health_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_health: {e}", exc_info=True)
    
    async def handle_health_async(self, message: Message) -> None:
        """Обработчик команды /health (async)"""
        try:
            health = await self.status_monitor.get_health_status()
            
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
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, health_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки статуса здоровья: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении статуса здоровья\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    async def handle_history_async(self, message: Message) -> None:
        """Обработчик команды /history (async)"""
        try:
            incidents = await self.incident_tracker.get_history(limit=5)
            
            if not incidents:
                self.bot.reply_to(
                    message, 
                    "📋 *История инцидентов*\n\nНет завершенных инцидентов в базе данных\\.", 
                    parse_mode='MarkdownV2'
                )
                return
            
            history_text = "📋 *Последние 5 инцидентов:*\n\n"
            
            for incident in incidents:
                start_dt = datetime.fromisoformat(incident['start_time'])
                end_dt = datetime.fromisoformat(incident['end_time']) if incident.get('end_time') else None
                
                # Форматируем даты отдельно, чтобы избежать проблем с обратными слешами в f-string
                start_str = start_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.')
                end_str = end_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.') if end_dt else None
                
                history_text += f"🔴 *Инцидент \\#{incident['id']}*\n"
                history_text += f"⏰ Начало: `{start_str}`\n"
                
                if end_dt and end_str:
                    history_text += f"✅ Конец: `{end_str}`\n"
                    history_text += f"⏱️ Длительность: `{incident.get('duration', 'N/A')}`\n"
                
                if incident.get('region'):
                    history_text += f"🌍 Регион: `{incident['region']}`\n"
                
                if incident.get('components'):
                    components = incident['components']
                    if isinstance(components, str):
                        # Если это строка с запятыми, просто используем её
                        components_str = components
                    else:
                        # Если это список, объединяем
                        components_str = ', '.join(components) if isinstance(components, list) else str(components)
                    if components_str:
                        history_text += f"🔧 Компоненты: `{components_str}`\n"
                
                history_text += "\n"
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, history_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки истории: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении истории\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    def handle_history(self, message: Message) -> None:
        """Обработчик команды /history (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_history_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_history_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_history: {e}", exc_info=True)
    
    async def handle_export_async(self, message: Message) -> None:
        """Обработчик команды /export (async)"""
        try:
            csv_data = await self.incident_tracker.export_to_csv_format()
            
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
    
    def handle_export(self, message: Message) -> None:
        """Обработчик команды /export (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_export_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_export_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_export: {e}", exc_info=True)
    
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
    
    async def handle_logs_async(self, message: Message) -> None:
        """Обработчик команды /logs (async) - показывает последние 15 строк логов"""
        try:
            log_file = self.config.LOG_FILE
            
            # Проверяем существование файла
            if not os.path.exists(log_file):
                self.bot.reply_to(
                    message,
                    f"❌ Файл логов не найден: `{log_file}`",
                    parse_mode='MarkdownV2'
                )
                return
            
            # Читаем последние 15 строк из файла
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    last_lines = lines[-15:] if len(lines) > 15 else lines
                    log_content = ''.join(last_lines).strip()
            except PermissionError as e:
                logger.error(f"Ошибка доступа к файлу логов: {e}")
                self.bot.reply_to(
                    message,
                    f"❌ Нет доступа к файлу логов: `{log_file}`",
                    parse_mode='MarkdownV2'
                )
                return
            except Exception as e:
                logger.error(f"Ошибка чтения файла логов: {e}")
                self.bot.reply_to(
                    message,
                    f"❌ Ошибка чтения файла логов: {e}",
                    parse_mode='MarkdownV2'
                )
                return
            
            if not log_content:
                self.bot.reply_to(
                    message,
                    "📋 *Логи*\n\nФайл логов пуст\\.",
                    parse_mode='MarkdownV2'
                )
                return
            
            # Форматируем сообщение
            # Экранируем специальные символы для MarkdownV2
            log_content_escaped = log_content.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
            
            # Разбиваем на части если сообщение слишком длинное (Telegram лимит 4096 символов)
            max_length = 4000  # Оставляем запас
            if len(log_content_escaped) > max_length:
                # Берем только последние символы
                log_content_escaped = log_content_escaped[-max_length:]
                log_content_escaped = "...\n" + log_content_escaped
            
            response = (
                f"📋 *Последние 15 строк логов*\n\n"
                f"`{log_content_escaped}`"
            )
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, response, parse_mode='MarkdownV2', reply_markup=keyboard)
            logger.info(f"Логи отправлены пользователю {message.chat.id}")
            
        except ApiTelegramException as e:
            logger.error(f"Ошибка Telegram API при отправке логов: {e}")
            try:
                self.bot.reply_to(
                    message,
                    "❌ Ошибка отправки логов\\. Сообщение слишком длинное или содержит недопустимые символы\\.",
                    parse_mode='MarkdownV2'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Ошибка обработки команды /logs: {e}", exc_info=True)
            try:
                self.bot.reply_to(
                    message,
                    "❌ Ошибка при получении логов\\.",
                    parse_mode='MarkdownV2'
                )
            except:
                pass
    
    def handle_logs(self, message: Message) -> None:
        """Обработчик команды /logs (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_logs_async(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_logs_async(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_logs: {e}", exc_info=True)
    
    async def handle_callback_menu_async(self, call: CallbackQuery) -> None:
        """Обработчик всех callback кнопок меню (async)"""
        try:
            callback_data = call.data
            chat_id = call.message.chat.id
            user_id = call.from_user.id
            is_admin = self.config.ADMIN_CHAT_ID is not None and user_id == self.config.ADMIN_CHAT_ID
            message_id = call.message.message_id
            
            # Отвечаем на callback сразу чтобы убрать "loading" и предотвратить timeout
            # НЕ отвечаем если это rate limiting - это может усугубить ситуацию
            callback_answered = False
            try:
                self.bot.answer_callback_query(call.id)
                callback_answered = True
            except ApiTelegramException as e:
                if getattr(e, 'error_code', None) == 429:
                    # При rate limiting не отвечаем на callback, чтобы не усугублять ситуацию
                    logger.debug(f"Rate limit при ответе на callback {call.id}, пропускаем")
                else:
                    logger.debug(f"Не удалось ответить на callback {call.id}: {e}")
            except Exception as e:
                logger.debug(f"Не удалось ответить на callback {call.id}: {e}")
            
            # Вспомогательная функция для безопасного редактирования сообщения
            def safe_edit_message(text: str, keyboard: InlineKeyboardMarkup = None) -> None:
                """Безопасно редактирует сообщение, при ошибке отправляет новое"""
                try:
                    self.bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode='MarkdownV2',
                        reply_markup=keyboard
                    )
                except ApiTelegramException as e:
                    error_msg = str(e).lower()
                    error_code = getattr(e, 'error_code', None)
                    
                    # Обрабатываем различные ошибки, при которых нужно отправить новое сообщение
                    should_send_new = (
                        "query is too old" in error_msg or
                        "message is not modified" in error_msg or
                        "message to edit not found" in error_msg or
                        "message_id_invalid" in error_msg or
                        error_code == 400  # Bad Request (включает MESSAGE_ID_INVALID)
                    )
                    
                    if should_send_new:
                        # Если callback устарел, сообщение не изменилось или не найдено - отправляем новое
                        logger.debug(f"Не удалось отредактировать сообщение ({error_msg[:50]}), отправляем новое")
                        try:
                            self.bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode='MarkdownV2',
                                reply_markup=keyboard
                            )
                        except Exception as send_err:
                            logger.error(f"Ошибка отправки нового сообщения: {send_err}")
                    elif error_code == 429:
                        # Rate limiting - извлекаем retry_after из описания ошибки
                        retry_after = self._extract_retry_after(str(e))
                        logger.warning(f"Rate limit достигнут, retry after {retry_after} секунд")
                        # Не отправляем новое сообщение при rate limiting - просто ждем
                        return
                    else:
                        # Другие ошибки пробрасываем дальше
                        raise
            
            # ===== НАВИГАЦИЯ ПО МЕНЮ =====
            
            if callback_data == "menu_main":
                text = "🤖 *Главное меню*\n\nВыберите раздел:"
                keyboard = MenuBuilder.get_main_menu(is_admin=is_admin)
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "menu_monitoring":
                text = "📊 *Мониторинг & Статус*\n\nВыберите действие:"
                keyboard = MenuBuilder.get_monitoring_menu(is_admin=is_admin)
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "menu_subscribe":
                is_subscribed = await self.subscriber_manager.is_subscribed(chat_id)
                status_text = "✅ Подписаны" if is_subscribed else "❌ Не подписаны"
                text = f"🔔 *Управление подписками*\n\nВаш статус: {status_text}\n\nВыберите действие:"
                keyboard = MenuBuilder.get_subscribe_menu(is_subscribed=is_subscribed)
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "menu_analytics":
                text = "📈 *Аналитика & Метрики*\n\nВыберите что вас интересует:"
                keyboard = MenuBuilder.get_analytics_menu()
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "menu_admin":
                if not is_admin:
                    try:
                        self.bot.answer_callback_query(call.id, "❌ У вас нет доступа", show_alert=True)
                    except:
                        pass
                    return
                
                text = "⚙️ *Администрирование*\n\nТолько для администраторов:"
                keyboard = MenuBuilder.get_admin_menu()
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "menu_help":
                text = "❓ *Справка & Помощь*\n\nВыберите что вас интересует:"
                keyboard = MenuBuilder.get_help_menu()
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "close_menu":
                self.bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
                return
            
            # ===== КОМАНДЫ ЧЕРЕЗ КНОПКИ =====
            
            elif callback_data == "cmd_status":
                try:
                    self.bot.answer_callback_query(call.id, "🔍 Проверяю статус...")
                except:
                    pass
                status_info = await self.parser.parse_status()
                status_message = format_status_message(status_info, self.config.URL)
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(status_message, keyboard)
                return
            
            elif callback_data == "cmd_stats":
                try:
                    self.bot.answer_callback_query(call.id, "📊 Загружаю статистику...")
                except:
                    pass
                escaped_url = escape_url(self.config.URL)
                subscriber_count = await self.subscriber_manager.get_count()
                stats_text = (
                    f"📊 *Статистика бота*\n\n"
                    f"👥 Подписчиков: `{subscriber_count}`\n"
                    f"⏰ Интервал проверки: `{self.config.CHECK_INTERVAL}` сек\n"
                    f"🌐 Мониторинг: [status\\.bitrix24\\.ru]({escaped_url})"
                )
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(stats_text, keyboard)
                return
            
            elif callback_data == "cmd_metrics":
                self.bot.answer_callback_query(call.id, "📉 Загружаю метрики...")
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
                subscriber_count = await self.subscriber_manager.get_count()
                
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
                    f"👥 *Подписчиков:* `{subscriber_count}`"
                )
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(metrics_text, keyboard)
                return
            
            elif callback_data == "cmd_incidents":
                try:
                    self.bot.answer_callback_query(call.id, "📋 Загружаю инциденты...")
                except:
                    pass
                # Получаем данные и форматируем
                active = await self.incident_tracker.get_active_incident()
                recent = await self.incident_tracker.get_recent_incidents(limit=5)
                
                if not active and not recent:
                    incidents_text = "📋 *История инцидентов*\n\nНет зарегистрированных инцидентов\\."
                    keyboard = MenuBuilder.get_quick_action_buttons()
                    safe_edit_message(incidents_text, keyboard)
                    return
                
                incidents_text = "📋 *Последние инциденты:*\n\n"
                
                if active:
                    start_dt = datetime.fromisoformat(active['start_time'])
                    start_str = start_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.')
                    incidents_text += (
                        f"🔴 *АКТИВНЫЙ ИНЦИДЕНТ*\n"
                        f"⏰ Начало: `{start_str}`\n"
                    )
                    if active.get('region'):
                        incidents_text += f"🌍 Регион: `{active['region']}`\n"
                    if active.get('components'):
                        components = active['components']
                        if isinstance(components, str):
                            components_str = components
                        else:
                            components_str = ', '.join(components) if isinstance(components, list) else str(components)
                        if components_str:
                            incidents_text += f"🔧 Компоненты: `{components_str}`\n"
                    incidents_text += "\n"
                
                for incident in recent[-5:]:
                    if incident.get('status') == 'active':
                        continue
                    
                    start_dt = datetime.fromisoformat(incident['start_time'])
                    end_dt = datetime.fromisoformat(incident['end_time']) if incident.get('end_time') else None
                    
                    start_str = start_dt.strftime('%d.%m %H:%M').replace('.', '\\.')
                    incidents_text += f"• `{start_str}`"
                    if end_dt:
                        end_str = end_dt.strftime('%H:%M').replace('.', '\\.')
                        incidents_text += f" \\- `{end_str}`"
                        if incident.get('duration'):
                            incidents_text += f" \\(`{incident['duration']}`\\)"
                    incidents_text += "\n"
                
                total_count = await self.incident_tracker.get_incidents_count()
                incidents_text += f"\n📊 Всего инцидентов: `{total_count}`"
                
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(incidents_text, keyboard)
                return
            
            elif callback_data == "cmd_history":
                try:
                    self.bot.answer_callback_query(call.id, "📜 Загружаю историю...")
                except:
                    pass
                incidents = await self.incident_tracker.get_history(limit=5)
                
                if not incidents:
                    history_text = "📋 *История инцидентов*\n\nНет завершенных инцидентов в базе данных\\."
                    keyboard = MenuBuilder.get_quick_action_buttons()
                    safe_edit_message(history_text, keyboard)
                    return
                
                history_text = "📋 *Последние 5 инцидентов:*\n\n"
                
                for incident in incidents:
                    start_dt = datetime.fromisoformat(incident['start_time'])
                    end_dt = datetime.fromisoformat(incident['end_time']) if incident.get('end_time') else None
                    
                    start_str = start_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.')
                    end_str = end_dt.strftime('%d.%m.%Y %H:%M:%S').replace('.', '\\.') if end_dt else None
                    
                    history_text += f"🔴 *Инцидент \\#{incident['id']}*\n"
                    history_text += f"⏰ Начало: `{start_str}`\n"
                    
                    if end_dt and end_str:
                        history_text += f"✅ Конец: `{end_str}`\n"
                        history_text += f"⏱️ Длительность: `{incident.get('duration', 'N/A')}`\n"
                    
                    if incident.get('region'):
                        history_text += f"🌍 Регион: `{incident['region']}`\n"
                    
                    if incident.get('components'):
                        components = incident['components']
                        if isinstance(components, str):
                            components_str = components
                        else:
                            components_str = ', '.join(components) if isinstance(components, list) else str(components)
                        if components_str:
                            history_text += f"🔧 Компоненты: `{components_str}`\n"
                    
                    history_text += "\n"
                
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(history_text, keyboard)
                return
            
            elif callback_data == "cmd_health":
                try:
                    self.bot.answer_callback_query(call.id, "🏥 Проверяю здоровье...")
                except:
                    pass
                health = await self.status_monitor.get_health_status()
                
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
                
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(health_text, keyboard)
                return
            
            elif callback_data == "cmd_export":
                self.bot.answer_callback_query(call.id, "📤 Экспортирую данные...")
                # Для экспорта отправляем файл отдельным сообщением
                try:
                    csv_data = await self.incident_tracker.export_to_csv_format()
                    
                    if not csv_data or csv_data == "Дата,Время начала,Время конца,Длительность,Регион,Компоненты,Описание":
                        self.bot.answer_callback_query(call.id, "❌ Нет данных для экспорта", show_alert=True)
                        return
                    
                    csv_file = io.BytesIO(csv_data.encode('utf-8'))
                    csv_file.name = f'bitrix24_incidents_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                    
                    self.bot.send_document(
                        chat_id=chat_id,
                        document=csv_file,
                        caption="📊 Экспорт истории инцидентов"
                    )
                    self.bot.answer_callback_query(call.id, "✅ CSV файл отправлен")
                except Exception as e:
                    logger.error(f"Ошибка экспорта через callback: {e}")
                    self.bot.answer_callback_query(call.id, "❌ Ошибка экспорта", show_alert=True)
                return
            
            elif callback_data == "cmd_subscribe":
                was_new = await self.subscriber_manager.add_subscriber(chat_id)
                if was_new:
                    text = "✅ Вы успешно подписаны на уведомления\\!"
                else:
                    text = "ℹ️ Вы уже были подписаны на уведомления\\!"
                keyboard = MenuBuilder.get_subscribe_menu(is_subscribed=True)
                safe_edit_message(text, keyboard)
                try:
                    self.bot.answer_callback_query(call.id, "✅ Подписка активирована")
                except:
                    pass
                return
            
            elif callback_data == "cmd_unsubscribe":
                removed = await self.subscriber_manager.remove_subscriber(chat_id)
                if removed:
                    text = "❌ Вы отписались от уведомлений"
                else:
                    text = "ℹ️ Вы не были подписаны"
                keyboard = MenuBuilder.get_subscribe_menu(is_subscribed=False)
                safe_edit_message(text, keyboard)
                try:
                    self.bot.answer_callback_query(call.id, "❌ Подписка отменена")
                except:
                    pass
                return
            
            elif callback_data == "cmd_logs":
                self.bot.answer_callback_query(call.id, "📋 Загружаю логи...")
                log_file = self.config.LOG_FILE
                
                if not os.path.exists(log_file):
                    logs_text = f"❌ Файл логов не найден: `{log_file}`"
                else:
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            last_lines = lines[-15:] if len(lines) > 15 else lines
                            log_content = ''.join(last_lines).strip()
                        
                        if not log_content:
                            logs_text = "📋 *Логи*\n\nФайл логов пуст\\."
                        else:
                            log_content_escaped = log_content.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                            
                            max_length = 4000
                            if len(log_content_escaped) > max_length:
                                log_content_escaped = "...\n" + log_content_escaped[-max_length:]
                            
                            logs_text = f"📋 *Последние 15 строк логов*\n\n`{log_content_escaped}`"
                    except Exception as e:
                        logger.error(f"Ошибка чтения логов: {e}")
                        logs_text = f"❌ Ошибка чтения файла логов: {e}"
                
                keyboard = MenuBuilder.get_quick_action_buttons()
                safe_edit_message(logs_text, keyboard)
                return
            
            elif callback_data == "cmd_db_info":
                if not is_admin:
                    self.bot.answer_callback_query(call.id, "❌ У вас нет доступа", show_alert=True)
                    return
                
                self.bot.answer_callback_query(call.id, "🔧 Загружаю информацию о БД...")
                await self.handle_db_info_async(call.message)
                return
            
            elif callback_data == "cmd_check_conn":
                if not is_admin:
                    self.bot.answer_callback_query(call.id, "❌ У вас нет доступа", show_alert=True)
                    return
                
                self.bot.answer_callback_query(call.id, "🧪 Проверяю подключения...")
                await self.handle_check_connections_async(call.message)
                return
            
            # ===== СПРАВКА =====
            
            elif callback_data == "help_how_to":
                text = (
                    "📖 *Как использовать бот*\n\n"
                    "1\\. *Мониторинг*: Проверяйте статус Bitrix24 в реальном времени\n"
                    "2\\. *Уведомления*: Подпишитесь чтобы получать алерты о сбоях\n"
                    "3\\. *Метрики*: Смотрите статистику и производительность\n"
                    "4\\. *История*: Посмотрите последние инциденты\n\n"
                    "Все команды доступны через меню или текстом \\(/help\\)\n\n"
                    "Используй кнопки для навигации 👆"
                )
                keyboard = MenuBuilder.get_help_menu()
                safe_edit_message(text, keyboard)
                return
            
            elif callback_data == "help_about":
                text = (
                    "💬 *О боте*\n\n"
                    "Telegram бот для мониторинга статуса Bitrix24\n\n"
                    "*Версия*: 2\\.0\n"
                    "*Функции*:\n"
                    "• ✅ Автоматический мониторинг статуса\n"
                    "• 🔔 Алерты о сбоях в реальном времени\n"
                    "• 🛡️ Дедупликация алертов\n"
                    "• 📊 Подробная аналитика\n"
                    "• 💾 История инцидентов\n"
                    "• 📤 Экспорт данных\n"
                    "• 📋 Просмотр логов"
                )
                keyboard = MenuBuilder.get_help_menu()
                safe_edit_message(text, keyboard)
                return
            
            # ===== СТАРЫЕ CALLBACK (для совместимости) =====
            
            elif callback_data == "check_status":
                await self.handle_callback_status_async(call)
                return
            
            elif callback_data == "show_incidents":
                await self.handle_callback_incidents_async(call)
                return
            
        except ApiTelegramException as e:
            error_msg = str(e).lower()
            error_code = getattr(e, 'error_code', None)
            
            if "query is too old" in error_msg:
                # Callback устарел - это нормально, просто логируем
                logger.debug(f"Callback query устарел для {callback_data}")
            elif "message is not modified" in error_msg:
                # Сообщение не изменилось - это нормально
                logger.debug(f"Message not modified for callback {callback_data}")
            elif error_code == 429:
                # Rate limiting - извлекаем retry_after из описания ошибки
                retry_after = self._extract_retry_after(str(e))
                logger.warning(f"Rate limit достигнут для callback {callback_data}, retry after {retry_after} секунд")
                try:
                    retry_msg = f"⏳ Слишком много запросов, попробуйте через {retry_after} сек" if retry_after != 'unknown' else "⏳ Слишком много запросов, попробуйте позже"
                    self.bot.answer_callback_query(call.id, retry_msg, show_alert=True)
                except:
                    pass
            elif "message_id_invalid" in error_msg or error_code == 400:
                # Сообщение не найдено или недействительно - это нормально при удалении сообщений
                logger.debug(f"Message ID invalid для callback {callback_data} - сообщение могло быть удалено")
            else:
                logger.error(f"Ошибка Telegram API в callback {callback_data}: {e}")
                try:
                    self.bot.answer_callback_query(call.id, "❌ Ошибка при выполнении", show_alert=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"Ошибка обработки callback {callback_data}: {e}", exc_info=True)
            try:
                self.bot.answer_callback_query(call.id, "❌ Произошла ошибка", show_alert=True)
            except:
                pass
    
    def handle_callback_menu(self, call: CallbackQuery) -> None:
        """Обработчик всех callback кнопок меню (синхронная обертка)"""
        import asyncio
        try:
            asyncio.run(self.handle_callback_menu_async(call))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.handle_callback_menu_async(call))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в handle_callback_menu: {e}", exc_info=True)
    
    async def handle_db_info_async(self, message: Message) -> None:
        """Обработчик команды /db_info (async) - информация о базе данных"""
        try:
            # Получаем статистику БД
            incidents_count = await self.incident_tracker.get_incidents_count()
            subscriber_count = await self.subscriber_manager.get_count()
            
            # Получаем размер файла БД
            db_path = 'data/bot.db'
            db_size = 0
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                db_size_mb = db_size / (1024 * 1024)
                db_size_str = f"{db_size_mb:.2f} МБ"
            else:
                db_size_str = "Файл не найден"
            
            # Получаем последний инцидент
            recent = await self.incident_tracker.get_recent_incidents(limit=1)
            last_incident = "Нет инцидентов"
            if recent:
                last_incident_dt = datetime.fromisoformat(recent[0]['start_time'])
                last_incident = last_incident_dt.strftime('%d.%m.%Y %H:%M:%S')
            
            db_info_text = (
                f"🔧 *Информация о базе данных*\n\n"
                f"📊 *Количество инцидентов:* `{incidents_count}`\n"
                f"👥 *Количество подписчиков:* `{subscriber_count}`\n"
                f"💾 *Размер БД:* `{db_size_str}`\n"
                f"📅 *Последний инцидент:* `{last_incident}`"
            )
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, db_info_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка получения информации о БД: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при получении информации о БД\\.", parse_mode='MarkdownV2')
            except:
                pass
    
    async def handle_check_connections_async(self, message: Message) -> None:
        """Обработчик команды /check_connections (async) - проверка подключений"""
        try:
            results = []
            
            # Проверка Telegram API
            try:
                bot_info = self.bot.get_me()
                results.append(f"✅ *Telegram API*: Работает \\(@{bot_info.username}\\)")
            except Exception as e:
                results.append(f"❌ *Telegram API*: Ошибка \\({str(e)[:50]}\\)")
            
            # Проверка Bitrix24 URL
            try:
                status_info = await self.parser.parse_status()
                if status_info.get('error'):
                    results.append(f"⚠️ *Bitrix24 URL*: Ошибка парсинга")
                else:
                    results.append(f"✅ *Bitrix24 URL*: Доступен")
            except Exception as e:
                results.append(f"❌ *Bitrix24 URL*: Ошибка \\({str(e)[:50]}\\)")
            
            # Проверка SQLite БД
            try:
                test_query = await self.subscriber_manager.get_count()
                results.append(f"✅ *SQLite БД*: Работает \\(подписчиков: {test_query}\\)")
            except Exception as e:
                results.append(f"❌ *SQLite БД*: Ошибка \\({str(e)[:50]}\\)")
            
            # Проверка файлов
            log_file = self.config.LOG_FILE
            if os.path.exists(log_file):
                results.append(f"✅ *Файл логов*: Существует")
            else:
                results.append(f"⚠️ *Файл логов*: Не найден")
            
            conn_text = "🧪 *Проверка подключений*\n\n" + "\n".join(results)
            
            keyboard = MenuBuilder.get_quick_action_buttons()
            self.bot.reply_to(message, conn_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка проверки подключений: {e}")
            try:
                self.bot.reply_to(message, "❌ Ошибка при проверке подключений\\.", parse_mode='MarkdownV2')
            except:
                pass

