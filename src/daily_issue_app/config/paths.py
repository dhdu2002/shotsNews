"""데스크톱 런타임용 파일 경로 유틸리티."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AppPaths:
    """앱이 사용하는 로컬 파일시스템 경로 집합."""

    root_data_dir: Path
    sqlite_db: Path
    log_dir: Path
    cache_dir: Path

    @classmethod
    def from_env(cls, app_name: str) -> "AppPaths":
        """환경변수 기준으로 Windows 친화 경로를 계산한다."""
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / app_name
        return cls(
            root_data_dir=base,
            sqlite_db=base / "daily_issues.sqlite3",
            log_dir=base / "logs",
            cache_dir=base / "cache",
        )

    def ensure_directories(self) -> None:
        """필수 런타임 디렉터리를 생성한다."""
        self.root_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
