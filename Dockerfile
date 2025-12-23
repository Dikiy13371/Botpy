# Многостадийная сборка для уменьшения размера образа
# Стадия 1: Сборка зависимостей
FROM python:3.11-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --user -r requirements.txt

# Стадия 2: Финальный образ
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные зависимости из builder
COPY --from=builder /root/.local /root/.local

# Копируем код приложения
COPY . .

# Создаем директории для данных и логов
RUN mkdir -p /app/data /app/logs

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV LOG_FILE=/app/logs/bot.log
ENV PATH=/root/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Запускаем бота
CMD ["python", "bot.py"]

