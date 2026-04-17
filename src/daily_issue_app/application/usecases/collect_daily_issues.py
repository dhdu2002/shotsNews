"""유스케이스: 날짜/카테고리 기준 이슈 후보 수집."""

from __future__ import annotations

from ..dto import CollectIssuesResult, DailyPipelineRequest
from ...domain.interfaces import NewsCollectorPort


class CollectDailyIssuesUseCase:
    """설정된 수집기에서 후보를 모은다."""

    def __init__(self, collector: NewsCollectorPort) -> None:
        self._collector = collector

    def execute(self, request: DailyPipelineRequest) -> CollectIssuesResult:
        """요청된 모든 카테고리에 대해 수집을 수행한다."""
        candidates = []
        for category in request.categories:
            candidates.extend(self._collector.collect(request.run_date, category))

        # 동일 URL이 여러 카테고리에서 중복 수집된 경우 score_hint가 가장 높은 것만 유지한다.
        seen: dict[str, object] = {}
        for candidate in candidates:
            key = candidate.source_url
            if key not in seen or candidate.score_hint > seen[key].score_hint:  # type: ignore[union-attr]
                seen[key] = candidate
        return CollectIssuesResult(candidates=list(seen.values()))
