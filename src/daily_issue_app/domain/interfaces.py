"""인프라/애플리케이션 계층에서 사용하는 포트 정의."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from .enums import IssueCategory
from .models import IssueCandidate, IssueScriptSet, PersistedIssue, RankedIssue


class NewsCollectorPort(Protocol):
    """지정 날짜/카테고리의 이슈 후보를 수집한다."""

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        """단일 카테고리 이슈 후보를 반환한다."""
        ...


class RankingServicePort(Protocol):
    """이슈 후보를 점수화해 Top 이슈를 선택한다."""

    def rank(self, candidates: list[IssueCandidate]) -> list[RankedIssue]:
        """우선순위 내림차순 랭킹 결과를 반환한다."""
        ...


class ScriptGeneratorPort(Protocol):
    """저장된 이슈를 바탕으로 3톤 스크립트를 생성한다."""

    def generate(self, issue: PersistedIssue) -> IssueScriptSet:
        """단일 이슈 스크립트 세트를 생성한다."""
        ...


class NotionSyncPort(Protocol):
    """로컬 이슈를 Notion DB로 동기화한다."""

    def sync(self, issues: list[PersistedIssue]) -> list[str]:
        """동기화 성공한 이슈 ID 목록을 반환한다."""
        ...

    def is_ready(self) -> bool:
        """Notion 외부 자격정보 준비 여부를 반환한다."""
        ...


class IssueRepositoryPort(Protocol):
    """이슈 영속화 리포지토리 포트."""

    def save_ranked_issues(self, run_date: date, issues: list[RankedIssue]) -> list[PersistedIssue]:
        """실행일 기준 랭킹 이슈를 저장한다."""
        ...

    def save_scripts(self, scripts: list[IssueScriptSet]) -> None:
        """생성된 스크립트를 저장한다."""
        ...

    def list_pending_sync(self, run_date: date) -> list[PersistedIssue]:
        """Notion 동기화 대기 이슈를 조회한다."""
        ...

    def mark_synced(self, issue_ids: list[str]) -> None:
        """선택한 이슈를 동기화 완료로 표시한다."""
        ...

    def mark_sync_failed(self, issue_ids: list[str], error: str) -> None:
        """선택한 이슈를 동기화 실패로 표시한다."""
        ...
