"""PySide6 데스크톱 대시보드가 소비하는 상태 모델 모음."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LinkedStatusStep:
    """상단 연결 상태 표시줄의 한 단계를 표현한다."""

    name: str
    detail: str
    healthy: bool = True


@dataclass(frozen=True)
class SourceStatusRow:
    """수집원 상태 표의 한 행을 표현한다."""

    source_name: str
    health: str
    last_checked: str
    pending_items: int
    note: str = ""


@dataclass(frozen=True)
class TopIssueRow:
    """오늘의 Top 5 표에 표시할 이슈 한 건이다."""

    rank: int
    title: str
    source_name: str
    severity: str
    readiness: str


@dataclass(frozen=True)
class LogEntry:
    """운영자에게 보여줄 최근 로그 한 줄이다."""

    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class SettingsField:
    """설정 탭의 읽기 전용 항목 한 줄이다."""

    label: str
    value: str
    helper_text: str = ""


@dataclass(frozen=True)
class SettingsState:
    """설정 탭에 보여줄 런타임 연결 정보다."""

    heading: str = "런타임 연결 정보"
    description: str = (
        "아래 값은 현재 DesktopApp 런타임에서 읽어 온 상태입니다. "
        "실제 저장과 변경 기능은 추후 서비스 연결 시점에 붙습니다."
    )
    fields: tuple[SettingsField, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DashboardState:
    """대시보드 한 화면 전체를 그리는 상태 집합이다."""

    window_title: str = "데일리 이슈 데스크톱"
    dashboard_title: str = "운영 대시보드"
    dashboard_subtitle: str = "수집, Top 5 선정, Notion 동기화 상태를 한 화면에서 확인합니다."
    overall_status: str = "런타임 연결 중"
    overall_detail: str = "DesktopApp 상태를 불러오는 중입니다."
    next_run_label: str = "대기 중"
    last_run_label: str = "아직 없음"
    notion_sync_status: str = "확인 중"
    notion_sync_detail: str = "동기화 상태를 불러오는 중입니다."
    linked_steps: tuple[LinkedStatusStep, ...] = field(default_factory=tuple)
    source_rows: tuple[SourceStatusRow, ...] = field(default_factory=tuple)
    top_issue_rows: tuple[TopIssueRow, ...] = field(default_factory=tuple)
    log_entries: tuple[LogEntry, ...] = field(default_factory=tuple)
