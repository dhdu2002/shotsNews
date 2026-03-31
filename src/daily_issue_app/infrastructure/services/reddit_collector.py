"""공개 JSON 엔드포인트 기반 Reddit 수집기."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from ...domain.enums import IssueCategory, SourceType
from ...domain.models import IssueCandidate


class RedditCollector:
    """설정된 서브레딧에서 이슈 후보를 수집한다."""

    def __init__(self, subreddits: tuple[str, ...], user_agent: str, timeout_seconds: int = 15) -> None:
        self._subreddits = tuple(sub for sub in subreddits if sub)
        self._user_agent = user_agent or "daily-issue-desktop/0.1"
        self._timeout_seconds = timeout_seconds

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        _ = target_date
        if not self._subreddits:
            return []

        output: list[IssueCandidate] = []
        for subreddit in self._subreddits:
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
