"""선택형 Twitter/X 수집기."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from ...domain.enums import IssueCategory, SourceType
from ...domain.models import IssueCandidate


class TwitterXCollector:
    """토큰이 없으면 조용히 비활성화되는 선택형 소스 어댑터."""

    def __init__(self, bearer_token: str, query: str, timeout_seconds: int = 15) -> None:
        self._bearer_token = bearer_token
        self._query = query
        self._timeout_seconds = timeout_seconds

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        """토큰이 설정된 경우에만 Twitter/X 후보를 반환한다."""
        _ = target_date
        if not self._bearer_token:
            return []

        url = (
            "https://api.twitter.com/2/tweets/search/recent"
            f"?query={quote_plus(self._query)}&max_results=20&tweet.fields=created_at,text"
        )
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self._bearer_token}",
                "User-Agent": "daily-issue-desktop/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, ValueError):
            return []

        out: list[IssueCandidate] = []
        for item in payload.get("data", []):
            text = (item.get("text") or "").strip()
            tweet_id = item.get("id") or ""
            if not text or not tweet_id:
                continue
            created_at = item.get("created_at") or ""
            try:
                published_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                published_at = datetime.now(tz=timezone.utc)
            out.append(
                IssueCandidate(
                    category=category,
                    source_type=SourceType.TWITTER_X,
                    source_id=str(tweet_id),
                    title=text[:120],
                    summary=text,
                    source_url=f"https://x.com/i/web/status/{tweet_id}",
                    published_at=published_at,
                    score_hint=0.6,
                )
            )
        return out
