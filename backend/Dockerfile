# Образ бэкенда дашборда: двухэтапная сборка, непривилегированный пользователь.
# Docker на машине разработки не установлен, поэтому образ здесь не проверялся —
# файл описывает целевой способ запуска на стенде.

# --- Этап 1: сборка зависимостей ---
FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /usr/local/bin/

WORKDIR /build

# Сначала только манифесты — слой с зависимостями кэшируется отдельно от кода.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Этап 2: рабочее окружение ---
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app

RUN groupadd --gid 1001 dashboard \
    && useradd --uid 1001 --gid dashboard --create-home --shell /usr/sbin/nologin dashboard

WORKDIR ${APP_HOME}

COPY --from=builder /opt/venv /opt/venv

COPY pyproject.toml alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app

RUN mkdir -p ${APP_HOME}/var \
    && chmod +x ${APP_HOME}/docker-entrypoint.sh \
    && chown -R dashboard:dashboard ${APP_HOME}

USER dashboard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
