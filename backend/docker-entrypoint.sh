#!/bin/sh
# Точка входа контейнера бэкенда: миграции, затем сервер.
# Миграции идут до старта uvicorn: приложение не должно подниматься на старой схеме.
set -e

echo "[entrypoint] Применяю миграции базы данных..."
alembic upgrade head

if [ "${SEED_DEMO_USER:-false}" = "true" ]; then
    echo "[entrypoint] Создаю демо-пользователя (только для разработки)..."
    python -m app.cli seed-demo || echo "[entrypoint] Демо-пользователь уже есть"
fi

echo "[entrypoint] Запускаю: $*"
exec "$@"
