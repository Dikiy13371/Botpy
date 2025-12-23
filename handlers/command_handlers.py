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
        
        @self.bot.callback_query_handler(func=lambda call: call.data == "show_incidents")
        def callback_incidents(call: CallbackQuery):
            """Обработчик callback для кнопки показа инцидентов"""
            self.handle_callback_incidents(call)
        
        @self.bot.message_handler(commands=['history'])
        def show_history(message: Message):
            """Обработчик команды /history"""
            self.handle_history(message)
    
    async def handle_start_async(self, message: Message) -> None:
        """Обработчик команды /start (async)"""
        chat_id = message.chat.id
        await self.subscriber_manager.add_subscriber(chat_id)
        
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
            "• `/history` \\- Последние 5 инцидентов\n"
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
    
    def handle_help(self, message: Message) -> None:
        """Обработчик команды /help"""
        self.handle_start(message)
    
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
            self.bot.reply_to(message, stats_text, parse_mode='MarkdownV2')
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
            self.bot.send_message(
                call.message.chat.id,
                status_message,
                parse_mode='MarkdownV2',
                reply_markup=create_status_button()
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
            await self.handle_incidents_async(call.message)
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
            
            self.bot.reply_to(message, metrics_text, parse_mode='MarkdownV2')
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
            
            self.bot.reply_to(message, incidents_text, parse_mode='MarkdownV2')
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
            
            self.bot.reply_to(message, history_text, parse_mode='MarkdownV2')
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

