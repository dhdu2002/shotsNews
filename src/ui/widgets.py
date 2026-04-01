# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false

"""대시보드에서 재사용하는 PySide6 위젯 모음."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QSizePolicy, QVBoxLayout, QWidget

from .models import LinkedStatusStep


def _clear_layout(layout: QLayout) -> None:
    """레이아웃 안의 기존 위젯과 하위 레이아웃을 모두 비운다."""
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


class SectionFrame(QFrame):
    """카드형 섹션 컨테이너를 만든다."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("sectionSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(12)
        layout.addLayout(self.body_layout)


class MetricCard(QFrame):
    """상단 요약 카드 공통 위젯이다."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("metricCardTitle")
        layout.addWidget(title_label)

        self.value_label = QLabel("-")
        self.value_label.setObjectName("metricCardValue")
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("metricCardDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

    def set_content(self, value: str, detail: str = "") -> None:
        """카드의 핵심 값과 보조 설명을 갱신한다."""
        self.value_label.setText(value)
        self.detail_label.setText(detail)


class LinkedStepChip(QFrame):
    """연결 상태 흐름에 표시하는 작은 상태 칩이다."""

    def __init__(self, step: LinkedStatusStep, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("linkedStepChip")
        self.setProperty("healthy", step.healthy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        label_row = QHBoxLayout()
        label_row.setSpacing(8)

        dot = QLabel("●")
        dot.setProperty("healthy", step.healthy)
        dot.setObjectName("linkedStepDot")
        label_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        name_label = QLabel(step.name)
        name_label.setObjectName("linkedStepName")
        label_row.addWidget(name_label)
        label_row.addStretch(1)
        layout.addLayout(label_row)

        detail_label = QLabel(step.detail)
        detail_label.setObjectName("linkedStepDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)


class LinkedStatusView(QWidget):
    """단순 연결 상태 흐름을 좌우로 보여주는 위젯이다."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_steps(self, steps: tuple[LinkedStatusStep, ...]) -> None:
        """현재 연결 상태 단계 목록을 화면에 반영한다."""
        _clear_layout(self._layout)

        for index, step in enumerate(steps):
            chip = LinkedStepChip(step)
            self._layout.addWidget(chip)

            if index < len(steps) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("linkedStepArrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._layout.addWidget(arrow)

        self._layout.addStretch(1)
