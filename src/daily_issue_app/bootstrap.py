"""비UI 런타임 의존성 조립 루트."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Protocol, cast

from .application.services.scheduler_service import SchedulerService
from .config.paths import AppPaths
from .config.settings import AppSettings, load_settings
from .pipeline import DailyIssuePipeline
from .infrastructure.repositories.sqlite_issue_repository import (
    SqliteIssueRepository,
)
from .infrastructure.services.multi_source_collector import MultiSourceCollector
from .infrastructure.services.notion_sync_service import NotionSyncService
from .infrastructure.services.openai_script_generator import (
    OpenAIScriptGenerator,
)
from .infrastructure.services.ranking_service import RankingService
from .infrastructure.services.rss_collector import RSSCollector
from .infrastructure.services.twitter_collector import TwitterXCollector
from .infrastructure.services.youtube_collector import YouTubeCollector


class SourceContentFetcherPort(Protocol):
    """수동 생성 시 source_url 본문을 다시 읽어 요약한다."""

    def fetch_summary(self, source_url: str) -> str | None:
        """기사 본문 기반 새 요약을 반환한다."""
        ...


@dataclass(slots=True)
class ApplicationContext:
    """코어 런타임 의존성 컨테이너."""

    settings: AppSettings
    paths: AppPaths
    scheduler: SchedulerService
    repository: SqliteIssueRepository
    collector: MultiSourceCollector
    ranking_service: RankingService
    script_generator: OpenAIScriptGenerator
    source_content_fetcher: SourceContentFetcherPort
    notion_sync: NotionSyncService
    pipeline: DailyIssuePipeline | None

    @property
    def db_path(self) -> str:
        """SQLite DB 파일 경로를 반환한다."""
        return str(self.paths.sqlite_db)


def build_application_context() -> ApplicationContext:
    """기본 런타임 의존성 그래프를 구성해 반환한다."""
    settings = load_settings()
    paths = AppPaths.from_env(settings.app_name)
    paths.ensure_directories()

    repository = SqliteIssueRepository(paths.sqlite_db)
    collector = MultiSourceCollector(
        {
            "rss": RSSCollector(
                feed_urls=settings.rss_urls,
                category_feed_urls=settings.source_pools.rss,
                domestic_feed_urls=settings.source_pools.rss_domestic,
                international_feed_urls=settings.source_pools.rss_international,
                default_limit=settings.max_candidates_per_category,
                timeout_seconds=settings.request_timeout_seconds,
            ),
            "youtube": YouTubeCollector(
                feed_urls=settings.youtube_feed_urls,
                category_feed_urls=settings.source_pools.youtube,
                default_limit=settings.max_candidates_per_category,
                timeout_seconds=settings.request_timeout_seconds,
            ),
            "twitter_x": TwitterXCollector(
                bearer_token=settings.twitter_bearer_token,
                query=settings.twitter_query,
                category_queries=settings.source_pools.twitter_x,
                timeout_seconds=settings.request_timeout_seconds,
            ),
        }
    )
    ranking_service = RankingService(top_k=settings.top_k)
    script_generator = OpenAIScriptGenerator(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )
    source_content_fetcher_module = import_module(f"{__package__}.infrastructure.services.source_content_fetcher")
    source_content_fetcher_cls = getattr(source_content_fetcher_module, "SourceContentFetcher")
    source_content_fetcher = cast(
        SourceContentFetcherPort,
        source_content_fetcher_cls(timeout_seconds=settings.request_timeout_seconds),
    )
    notion_sync = NotionSyncService(
        database_id=settings.notion_database_id,
        notion_token=settings.notion_token,
        enabled=settings.notion_enabled,
        timeout_seconds=settings.request_timeout_seconds,
    )
    scheduler = SchedulerService(timezone=settings.timezone)

    context = ApplicationContext(
        settings=settings,
        paths=paths,
        scheduler=scheduler,
        repository=repository,
        collector=collector,
        ranking_service=ranking_service,
        script_generator=script_generator,
        source_content_fetcher=source_content_fetcher,
        notion_sync=notion_sync,
        pipeline=None,
    )
    pipeline = DailyIssuePipeline(context)
    context.pipeline = pipeline
    def _scheduled_run() -> None:
        _ = pipeline.run_for_date(date.today())

    _ = scheduler.register_interval_job(_scheduled_run, settings.scheduler_interval_minutes)

    return context
