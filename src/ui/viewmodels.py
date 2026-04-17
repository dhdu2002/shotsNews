# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false

"""PySide6 대시보드와 DesktopApp 런타임을 잇는 뷰모델."""

from __future__ import annotations

from datetime import datetime
from threading import Lock, Thread
from PySide6.QtCore import QObject, Signal

from .models import DashboardState, LinkedStatusStep, LogEntry, SettingsField, SettingsState, SourceStatusRow, TopIssueRow
from .runtime_bridge import DashboardPresenter, DesktopAppAdapter


def build_mock_dashboard_state() -> DashboardState:
    """런타임 연결 전 기본 화면 상태를 만든다."""
    return DashboardState(
        linked_steps=(
            LinkedStatusStep("소스 수집", "런타임 연결 전", healthy=False),
            LinkedStatusStep("오늘의 Top 5", "아직 데이터 없음", healthy=False),
            LinkedStatusStep("Notion 동기화", "상태 확인 전", healthy=False),
        ),
        source_rows=(
            SourceStatusRow("RSS", "대기", "아직 없음", 0, "DesktopApp 연결 후 실제 상태를 표시합니다."),
        ),
        top_issue_rows=(
            TopIssueRow(
                1,
                "런타임 연결을 기다리는 중입니다.",
                "런타임 연결을 기다리는 중입니다.",
                "출처 없음",
                "",
                "",
                "미분류",
                "0.0점",
                "대기",
                "분류 정보가 아직 없습니다.",
                "숏폼 점수: 0.0점",
            ),
        ),
        log_entries=(
            LogEntry("지금", "안내", "PySide6 화면이 준비되었고 런타임 연결을 기다리는 중입니다."),
        ),
    )


def build_mock_settings_state() -> SettingsState:
    """런타임 연결 전 설정 탭 기본 상태를 만든다."""
    return SettingsState(
        fields=(
            SettingsField("APP_NAME", "앱 이름", "DailyIssueDesktop", "실제 값은 DesktopApp 시작 후 채워집니다."),
        )
    )


