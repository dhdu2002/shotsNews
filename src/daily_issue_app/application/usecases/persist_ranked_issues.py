"""유스케이스: 랭킹 이슈를 로컬 DB에 저장."""

from __future__ import annotations

from ..dto import DailyPipelineRequest, PersistIssuesResult, RankIssuesResult
from ...domain.interfaces import IssueRepositoryPort


class PersistRankedIssuesUseCase:
    """선정된 이슈를 SQLite에 저장한다."""

    def __init__(self, repository: IssueRepositoryPort) -> None:
        self._repository = repository

    def execute(self, request: DailyPipelineRequest, ranked: RankIssuesResult) -> PersistIssuesResult:
        """저장 후 저장 결과를 반환한다."""
        records = self._repository.save_ranked_issues(request.run_date, ranked.ranked_issues)
        return PersistIssuesResult(records=records)
