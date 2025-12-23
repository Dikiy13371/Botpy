"""Утилиты для форматирования сообщений Telegram."""

from typing import Optional
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.time_utils import get_msk_time


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для MarkdownV2.
    
    Args:
        text: Текст для экранирования
        
    Returns:
        str: Экранированный текст
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def escape_url(url: str) -> str:
    """
    Экранирует URL для MarkdownV2.
    
    Args:
        url: URL для экранирования
        
    Returns:
        str: Экранированный URL
    """
    return url.replace('-', '\\-').replace('.', '\\.').replace(':', '\\:').replace('/', '\\/')


def create_status_button() -> InlineKeyboardMarkup:
    """
    Создает кнопку для проверки статуса.
    
    Returns:
        InlineKeyboardMarkup: Разметка с кнопкой
    """
    markup = InlineKeyboardMarkup()
    button = InlineKeyboardButton("🔄 Проверить статус", callback_data="check_status")
    markup.add(button)
    return markup


def format_status_message(
    status_info: dict,
    url: str,
    is_alert: bool = False,
    start_time: Optional[datetime] = None,
    duration: Optional[str] = None
) -> str:
    """
    Форматирует сообщение о статусе для отправки в Telegram.
    
    Args:
        status_info: Словарь с информацией о статусе
        url: URL страницы статуса
        is_alert: Является ли это алертом
        start_time: Время начала сбоя
        duration: Длительность сбоя
        
    Returns:
        str: Отформатированное сообщение в MarkdownV2
    """
    if status_info.get('error'):
        return f"❌ {status_info['message']}"

    if status_info['has_issues']:
        msg = "🚨 *АЛЕРТ: Обнаружены проблемы\\!*\n\n"
        msg += "🔴 *ВРЕМЕННЫЙ СБОЙ*\n"

        if status_info.get('region'):
            msg += f"🌍 *Регион:* `{status_info['region']}`\n"

        if start_time:
            msg += f"⏰ *Сбой с:* `{start_time.strftime('%H:%M:%S')}` \\(МСК\\)\n"
            if duration:
                msg += f"⏱️ *Длится:* `{duration}`\n"

        msg += "\n"

        if status_info.get('description'):
            desc = escape_markdown_v2(status_info['description'])
            msg += f"📝 *Описание проблемы:*\n_{desc}_\n\n"

        msg += "⚠️ _Мы уже зафиксировали и решаем ситуацию\\._\n"
        msg += "⏳ _Пожалуйста, подождите\\. Скоро всё заработает\\._\n\n"

        escaped_url = escape_url(url)
        msg += f"🔄 *Обновлено:* `{get_msk_time().strftime('%H:%M:%S')}` \\(МСК\\)\n"
        msg += f"🔗 [Проверить статус]({escaped_url})"
    else:
        if is_alert:
            msg = "✅ *СЕРВИС ВОССТАНОВЛЕН\\!*\n\n"
            msg += "✅ *ВСЕ РАБОТАЕТ*\n"

            if status_info.get('region'):
                msg += f"🌍 *Регион:* `{status_info['region']}`\n"

            if start_time and duration:
                msg += f"⏰ *Сбой длился:* `{duration}`\n"
                msg += f"✅ *Восстановлено:* `{get_msk_time().strftime('%H:%M:%S')}` \\(МСК\\)\n\n"
            else:
                msg += "\n"
        else:
            msg = "✅ *Битрикс24 работает нормально*\n\n"
            msg += "Все системы функционируют штатно\\.\n\n"

        escaped_url = escape_url(url)
        msg += f"🔄 *Обновлено:* `{get_msk_time().strftime('%H:%M:%S')}` \\(МСК\\)\n"
        msg += f"🔗 [Проверить статус]({escaped_url})"

    return msg

