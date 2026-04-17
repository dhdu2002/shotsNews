"""유스케이스: 날짜/카테고리 기준 이슈 후보 수집."""

from __future__ import annotations

import re

from ..dto import CollectIssuesResult, DailyPipelineRequest
from ...domain.category_classifier import classify
from ...domain.interfaces import NewsCollectorPort


class CollectDailyIssuesUseCase:
    """설정된 수집기에서 후보를 모은다."""

    def __init__(self, collector: NewsCollectorPort) -> None:
        self._collector = collector

    def execute(self, request: DailyPipelineRequest) -> CollectIssuesResult:
        """요청된 모든 카테고리에 대해 수집을 수행한다."""
        all_candidates = []
        for category in request.categories:
            all_candidates.extend(self._collector.collect(request.run_date, category))

        # 1단계: 내용(제목+요약) 기반 카테고리 재분류
        # 수집 시 할당된 카테고리보다 키워드 밀도가 높은 카테고리가 있으면 재할당한다.
        for candidate in all_candidates:
            candidate.category = classify(candidate.title, candidate.summary, candidate.category)

        # 2단계: score_hint 내림차순 정렬 후 URL·제목 기반 전역 중복 제거
        all_candidates.sort(key=lambda c: c.score_hint, reverse=True)
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        deduped = []
        for candidate in all_candidates:
            url_key = candidate.source_url
            title_key = re.sub(r"\W+", " ", candidate.title.lower()).strip()
            if url_key in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            deduped.append(candidate)

        # 3단계: 국내/국외 각각 25개로 제한
        domestic = [c for c in deduped if c.region == "domestic"][:25]
        international = [c for c in deduped if c.region != "domestic"][:25]

        return CollectIssuesResult(candidates=domestic + international)
