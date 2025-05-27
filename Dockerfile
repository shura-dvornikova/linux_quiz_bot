# syntax=docker/dockerfile:1        # можно удалить, если buildx всё равно не нужен
FROM python:3.12-slim

# отключаем .pyc и буферизацию вывода
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# сначала — только зависимости, чтобы кешировалось
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# потом код
COPY bot/ bot/

CMD ["python", "-m", "bot.main"]
