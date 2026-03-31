"""코어 영속화를 위한 SQLite 스키마 초기화."""

from __future__ import annotations

from pathlib import Path

from .sqlite import connect_sqlite

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    run_date TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL,
    collected_count INTEGER NOT NULL DEFAULT 0,
    ranked_count INTEGER NOT NULL DEFAULT 0,
    script_count INTEGER NOT NULL DEFAULT 0,
    queued_sync_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,
    run_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    key_points_json TEXT NOT NULL,
    source_url TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    run_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_issues_run_date_rank
ON issues(run_date, rank);

CREATE TABLE IF NOT EXISTS issue_scripts (
    issue_id TEXT NOT NULL,
    tone TEXT NOT NULL,
    script_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (issue_id, tone),
    FOREIGN KEY(issue_id) REFERENCES issues(issue_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notion_sync_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id TEXT NOT NULL,
    run_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(issue_id) REFERENCES issues(issue_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notion_sync_queue_run_date_status
ON notion_sync_queue(run_date, status);

CREATE TABLE IF NOT EXISTS source_failures (
    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);
"""


def bootstrap_sqlite_schema(db_path: str | Path) -> None:
    """MVP 테이블 스키마를 생성/마이그레이션한다."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect_sqlite(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
