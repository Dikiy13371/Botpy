# 🚀 Быстрая настройка тестирования

## ⚠️ ВАЖНО: Сначала установите зависимости!

**Без установки зависимостей тесты не запустятся!**

## Установка зависимостей

### Linux/WSL

```bash
# 1. Установить зависимости проекта (ОБЯЗАТЕЛЬНО!)
python3 -m pip install -r requirements.txt

# Или если pip3 установлен глобально
pip3 install -r requirements.txt

# 2. Проверить установку
python3 -c "import aiosqlite, aiohttp, pytest; print('✅ Зависимости установлены')"
```

### Windows

```bash
# 1. Установить зависимости проекта (ОБЯЗАТЕЛЬНО!)
pip install -r requirements.txt

# 2. Проверить установку
python -c "import aiosqlite, aiohttp, pytest; print('✅ Зависимости установлены')"
```

### Если pip не найден

```bash
# Linux/WSL - установить pip
sudo apt update
sudo apt install python3-pip

# Затем установить зависимости
python3 -m pip install -r requirements.txt
```

## Проверка установки

```bash
# Linux/WSL
python3 -m pytest --version

# Windows
pytest --version
```

Должно показать версию pytest (например, `pytest 7.4.3`)

## Запуск тестов

### Linux/WSL

```bash
# Все тесты
python3 -m pytest tests/ -v

# С покрытием кода
python3 -m pytest tests/ --cov=services --cov=handlers --cov=config

# Только быстрые тесты
python3 -m pytest tests/ -m "not slow" -v
```

### Windows

```bash
# Все тесты
pytest tests/ -v

# С покрытием кода
pytest tests/ --cov=services --cov=handlers --cov=config

# Только быстрые тесты
pytest tests/ -m "not slow" -v
```

## Запуск Health Check

### Linux/WSL

```bash
python3 debug/check_bot.py
```

### Windows

```bash
python debug/check_bot.py
```

## Решение проблем

### Ошибка: `ModuleNotFoundError: No module named 'aiosqlite'` или `No module named 'aiohttp'`

**Решение:** Установите зависимости проекта:
```bash
# Linux/WSL
python3 -m pip install -r requirements.txt

# Windows
pip install -r requirements.txt

# Проверьте установку
python3 -c "import aiosqlite, aiohttp; print('✅ OK')"
```

### Ошибка: `ModuleNotFoundError: No module named 'pytest_asyncio'`

**Решение:** Установите pytest-asyncio:
```bash
# Linux/WSL
python3 -m pip install pytest-asyncio

# Windows
pip install pytest-asyncio

# Или установите все зависимости сразу
python3 -m pip install -r requirements.txt
```

### Ошибка: `python: command not found`

**Решение:** Используйте `python3` вместо `python`:
```bash
python3 -m pytest tests/ -v
```

### Ошибка: `pytest: command not found`

**Решение:** Установите pytest:
```bash
# Linux/WSL
python3 -m pip install pytest pytest-asyncio

# Windows
pip install pytest pytest-asyncio
```

### Ошибка: `Unknown config option: asyncio_mode`

**Решение:** Обновите pytest-asyncio:
```bash
# Linux/WSL
python3 -m pip install --upgrade pytest-asyncio

# Windows
pip install --upgrade pytest-asyncio
```

## Проверка окружения

Убедитесь, что все зависимости установлены:

```bash
# Linux/WSL
python3 -c "import aiosqlite, aiohttp, pytest; print('✅ Все зависимости установлены')"

# Windows
python -c "import aiosqlite, aiohttp, pytest; print('✅ Все зависимости установлены')"
```

