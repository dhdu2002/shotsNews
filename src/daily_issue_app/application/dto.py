"""애플리케이션 계층 DTO 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..domain.enums import IssueCategory
from ..domain.models import IssueCandidate, PersistedIssue, RankedIssue


@dataclass(slots=True, frozen=True)
class DailyPipelineRequest:
    """일일 파이프라인 1회 실행 입력값."""

    run_date: date
    categories: tuple[IssueCategory, ...]


@dataclass(slots=True)
class CollectIssuesResult:
    """전체 카테고리 수집 결과."""

    candidates: list[IssueCandidate] = field(default_factory=list)


@dataclass(slots=True)
class RankIssuesResult:
    """최종 Top 이슈 랭킹 결과."""

    ranked_issues: list[RankedIssue] = field(default_factory=list)


@dataclass(slots=True)
class PersistIssuesResult:
    """저장 완료된 이슈 집합."""

    records: list[PersistedIssue] = field(default_factory=list)


@dataclass(slots=True)
class SyncResult:
    """Notion 동기화 결과 요약."""

    synced_issue_ids: list[str] = field(default_factory=list)
