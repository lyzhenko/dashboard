"""Выгрузка ``openapi.json`` в корень проекта.

Запуск (из каталога ``backend/``)::

    uv run python -m app.openapi

Файл нужен фронтенду для генерации типов (``pnpm api:types``), поэтому схема
должна быть полной — теги, описания и примеры задаются в схемах и роутерах.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from app.core.logging import get_logger
from app.main import create_app

logger = get_logger(__name__)

#: ``backend/app/openapi.py`` → корень проекта.
PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT: Final = PROJECT_ROOT / "openapi.json"


def openapi_schema() -> dict[str, Any]:
    """Собрать схему OpenAPI текущего приложения."""
    return create_app().openapi()


def write_openapi(output: Path | None = None) -> Path:
    """Записать схему в файл (по умолчанию — ``<корень проекта>/openapi.json``)."""
    target = output or DEFAULT_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = openapi_schema()
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    """Точка входа ``python -m app.openapi``."""
    target = write_openapi()
    schema = openapi_schema()
    paths = schema.get("paths", {})
    operations = sum(len(item) for item in paths.values())
    logger.info("openapi.json записан: %s", target)
    logger.info("Путей: %s, операций: %s", len(paths), operations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DEFAULT_OUTPUT", "PROJECT_ROOT", "main", "openapi_schema", "write_openapi"]
