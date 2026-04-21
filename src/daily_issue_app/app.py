# pyright: reportExplicitAny=false

"""데스크톱 런타임 셸과 UI 연결 진입점을 제공한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from os import environ
from typing import TYPE_CHECKING
from typing import Any, Callable, cast

from .bootstrap import build_application_context
from .config.settings import save_settings_file
from .domain.enums import ScriptTone
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
            self.context = None

    def run_now(
        self,
        run_date: date | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """하루 파이프라인을 즉시 한 번 실행하고 요약을 반환한다."""
        if self.context is None:
            self.start()

        assert self.context is not None
        assert self.context.pipeline is not None

        selected_date = run_date or date.today()
        result = self.context.pipeline.run_for_date(selected_date, progress_callback=progress_callback)
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
                "source_pools_path": "",
                "source_pools_enabled": False,
                "source_pool_summary": "",
                "db_path": "",
                "data_dir": "",
                "log_dir": "",
                "cache_dir": "",
                "notion_enabled": False,
                "openai_model": "",
                "rss_urls": "",
                "youtube_feed_urls": "",
                "reddit_subreddits": "",
                "twitter_query": "",
                "notion_database_id": "",
                "notion_token_masked": "",
                "openai_api_key_masked": "",
                "twitter_bearer_token_masked": "",
                "last_manual_run": self.last_manual_run,
            }

        context = self.context
        latest_run = context.repository.get_latest_run_summary()

        latest_run_date = date.today()
        if latest_run is not None:
            latest_run_date = date.fromisoformat(str(latest_run["run_date"]))

        pending = context.repository.list_pending_sync(latest_run_date)
        top_issues = self._normalize_top_issue_payloads(
            context.repository.list_ranked_issue_summaries(
                latest_run_date,
                limit=5 * 5 * 2,  # 5분류 × Top 5 × 2지역 = 최대 50개
            )
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
            "source_pools_path": context.settings.source_pools.path,
            "source_pools_enabled": context.settings.source_pools.enabled,
            "source_pool_summary": self._build_source_pool_summary(),
            "db_path": context.db_path,
            "data_dir": str(context.paths.root_data_dir),
            "log_dir": str(context.paths.log_dir),
            "cache_dir": str(context.paths.cache_dir),
            "notion_enabled": context.settings.notion_enabled,
            "openai_model": context.settings.openai_model,
            "rss_urls": ", ".join(context.settings.rss_urls),
            "youtube_feed_urls": ", ".join(context.settings.youtube_feed_urls),
            "reddit_subreddits": ", ".join(context.settings.reddit_subreddits),
            "twitter_query": context.settings.twitter_query,
            "notion_database_id": context.settings.notion_database_id,
            "notion_token_masked": self._mask_secret(context.settings.notion_token),
            "openai_api_key_masked": self._mask_secret(context.settings.openai_api_key),
            "twitter_bearer_token_masked": self._mask_secret(context.settings.twitter_bearer_token),
            "last_manual_run": self.last_manual_run,
        }

    def generate_issue_scripts(self, issue_id: str) -> dict[str, Any]:
        """선택 이슈 1건의 3톤 스크립트를 즉시 생성하고 반환한다."""
        if self.context is None:
            self.start()

        assert self.context is not None
        issue = self.context.repository.get_issue_by_id(issue_id)
        if issue is None:
            raise ValueError("선택한 이슈를 찾을 수 없습니다.")

        script_set = self.context.script_generator.generate(issue)
        self.context.repository.save_scripts([script_set])
        return self._build_issue_script_payload(issue.issue_id)

    def get_issue_scripts(self, issue_id: str) -> dict[str, Any]:
        """선택 이슈 1건의 저장된 3톤 스크립트를 반환한다."""
        if self.context is None:
            self.start()

        return self._build_issue_script_payload(issue_id)

    @staticmethod
    def _normalize_top_issue_payloads(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """런타임 status payload에 점수 총합/세부항목 키를 안정적으로 보장한다."""
        normalized: list[dict[str, Any]] = []
        for item in items:
            category = str(item.get("category") or "")
            final_category = str(item.get("final_category") or category)
            initial_category = str(item.get("initial_category") or "")
            normalized.append(
                {
                    **item,
                    "category": final_category or category,
                    "final_category": final_category,
                    "initial_category": initial_category,
                    "duplicate_count": DesktopApp._to_int(item.get("duplicate_count")),
                    "score": DesktopApp._normalize_score_payload(item.get("score")),
                    "score_breakdown": DesktopApp._normalize_score_breakdown(item.get("score_breakdown")),
                }
            )
        return normalized

    @staticmethod
    def _normalize_score_payload(value: object) -> float | str | dict[str, object]:
        """숫자/문자/딕셔너리 형태의 점수 payload를 UI 친화적으로 정리한다."""
        if isinstance(value, dict):
            source = cast(dict[object, object], value)
            normalized: dict[str, object] = {}
            for key, item in source.items():
                normalized[str(key)] = item
            return normalized
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0.0
            try:
                return float(stripped)
            except ValueError:
                return stripped
        return 0.0

    @staticmethod
    def _normalize_score_breakdown(value: object) -> dict[str, object] | list[object] | str:
        """세부 점수 payload를 UI 프리젠터가 그대로 읽을 수 있는 형태로 정리한다."""
        if isinstance(value, dict):
            source = cast(dict[object, object], value)
            normalized: dict[str, object] = {}
            for key, item in source.items():
                normalized[str(key)] = item
            return normalized
        if isinstance(value, list):
            return cast(list[object], value)
        if isinstance(value, str):
            return value
        return {}

    @staticmethod
    def _to_int(value: object) -> int:
        """숫자/문자 혼합 입력도 안전하게 정수로 정규화한다."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0
            try:
                return int(float(stripped))
            except ValueError:
                return 0
        return 0

    def save_settings(self, values: dict[str, str]) -> str:
        """설정 파일을 저장하고 런타임을 다시 로드한다."""
        saved_path = save_settings_file(values)

        for key, value in values.items():
            normalized = value.strip()
            if normalized and not normalized.startswith("*"):
                environ[key] = normalized

        self.stop()
        self.start()
        return saved_path

    def _build_source_snapshots(self) -> list[dict[str, Any]]:
        """UI에 표시할 수집원 구성 상태를 만든다."""
        assert self.context is not None

        collector = self.context.collector
        describe_fn = getattr(collector, "describe_sources", None)
        if callable(describe_fn):
            snapshots = describe_fn()
            if isinstance(snapshots, list):
                snapshot_items = cast(list[object], snapshots)
                normalized_snapshots: list[dict[str, Any]] = []
                for item in snapshot_items:
                    if not isinstance(item, dict):
                        continue
                    source_item = cast(dict[object, object], item)
                    normalized_item: dict[str, Any] = {}
                    for key, value in source_item.items():
                        normalized_item[str(key)] = value
                    normalized_snapshots.append(normalized_item)
                return normalized_snapshots

        settings = self.context.settings
        return [
            {
                "name": "rss",
                "configured_count": len(settings.rss_urls),
                "configured": bool(settings.rss_urls),
                "note": f"공용 피드 {len(settings.rss_urls)}개",
            },
            {
                "name": "youtube",
                "configured_count": len(settings.youtube_feed_urls),
                "configured": bool(settings.youtube_feed_urls),
                "note": f"공용 피드 {len(settings.youtube_feed_urls)}개",
            },
            {
                "name": "reddit",
                "configured_count": len(settings.reddit_subreddits),
                "configured": bool(settings.reddit_subreddits),
                "note": f"공용 서브레딧 {len(settings.reddit_subreddits)}개",
            },
            {
                "name": "twitter_x",
                "configured_count": 1 if settings.twitter_bearer_token else 0,
                "configured": bool(settings.twitter_bearer_token),
                "note": "공용 쿼리 1개 · Bearer 토큰 필요",
            },
        ]

    def _build_issue_script_payload(self, issue_id: str) -> dict[str, Any]:
        """이슈 ID 기준 초안/메타정보를 UI 친화 payload로 정리한다."""
        assert self.context is not None

        issue = self.context.repository.get_issue_by_id(issue_id)
        if issue is None:
            raise ValueError("선택한 이슈를 찾을 수 없습니다.")

        scripts = self.context.repository.list_scripts_for_issue(issue_id)
        tone_payload: dict[str, str] = {}
        for tone in ScriptTone:
            tone_payload[tone.value] = str(scripts.get(tone) or "")

        return {
            "issue_id": issue.issue_id,
            "title": issue.title,
            "source_url": issue.source_url,
            "category": issue.category.value,
            "score": issue.score,
            "tones": tone_payload,
        }

    def _build_source_pool_summary(self) -> str:
        """카테고리별 소스 풀 적용 여부를 한 줄 요약으로 반환한다."""
        assert self.context is not None

        pools = self.context.settings.source_pools
        if not pools.enabled:
            return "카테고리 전용 source pool 없이 공용 환경변수 소스를 사용 중입니다."

        summaries: list[str] = []
        for source_name in ("rss", "youtube", "reddit", "twitter_x"):
            categories = pools.categories_for_source(source_name)
            if not categories:
                continue
            category_names = ", ".join(category.label for category in categories)
            summaries.append(f"{source_name}: {len(categories)}개 카테고리 ({category_names})")
        return "카테고리 전용 source pool 적용 중 · " + " / ".join(summaries)

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        """UI용 날짜/시간 문자열을 반환한다."""
        if value is None:
            return None
        return value.isoformat(timespec="seconds")

    @staticmethod
    def _mask_secret(value: str) -> str:
        """민감값은 일부만 보이도록 마스킹한다."""
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * max(4, len(value) - 8)}{value[-4:]}"
