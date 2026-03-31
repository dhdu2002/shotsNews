"""소스별 실패를 격리하는 복합 수집기."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...domain.enums import IssueCategory
from ...domain.models import IssueCandidate


@dataclass(slots=True)
class SourceFailure:
    source_name: str
    message: str


class MultiSourceCollector:
    """여러 수집기에 fan-out 하되, 개별 실패를 누적 기록한다."""

    def __init__(self, collectors: dict[str, object]) -> None:
        self._collectors = collectors
        self._failures: list[SourceFailure] = []

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        out: list[IssueCandidate] = []
        for source_name, collector in self._collectors.items():
            try:
                collect_fn = getattr(collector, "collect")
                out.extend(collect_fn(target_date, category))
            except Exception as exc:
                self._failures.append(SourceFailure(source_name=source_name, message=str(exc)[:300]))
        return out

    def drain_failures(self) -> list[SourceFailure]:
        failures = list(self._failures)
        self._failures.clear()
        return failures
