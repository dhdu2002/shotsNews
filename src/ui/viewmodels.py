# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false

"""PySide6 대시보드와 DesktopApp 런타임을 잇는 뷰모델."""

from __future__ import annotations

from datetime import datetime
from threading import Lock, Thread
from typing import cast

from PySide6.QtCore import QObject, Signal

from .models import (
    CategoryTopIssueSection,
    DashboardState,
    GeneratedToneDraft,
    GenerationState,
    LinkedStatusStep,
    LogEntry,
    SettingsField,
    SettingsState,
    SourceStatusRow,
    TopIssueRow,
)
from .runtime_bridge import DashboardPresenter, DesktopAppAdapter

_CHATGPT_WEB_URL = "https://chatgpt.com/"

_TONE_GUIDES: dict[str, dict[str, str]] = {
    "informative": {
        "label": "정보형",
        "template": (
            "당신은 한국어 숏폼 콘텐츠를 다듬는 편집자입니다.\n"
            "아래 [입력 초안]을 정보형 최종 대본으로 재작성하세요.\n\n"
            "[작성 목표]\n"
            "- 설명형 톤을 유지하되 정보 전달이 가장 잘 되도록 문장을 정리하세요.\n"
            "- 핵심을 쉬운 말로 풀고, 필요하면 순서·포인트를 자연스럽게 살려 주세요.\n"
            "- 제목을 그대로 반복하지 말고 시청자가 바로 이해할 수 있게 풀어서 설명하세요.\n"
            "- 전문 용어는 쉬운 한국어로 바꾸거나 짧게 풀어 주세요.\n"
            "- 초안의 사실관계와 핵심 메시지는 유지하고, 없는 내용을 추가하지 마세요.\n\n"
            "[출력 규칙]\n"
            "- 최종 대본 본문만 출력하세요.\n"
            "- 설명, 메모, 제목, 번호 매기기, 따옴표, 마크다운은 넣지 마세요.\n"
            "- 자연스러운 한국어 숏폼 내레이션 문장으로 정리하세요.\n\n"
            "[입력 초안]\n"
            "{초안 전문}"
        ),
    },
    "stimulating": {
        "label": "자극형",
        "template": (
            "당신은 한국어 숏폼 콘텐츠를 다듬는 편집자입니다.\n"
            "아래 [입력 초안]을 자극형 최종 대본으로 재작성하세요.\n\n"
            "[작성 목표]\n"
            "- 강한 흡입력과 감정선은 살리되 과장, 허위, 혐오 표현 없이 설득력 있게 다듬으세요.\n"
            "- 첫 문장은 스크롤을 멈추게 할 정도로 강해야 하지만 전체 흐름은 자연스러워야 합니다.\n"
            "- 자극적인 표현을 쓰더라도 사실과 어긋나면 안 됩니다.\n"
            "- 제목을 그대로 복붙하지 말고, 핵심 갈등과 포인트가 즉시 느껴지게 다시 써 주세요.\n"
            "- 초안의 사실관계와 핵심 메시지는 유지하고, 없는 내용을 추가하지 마세요.\n\n"
            "[출력 규칙]\n"
            "- 최종 대본 본문만 출력하세요.\n"
            "- 설명, 메모, 제목, 번호 매기기, 따옴표, 마크다운은 넣지 마세요.\n"
            "- 실제 한국어 숏폼 화법처럼 리듬감 있게 정리하세요.\n\n"
            "[입력 초안]\n"
            "{초안 전문}"
        ),
    },
    "news": {
        "label": "뉴스형",
        "template": (
            "당신은 한국어 숏폼 뉴스 대본을 다듬는 편집자입니다.\n"
            "아래 [입력 초안]을 뉴스형 최종 대본으로 재작성하세요.\n\n"
            "[작성 목표]\n"
            "- 리포터처럼 차분하고 신뢰감 있게 다듬으세요.\n"
            "- 팩트 중심으로 정리하되 딱딱한 문어체보다 실제 숏폼 내레이션처럼 자연스럽게 써 주세요.\n"
            "- 제목을 그대로 반복하지 말고, 기사 핵심이 첫 문장부터 바로 전달되게 써 주세요.\n"
            "- URL이나 도메인이 문장에 그대로 보이면 자연스러운 매체명 표현으로 바꿔 주세요.\n"
            "- 출처가 필요할 때도 링크를 읽지 말고 뉴스에서 말할 법한 매체명으로 정리하세요.\n"
            "- 초안의 사실관계와 핵심 메시지는 유지하고, 없는 내용을 추가하지 마세요.\n\n"
            "[출력 규칙]\n"
            "- 최종 대본 본문만 출력하세요.\n"
            "- 설명, 메모, 제목, 번호 매기기, 따옴표, 마크다운은 넣지 마세요.\n"
            "- 실제 앵커/리포터 내레이션처럼 자연스러운 한국어 문장으로 정리하세요.\n\n"
            "[입력 초안]\n"
            "{초안 전문}"
        ),
    },
}


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
        category_sections=(
            CategoryTopIssueSection(
                category_key="ai_tech",
                category_label="AI/테크",
                domestic_rows=(
                    TopIssueRow(
                        1,
                        "런타임 연결을 기다리는 중입니다.",
                        "런타임 연결을 기다리는 중입니다.",
                        "",
                        "출처 없음",
                        "",
                        "ai_tech",
                        "AI/테크",
                        "0.0점",
                        "대기",
                        "분류 정보가 아직 없습니다.",
                        "숏폼 점수: 0.0점",
                        region="domestic",
                    ),
                ),
                international_rows=(
                    TopIssueRow(
                        1,
                        "런타임 연결을 기다리는 중입니다.",
                        "런타임 연결을 기다리는 중입니다.",
                        "",
                        "출처 없음",
                        "",
                        "ai_tech",
                        "AI/테크",
                        "0.0점",
                        "대기",
                        "분류 정보가 아직 없습니다.",
                        "숏폼 점수: 0.0점",
                        region="international",
                    ),
                ),
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


def build_mock_generation_state() -> GenerationState:
    """런타임 연결 전 생성 탭 기본 상태를 만든다."""
    return GenerationState(
        status_text="이슈 행의 생성 버튼을 눌러 최신 쇼츠 초안을 만드세요.",
        chatgpt_web_url=_CHATGPT_WEB_URL,
        tones=(
            GeneratedToneDraft("informative", "정보형", "", ""),
            GeneratedToneDraft("stimulating", "자극형", "", ""),
            GeneratedToneDraft("news", "뉴스형", "", ""),
        ),
    )


class DashboardViewModel(QObject):
    """DesktopApp 상태 조회와 사용자 액션을 조율하는 Qt 뷰모델."""

    CHATGPT_WEB_URL = _CHATGPT_WEB_URL

    dashboard_state_changed = Signal(object)
    generation_state_changed = Signal(object)
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
        self._generation_state = build_mock_generation_state()
        self._settings_state = settings_state or build_mock_settings_state()
        self._busy_lock = Lock()
        self._busy = False

    @property
    def dashboard_state(self) -> DashboardState:
        return self._dashboard_state

    @property
    def settings_state(self) -> SettingsState:
        return self._settings_state

    @property
    def generation_state(self) -> GenerationState:
        return self._generation_state

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

    def set_generation_state(self, state: GenerationState) -> None:
        """생성 탭 상태를 갱신한다."""
        self._generation_state = state
        self.generation_state_changed.emit(self._generation_state)

    def get_chatgpt_prompt_for_tone(self, tone_key: str) -> str:
        """UI가 복사 버튼에 바로 연결할 수 있는 톤별 ChatGPT 프롬프트를 돌려준다."""
        for tone in self._generation_state.tones:
            if tone.tone_key == tone_key:
                return tone.final_prompt_text
        return ""

    def get_chatgpt_open_url(self, tone_key: str) -> str:
        """UI가 브라우저 열기 버튼에 연결할 수 있는 ChatGPT URL을 돌려준다."""
        if not self.get_chatgpt_prompt_for_tone(tone_key):
            return ""
        return self._generation_state.chatgpt_web_url

    def request_generate_issue_scripts(self, issue_row: TopIssueRow) -> None:
        """선택 이슈 1건의 3톤 초안 생성을 요청한다."""
        if not issue_row.issue_id:
            self._append_log("오류", "선택 이슈 ID가 없어 쇼츠 초안을 생성할 수 없습니다.")
            return
        if not self._enter_busy_state():
            self._append_log("안내", "이미 작업이 진행 중입니다. 잠시만 기다려 주세요.")
            return

        self.set_generation_state(
            GenerationState(
                issue_id=issue_row.issue_id,
                title=issue_row.title,
                translated_title=issue_row.translated_title,
                source_name=issue_row.source_name,
                source_url=issue_row.source_url,
                category_label=issue_row.severity,
                score=issue_row.score,
                status_text="선택한 이슈로 3톤 쇼츠 초안을 생성 중입니다.",
                chatgpt_web_url=self.CHATGPT_WEB_URL,
                tones=self._empty_tone_drafts(),
            )
        )
        self.progress_changed.emit(0, "쇼츠 초안 생성 중", True)

        def _generate() -> None:
            try:
                payload = self._runtime_adapter.generate_issue_scripts(issue_row.issue_id)
                self.set_generation_state(self._build_generation_state(issue_row, payload, "최신 1건 초안을 불러왔습니다."))
                self._append_log("안내", f"쇼츠 초안 생성 완료: {issue_row.translated_title}")
                self.progress_changed.emit(100, "쇼츠 초안 생성 완료", False)
            except Exception as exc:
                self.set_generation_state(
                    GenerationState(
                        issue_id=issue_row.issue_id,
                        title=issue_row.title,
                        translated_title=issue_row.translated_title,
                        source_name=issue_row.source_name,
                        source_url=issue_row.source_url,
                        category_label=issue_row.severity,
                        score=issue_row.score,
                        status_text=f"쇼츠 초안 생성 실패: {exc}",
                        chatgpt_web_url=self.CHATGPT_WEB_URL,
                        tones=self._empty_tone_drafts(),
                    )
                )
                self._append_log("오류", f"쇼츠 초안 생성 실패: {exc}")
                self.progress_changed.emit(100, "쇼츠 초안 생성 실패", False)
            self._leave_busy_state()

        Thread(target=_generate, daemon=True).start()

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
                    category_sections=self._dashboard_state.category_sections,
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

    @staticmethod
    def _empty_tone_drafts() -> tuple[GeneratedToneDraft, ...]:
        """초기/실패 상태에서 공통으로 쓰는 빈 3톤 목록을 만든다."""
        return (
            GeneratedToneDraft("informative", "정보형", "", ""),
            GeneratedToneDraft("stimulating", "자극형", "", ""),
            GeneratedToneDraft("news", "뉴스형", "", ""),
        )

    def _build_generation_state(
        self,
        issue_row: TopIssueRow,
        payload: dict[str, object],
        status_text: str,
    ) -> GenerationState:
        """런타임 생성 결과 payload를 생성 탭 상태로 변환한다."""
        tones_payload = payload.get("tones")
        tone_map = cast(dict[str, object], tones_payload) if isinstance(tones_payload, dict) else {}
        return GenerationState(
            issue_id=issue_row.issue_id,
            title=issue_row.title,
            translated_title=issue_row.translated_title,
            source_name=issue_row.source_name,
            source_url=issue_row.source_url,
            category_label=issue_row.severity,
            score=issue_row.score,
            status_text=status_text,
            chatgpt_web_url=self.CHATGPT_WEB_URL,
            tones=(
                self._build_tone_draft("informative", str(tone_map.get("informative") or "")),
                self._build_tone_draft("stimulating", str(tone_map.get("stimulating") or "")),
                self._build_tone_draft("news", str(tone_map.get("news") or "")),
            ),
        )

    def _build_tone_draft(
        self,
        tone_key: str,
        script_text: str,
    ) -> GeneratedToneDraft:
        """원본 초안과 ChatGPT 보정용 프롬프트를 함께 묶는다."""
        tone_meta = _TONE_GUIDES.get(tone_key, {"label": tone_key, "template": "{초안 전문}"})
        tone_label = str(tone_meta.get("label") or tone_key)
        cleaned_script = script_text.strip()
        return GeneratedToneDraft(
            tone_key=tone_key,
            tone_label=tone_label,
            script_text=cleaned_script,
            final_prompt_text=self._build_final_complete_draft_prompt(
                tone_template=str(tone_meta.get("template") or "{초안 전문}"),
                script_text=cleaned_script,
            ),
        )

    @staticmethod
    def _build_final_complete_draft_prompt(
        tone_template: str,
        script_text: str,
    ) -> str:
        """최신 생성 결과를 ChatGPT에서 최종 완성 대본으로 다듬기 위한 프롬프트를 만든다."""
        if not script_text:
            return ""

        return tone_template.replace("{초안 전문}", script_text)
