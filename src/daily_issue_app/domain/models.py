"""도메인 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import IssueCategory, NewsRegion, RecordSyncStatus, ScriptTone, SourceType


@dataclass(slots=True, frozen=True)
class ShortFormScoreBreakdown:
    """숏폼 적합도를 6개 요인으로 분해한 점수 모델."""

    latestness: float = 0.0
    hook_strength: float = 0.0
    popularity: float = 0.0
    controversy: float = 0.0
    ad_friendly: float = 0.0
    info_density: float = 0.0

    @property
    def total(self) -> float:
        """6개 요인의 가중 합산 총점을 반환한다."""
        return round(
            (self.latestness * 0.24)
            + (self.hook_strength * 0.20)
            + (self.popularity * 0.18)
            + (self.controversy * 0.14)
            + (self.ad_friendly * 0.10)
            + (self.info_density * 0.14),
            2,
        )

    def to_dict(self) -> dict[str, float]:
        """영속화/런타임 payload용 딕셔너리로 직렬화한다."""
        return {
            "latestness": self.latestness,
            "hook_strength": self.hook_strength,
            "popularity": self.popularity,
            "controversy": self.controversy,
            "ad_friendly": self.ad_friendly,
            "info_density": self.info_density,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "ShortFormScoreBreakdown":
        """저장값이 비어 있거나 일부만 있어도 안전하게 복원한다."""
        source = payload or {}
        return cls(
            latestness=_to_float(source.get("latestness")),
            hook_strength=_to_float(source.get("hook_strength")),
            popularity=_to_float(source.get("popularity")),
            controversy=_to_float(source.get("controversy")),
            ad_friendly=_to_float(source.get("ad_friendly")),
            info_density=_to_float(source.get("info_density")),
        )


def _to_float(value: object) -> float:
    """예상치 못한 저장값도 0.0으로 정규화한다."""
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, str):
        try:
            return round(float(value), 2)
        except ValueError:
            return 0.0
    return 0.0


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
    short_form_score: float | None = None
    score_breakdown: ShortFormScoreBreakdown | None = None
    region: str = NewsRegion.INTERNATIONAL.value

    @property
    def total_score(self) -> float:
        """호환성을 유지하면서 최종 랭킹 점수를 반환한다."""
        if self.short_form_score is not None:
            return self.short_form_score
        if self.score_breakdown is not None:
            return self.score_breakdown.total
        return self.score_hint


@dataclass(slots=True)
class RankedIssue:
    """최종 Top 이슈로 선정된 랭킹 결과."""

    rank: int
    category: IssueCategory
    title: str
    key_points: list[str]
    source_url: str
    score: float
    score_breakdown: ShortFormScoreBreakdown | None = None
    region: str = NewsRegion.INTERNATIONAL.value


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
    score: float = 0.0
    score_breakdown: ShortFormScoreBreakdown | None = None
    sync_status: RecordSyncStatus = RecordSyncStatus.PENDING
    region: str = NewsRegion.INTERNATIONAL.value
