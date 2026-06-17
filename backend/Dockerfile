# ============================================================
# Dockerfile — Oil Expert SaaS MVP (multi-stage)
# ============================================================

# Stage 1: Зависимости
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Финальный образ
FROM python:3.12-slim

WORKDIR /app

# Копируем установленные пакеты из builder
COPY --from=builder /install /usr/local

# Системные зависимости для psycopg2, openpyxl
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Код приложения
COPY app/ ./app/

# Создаём непривилегированного пользователя
RUN groupadd -r oiluser && useradd -r -g oiluser -d /app -s /bin/bash oiluser && \
    chown -R oiluser:oiluser /app

USER oiluser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
