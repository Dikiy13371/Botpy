# 🔧 Исправление проблем с виртуальным окружением

## Проблема: `ModuleNotFoundError: No module named 'pip._vendor.pyparsing'`

Это означает, что виртуальное окружение повреждено.

## Решение 1: Пересоздать venv (быстрый способ)

### В WSL/Linux:

```bash
# 1. Удалить старое venv
rm -rf venv

# 2. Создать новое виртуальное окружение БЕЗ pip (быстрее)
python3 -m venv venv --without-pip

# 3. Активировать venv
source venv/bin/activate

# 4. Установить pip вручную
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
rm get-pip.py

# 5. Установить зависимости
python3 -m pip install -r requirements.txt

# 6. Проверить установку
python3 -c "import aiosqlite, aiohttp, pytest; print('✅ Все установлено!')"
```

## Решение 2: Использовать системный Python (без venv)

Если venv создается проблематично, можно использовать системный Python:

```bash
# 1. Установить зависимости в системный Python (с --user для безопасности)
python3 -m pip install --user -r requirements.txt

# 2. Проверить установку
python3 -c "import aiosqlite, aiohttp, pytest; print('✅ Все установлено!')"

# 3. Запустить тесты
python3 -m pytest tests/ -v
```

**Примечание:** Использование `--user` устанавливает пакеты только для текущего пользователя, не требуя sudo.

### В Windows (PowerShell):

```powershell
# 1. Удалить старое venv
Remove-Item -Recurse -Force venv

# 2. Создать новое виртуальное окружение
python -m venv venv

# 3. Активировать venv
venv\Scripts\Activate.ps1

# 4. Обновить pip
python -m pip install --upgrade pip

# 5. Установить зависимости
pip install -r requirements.txt

# 6. Проверить установку
python -c "import aiosqlite, aiohttp, pytest; print('✅ Все установлено!')"
```

## Решение 3: Если venv зависает при создании

Если `python3 -m venv venv` зависает или прерывается:

```bash
# Попробуйте создать venv с явным указанием Python
python3.12 -m venv venv --without-pip

# Или используйте virtualenv (если установлен)
sudo apt install python3-virtualenv
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## После исправления

Теперь можно запускать тесты:

```bash
# WSL/Linux
python3 -m pytest tests/ -v

# Windows
pytest tests/ -v
```

И health check:

```bash
# WSL/Linux
python3 debug/check_bot.py

# Windows
python debug/check_bot.py
```

