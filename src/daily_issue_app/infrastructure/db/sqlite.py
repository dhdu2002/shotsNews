"""SQLite 연결 유틸리티."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """row_factory가 설정된 SQLite 연결을 반환한다."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
