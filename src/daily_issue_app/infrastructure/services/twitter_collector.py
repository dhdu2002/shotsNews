"""선택형 Twitter/X 수집기."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from ...domain.enums import IssueCategory, SourceType
from ...domain.models import IssueCandidate
from ...config.source_pools import build_source_configuration_snapshot


class TwitterXCollector:
    """토큰이 없으면 조용히 비활성화되는 선택형 소스 어댑터."""

    def __init__(
        self,
        bearer_token: str,
        query: str,
        timeout_seconds: int = 15,
        category_queries: dict[IssueCategory, tuple[str, ...]] | None = None,
    ) -> None:
        self._bearer_token = bearer_token
        self._query = query
        self._shared_queries = (query.strip(),) if query.strip() else ()
        self._category_queries = {category: tuple(item for item in queries if item) for category, queries in (category_queries or {}).items()}
        self._timeout_seconds = timeout_seconds

    def _resolve_queries(self, category: IssueCategory) -> tuple[str, ...]:
        """카테고리 전용 쿼리가 있으면 우선 사용하고, 없으면 공용 쿼리를 사용한다."""
        return self._category_queries.get(category, self._shared_queries)

    def describe_source_config(self) -> dict[str, object]:
        """런타임 status용 X/Twitter 소스 구성 요약을 반환한다."""
        extra_note = "Bearer 토큰 확인됨" if self._bearer_token else "Bearer 토큰 필요"
        return build_source_configuration_snapshot(
            source_name="twitter_x",
            shared_values=self._shared_queries,
            category_values=self._category_queries,
            unit_label="쿼리",
            configured=bool(self._bearer_token) and bool(self._shared_queries or self._category_queries),
            extra_note=extra_note,
        )

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        """토큰이 설정된 경우에만 Twitter/X 후보를 반환한다."""
        _ = target_date
        if not self._bearer_token:
            return []

        queries = self._resolve_queries(category)
        if not queries:
            return []

        out: list[IssueCandidate] = []
        for query in queries:
            url = (
                "https://api.twitter.com/2/tweets/search/recent"
                f"?query={quote_plus(query)}&max_results=20&tweet.fields=created_at,text"
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
                continue

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
