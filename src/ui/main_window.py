# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false

"""PySide6 메인 윈도우와 대시보드 화면 구성."""

from __future__ import annotations

from PySide6.QtCore import Qt
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
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .models import DashboardState, SettingsState
from .viewmodels import DashboardViewModel
from .widgets import LinkedStatusView, MetricCard, SectionFrame


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
        dashboard_layout.addLayout(cards_row)

        linked_section = SectionFrame(
            "연결 상태",
            "소스 수집 → 오늘의 Top 5 → Notion 동기화 흐름을 단순하게 보여줍니다.",
        )
        self.linked_status_view = LinkedStatusView()
        linked_section.body_layout.addWidget(self.linked_status_view)
        dashboard_layout.addWidget(linked_section)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setChildrenCollapsible(False)

        source_section = SectionFrame(
            "수집원 상태",
            "각 수집원의 연결 여부와 최근 확인 결과를 빠르게 파악합니다.",
        )
        self.source_table = QTableWidget(0, 5)
        self.source_table.setHorizontalHeaderLabels(["수집원", "상태", "최근 확인", "확인 필요", "메모"])
        self._prepare_table(self.source_table)
        source_section.body_layout.addWidget(self.source_table)
        top_splitter.addWidget(source_section)

        issues_section = SectionFrame(
            "오늘의 Top 5",
            "가장 최근 실행에서 선정된 상위 이슈를 간단하게 확인합니다.",
        )
        self.issues_table = QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels(["순위", "이슈", "출처", "분류", "상태"])
        self._prepare_table(self.issues_table)
        issues_section.body_layout.addWidget(self.issues_table)
        top_splitter.addWidget(issues_section)
        top_splitter.setSizes([640, 560])
        dashboard_layout.addWidget(top_splitter, 3)

        logs_section = SectionFrame(
            "최근 로그",
            "수동 실행, 새로고침, 최근 런타임 요약을 운영자 관점에서 보여줍니다.",
        )
        self.logs_list = QListWidget()
        self.logs_list.setObjectName("logsList")
        logs_section.body_layout.addWidget(self.logs_list)
        dashboard_layout.addWidget(logs_section, 2)

        self.tab_widget.addTab(self.dashboard_page, "대시보드")

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
        settings_layout.addWidget(settings_section)
        settings_layout.addStretch(1)

        self.tab_widget.addTab(self.settings_page, "설정")

        self.setCentralWidget(root)
        self._apply_styles()

    def _connect_signals(self) -> None:
        """버튼과 뷰모델 시그널을 연결한다."""
        self.run_button.clicked.connect(self.viewmodel.request_run)
        self.refresh_button.clicked.connect(self.viewmodel.request_refresh)
        self.settings_button.clicked.connect(self.viewmodel.open_settings)
        self.viewmodel.settings_requested.connect(self._show_settings_tab)
        self.viewmodel.dashboard_state_changed.connect(self._render_dashboard_state)
        self.viewmodel.settings_state_changed.connect(self._render_settings_state)

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

        self.issues_table.setRowCount(len(state.top_issue_rows))
        for row_index, row in enumerate(state.top_issue_rows):
            values = [str(row.rank), row.title, row.source_name, row.severity, row.readiness]
            for column_index, value in enumerate(values):
                self.issues_table.setItem(row_index, column_index, QTableWidgetItem(value))

        self.logs_list.clear()
        for entry in state.log_entries:
            self.logs_list.addItem(QListWidgetItem(f"[{entry.timestamp}] {entry.level} · {entry.message}"))

    def _render_settings_state(self, state: SettingsState) -> None:
        """설정 탭을 최신 읽기 전용 상태로 다시 그린다."""
        self.settings_heading_label.setText(state.heading)
        self.settings_description_label.setText(state.description)

        while self.settings_form.rowCount():
            self.settings_form.removeRow(0)

        for field in state.fields:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)

            line_edit = QLineEdit(field.value)
            line_edit.setReadOnly(True)
            container_layout.addWidget(line_edit)

            helper_label = QLabel(field.helper_text)
            helper_label.setObjectName("fieldHelper")
            helper_label.setWordWrap(True)
            container_layout.addWidget(helper_label)

            self.settings_form.addRow(field.label, container)

    def _show_settings_tab(self) -> None:
        """설정 탭으로 전환한다."""
        self.tab_widget.setCurrentWidget(self.settings_page)

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
            QTableWidget,
            QListWidget,
            QLineEdit {
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
                background: #e9eef5;
                color: #52606d;
                padding: 10px 18px;
                margin-right: 6px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #102a43;
            }
            QListWidget#logsList::item {
                padding: 6px 4px;
                border-bottom: 1px solid #eef2f6;
            }
            """
        )
