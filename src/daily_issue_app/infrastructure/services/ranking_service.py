"""후보 점수 기반의 단순 랭킹 서비스."""

from __future__ import annotations

from ...domain.models import IssueCandidate, RankedIssue


class RankingService:
    """score_hint 기준으로 Top-K를 선별한다."""

    def __init__(self, top_k: int = 5) -> None:
        self._top_k = top_k

    def rank(self, candidates: list[IssueCandidate]) -> list[RankedIssue]:
        """점수 내림차순으로 정렬 후 랭킹 모델로 변환한다."""
        sorted_candidates = sorted(candidates, key=lambda item: item.score_hint, reverse=True)
        ranked: list[RankedIssue] = []
        for index, candidate in enumerate(sorted_candidates[: self._top_k], start=1):
            ranked.append(
                RankedIssue(
                    rank=index,
                    category=candidate.category,
                    title=candidate.title,
                    key_points=[candidate.summary],
                    source_url=candidate.source_url,
                    score=candidate.score_hint,
                )
            )
        return ranked
