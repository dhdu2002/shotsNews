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
_CLAUDE_WEB_URL = "https://claude.ai/new"

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
        openai_status="idle",
        delivery_mode="idle",
        status_text="이슈 행의 생성 버튼을 눌러 최신 쇼츠 초안을 만드세요.",
        prompt_guide_text="OpenAI 초안이 준비되면 여기에서 확인할 수 있습니다.",
        action_helper_text="생성된 결과가 있으면 톤별 버튼을 사용할 수 있습니다.",
        chatgpt_web_url=_CHATGPT_WEB_URL,
        claude_web_url=_CLAUDE_WEB_URL,
        tones=(
            GeneratedToneDraft("informative", "정보형", "", ""),
            GeneratedToneDraft("stimulating", "자극형", "", ""),
            GeneratedToneDraft("news", "뉴스형", "", ""),
        ),
    )


class DashboardViewModel(QObject):
    """DesktopApp 상태 조회와 사용자 액션을 조율하는 Qt 뷰모델."""

    CHATGPT_WEB_URL = _CHATGPT_WEB_URL
    CLAUDE_WEB_URL = _CLAUDE_WEB_URL

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
                openai_status="pending",
                delivery_mode="pending",
                status_text="선택한 이슈로 3톤 쇼츠 초안을 생성 중입니다.",
                prompt_guide_text="OpenAI 결과를 확인하는 중입니다.",
                action_helper_text="완료되면 톤별 버튼을 바로 사용할 수 있습니다.",
                chatgpt_web_url=self.CHATGPT_WEB_URL,
                claude_web_url=self.CLAUDE_WEB_URL,
                tones=self._empty_tone_drafts(),
            )
        )
        self.progress_changed.emit(0, "쇼츠 초안 생성 중", True)

        def _generate() -> None:
            try:
                payload = self._runtime_adapter.generate_issue_scripts(issue_row.issue_id)
                self.set_generation_state(self._build_generation_state(issue_row, payload))
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
                        openai_status="failed",
                        delivery_mode="none",
                        status_text=f"쇼츠 초안 생성 실패: {exc}",
                        prompt_guide_text="지금은 OpenAI 초안을 불러오지 못했습니다.",
                        action_helper_text="지금은 복사할 프롬프트를 준비하지 못했습니다.",
                        chatgpt_web_url=self.CHATGPT_WEB_URL,
                        claude_web_url=self.CLAUDE_WEB_URL,
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
    ) -> GenerationState:
        """런타임 생성 결과 payload를 생성 탭 상태로 변환한다."""
        tones_payload = payload.get("tones")
        tone_map = cast(dict[str, object], tones_payload) if isinstance(tones_payload, dict) else {}
        prompts_payload = payload.get("prompts")
        prompt_map = cast(dict[str, object], prompts_payload) if isinstance(prompts_payload, dict) else {}
        has_any_script = any(str(value or "").strip() for value in tone_map.values())
        has_any_prompt = any(str(value or "").strip() for value in prompt_map.values())
        raw_openai_status = str(payload.get("openai_status") or "").strip().lower()
        raw_delivery_mode = str(payload.get("delivery_mode") or "").strip().lower()
        openai_status = self._normalize_openai_status(raw_openai_status, has_any_script, has_any_prompt)
        delivery_mode = self._normalize_delivery_mode(raw_delivery_mode, openai_status, has_any_script, has_any_prompt)
        status_text, prompt_guide_text, action_helper_text = self._build_generation_feedback(
            openai_status,
            delivery_mode,
            has_any_prompt,
        )
        return GenerationState(
            issue_id=issue_row.issue_id,
            title=issue_row.title,
            translated_title=issue_row.translated_title,
            source_name=issue_row.source_name,
            source_url=issue_row.source_url,
            category_label=issue_row.severity,
            score=issue_row.score,
            openai_status=openai_status,
            delivery_mode=delivery_mode,
            status_text=status_text,
            prompt_guide_text=prompt_guide_text,
            action_helper_text=action_helper_text,
            chatgpt_web_url=self.CHATGPT_WEB_URL,
            claude_web_url=self.CLAUDE_WEB_URL,
            tones=(
                self._build_tone_draft(
                    "informative",
                    str(tone_map.get("informative") or ""),
                    str(prompt_map.get("informative") or ""),
                ),
                self._build_tone_draft(
                    "stimulating",
                    str(tone_map.get("stimulating") or ""),
                    str(prompt_map.get("stimulating") or ""),
                ),
                self._build_tone_draft(
                    "news",
                    str(tone_map.get("news") or ""),
                    str(prompt_map.get("news") or ""),
                ),
            ),
        )

    @staticmethod
    def _normalize_openai_status(raw_status: str, has_any_script: bool, has_any_prompt: bool) -> str:
        """백엔드 상태값을 UI에서 쓰는 OpenAI 결과 상태로 정규화한다."""
        if raw_status in {"success", "succeeded", "completed", "ok"}:
            return "success"
        if raw_status in {"failed", "failure", "error"}:
            return "failed"
        if raw_status in {"skipped", "skip"}:
            return "skipped"
        if raw_status in {"unavailable", "disabled", "offline"}:
            return "unavailable"
        if raw_status in {"pending", "running", "processing"}:
            return "pending"
        if has_any_script:
            return "success"
        if has_any_prompt:
            return "skipped"
        return "idle"

    @staticmethod
    def _normalize_delivery_mode(
        raw_mode: str,
        openai_status: str,
        has_any_script: bool,
        has_any_prompt: bool,
    ) -> str:
        """백엔드 전달 방식을 UI에서 쓰는 모드 값으로 정규화한다."""
        if raw_mode in {"openai", "openai_success", "openai_draft", "generated"}:
            return "openai"
        if raw_mode in {"external_prompt", "external_copy", "prompt_copy", "prompt_only", "fallback_prompt"}:
            return "external_prompt"
        if raw_mode in {"pending", "running", "processing"}:
            return "pending"
        if has_any_script or openai_status == "success":
            return "openai"
        if has_any_prompt or openai_status in {"failed", "skipped", "unavailable"}:
            return "external_prompt"
        return "none"

    @staticmethod
    def _build_generation_feedback(
        openai_status: str,
        delivery_mode: str,
        has_any_prompt: bool,
    ) -> tuple[str, str, str]:
        """생성 탭 상단과 액션 영역에 보여줄 문구를 만든다."""
        if delivery_mode == "openai" and openai_status == "success":
            return (
                "OpenAI 초안을 불러왔습니다.",
                "OpenAI가 만든 3톤 초안을 바로 검토하세요.",
                "프롬프트 복사는 필요할 때만 사용하세요.",
            )
        if delivery_mode == "external_prompt":
            if openai_status == "failed":
                status_text = "OpenAI 생성에 실패해 외부 복사 프롬프트를 보여줍니다."
            elif openai_status == "unavailable":
                status_text = "OpenAI를 사용할 수 없어 외부 복사 프롬프트를 보여줍니다."
            else:
                status_text = "OpenAI 초안을 건너뛰고 외부 복사 프롬프트를 보여줍니다."
            prompt_guide_text = (
                "톤별 프롬프트를 복사해 ChatGPT 또는 Claude 웹에서 이어서 생성하세요."
                if has_any_prompt
                else "외부 복사 프롬프트를 준비 중입니다."
            )
            action_helper_text = (
                "복사할 톤을 고른 뒤 ChatGPT 또는 Claude 웹에 붙여넣으세요."
                if has_any_prompt
                else "복사할 프롬프트가 준비되면 톤별 버튼을 사용할 수 있습니다."
            )
            return status_text, prompt_guide_text, action_helper_text
        if openai_status == "pending" or delivery_mode == "pending":
            return (
                "선택한 이슈로 3톤 쇼츠 초안을 생성 중입니다.",
                "OpenAI 결과를 확인하는 중입니다.",
                "완료되면 톤별 버튼을 바로 사용할 수 있습니다.",
            )
        return (
            "이슈 행의 생성 버튼을 눌러 최신 쇼츠 초안을 만드세요.",
            "OpenAI 초안이 준비되면 여기에서 확인할 수 있습니다.",
            "생성된 결과가 있으면 톤별 버튼을 사용할 수 있습니다.",
        )

    def _build_tone_draft(
        self,
        tone_key: str,
        script_text: str,
        prompt_text: str,
    ) -> GeneratedToneDraft:
        """원본 초안과 공통 생성 프롬프트를 함께 묶는다."""
        tone_label_map = {"informative": "정보형", "stimulating": "자극형", "news": "뉴스형"}
        tone_label = tone_label_map.get(tone_key, tone_key)
        cleaned_script = script_text.strip()
        return GeneratedToneDraft(
            tone_key=tone_key,
            tone_label=tone_label,
            script_text=cleaned_script,
            final_prompt_text=prompt_text.strip(),
        )
