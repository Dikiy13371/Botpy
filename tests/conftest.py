"""Конфигурация pytest для тестов."""
import pytest
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Настройка pytest-asyncio (опционально)
try:
    import pytest_asyncio
    pytest_plugins = ('pytest_asyncio',)
except ImportError:
    # pytest-asyncio не установлен, тесты все равно будут работать
    pass

