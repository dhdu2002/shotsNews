"""런타임 설정 모델 및 로더."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(slots=True, frozen=True)
class AppSettings:
    """계층 간 공유되는 설정 계약."""

    app_name: str
    timezone: str
    top_k: int
    max_candidates_per_category: int
    notion_database_id: str
    notion_token: str
    notion_enabled: bool
    openai_model: str
    openai_api_key: str
    request_timeout_seconds: int
    scheduler_interval_minutes: int
    rss_urls: tuple[str, ...]
    youtube_feed_urls: tuple[str, ...]
    reddit_subreddits: tuple[str, ...]
    reddit_user_agent: str
    twitter_bearer_token: str
    twitter_query: str


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def load_settings() -> AppSettings:
    """환경변수에서 기본값과 함께 앱 설정을 로드한다."""
    return AppSettings(
        app_name=getenv("APP_NAME", "DailyIssueDesktop"),
        timezone=getenv("APP_TIMEZONE", "Asia/Seoul"),
        top_k=int(getenv("APP_TOP_K", "5")),
        max_candidates_per_category=int(getenv("APP_MAX_CANDIDATES", "20")),
        notion_database_id=getenv("NOTION_DATABASE_ID", ""),
        notion_token=getenv("NOTION_TOKEN", ""),
        notion_enabled=getenv("NOTION_ENABLED", "false").lower() in {"1", "true", "yes"},
        openai_model=getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_api_key=getenv("OPENAI_API_KEY", ""),
        request_timeout_seconds=int(getenv("APP_REQUEST_TIMEOUT_SECONDS", "15")),
        scheduler_interval_minutes=int(getenv("APP_SCHEDULER_INTERVAL_MINUTES", "60")),
        rss_urls=_split_csv(
            getenv(
                "APP_RSS_URLS",
                "https://hnrss.org/frontpage,https://www.theverge.com/rss/index.xml",
            )
        ),
        youtube_feed_urls=_split_csv(getenv("APP_YOUTUBE_FEED_URLS", "")),
        reddit_subreddits=_split_csv(getenv("APP_REDDIT_SUBREDDITS", "technology,MachineLearning")),
        reddit_user_agent=getenv("APP_REDDIT_USER_AGENT", "daily-issue-desktop/0.1"),
        twitter_bearer_token=getenv("TWITTER_BEARER_TOKEN", ""),
        twitter_query=getenv("TWITTER_QUERY", "ai OR technology"),
    )
