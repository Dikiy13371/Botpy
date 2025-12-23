# 🧪 Тесты для Telegram бота Bitrix24

## Установка зависимостей

```bash
# Установить все зависимости проекта (включая тестовые)
pip install -r requirements.txt

# Или только тестовые зависимости
pip install pytest pytest-asyncio pytest-cov pytest-mock pytest-xdist
```

**Примечание:** В Linux/WSL используйте `python3` и `pip3` вместо `python` и `pip`:
```bash
python3 -m pip install -r requirements.txt
```

## Запуск тестов

### Все тесты
```bash
# Linux/WSL
python3 -m pytest tests/ -v

# Windows
pytest tests/ -v
```

### Только unit тесты
```bash
pytest tests/test_database.py -v
```

### Только integration тесты
```bash
pytest tests/test_integration.py -v
```

### Только stress тесты (медленные)
```bash
pytest tests/test_stress.py -v -m slow
```

### С покрытием кода
```bash
pytest tests/ --cov=services --cov=handlers --cov=config --cov-report=html
```

### Параллельный запуск (быстрее)
```bash
pytest tests/ -n auto
```

## Структура тестов

- `test_database.py` - Unit тесты для БД и сервисов
- `test_integration.py` - Integration тесты для критичных потоков
- `test_stress.py` - Stress тесты для проверки производительности

## Маркеры

- `@pytest.mark.slow` - Медленные тесты (можно пропустить: `-m "not slow"`)

## Примеры

```bash
# Запустить один тест
pytest tests/test_database.py::test_add_subscriber -v

# Запустить тесты с фильтром
pytest tests/ -k "subscriber" -v

# Запустить с максимальным выводом
pytest tests/ -vv -s --tb=long

# Генерировать HTML отчет
pytest tests/ --html=report.html --self-contained-html
```

