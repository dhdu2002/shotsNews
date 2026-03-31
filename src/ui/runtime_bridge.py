# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportExplicitAny=false, reportUnusedVariable=false

"""DesktopApp 런타임을 UI 상태로 변환하는 어댑터와 프리젠터."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from src.daily_issue_app import DesktopApp

from .models import DashboardState, LinkedStatusStep, LogEntry, SettingsField, SettingsState, SourceStatusRow, TopIssueRow

_SOURCE_LABELS = {
    "rss": "RSS",
    "youtube": "YouTube",
    "reddit": "Reddit",
    "twitter_x": "X / Twitter",
}

_CATEGORY_LABELS = {
    "ai_tech": "AI/테크",
    "economy": "경제",
    "society": "사회",
    "health": "건강",
    "entertainment_trend": "연예/트렌드",
}

_SYNC_LABELS = {
    "pending": "대기",
    "synced": "완료",
    "failed": "실패",
}


@dataclass(slots=True)
class DesktopAppAdapter:
    """UI가 DesktopApp을 안전하게 호출하도록 감싸는 얇은 어댑터."""

    desktop_app: DesktopApp = field(default_factory=DesktopApp)

    def load_status(self) -> dict[str, Any]:
        """런타임을 시작한 뒤 최신 상태 스냅샷을 반환한다."""
        self.desktop_app.start()
        return self.desktop_app.status()

    def run_now(self) -> dict[str, Any]:
        """수동 실행을 시작하고 요약 결과를 반환한다."""
        self.desktop_app.start()
        return self.desktop_app.run_now()

    def stop(self) -> None:
        """앱 종료 시 런타임을 정리한다."""
        self.desktop_app.stop()


class DashboardPresenter:
    """DesktopApp 상태 딕셔너리를 화면용 상태 객체로 변환한다."""

    def present_dashboard(
        self,
        runtime_status: dict[str, Any],
        interaction_logs: tuple[LogEntry, ...] = (),
    ) -> DashboardState:
        """런타임 상태를 대시보드 상태로 변환한다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        sources = runtime_status.get("sources") or []
        top_issues = runtime_status.get("top_issues") or []

        overall_status, overall_detail = self._present_overall_status(latest_run, source_failures)
        linked_steps = self._build_linked_steps(runtime_status)
        source_rows = self._build_source_rows(sources, source_failures, latest_run)
        top_issue_rows = self._build_top_issue_rows(top_issues)
        runtime_logs = self._build_runtime_logs(runtime_status)
        logs = tuple([*interaction_logs, *runtime_logs][:8])

        return DashboardState(
            window_title="데일리 이슈 데스크톱",
            dashboard_title="운영 대시보드",
            dashboard_subtitle="오늘의 수집 상태와 Top 5, Notion 대기 현황을 간단하게 확인합니다.",
            overall_status=overall_status,
            overall_detail=overall_detail,
            next_run_label=self._build_next_run_label(runtime_status),
            last_run_label=self._build_last_run_label(latest_run),
            notion_sync_status=self._build_notion_status(runtime_status),
            notion_sync_detail=self._build_notion_detail(runtime_status),
            linked_steps=linked_steps,
            source_rows=source_rows,
            top_issue_rows=top_issue_rows,
            log_entries=logs,
        )

    def present_settings(self, runtime_status: dict[str, Any]) -> SettingsState:
        """런타임 상태를 설정 탭의 읽기 전용 정보로 변환한다."""
        interval_minutes = int(runtime_status.get("scheduler_interval_minutes") or 0)
        notion_enabled = bool(runtime_status.get("notion_enabled"))

        return SettingsState(
            heading="런타임 연결 정보",
            description=(
                "현재 데스크톱 셸이 읽어 온 런타임 구성입니다. "
                "설정값 저장은 아직 붙지 않았고, 화면은 연결 지점만 제공합니다."
            ),
            fields=(
                SettingsField(
                    "앱 이름",
                    str(runtime_status.get("app_name") or "DailyIssueDesktop"),
                    "DesktopApp 시작 시 로드된 런타임 이름입니다.",
                ),
                SettingsField(
                    "실행 주기",
                    f"{interval_minutes}분 간격" if interval_minutes else "미설정",
                    "백그라운드 스케줄러가 이 간격으로 파이프라인을 반복합니다.",
                ),
                SettingsField(
                    "SQLite 경로",
                    str(runtime_status.get("db_path") or ""),
                    "파이프라인 실행 결과와 동기화 대기 정보가 저장되는 위치입니다.",
                ),
                SettingsField(
                    "데이터 폴더",
                    str(runtime_status.get("data_dir") or ""),
                    "로그와 캐시를 포함한 로컬 런타임 작업 폴더입니다.",
                ),
                SettingsField(
                    "Notion 연동",
                    "사용" if notion_enabled else "사용 안 함",
                    "실제 API 호출은 런타임 계층이 담당하며, UI는 상태만 보여줍니다.",
                ),
                SettingsField(
                    "스크립트 모델",
                    str(runtime_status.get("openai_model") or "로컬 기본값"),
                    "스크립트 생성 런타임이 사용하는 모델 이름입니다.",
                ),
            ),
        )

    def _present_overall_status(
        self,
        latest_run: dict[str, Any],
        source_failures: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """상단 상태 카드의 문구를 결정한다."""
        if not latest_run:
            return (
                "실행 대기",
                "런타임은 시작되었지만 아직 완료된 파이프라인 실행 기록이 없습니다.",
            )

        status = str(latest_run.get("status") or "")
        collected = int(latest_run.get("collected_count") or 0)
        ranked = int(latest_run.get("ranked_count") or 0)
        queued = int(latest_run.get("queued_sync_count") or 0)
        failure_count = int(latest_run.get("failure_count") or 0)

        if status == "failed":
            return (
                "실행 실패",
                f"최근 실행에서 실패가 발생했습니다. 수집 {collected}건, 실패 기록 {max(1, failure_count)}건입니다.",
            )
        if source_failures or failure_count:
            return (
                "주의 필요",
                f"최근 실행은 완료되었지만 소스 경고 {max(len(source_failures), failure_count)}건이 남아 있습니다.",
            )
        return (
            "정상",
            f"최근 실행에서 {collected}건 수집, {ranked}건 Top 이슈 선정, {queued}건 동기화 대기 상태입니다.",
        )

    def _build_linked_steps(self, runtime_status: dict[str, Any]) -> tuple[LinkedStatusStep, ...]:
        """단순 연결 상태 표시용 단계 목록을 만든다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        notion_enabled = bool(runtime_status.get("notion_enabled"))

        ranked_count = int(latest_run.get("ranked_count") or 0)
        pending_sync = int(queue.get("pending") or 0)

        source_detail = "아직 실행 기록이 없습니다."
        if latest_run:
            source_detail = f"최근 실행 기준 경고 {len(source_failures)}건"

        notion_detail = "Notion 연동이 꺼져 있습니다."
        notion_healthy = True
        if notion_enabled:
            notion_detail = f"대기 {pending_sync}건"
            notion_healthy = pending_sync == 0

        return (
            LinkedStatusStep("소스 수집", source_detail, healthy=not source_failures),
            LinkedStatusStep(
                "오늘의 Top 5",
                f"선정 {ranked_count}건" if ranked_count else "아직 선정 결과가 없습니다.",
                healthy=ranked_count > 0,
            ),
            LinkedStatusStep("Notion 동기화", notion_detail, healthy=notion_healthy),
        )

    def _build_source_rows(
        self,
        sources: list[dict[str, Any]],
        source_failures: list[dict[str, Any]],
        latest_run: dict[str, Any],
    ) -> tuple[SourceStatusRow, ...]:
        """수집원 상태 표를 구성한다."""
        failure_by_name = {str(item.get("source_name")): item for item in source_failures}
        checked_label = self._build_last_run_label(latest_run)
        rows: list[SourceStatusRow] = []

        for source in sources:
            source_name = str(source.get("name") or "")
            configured = bool(source.get("configured"))
            configured_count = int(source.get("configured_count") or 0)
            note = str(source.get("note") or "")
            failure = failure_by_name.get(source_name)

            if not configured:
                rows.append(
                    SourceStatusRow(
                        source_name=_SOURCE_LABELS.get(source_name, source_name),
                        health="미설정",
                        last_checked="아직 없음",
                        pending_items=0,
                        note=note,
                    )
                )
                continue

            if failure is not None:
                rows.append(
                    SourceStatusRow(
                        source_name=_SOURCE_LABELS.get(source_name, source_name),
                        health="주의",
                        last_checked=self._format_timestamp(str(failure.get("created_at") or "")),
                        pending_items=1,
                        note=str(failure.get("message") or "최근 실행에서 오류가 기록되었습니다."),
                    )
                )
                continue

            rows.append(
                SourceStatusRow(
                    source_name=_SOURCE_LABELS.get(source_name, source_name),
                    health="정상" if latest_run else "대기",
                    last_checked=checked_label,
                    pending_items=0,
                    note=f"연결 항목 {configured_count}개 · {note}",
                )
            )

        return tuple(rows)

    def _build_top_issue_rows(self, top_issues: list[dict[str, Any]]) -> tuple[TopIssueRow, ...]:
        """오늘의 Top 5 표 데이터를 구성한다."""
        rows: list[TopIssueRow] = []
        for issue in top_issues:
            category = str(issue.get("category") or "")
            rows.append(
                TopIssueRow(
                    rank=int(issue.get("rank") or 0),
                    title=str(issue.get("title") or "제목 없음"),
                    source_name=self._build_source_label_from_url(str(issue.get("source_url") or "")),
                    severity=_CATEGORY_LABELS.get(category, category or "미분류"),
                    readiness=_SYNC_LABELS.get(str(issue.get("sync_status") or ""), "대기"),
                )
            )
        return tuple(rows)

    def _build_runtime_logs(self, runtime_status: dict[str, Any]) -> tuple[LogEntry, ...]:
        """런타임 스냅샷에서 최근 로그 패널용 메시지를 만든다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        logs: list[LogEntry] = []

        if latest_run:
            logs.append(
                LogEntry(
                    self._build_last_run_label(latest_run),
                    "안내",
                    (
                        f"최근 실행 상태: {latest_run.get('status', 'unknown')} · "
                        f"수집 {latest_run.get('collected_count', 0)}건 · "
                        f"Top {latest_run.get('ranked_count', 0)}건"
                    ),
                )
            )

        pending_count = int(queue.get("pending") or 0)
        logs.append(
            LogEntry(
                self._format_timestamp(str(runtime_status.get("started_at") or "")),
                "안내",
                f"현재 Notion 동기화 대기 {pending_count}건을 확인했습니다.",
            )
        )

        for failure in source_failures[:3]:
            logs.append(
                LogEntry(
                    self._format_timestamp(str(failure.get("created_at") or "")),
                    "주의",
                    f"{_SOURCE_LABELS.get(str(failure.get('source_name') or ''), str(failure.get('source_name') or '소스'))}: {failure.get('message', '')}",
                )
            )

        if not logs:
            logs.append(LogEntry("지금", "안내", "런타임이 시작되었고 첫 상태 갱신을 기다리는 중입니다."))

        return tuple(logs)

    def _build_next_run_label(self, runtime_status: dict[str, Any]) -> str:
        """다음 실행 예상 시각을 문자열로 만든다."""
        interval_minutes = int(runtime_status.get("scheduler_interval_minutes") or 0)
        latest_run = runtime_status.get("latest_run") or {}
        reference_text = str(
            latest_run.get("finished_at")
            or latest_run.get("started_at")
            or runtime_status.get("started_at")
            or ""
        )
        reference = self._parse_datetime(reference_text)
        if reference is None:
            return f"{interval_minutes}분 주기" if interval_minutes else "대기 중"
        return (reference + timedelta(minutes=interval_minutes)).strftime("%m-%d %H:%M") if interval_minutes else "대기 중"

    def _build_last_run_label(self, latest_run: dict[str, Any]) -> str:
        """최근 실행 시각 레이블을 만든다."""
        if not latest_run:
            return "아직 없음"
        return self._format_timestamp(str(latest_run.get("finished_at") or latest_run.get("started_at") or ""))

    def _build_notion_status(self, runtime_status: dict[str, Any]) -> str:
        """Notion 상태 카드의 핵심 문구를 만든다."""
        if not bool(runtime_status.get("notion_enabled")):
            return "사용 안 함"
        queue = runtime_status.get("queue") or {}
        pending = int(queue.get("pending") or 0)
        if pending:
            return f"대기 {pending}건"
        return "처리 완료"

    def _build_notion_detail(self, runtime_status: dict[str, Any]) -> str:
        """Notion 상태 카드의 보조 설명을 만든다."""
        if not bool(runtime_status.get("notion_enabled")):
            return "설정에서 연동이 꺼져 있어 UI에는 상태만 표시합니다."
        queue = runtime_status.get("queue") or {}
        return (
            f"완료 {int(queue.get('synced') or 0)}건 · 실패 {int(queue.get('failed') or 0)}건 · "
            f"대기 {int(queue.get('pending') or 0)}건"
        )

    @staticmethod
    def _build_source_label_from_url(url: str) -> str:
        """출처 URL을 짧은 표시 이름으로 바꾼다."""
        if not url:
            return "출처 없음"
        host = urlparse(url).netloc.replace("www.", "")
        return host or "출처 없음"

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        """SQLite/ISO 날짜 문자열을 datetime으로 변환한다."""
        if not value:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

    def _format_timestamp(self, value: str) -> str:
        """UI용 간단한 날짜/시간 문자열을 만든다."""
        parsed = self._parse_datetime(value)
        if parsed is None:
            return "지금" if not value else value
        return parsed.strftime("%m-%d %H:%M")
