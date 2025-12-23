"""Главный файл Telegram бота для мониторинга статуса Bitrix24."""

import signal
import sys
import logging
import telebot

import asyncio
from config.config import BotConfig
from services.database import Database
from services.bitrix_parser import BitrixStatusParser
from services.subscriber_manager import SubscriberManager
from services.metrics_collector import MetricsCollector
from services.incident_tracker import IncidentTracker
from services.status_monitor import StatusMonitor
from handlers.command_handlers import CommandHandlers
from utils.logger_config import setup_logging

logger = logging.getLogger(__name__)


class Bitrix24MonitorBot:
    """Главный класс бота для мониторинга статуса Bitrix24."""
    
    def __init__(self):
        """Инициализирует бота и все необходимые компоненты."""
        # Загружаем конфигурацию
        self.config = BotConfig()
        
        # Настраиваем логирование
        setup_logging(self.config.LOG_LEVEL, self.config.LOG_FILE)
        
        # Валидируем конфигурацию
        is_valid, error_message = self.config.validate()
        if not is_valid:
            logger.error(f"Ошибка конфигурации: {error_message}")
            sys.exit(1)
        
        logger.info(f"Конфигурация загружена: {self.config}")
        
        # Инициализируем базу данных
        self.database = Database('data/bot.db')
        
        # Инициализируем компоненты
        self.bot = telebot.TeleBot(self.config.BOT_TOKEN)
        self.parser = BitrixStatusParser(
            url=self.config.URL,
            timeout=self.config.REQUEST_TIMEOUT,
            retry_attempts=self.config.RETRY_ATTEMPTS,
            retry_delay=self.config.RETRY_DELAY,
            cache_ttl=self.config.CACHE_TTL
        )
        self.subscriber_manager = SubscriberManager(self.database)
        self.metrics_collector = MetricsCollector('data/metrics.json')
        self.incident_tracker = IncidentTracker(self.database)
        self.status_monitor = StatusMonitor(
            bot=self.bot,
            parser=self.parser,
            config=self.config,
            subscriber_manager=self.subscriber_manager,
            metrics_collector=self.metrics_collector,
            incident_tracker=self.incident_tracker
        )
        self.command_handlers = CommandHandlers(
            bot=self.bot,
            subscriber_manager=self.subscriber_manager,
            parser=self.parser,
            config=self.config,
            status_monitor=self.status_monitor,
            metrics_collector=self.metrics_collector,
            incident_tracker=self.incident_tracker
        )
        
        # Настраиваем обработку сигналов для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown."""
        logger.info(f"Получен сигнал {signum}, выполняю graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    async def _init_async(self) -> None:
        """Асинхронная инициализация компонентов."""
        await self.database.connect()
        await self.subscriber_manager.load_subscribers()
        # Восстанавливаем активный инцидент из БД
        await self.incident_tracker.restore_active_incident()
        logger.info("Асинхронные компоненты инициализированы")
    
    def start(self) -> None:
        """Запускает бота и мониторинг."""
        # Инициализируем async компоненты
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self._init_async())
        
        logger.info("🤖 Бот запущен!")
        logger.info(f"⏰ Интервал проверки: {self.config.CHECK_INTERVAL} секунд")
        logger.info(f"📡 Мониторинг: {self.config.URL}")
        
        # Получаем количество подписчиков
        subscriber_count = loop.run_until_complete(self.subscriber_manager.get_count())
        logger.info(f"✅ Ожидание команд... (Подписчиков: {subscriber_count})")
        
        # Запускаем мониторинг
        self.status_monitor.start()
        
        try:
            # Запускаем бота
            self.bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания (Ctrl+C)")
            self.stop()
        except Exception as e:
            logger.error(f"Критическая ошибка при работе бота: {e}", exc_info=True)
            self.stop()
            sys.exit(1)
    
    async def _stop_async(self) -> None:
        """Асинхронная остановка компонентов."""
        await self.status_monitor.stop_async()
        await self.parser.close()
        await self.database.close()
    
    def stop(self) -> None:
        """Останавливает бота и мониторинг."""
        logger.info("Остановка бота...")
        self.status_monitor.stop()
        
        # Закрываем async компоненты
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._stop_async())
        except RuntimeError:
            # Если event loop не запущен, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stop_async())
        
        logger.info("Бот остановлен")


def main():
    """Главная функция запуска бота."""
    bot = Bitrix24MonitorBot()
    bot.start()


if __name__ == "__main__":
    main()
