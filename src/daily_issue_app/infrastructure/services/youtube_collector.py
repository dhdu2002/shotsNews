"""공개 채널 RSS 기반 YouTube 수집기."""

from __future__ import annotations

from datetime import date

from ...domain.enums import IssueCategory, SourceType
from ...domain.models import IssueCandidate
from .rss_collector import RSSCollector


class YouTubeCollector:
    """YouTube 피드 URL에서 후보를 수집한다."""

    def __init__(self, feed_urls: tuple[str, ...], default_limit: int = 20, timeout_seconds: int = 15) -> None:
        self._rss = RSSCollector(feed_urls=feed_urls, default_limit=default_limit, timeout_seconds=timeout_seconds)

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        candidates = self._rss.collect(target_date, category)
        for item in candidates:
            item.source_type = SourceType.YOUTUBE
        return candidates
