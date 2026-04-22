# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false

"""PySide6 메인 윈도우와 대시보드 화면 구성."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .models import CategoryTopIssueSection, DashboardState, GenerationState, SettingsState, TopIssueRow
from .viewmodels import DashboardViewModel
from .widgets import LinkedStatusView, MetricCard, SectionFrame


_CATEGORY_PASTELS = {
    "ai_tech": {"row": "#eff6ff", "accent": "#dbeafe", "text": "#1d4ed8"},
    "economy": {"row": "#fef3c7", "accent": "#fde68a", "text": "#b45309"},
    "society": {"row": "#f3e8ff", "accent": "#e9d5ff", "text": "#7e22ce"},
    "health": {"row": "#ecfdf5", "accent": "#d1fae5", "text": "#047857"},
    "entertainment_trend": {"row": "#fff1f2", "accent": "#ffe4e6", "text": "#be123c"},
    "default": {"row": "#f8fafc", "accent": "#e5e7eb", "text": "#475569"},
}

class DashboardMainWindow(QMainWindow):
    """런타임 연결형 대시보드 메인 윈도우."""

    def __init__(self, viewmodel: DashboardViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.setMinimumSize(1200, 780)

        self._build_ui()
        self._connect_signals()
        self.viewmodel.emit_initial_state()

    def _build_ui(self) -> None:
        """윈도우의 주요 레이아웃과 위젯을 구성한다."""
        self.setWindowTitle("데일리 이슈 데스크톱")

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        self.title_label = QLabel("운영 대시보드")
        self.title_label.setObjectName("pageTitle")
        title_wrap.addWidget(self.title_label)

        self.subtitle_label = QLabel("수집, Top 5 선정, Notion 상태를 한 화면에서 확인합니다.")
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setWordWrap(True)
        title_wrap.addWidget(self.subtitle_label)
        header_layout.addLayout(title_wrap, 1)

        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setObjectName("secondaryButton")
        header_layout.addWidget(self.refresh_button)

        self.settings_button = QPushButton("설정")
        self.settings_button.setObjectName("secondaryButton")
        header_layout.addWidget(self.settings_button)

        self.run_button = QPushButton("지금 실행")
        self.run_button.setObjectName("primaryButton")
        header_layout.addWidget(self.run_button)
        root_layout.addWidget(header_frame)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        root_layout.addWidget(self.tab_widget, 1)

        self.dashboard_page = QWidget()
        dashboard_layout = QVBoxLayout(self.dashboard_page)
        dashboard_layout.setContentsMargins(8, 12, 8, 8)
        dashboard_layout.setSpacing(16)

        issues_section = SectionFrame(
            "분야별 TOP 5",
            "5개 분류별로 국내 TOP 5 / 해외 TOP 5를 모두 확인합니다.",
        )
        self.category_sections_wrap = QWidget()
        self.category_sections_layout = QVBoxLayout(self.category_sections_wrap)
        self.category_sections_layout.setContentsMargins(0, 0, 0, 0)
        self.category_sections_layout.setSpacing(14)
        issues_section.body_layout.addWidget(self.category_sections_wrap)
        self._issue_tables: list[QTableWidget] = []

        dashboard_layout.addWidget(issues_section, 1)

        self.dashboard_scroll = QScrollArea()
        self.dashboard_scroll.setWidgetResizable(True)
        self.dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.dashboard_scroll.setWidget(self.dashboard_page)

        _ = self.tab_widget.addTab(self.dashboard_scroll, "대시보드")

        self.status_page = QWidget()
        status_layout = QVBoxLayout(self.status_page)
        status_layout.setContentsMargins(8, 12, 8, 8)
        status_layout.setSpacing(16)

        summary_section = SectionFrame(
            "실행 요약",
            "현재 실행 상태, 다음 일정, 최근 실행 결과를 한 번에 확인합니다.",
        )
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.status_card = MetricCard("실행 상태")
        self.next_run_card = MetricCard("다음 실행")
        self.last_run_card = MetricCard("최근 실행")
        self.notion_card = MetricCard("Notion 동기화")
        cards_row.addWidget(self.status_card)
        cards_row.addWidget(self.next_run_card)
        cards_row.addWidget(self.last_run_card)
        cards_row.addWidget(self.notion_card)
        summary_section.body_layout.addLayout(cards_row)

        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self.progress_label = QLabel("대기 중")
        self.progress_label.setObjectName("progressLabel")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        summary_section.body_layout.addWidget(progress_frame)
        status_layout.addWidget(summary_section)

        linked_section = SectionFrame(
            "연결 상태",
            "소스 수집 → 오늘의 Top 5 → Notion 동기화 흐름을 상태 중심으로 보여줍니다.",
        )
        self.linked_status_view = LinkedStatusView()
        linked_section.body_layout.addWidget(self.linked_status_view)
        status_layout.addWidget(linked_section)

        source_section = SectionFrame(
            "수집원 상태",
            "각 수집원의 연결 여부와 최근 확인 결과를 빠르게 파악합니다.",
        )
        self.source_table = QTableWidget(0, 5)
        self.source_table.setHorizontalHeaderLabels(["수집원", "상태", "최근 확인", "확인 필요", "메모"])
        self._prepare_table(self.source_table)
        source_section.body_layout.addWidget(self.source_table)
        status_layout.addWidget(source_section, 1)

        logs_section = SectionFrame(
            "최근 로그",
            "수집, 선정, 생성 흐름의 최신 이벤트를 상태 탭 하단에서 확인합니다.",
        )
        self.logs_list = QListWidget()
        self.logs_list.setObjectName("logsList")
        logs_section.body_layout.addWidget(self.logs_list)
        status_layout.addWidget(logs_section)

        self.status_scroll = QScrollArea()
        self.status_scroll.setWidgetResizable(True)
        self.status_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.status_scroll.setWidget(self.status_page)

        _ = self.tab_widget.addTab(self.status_scroll, "상태")

        self.generation_page = QWidget()
        generation_layout = QVBoxLayout(self.generation_page)
        generation_layout.setContentsMargins(8, 12, 8, 8)
        generation_layout.setSpacing(16)

        generation_summary = SectionFrame(
            "최신 쇼츠 초안",
            "대시보드에서 선택한 최신 1건 기준으로 정보형/자극형/뉴스형 초안을 확인합니다.",
        )
        self.generation_title_label = QLabel("선택된 이슈가 없습니다.")
        self.generation_title_label.setObjectName("sectionTitle")
        self.generation_title_label.setWordWrap(True)
        generation_summary.body_layout.addWidget(self.generation_title_label)

        self.generation_meta_label = QLabel("이슈 행의 생성 버튼을 눌러 최신 쇼츠 초안을 만드세요.")
        self.generation_meta_label.setObjectName("sectionSubtitle")
        self.generation_meta_label.setWordWrap(True)
        generation_summary.body_layout.addWidget(self.generation_meta_label)

        self.generation_source_button = QPushButton("원문 열기")
        self.generation_source_button.setObjectName("secondaryButton")
        self.generation_source_button.setEnabled(False)
        generation_summary.body_layout.addWidget(self.generation_source_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.generation_prompt_guide_label = QLabel("최종 프롬프트를 복사한 뒤 ChatGPT 웹에 직접 붙여넣어 반자동으로 마무리하세요.")
        self.generation_prompt_guide_label.setObjectName("sectionSubtitle")
        self.generation_prompt_guide_label.setWordWrap(True)
        generation_summary.body_layout.addWidget(self.generation_prompt_guide_label)

        generation_action_row = QWidget()
        generation_action_layout = QHBoxLayout(generation_action_row)
        generation_action_layout.setContentsMargins(0, 0, 0, 0)
        generation_action_layout.setSpacing(8)
        self.generation_chatgpt_button = QPushButton("ChatGPT 열기")
        self.generation_chatgpt_button.setObjectName("generationChatgptButton")
        self.generation_chatgpt_button.setEnabled(False)
        generation_action_layout.addWidget(self.generation_chatgpt_button)
        generation_action_layout.addStretch(1)
        generation_summary.body_layout.addWidget(generation_action_row)

        self.generation_action_status_label = QLabel("생성된 초안이 있으면 톤별 최종 프롬프트를 바로 복사할 수 있습니다.")
        self.generation_action_status_label.setObjectName("fieldHelper")
        self.generation_action_status_label.setWordWrap(True)
        generation_summary.body_layout.addWidget(self.generation_action_status_label)
        generation_layout.addWidget(generation_summary)

        self._generation_editors: dict[str, QPlainTextEdit] = {}
        self._generation_prompt_buttons: dict[str, QPushButton] = {}
        self._generation_prompt_texts: dict[str, str] = {}
        tones_section = SectionFrame("3톤 초안")
        for tone_key, tone_label in (("informative", "정보형"), ("stimulating", "자극형"), ("news", "뉴스형")):
            tone_block = QWidget()
            tone_layout = QVBoxLayout(tone_block)
            tone_layout.setContentsMargins(0, 0, 0, 0)
            tone_layout.setSpacing(6)

            tone_label_widget = QLabel(tone_label)
            tone_label_widget.setStyleSheet("font-weight: 700; font-size: 14px; color: #102a43; padding-top: 4px;")
            tone_layout.addWidget(tone_label_widget)

            tone_editor = QPlainTextEdit()
            tone_editor.setReadOnly(True)
            tone_editor.setMinimumHeight(120)
            self._generation_editors[tone_key] = tone_editor
            tone_layout.addWidget(tone_editor)

            prompt_row = QHBoxLayout()
            prompt_row.setContentsMargins(0, 0, 0, 0)
            prompt_row.setSpacing(0)
            prompt_row.addStretch(1)

            prompt_button = QPushButton(f"{tone_label} 프롬프트 복사")
            prompt_button.setObjectName("generationActionButton")
            prompt_button.setEnabled(False)
            prompt_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            _ = prompt_button.setProperty("toneKey", tone_key)
            prompt_row.addWidget(prompt_button)
            tone_layout.addLayout(prompt_row)
            self._generation_prompt_buttons[tone_key] = prompt_button

            tones_section.body_layout.addWidget(tone_block)
        generation_layout.addWidget(tones_section, 1)

        self.generation_scroll = QScrollArea()
        self.generation_scroll.setWidgetResizable(True)
        self.generation_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.generation_scroll.setWidget(self.generation_page)

        _ = self.tab_widget.addTab(self.generation_scroll, "생성")

        self.settings_page = QWidget()
        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setContentsMargins(8, 12, 8, 8)
        settings_layout.setSpacing(16)

        settings_section = SectionFrame("설정 연결 자리")
        self.settings_heading_label = QLabel()
        self.settings_heading_label.setObjectName("settingsHeading")
        self.settings_heading_label.setWordWrap(True)
        settings_section.body_layout.addWidget(self.settings_heading_label)

        self.settings_description_label = QLabel()
        self.settings_description_label.setObjectName("settingsDescription")
        self.settings_description_label.setWordWrap(True)
        settings_section.body_layout.addWidget(self.settings_description_label)

        self.settings_form = QFormLayout()
        self.settings_form.setContentsMargins(0, 4, 0, 0)
        self.settings_form.setSpacing(12)
        settings_section.body_layout.addLayout(self.settings_form)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.save_settings_button = QPushButton("설정 저장")
        self.save_settings_button.setObjectName("primaryButton")
        action_row.addWidget(self.save_settings_button)
        settings_section.body_layout.addLayout(action_row)

        settings_layout.addWidget(settings_section)
        settings_layout.addStretch(1)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setWidget(self.settings_page)

        _ = self.tab_widget.addTab(self.settings_scroll, "설정")

        self.setCentralWidget(root)
        self._apply_styles()

    def _connect_signals(self) -> None:
        """버튼과 뷰모델 시그널을 연결한다."""
        _ = self.run_button.clicked.connect(self.viewmodel.request_run)
        _ = self.refresh_button.clicked.connect(self.viewmodel.request_refresh)
        _ = self.settings_button.clicked.connect(self.viewmodel.open_settings)
        _ = self.viewmodel.settings_requested.connect(self._show_settings_tab)
        _ = self.viewmodel.dashboard_state_changed.connect(self._render_dashboard_state)
        _ = self.viewmodel.generation_state_changed.connect(self._render_generation_state)
        _ = self.viewmodel.settings_state_changed.connect(self._render_settings_state)
        _ = self.viewmodel.busy_state_changed.connect(self._set_busy_state)
        _ = self.viewmodel.progress_changed.connect(self._render_progress)
        _ = self.viewmodel.settings_saved.connect(self._on_settings_saved)
        _ = self.save_settings_button.clicked.connect(self._save_settings)
        _ = self.generation_source_button.clicked.connect(self._open_generation_source)
        for tone_key, button in self._generation_prompt_buttons.items():
            _ = button.clicked.connect(
                lambda checked=False, current_tone_key=tone_key: self._copy_generation_final_prompt(current_tone_key)
            )
        _ = self.generation_chatgpt_button.clicked.connect(self._open_chatgpt_web)
        self._settings_inputs: dict[str, QLineEdit] = {}
        self._generation_source_url = ""
        self._generation_chatgpt_url = ""
        self._render_generation_state(self.viewmodel.generation_state)

    def _prepare_table(self, table: QTableWidget) -> None:
        """표의 공통 표시 옵션을 맞춘다."""
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setWordWrap(False)
        table.setMouseTracking(True)

    def _configure_issue_table_columns(self, table: QTableWidget) -> None:
        """Top 5 표에서 이슈 열이 가장 넓게 보이도록 컬럼 폭을 조정한다."""
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

        table.setColumnWidth(0, 56)
        table.setColumnWidth(2, 180)
        table.setColumnWidth(3, 82)
        table.setColumnWidth(4, 82)
        table.setColumnWidth(5, 118)
        table.setCursor(Qt.CursorShape.ArrowCursor)

    def _render_dashboard_state(self, state: DashboardState) -> None:
        """대시보드 탭을 최신 상태로 다시 그린다."""
        self.setWindowTitle(state.window_title)
        self.title_label.setText(state.dashboard_title)
        self.subtitle_label.setText(state.dashboard_subtitle)

        self.status_card.set_content(state.overall_status, state.overall_detail)
        self.next_run_card.set_content(state.next_run_label, "백그라운드 스케줄러 기준 다음 실행 예상 시각")
        self.last_run_card.set_content(state.last_run_label, "가장 최근에 확인된 실행 시각")
        self.notion_card.set_content(state.notion_sync_status, state.notion_sync_detail)
        self.linked_status_view.set_steps(state.linked_steps)

        self.source_table.setRowCount(len(state.source_rows))
        for row_index, row in enumerate(state.source_rows):
            values = [row.source_name, row.health, row.last_checked, str(row.pending_items), row.note]
            for column_index, value in enumerate(values):
                self.source_table.setItem(row_index, column_index, QTableWidgetItem(value))

        self._render_category_sections(state.category_sections)

        self.logs_list.clear()
        for entry in state.log_entries:
            self.logs_list.addItem(QListWidgetItem(f"[{entry.timestamp}] {entry.level} · {entry.message}"))

    def _render_generation_state(self, state: GenerationState) -> None:
        """생성 탭을 최신 1건 기준 상태로 갱신한다."""
        display_title = state.translated_title or state.title or "선택된 이슈가 없습니다."
        self.generation_title_label.setText(display_title)

        meta_parts = [part for part in (state.category_label, state.score, state.source_name) if part]
        meta_text = " · ".join(meta_parts)
        if state.status_text:
            meta_text = f"{meta_text}\n{state.status_text}" if meta_text else state.status_text
        self.generation_meta_label.setText(meta_text or "이슈 행의 생성 버튼을 눌러 최신 쇼츠 초안을 만드세요.")

        self._generation_source_url = state.source_url
        self.generation_source_button.setEnabled(bool(state.source_url))

        tone_map = {tone.tone_key: tone.script_text for tone in state.tones}
        prompt_map = {tone.tone_key: tone.final_prompt_text.strip() for tone in state.tones}
        self._generation_prompt_texts = prompt_map
        has_any_prompt = False
        for tone_key, button in self._generation_prompt_buttons.items():
            has_prompt = bool(prompt_map.get(tone_key))
            button.setEnabled(has_prompt)
            has_any_prompt = has_any_prompt or has_prompt
        self._generation_chatgpt_url = state.chatgpt_web_url.strip() if has_any_prompt else ""
        self.generation_chatgpt_button.setEnabled(bool(self._generation_chatgpt_url))
        self.generation_action_status_label.setText(
            "복사할 톤을 고른 뒤 ChatGPT 웹을 열어 수동으로 붙여넣으세요."
            if has_any_prompt
            else "생성된 초안이 있으면 톤별 최종 프롬프트를 바로 복사할 수 있습니다."
        )
        for tone_key, editor in self._generation_editors.items():
            editor.setPlainText(str(tone_map.get(tone_key) or ""))

    def _render_category_sections(self, sections: tuple[CategoryTopIssueSection, ...]) -> None:
        """카테고리별 국내/해외 Top 5 섹션을 다시 그린다."""
        self._clear_layout(self.category_sections_layout)
        self._issue_tables = []

        for section in sections:
            section_frame = SectionFrame(section.category_label)

            total_count = len(section.domestic_rows) + len(section.international_rows)
            section_header = QLabel(f"{section.category_label} · {total_count}개")
            section_header.setStyleSheet("font-weight: 700; font-size: 14px; color: #102a43; padding-bottom: 2px;")
            section_frame.body_layout.addWidget(section_header)

            tables_column = QVBoxLayout()
            tables_column.setSpacing(10)
            tables_column.addWidget(self._build_region_table_block("🇰🇷 국내 TOP 5", section.domestic_rows, "#1d4ed8"))
            tables_column.addWidget(self._build_region_table_block("🌍 해외 TOP 5", section.international_rows, "#047857"))
            section_frame.body_layout.addLayout(tables_column)

            self.category_sections_layout.addWidget(section_frame)

        self.category_sections_layout.addStretch(1)

    def _build_region_table_block(self, title: str, rows: tuple[TopIssueRow, ...], color: str) -> QWidget:
        """카테고리 내부의 국내/해외 Top 5 한 블록을 구성한다."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(f"{title} · {len(rows)}개")
        label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {color}; padding: 2px 0;")
        layout.addWidget(label)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["순위", "이슈", "출처", "점수", "상태", "생성"])
        self._prepare_table(table)
        self._configure_issue_table_columns(table)
        self._fill_issue_table(table, rows)
        _ = table.cellClicked.connect(self._open_issue_link)
        self._issue_tables.append(table)
        layout.addWidget(table)

        return container

    def _render_settings_state(self, state: SettingsState) -> None:
        """설정 탭을 최신 편집 가능 상태로 다시 그린다."""
        self.settings_heading_label.setText(state.heading)
        self.settings_description_label.setText(state.description)
        self._settings_inputs = {}

        while self.settings_form.rowCount():
            self.settings_form.removeRow(0)

        for field in state.fields:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)

            line_edit = QLineEdit(field.value)
            line_edit.setReadOnly(not field.editable)
            if field.secret:
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            container_layout.addWidget(line_edit)
            self._settings_inputs[field.key] = line_edit

            helper_label = QLabel(field.helper_text)
            helper_label.setObjectName("fieldHelper")
            helper_label.setWordWrap(True)
            container_layout.addWidget(helper_label)

            self.settings_form.addRow(field.label, container)

    def _show_settings_tab(self) -> None:
        """설정 탭으로 전환한다."""
        self.tab_widget.setCurrentWidget(self.settings_scroll)

    def _set_busy_state(self, busy: bool) -> None:
        """백그라운드 작업 중 버튼 상태를 조정하고, 실행 시작 시 상태 탭으로 전환한다."""
        self.run_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.settings_button.setEnabled(True)
        self.save_settings_button.setEnabled(not busy)
        if busy and self.tab_widget.currentWidget() is not self.generation_scroll:
            self.tab_widget.setCurrentWidget(self.status_scroll)

    def _render_progress(self, value: int, message: str, indeterminate: bool) -> None:
        """대시보드 상단의 진행률 표시를 갱신한다."""
        self.progress_label.setText(message)
        if indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def _save_settings(self) -> None:
        """설정 입력값을 수집해 저장 요청을 보낸다."""
        payload = {key: widget.text() for key, widget in self._settings_inputs.items()}
        self.viewmodel.save_settings(payload)

    def _on_settings_saved(self, saved_path: str) -> None:
        """설정 저장 완료 후 안내 문구를 갱신한다."""
        self.progress_label.setText(f"설정 저장 완료: {saved_path}")

    def _fill_issue_table(self, table: QTableWidget, rows: tuple[TopIssueRow, ...]) -> None:
        """이슈 테이블을 주어진 rows로 채운다."""
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            table.setRowHeight(row_index, 38)
            items = [
                self._create_issue_table_item(str(row.rank), align_center=True),
                self._create_issue_table_item(row.translated_title),
                self._create_issue_table_item(row.source_name),
                self._create_issue_table_item(row.score, tooltip=row.score_tooltip, align_center=True, emphasize=True),
                self._create_issue_table_item(row.readiness, tooltip=row.status_tooltip, align_center=True),
                self._create_issue_table_item("", align_center=True),
            ]
            items[0].setData(Qt.ItemDataRole.UserRole + 1, row)
            for column_index, item in enumerate(items):
                if column_index in {1, 2} and row.source_url:
                    item.setData(Qt.ItemDataRole.UserRole, row.source_url)
                    item.setToolTip(row.source_url)
                    item.setForeground(Qt.GlobalColor.blue)
                    font = item.font()
                    font.setUnderline(True)
                    item.setFont(font)
                table.setItem(row_index, column_index, item)
            self._apply_category_palette_for_table(table, row_index, row.category_key)
            action_button = QPushButton("초안 생성")
            action_button.setObjectName("rowActionButton")
            _ = action_button.clicked.connect(lambda checked=False, current_row=row: self._trigger_generate_issue(current_row))
            table.setCellWidget(row_index, 5, action_button)
        self._adjust_issue_table_height(table, len(rows))

    def _trigger_generate_issue(self, row: TopIssueRow) -> None:
        """선택 이슈의 3톤 초안 생성을 시작하고 생성 탭으로 이동한다."""
        self.tab_widget.setCurrentWidget(self.generation_scroll)
        self.viewmodel.request_generate_issue_scripts(row)

    def _open_issue_link(self, row_index: int, column: int) -> None:
        """이슈/출처 셀 클릭 시 원문 링크를 바로 연다."""
        if column not in {1, 2}:
            return
        table = cast(QTableWidget | None, self.sender())
        if table is None:
            return
        item = table.item(row_index, column)
        if item is None:
            return
        source_url = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if source_url:
            _ = QDesktopServices.openUrl(QUrl(source_url))

    def _open_generation_source(self) -> None:
        """생성 탭에서 최신 이슈 원문 링크를 연다."""
        if self._generation_source_url:
            _ = QDesktopServices.openUrl(QUrl(self._generation_source_url))

    def _copy_generation_final_prompt(self, tone_key: str) -> None:
        """선택한 톤의 최종 프롬프트를 클립보드에 복사한다."""
        prompt_text = self._generation_prompt_texts.get(tone_key, "").strip()
        if not prompt_text:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(prompt_text)
        tone_label_map = {"informative": "정보형", "stimulating": "자극형", "news": "뉴스형"}
        self.generation_action_status_label.setText(
            f"{tone_label_map.get(tone_key, tone_key)} 최종 프롬프트를 클립보드에 복사했습니다."
        )

    def _open_chatgpt_web(self) -> None:
        """반자동 마무리를 위해 ChatGPT 웹을 연다."""
        if self._generation_chatgpt_url:
            _ = QDesktopServices.openUrl(QUrl(self._generation_chatgpt_url))

    def _create_issue_table_item(
        self,
        value: str,
        *,
        tooltip: str = "",
        align_center: bool = False,
        emphasize: bool = False,
    ) -> QTableWidgetItem:
        """Top 이슈 표 셀에 맞는 공통 아이템을 만든다."""
        item = QTableWidgetItem(value)
        if tooltip:
            item.setToolTip(tooltip)
        if align_center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if emphasize:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        return item

    def _apply_category_palette_for_table(self, table: QTableWidget, row_index: int, category_key: str) -> None:
        """카테고리별 파스텔 톤을 행과 분류/점수 셀에 적용한다."""
        palette = _CATEGORY_PASTELS.get(category_key, _CATEGORY_PASTELS["default"])
        row_color = QColor(palette["row"])
        accent_color = QColor(palette["accent"])
        text_color = QColor(palette["text"])

        for column_index in range(table.columnCount()):
            item = table.item(row_index, column_index)
            if item is None:
                continue
            item.setBackground(row_color)

        for column_index in (3,):
            item = table.item(row_index, column_index)
            if item is None:
                continue
            item.setBackground(accent_color)
            item.setForeground(text_color)

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        """동적 섹션 재구성을 위해 기존 레이아웃 자식을 비운다."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            child_layout = cast(object, item.layout())
            if widget is not None:
                widget.deleteLater()
                continue
            if child_layout is None:
                continue
            self._clear_layout(cast(QVBoxLayout | QHBoxLayout, child_layout))

    def _adjust_issue_table_height(self, table: QTableWidget, row_count: int) -> None:
        """5행 이하 표가 과도하게 늘어나지 않도록 높이를 고정한다."""
        visible_rows = max(row_count, 1)
        table_height = table.horizontalHeader().height() + (visible_rows * 38) + 14
        table.setMinimumHeight(table_height)
        table.setMaximumHeight(table_height)

    def _apply_styles(self) -> None:
        """대시보드 전반의 가벼운 스타일을 적용한다."""
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f6f8;
                color: #1f2933;
            }
            QLabel#pageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #14213d;
            }
            QLabel#pageSubtitle,
            QLabel#sectionSubtitle,
            QLabel#settingsDescription,
            QLabel#fieldHelper {
                color: #5b6b79;
                font-size: 13px;
            }
            QLabel#sectionTitle,
            QLabel#settingsHeading {
                font-size: 18px;
                font-weight: 650;
                color: #1d3557;
            }
            QFrame#sectionFrame,
            QFrame#metricCard,
            QFrame#linkedStepChip {
                background: #ffffff;
                border: 1px solid #d8dee4;
                border-radius: 14px;
            }
            QLabel#metricCardTitle {
                color: #52606d;
                font-size: 12px;
            }
            QLabel#metricCardValue {
                color: #102a43;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#metricCardDetail {
                color: #5b6b79;
                font-size: 13px;
            }
            QLabel#linkedStepName {
                color: #243b53;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#linkedStepDetail,
            QLabel#linkedStepArrow {
                color: #627d98;
                font-size: 13px;
            }
            QLabel#linkedStepDot[healthy="true"] {
                color: #2f855a;
                font-size: 16px;
            }
            QLabel#linkedStepDot[healthy="false"] {
                color: #c05621;
                font-size: 16px;
            }
            QPushButton#primaryButton {
                background: #1d4ed8;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background: #1e40af;
            }
            QPushButton#secondaryButton {
                background: white;
                color: #1f2933;
                border: 1px solid #cbd2d9;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton#rowActionButton {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QPushButton#rowActionButton:hover {
                background: #dbeafe;
            }
            QPushButton#generationActionButton {
                background: #ffffff;
                color: #1f2933;
                border: 1px solid #cbd2d9;
                border-radius: 9px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QPushButton#generationActionButton:hover:enabled {
                background: #f8fafc;
                border-color: #9fb3c8;
            }
            QPushButton#generationChatgptButton {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 9px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QPushButton#generationChatgptButton:hover:enabled {
                background: #dbeafe;
            }
            QTableWidget,
            QListWidget,
            QLineEdit,
            QPlainTextEdit {
                background: white;
                border: 1px solid #d9e2ec;
                border-radius: 10px;
                padding: 6px;
                gridline-color: #e5e7eb;
            }
            QHeaderView::section {
                background: #eef2f6;
                color: #334e68;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #d9e2ec;
                font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #d8dee4;
                border-radius: 14px;
                background: #f8fafc;
                margin-top: 8px;
            }
            QTabBar::tab {
                background: white;
                color: #52606d;
                border: 1px solid #d8dee4;
                border-bottom: none;
                padding: 10px 18px;
                margin-right: 6px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QTabBar::tab:hover {
                background: #f8fafc;
                color: #243b53;
            }
            QTabBar::tab:selected {
                background: #d1d5db;
                color: #102a43;
            }
            QListWidget#logsList::item {
                padding: 6px 4px;
                border-bottom: 1px solid #eef2f6;
            }
            """
        )
