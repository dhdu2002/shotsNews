"""유스케이스: 후보 점수화 및 Top-K 선별."""

from __future__ import annotations

from ..dto import CollectIssuesResult, RankIssuesResult
from ...domain.interfaces import RankingServicePort


class RankTopIssuesUseCase:
    """원시 후보를 최종 랭킹 이슈로 변환한다."""

    def __init__(self, ranking_service: RankingServicePort) -> None:
        self._ranking_service = ranking_service

    def execute(self, collected: CollectIssuesResult) -> RankIssuesResult:
        """수집된 후보로부터 랭킹 결과를 반환한다."""
        ranked = self._ranking_service.rank(collected.candidates)
        return RankIssuesResult(ranked_issues=ranked)
