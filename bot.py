"""Главный файл Telegram бота для мониторинга статуса Bitrix24."""

import signal
import sys
import logging
import telebot

from config.config import BotConfig
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
        
        # Инициализируем компоненты
        self.bot = telebot.TeleBot(self.config.BOT_TOKEN)
        self.parser = BitrixStatusParser(
            url=self.config.URL,
            timeout=self.config.REQUEST_TIMEOUT,
            retry_attempts=self.config.RETRY_ATTEMPTS,
            retry_delay=self.config.RETRY_DELAY,
            cache_ttl=self.config.CACHE_TTL
        )
        self.subscriber_manager = SubscriberManager(self.config.SUBSCRIBERS_FILE)
        self.metrics_collector = MetricsCollector('data/metrics.json')
        self.incident_tracker = IncidentTracker('data/incidents.json')
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
    
    def start(self) -> None:
        """Запускает бота и мониторинг."""
        logger.info("🤖 Бот запущен!")
        logger.info(f"⏰ Интервал проверки: {self.config.CHECK_INTERVAL} секунд")
        logger.info(f"📡 Мониторинг: {self.config.URL}")
        logger.info(f"✅ Ожидание команд... (Подписчиков: {self.subscriber_manager.get_count()})")
        
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
    
    def stop(self) -> None:
        """Останавливает бота и мониторинг."""
        logger.info("Остановка бота...")
        self.status_monitor.stop()
        logger.info("Бот остановлен")


def main():
    """Главная функция запуска бота."""
    bot = Bitrix24MonitorBot()
    bot.start()


if __name__ == "__main__":
    main()
