"""Построитель меню и клавиатур для Telegram бота."""

from typing import List
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


class MenuBuilder:
    """Построитель меню и клавиатур для бота."""
    
    @staticmethod
    def get_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
        """
        Главное меню со всеми основными разделами.
        
        Args:
            is_admin: Является ли пользователь администратором
        
        Returns:
            InlineKeyboardMarkup: Меню с кнопками
        """
        buttons: List[List[InlineKeyboardButton]] = [
            [InlineKeyboardButton("📊 Мониторинг & Статус", callback_data="menu_monitoring")],
            [InlineKeyboardButton("🔔 Управление подписками", callback_data="menu_subscribe")],
            [InlineKeyboardButton("📈 Аналитика & Метрики", callback_data="menu_analytics")],
        ]
        
        if is_admin:
            buttons.append(
                [InlineKeyboardButton("⚙️ Администрирование", callback_data="menu_admin")]
            )
        
        buttons.extend([
            [InlineKeyboardButton("❓ Справка", callback_data="menu_help")],
            [InlineKeyboardButton("✖️ Закрыть меню", callback_data="close_menu")]
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_monitoring_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
        """
        Меню мониторинга и статуса.
        
        Args:
            is_admin: Является ли пользователь администратором (параметр оставлен для совместимости)
        
        Returns:
            InlineKeyboardMarkup: Меню мониторинга
        """
        buttons = [
            [InlineKeyboardButton("🔄 Проверить статус сейчас", callback_data="cmd_status")],
            [InlineKeyboardButton("📋 История инцидентов", callback_data="cmd_incidents")],
            [InlineKeyboardButton("🏥 Статус здоровья бота", callback_data="cmd_health")],
            [InlineKeyboardButton("📝 Последние логи", callback_data="cmd_logs")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")],
        ]
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_subscribe_menu(is_subscribed: bool = False) -> InlineKeyboardMarkup:
        """
        Меню управления подписками.
        
        Args:
            is_subscribed: Подписан ли пользователь
        
        Returns:
            InlineKeyboardMarkup: Меню подписок
        """
        buttons: List[List[InlineKeyboardButton]] = []
        
        if not is_subscribed:
            buttons.append([InlineKeyboardButton("✅ Подписаться", callback_data="cmd_subscribe")])
        else:
            buttons.append([InlineKeyboardButton("❌ Отписаться", callback_data="cmd_unsubscribe")])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_main")])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_analytics_menu() -> InlineKeyboardMarkup:
        """
        Меню аналитики и метрик.
        
        Returns:
            InlineKeyboardMarkup: Меню аналитики
        """
        buttons = [
            [InlineKeyboardButton("📊 Базовая статистика", callback_data="cmd_stats")],
            [InlineKeyboardButton("📉 Подробные метрики", callback_data="cmd_metrics")],
            [InlineKeyboardButton("📤 Экспорт данных CSV", callback_data="cmd_export")],
            [InlineKeyboardButton("📜 Последние инциденты", callback_data="cmd_history")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_admin_menu() -> InlineKeyboardMarkup:
        """
        Меню администратора (только для ADMIN_CHAT_ID).
        
        Returns:
            InlineKeyboardMarkup: Меню администратора
        """
        buttons = [
            [InlineKeyboardButton("📋 Последние логи", callback_data="cmd_logs")],
            [InlineKeyboardButton("🔧 Информация о БД", callback_data="cmd_db_info")],
            [InlineKeyboardButton("🧪 Проверить подключения", callback_data="cmd_check_conn")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_help_menu() -> InlineKeyboardMarkup:
        """
        Меню справки.
        
        Returns:
            InlineKeyboardMarkup: Меню справки
        """
        buttons = [
            [InlineKeyboardButton("📖 Как использовать бот", callback_data="help_how_to")],
            [InlineKeyboardButton("💬 О боте", callback_data="help_about")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")],
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_quick_action_buttons() -> InlineKeyboardMarkup:
        """
        Быстрые кнопки в сообщениях (для часто используемых команд).
        
        Returns:
            InlineKeyboardMarkup: Быстрые кнопки
        """
        buttons = [
            [
                InlineKeyboardButton("🔄 Статус", callback_data="cmd_status"),
                InlineKeyboardButton("📊 Метрики", callback_data="cmd_metrics"),
            ],
            [
                InlineKeyboardButton("📋 История", callback_data="cmd_history"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu_main"),
            ],
        ]
        return InlineKeyboardMarkup(buttons)

