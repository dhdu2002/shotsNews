"""로컬 SQLite 스키마 초기화 스크립트."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



def _load_dependencies() -> tuple[Callable[[], Any], Callable[[str], None]]:
    bootstrap_module = import_module("src.daily_issue_app.bootstrap")
    schema_module = import_module("src.daily_issue_app.infrastructure.db.schema")
    return getattr(bootstrap_module, "build_application_context"), getattr(schema_module, "bootstrap_sqlite_schema")


def main() -> int:
    """SQLite 데이터베이스와 스키마를 생성한다."""
    build_application_context, bootstrap_sqlite_schema = _load_dependencies()
    context = build_application_context()
    bootstrap_sqlite_schema(context.db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
