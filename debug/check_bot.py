#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки здоровья бота
Запуск: python debug/check_bot.py
"""
import asyncio
import aiohttp
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import os
import sys

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()


class BotHealthCheck:
    def __init__(self):
        self.db_path = "data/bot.db"
        self.logs_path = "logs/bot.log"
        self.metrics_path = "data/metrics.json"
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bitrix_url = os.getenv("URL", "https://status.bitrix24.ru/")
    
    async def run_all_checks(self):
        """Запустить все проверки"""
        print("=" * 60)
        print("🤖 BOT HEALTH CHECK")
        print("=" * 60)
        
        await self.check_config()
        await self.check_database()
        await self.check_bitrix24()
        await self.check_telegram_api()
        await self.check_logs()
        await self.check_metrics()
        await self.check_file_permissions()
        
        print("=" * 60)
        print("✅ Проверка завершена")
        print("=" * 60)
    
    async def check_config(self):
        """Проверка конфигурации"""
        print("\n📋 Проверка конфигурации:")
        
        checks = {
            "BOT_TOKEN": self.bot_token is not None and len(self.bot_token) > 20,
            "URL Bitrix24": self.bitrix_url is not None,
            "GROUP_ID": os.getenv("GROUP_ID") is not None,
            "CHECK_INTERVAL": os.getenv("CHECK_INTERVAL", "300") != "",
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}")
    
    async def check_database(self):
        """Проверка БД"""
        print("\n📊 Проверка базы данных:")
        
        if not Path(self.db_path).exists():
            print(f"  ❌ БД файл не найден: {self.db_path}")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверка целостности
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()[0]
            integrity_ok = result == "ok"
            print(f"  {'✅' if integrity_ok else '❌'} Целостность БД")
            
            # Подписчики
            cursor.execute("SELECT COUNT(*) FROM subscribers;")
            sub_count = cursor.fetchone()[0]
            print(f"  📌 Подписчиков: {sub_count}")
            
            # Инциденты
            cursor.execute("SELECT COUNT(*) FROM incidents;")
            incident_count = cursor.fetchone()[0]
            print(f"  🚨 Инцидентов всего: {incident_count}")
            
            # Активные инциденты
            cursor.execute("SELECT COUNT(*) FROM incidents WHERE status='active';")
            active_count = cursor.fetchone()[0]
            print(f"  🔴 Активных инцидентов: {active_count}")
            
            # Размер БД
            db_size = Path(self.db_path).stat().st_size / (1024 * 1024)
            print(f"  💾 Размер БД: {db_size:.2f} МБ")
            
            conn.close()
            
        except Exception as e:
            print(f"  ❌ Ошибка при проверке БД: {e}")
    
    async def check_bitrix24(self):
        """Проверка доступности Bitrix24"""
        print("\n🌐 Проверка Bitrix24:")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.bitrix_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    is_ok = resp.status == 200
                    print(f"  {'✅' if is_ok else '⚠️'} HTTP {resp.status}")
        except asyncio.TimeoutError:
            print(f"  ❌ Таймаут при подключении (10s)")
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    async def check_telegram_api(self):
        """Проверка Telegram API"""
        print("\n📱 Проверка Telegram API:")
        
        if not self.bot_token:
            print(f"  ⚠️ BOT_TOKEN не установлен")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ok'):
                            bot_info = data.get('result', {})
                            print(f"  ✅ Telegram API доступен")
                            print(f"  🤖 Имя бота: @{bot_info.get('username', 'N/A')}")
                        else:
                            print(f"  ❌ Ошибка API: {data.get('description', 'Unknown')}")
                    else:
                        print(f"  ❌ HTTP {resp.status}")
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
    
    async def check_logs(self):
        """Проверка логов"""
        print("\n📝 Проверка логов:")
        
        if not Path(self.logs_path).exists():
            print(f"  ⚠️ Файл логов не найден: {self.logs_path}")
            return
        
        try:
            # Прочитать последние 20 строк
            with open(self.logs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-20:]
            
            # Подсчитать ошибки
            errors = sum(1 for line in lines if 'ERROR' in line or 'CRITICAL' in line)
            warnings = sum(1 for line in lines if 'WARNING' in line)
            
            print(f"  📊 Последние 20 строк логов:")
            print(f"  ❌ Ошибок: {errors}")
            print(f"  ⚠️ Предупреждений: {warnings}")
            
            # Показать последние ошибки
            if errors > 0:
                print(f"\n  Последние ошибки:")
                for line in lines:
                    if 'ERROR' in line or 'CRITICAL' in line:
                        print(f"    {line.strip()[:100]}")
        
        except Exception as e:
            print(f"  ❌ Ошибка при чтении логов: {e}")
    
    async def check_metrics(self):
        """Проверка метрик"""
        print("\n📈 Проверка метрик:")
        
        if not Path(self.metrics_path).exists():
            print(f"  ⚠️ Файл метрик не найден: {self.metrics_path}")
            return
        
        try:
            with open(self.metrics_path, 'r') as f:
                metrics = json.load(f)
            
            print(f"  ⏱️ Uptime: {metrics.get('uptime', 'N/A')}")
            print(f"  🚨 Алертов отправлено: {metrics.get('alerts_sent', 0)}")
            print(f"  ✅ Восстановлений: {metrics.get('recoveries_sent', 0)}")
            print(f"  📊 Проверок всего: {metrics.get('total_checks', 0)}")
            print(f"  🐛 Ошибок за час: {metrics.get('errors_last_hour', 0)}")
        
        except Exception as e:
            print(f"  ❌ Ошибка при чтении метрик: {e}")
    
    async def check_file_permissions(self):
        """Проверка прав доступа к файлам"""
        print("\n🔐 Проверка прав доступа:")
        
        paths = [
            ("data/", "Data directory"),
            ("logs/", "Logs directory"),
            (self.db_path, "Database file"),
            (self.logs_path, "Log file"),
            (".env", "Environment file"),
        ]
        
        for path, description in paths:
            if Path(path).exists():
                is_readable = os.access(path, os.R_OK)
                is_writable = os.access(path, os.W_OK)
                
                if is_readable and is_writable:
                    status = "✅"
                elif is_readable:
                    status = "⚠️"
                else:
                    status = "❌"
                
                print(f"  {status} {description}")
            else:
                print(f"  ⚠️ {description} - не найден")


if __name__ == "__main__":
    checker = BotHealthCheck()
    asyncio.run(checker.run_all_checks())

