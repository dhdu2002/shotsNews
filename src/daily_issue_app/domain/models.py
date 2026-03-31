"""도메인 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import IssueCategory, RecordSyncStatus, ScriptTone, SourceType


@dataclass(slots=True)
class IssueCandidate:
    """수집 소스에서 가져온 원시 이슈 후보."""

    category: IssueCategory
    source_type: SourceType
    source_id: str
    title: str
    summary: str
    source_url: str
    published_at: datetime
    score_hint: float = 0.0


@dataclass(slots=True)
class RankedIssue:
    """최종 Top 이슈로 선정된 랭킹 결과."""

    rank: int
    category: IssueCategory
    title: str
    key_points: list[str]
    source_url: str
    score: float


@dataclass(slots=True)
class IssueScriptSet:
    """하나의 이슈에 대해 생성된 3톤 스크립트."""

    issue_id: str
    scripts_by_tone: dict[ScriptTone, str] = field(default_factory=dict)


@dataclass(slots=True)
class PersistedIssue:
    """SQLite 저장/동기화에 사용하는 이슈 레코드 모델."""

    issue_id: str
    run_date: str
    rank: int
    category: IssueCategory
    title: str
    key_points: list[str]
    source_url: str
    sync_status: RecordSyncStatus = RecordSyncStatus.PENDING
