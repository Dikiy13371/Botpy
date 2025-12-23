# ⚡ Быстрый старт для тестирования

## Шаг 1: Создайте виртуальное окружение (рекомендуется)

```bash
# Linux/WSL
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

## Шаг 2: Установите зависимости (ОБЯЗАТЕЛЬНО!)

```bash
# Linux/WSL (после активации venv)
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Windows (после активации venv)
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Если venv сломан, пересоздайте его:**
```bash
# Linux/WSL
rm -rf venv
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

**Это установит:**
- Все зависимости проекта (aiohttp, aiosqlite, beautifulsoup4 и т.д.)
- Все зависимости для тестирования (pytest, pytest-asyncio и т.д.)

## Шаг 3: Проверьте установку

```bash
# Linux/WSL
python3 -c "import aiosqlite, aiohttp, pytest, pytest_asyncio; print('✅ Все установлено!')"

# Windows
python -c "import aiosqlite, aiohttp, pytest, pytest_asyncio; print('✅ Все установлено!')"
```

Если видите `✅ Все установлено!` - можно продолжать.

## Шаг 4: Запустите тесты

```bash
# Linux/WSL
python3 -m pytest tests/ -v

# Windows
pytest tests/ -v
```

## Шаг 5: Запустите Health Check

```bash
# Linux/WSL
python3 debug/check_bot.py

# Windows
python debug/check_bot.py
```

## ❌ Если что-то не работает

### Проблема: `python3: command not found`

**Решение:** Используйте `python` вместо `python3`:
```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

### Проблема: `pip: command not found`

**Решение:** Установите pip:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-pip

# Затем
python3 -m pip install -r requirements.txt
```

### Проблема: `Permission denied`

**Решение:** Используйте `--user`:
```bash
python3 -m pip install --user -r requirements.txt
```

### Проблема: Все еще ошибки импорта

**Решение:** Проверьте, что вы в правильной директории и используете правильный Python:
```bash
# Проверить текущую директорию
pwd

# Проверить версию Python
python3 --version

# Проверить установленные пакеты
python3 -m pip list | grep -E "aiohttp|aiosqlite|pytest"
```

### Проблема: `ModuleNotFoundError: No module named 'pip._vendor.pyparsing'`

**Решение:** Виртуальное окружение повреждено, пересоздайте его:
```bash
# Удалить старое venv
rm -rf venv

# Создать новое
python3 -m venv venv
source venv/bin/activate

# Обновить pip и установить зависимости
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 📚 Дополнительная информация

- Полная документация: [SETUP_TESTING.md](SETUP_TESTING.md)
- Руководство по тестированию: [TESTING_GUIDE.md](TESTING_GUIDE.md)
- Документация по тестам: [tests/README.md](tests/README.md)

