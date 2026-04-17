"""런타임 설정 모델 및 로더."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from os import getenv
from pathlib import Path

from .source_pools import CategorySourcePools, load_category_source_pools


_ENV_FILE_ORDER = (
    "APP_NAME",
    "APP_TIMEZONE",
    "APP_TOP_K",
    "APP_MAX_CANDIDATES",
    "APP_REQUEST_TIMEOUT_SECONDS",
    "APP_SCHEDULER_INTERVAL_MINUTES",
    "APP_RSS_URLS",
    "APP_YOUTUBE_FEED_URLS",
    "APP_REDDIT_SUBREDDITS",
    "APP_REDDIT_USER_AGENT",
    "TWITTER_QUERY",
    "TWITTER_BEARER_TOKEN",
    "NOTION_ENABLED",
    "NOTION_DATABASE_ID",
    "NOTION_TOKEN",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
)


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
    source_pools: CategorySourcePools


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _load_env_file() -> None:
    """`config/app.env` 또는 루트 `.env` 파일을 읽어 환경변수로 반영한다."""
    root = Path(__file__).resolve().parents[3]
    candidates = (root / "config" / "app.env", root / ".env")

    for env_path in candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in environ:
                environ[key] = value

        break


def _resolve_env_file_path() -> Path:
    """실제 저장에 사용할 설정 파일 경로를 반환한다."""
    root = Path(__file__).resolve().parents[3]
    return root / "config" / "app.env"


def save_settings_file(updates: dict[str, str]) -> str:
    """현재 환경과 전달된 변경값을 합쳐 `config/app.env`에 저장한다."""
    env_path = _resolve_env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    current_values: dict[str, str] = {key: getenv(key, "") for key in _ENV_FILE_ORDER}

    for key, value in updates.items():
        if key not in current_values:
            continue

        normalized = value.strip()
        if normalized.startswith("*") and current_values[key]:
            continue

        if key == "APP_SCHEDULER_INTERVAL_MINUTES":
            digits = "".join(ch for ch in normalized if ch.isdigit())
            current_values[key] = digits or "60"
            continue

        if key == "NOTION_ENABLED":
            current_values[key] = "true" if normalized.lower() in {"1", "true", "yes", "on", "사용", "사용함"} else "false"
            continue

        current_values[key] = normalized

    lines = [f"{key}={current_values[key]}" for key in _ENV_FILE_ORDER if current_values[key] != ""]
    _ = env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(env_path)


def load_settings() -> AppSettings:
    """환경변수에서 기본값과 함께 앱 설정을 로드한다."""
    _load_env_file()
    root = Path(__file__).resolve().parents[3]
    source_pools = load_category_source_pools(root)
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
        source_pools=source_pools,
    )
