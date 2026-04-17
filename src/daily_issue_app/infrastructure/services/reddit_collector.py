"""공개 JSON 엔드포인트 기반 Reddit 수집기."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from ...domain.enums import IssueCategory, SourceType
from ...domain.models import IssueCandidate
from ...config.source_pools import build_source_configuration_snapshot


class RedditCollector:
    """설정된 서브레딧에서 이슈 후보를 수집한다."""

    def __init__(
        self,
        subreddits: tuple[str, ...],
        user_agent: str,
        timeout_seconds: int = 15,
        category_subreddits: dict[IssueCategory, tuple[str, ...]] | None = None,
    ) -> None:
        self._subreddits = tuple(sub for sub in subreddits if sub)
        self._category_subreddits = {category: tuple(sub for sub in subs if sub) for category, subs in (category_subreddits or {}).items()}
        self._user_agent = user_agent or "daily-issue-desktop/0.1"
        self._timeout_seconds = timeout_seconds

    def _resolve_subreddits(self, category: IssueCategory) -> tuple[str, ...]:
        """카테고리별 서브레딧 전용 풀이 있으면 우선 사용한다."""
        return self._category_subreddits.get(category, self._subreddits)

    def describe_source_config(self) -> dict[str, object]:
        """런타임 status용 Reddit 소스 구성 요약을 반환한다."""
        return build_source_configuration_snapshot(
            source_name="reddit",
            shared_values=self._subreddits,
            category_values=self._category_subreddits,
            unit_label="서브레딧",
        )

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        _ = target_date
        subreddits = self._resolve_subreddits(category)
        if not subreddits:
            return []

        output: list[IssueCandidate] = []
        for subreddit in subreddits:
            request = Request(
                f"https://www.reddit.com/r/{quote_plus(subreddit)}/hot.json?limit=20",
                headers={"User-Agent": self._user_agent},
            )
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (URLError, TimeoutError, ValueError):
                continue

            for child in payload.get("data", {}).get("children", []):
                data = child.get("data", {})
                title = data.get("title") or ""
                link = data.get("url") or ""
                summary = data.get("selftext") or title
                created_utc = data.get("created_utc")
                if not title or not link:
                    continue
                published = datetime.now(tz=timezone.utc)
                if isinstance(created_utc, (int, float)):
                    published = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                output.append(
                    IssueCandidate(
                        category=category,
                        source_type=SourceType.REDDIT,
                        source_id=str(data.get("id") or link),
                        title=title,
                        summary=summary[:500],
                        source_url=link,
                        published_at=published,
                        score_hint=0.7,
                    )
                )
        return output