class DashboardViewModel(QObject):
    """DesktopApp 상태 조회와 사용자 액션을 조율하는 Qt 뷰모델."""

    dashboard_state_changed = Signal(object)
    settings_state_changed = Signal(object)
    busy_state_changed = Signal(bool)
    progress_changed = Signal(int, str, bool)
    settings_saved = Signal(str)
    run_requested = Signal()
    refresh_requested = Signal()
    settings_requested = Signal()

    def __init__(
        self,
        runtime_adapter: DesktopAppAdapter | None = None,
        presenter: DashboardPresenter | None = None,
        dashboard_state: DashboardState | None = None,
        settings_state: SettingsState | None = None,
    ) -> None:
        super().__init__()
        self._runtime_adapter = runtime_adapter or DesktopAppAdapter()
        self._presenter = presenter or DashboardPresenter()
        self._interaction_logs: tuple[LogEntry, ...] = ()
        self._dashboard_state = dashboard_state or build_mock_dashboard_state()
        self._settings_state = settings_state or build_mock_settings_state()
        self._busy_lock = Lock()
        self._busy = False

    @property
    def dashboard_state(self) -> DashboardState:
        return self._dashboard_state

    @property
    def settings_state(self) -> SettingsState:
        return self._settings_state

    def emit_initial_state(self) -> None:
        """초기 상태를 런타임에서 읽어 화면에 뿌린다."""
        self._append_log("안내", "데스크톱 셸을 시작하고 현재 상태를 불러왔습니다.")
        self.request_refresh()

    def set_dashboard_state(self, state: DashboardState) -> None:
        """대시보드 상태를 갱신한다."""
        self._dashboard_state = state
        self.dashboard_state_changed.emit(self._dashboard_state)

    def set_settings_state(self, state: SettingsState) -> None:
        """설정 상태를 갱신한다."""
        self._settings_state = state
        self.settings_state_changed.emit(self._settings_state)

    def request_run(self) -> None:
        """사용자의 수동 실행 요청을 DesktopApp으로 전달한다."""
        if not self._enter_busy_state():
            self._append_log("안내", "이미 작업이 진행 중입니다. 잠시만 기다려 주세요.")
            return

        self.run_requested.emit()
        self._append_log("안내", "수동 실행을 시작했습니다.")
        self.progress_changed.emit(0, "실행 준비 중", True)

        def _run() -> None:
            try:
                result = self._runtime_adapter.run_now(progress_callback=self._report_progress)
                self._append_log(
                    "안내",
                    (
                        f"수동 실행 완료: 수집 {result.get('collected_count', 0)}건 · "
                        f"Top {result.get('ranked_count', 0)}건 · 동기화 {result.get('synced_count', 0)}건"
                    ),
                )
            except Exception as exc:
                self._append_log("오류", f"수동 실행 실패: {exc}")
                self.progress_changed.emit(100, "실행 실패", False)
            self.refresh_from_runtime()
            if self._busy:
                self.progress_changed.emit(100, "실행 완료", False)
            self._leave_busy_state()

        Thread(target=_run, daemon=True).start()

    def request_refresh(self) -> None:
        """현재 런타임 상태를 다시 읽어 온다."""
        if not self._enter_busy_state():
            return

        self.refresh_requested.emit()
        self._append_log("안내", "현재 상태를 새로고침했습니다.")

        def _refresh() -> None:
            self.refresh_from_runtime()
            self._leave_busy_state()

        Thread(target=_refresh, daemon=True).start()

    def open_settings(self) -> None:
        """설정 탭 전환 요청을 알린다."""
        self.settings_requested.emit()

    def save_settings(self, values: dict[str, str]) -> None:
        """설정값을 저장하고 런타임을 다시 읽는다."""
        if not self._enter_busy_state():
            self._append_log("안내", "이미 작업이 진행 중입니다. 잠시만 기다려 주세요.")
            return

        self._append_log("안내", "설정 저장을 시작했습니다.")
        self.progress_changed.emit(0, "설정 저장 중", True)

        def _save() -> None:
            try:
                saved_path = self._runtime_adapter.save_settings(values)
                self._append_log("안내", f"설정을 저장했습니다: {saved_path}")
                self.settings_saved.emit(saved_path)
                self.progress_changed.emit(100, "설정 저장 완료", False)
            except Exception as exc:
                self._append_log("오류", f"설정 저장 실패: {exc}")
                self.progress_changed.emit(100, "설정 저장 실패", False)
            self.refresh_from_runtime()
            self._leave_busy_state()

        Thread(target=_save, daemon=True).start()

    def shutdown(self) -> None:
        """Qt 종료 시 런타임을 정리한다."""
        self._runtime_adapter.stop()

    def refresh_from_runtime(self) -> None:
        """DesktopApp 상태를 읽어 두 탭의 상태 객체로 변환한다."""
        try:
            runtime_status = self._runtime_adapter.load_status()
            self.set_settings_state(self._presenter.present_settings(runtime_status))
            self.set_dashboard_state(self._presenter.present_dashboard(runtime_status, self._interaction_logs))
        except Exception as exc:
            self._append_log("오류", f"런타임 상태 조회 실패: {exc}")
            self.set_dashboard_state(
                DashboardState(
                    overall_status="연결 실패",
                    overall_detail="DesktopApp 상태를 가져오지 못했습니다. 로그 패널을 확인해 주세요.",
                    linked_steps=self._dashboard_state.linked_steps,
                    source_rows=self._dashboard_state.source_rows,
                    top_issue_rows=self._dashboard_state.top_issue_rows,
                    log_entries=self._interaction_logs,
                )
            )

    def _append_log(self, level: str, message: str) -> None:
        """뷰모델 내부 상호작용 로그를 앞쪽에 누적한다."""
        timestamp = datetime.now().strftime("%H:%M")
        self._interaction_logs = (LogEntry(timestamp, level, message), *self._interaction_logs[:5])

    def _report_progress(self, value: int, message: str) -> None:
        """파이프라인 단계형 진행률을 UI에 전달한다."""
        self.progress_changed.emit(value, message, False)

    def _enter_busy_state(self) -> bool:
        """백그라운드 작업 시작 전 중복 실행을 막는다."""
        with self._busy_lock:
            if self._busy:
                return False
            self._busy = True
        self.busy_state_changed.emit(True)
        return True

    def _leave_busy_state(self) -> None:
        """백그라운드 작업 종료 후 입력 잠금을 해제한다."""
        with self._busy_lock:
            self._busy = False
        self.busy_state_changed.emit(False)
