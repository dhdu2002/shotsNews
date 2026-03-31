# pyright: reportExplicitAny=false

"""데스크톱 런타임 셸과 UI 연결 진입점을 제공한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING
from typing import Any

from .bootstrap import build_application_context
from .infrastructure.db.schema import bootstrap_sqlite_schema

if TYPE_CHECKING:
    from .bootstrap import ApplicationContext


@dataclass(slots=True)
class DesktopApp:
    """PySide6 UI가 호출하는 런타임 셸이다.

    위젯과 화면 로직은 포함하지 않고, 시작/중지/상태 조회/수동 실행만 노출한다.
    """

    context: ApplicationContext | None = None
    started_at: datetime | None = None
    last_manual_run: dict[str, Any] | None = None

    def start(self) -> None:
        """애플리케이션 컨텍스트와 로컬 저장소를 준비한다."""
        if self.context is not None:
            return

        self.context = build_application_context()
        bootstrap_sqlite_schema(self.context.db_path)
        self.context.scheduler.start()
        self.started_at = datetime.now()

    def stop(self) -> None:
        """백그라운드 런타임을 안전하게 정리한다."""
        if self.context is not None:
            self.context.scheduler.stop()

    def run_now(self, run_date: date | None = None) -> dict[str, Any]:
        """하루 파이프라인을 즉시 한 번 실행하고 요약을 반환한다."""
        if self.context is None:
            self.start()

        assert self.context is not None
        assert self.context.pipeline is not None

        selected_date = run_date or date.today()
        result = self.context.pipeline.run_for_date(selected_date)
        self.last_manual_run = result
        return result

    def status(self) -> dict[str, Any]:
        """UI가 사용할 런타임 스냅샷을 반환한다."""
        if self.context is None:
            return {
                "app_name": "DailyIssueDesktop",
                "started_at": self._format_datetime(self.started_at),
                "scheduler_running": False,
                "scheduler_interval_minutes": 0,
                "latest_run": None,
                "queue": {"pending": 0, "synced": 0, "failed": 0},
                "top_issues": [],
                "source_failures": [],
                "sources": [],
                "db_path": "",
                "data_dir": "",
                "log_dir": "",
                "cache_dir": "",
                "notion_enabled": False,
                "openai_model": "",
                "last_manual_run": self.last_manual_run,
            }

        context = self.context
        latest_run = context.repository.get_latest_run_summary()

        latest_run_date = date.today()
        if latest_run is not None:
            latest_run_date = date.fromisoformat(str(latest_run["run_date"]))

        pending = context.repository.list_pending_sync(latest_run_date)
        top_issues = context.repository.list_ranked_issue_summaries(
            latest_run_date,
            limit=context.settings.top_k,
        )
        source_failures = []
        if latest_run is not None:
            source_failures = context.repository.list_source_failures_for_run(str(latest_run["run_id"]))

        return {
            "app_name": context.settings.app_name,
            "started_at": self._format_datetime(self.started_at),
            "scheduler_running": True,
            "scheduler_interval_minutes": context.settings.scheduler_interval_minutes,
            "latest_run": latest_run,
            "queue": {
                "pending": len(pending),
                "synced": latest_run["queued_sync_count"] if latest_run else 0,
                "failed": latest_run["failure_count"] if latest_run else 0,
            },
            "top_issues": top_issues,
            "source_failures": source_failures,
            "sources": self._build_source_snapshots(),
            "db_path": context.db_path,
            "data_dir": str(context.paths.root_data_dir),
            "log_dir": str(context.paths.log_dir),
            "cache_dir": str(context.paths.cache_dir),
            "notion_enabled": context.settings.notion_enabled,
            "openai_model": context.settings.openai_model,
            "last_manual_run": self.last_manual_run,
        }

    def _build_source_snapshots(self) -> list[dict[str, Any]]:
        """UI에 표시할 수집원 구성 상태를 만든다."""
        assert self.context is not None

        settings = self.context.settings
        return [
            {
                "name": "rss",
                "configured_count": len(settings.rss_urls),
                "configured": bool(settings.rss_urls),
                "note": f"피드 {len(settings.rss_urls)}개 연결",
            },
            {
                "name": "youtube",
                "configured_count": len(settings.youtube_feed_urls),
                "configured": bool(settings.youtube_feed_urls),
                "note": f"피드 {len(settings.youtube_feed_urls)}개 연결",
            },
            {
                "name": "reddit",
                "configured_count": len(settings.reddit_subreddits),
                "configured": bool(settings.reddit_subreddits),
                "note": f"서브레딧 {len(settings.reddit_subreddits)}개 연결",
            },
            {
                "name": "twitter_x",
                "configured_count": 1 if settings.twitter_bearer_token else 0,
                "configured": bool(settings.twitter_bearer_token),
                "note": "Bearer 토큰 필요",
            },
        ]

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        """UI용 날짜/시간 문자열을 반환한다."""
        if value is None:
            return None
        return value.isoformat(timespec="seconds")
