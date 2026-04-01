# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false

"""PySide6 데스크톱 셸 부트스트랩 함수 모음."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any

from PySide6.QtWidgets import QApplication

from .main_window import DashboardMainWindow
from .runtime_bridge import DashboardPresenter, DesktopAppAdapter
from .viewmodels import DashboardViewModel

def _create_desktop_app() -> Any:
    """실행 환경에 맞는 DesktopApp 인스턴스를 생성한다."""
    try:
        module = import_module("daily_issue_app")
    except ModuleNotFoundError:
        module = import_module("src.daily_issue_app")
    desktop_app_cls = getattr(module, "DesktopApp")
    return desktop_app_cls()


def create_application() -> QApplication:
    """Qt 애플리케이션 인스턴스를 만들거나 재사용한다."""
    application = QApplication.instance()
    if isinstance(application, QApplication):
        resolved = application
    else:
        resolved = QApplication(sys.argv)

    resolved.setApplicationName("데일리 이슈 데스크톱")
    resolved.setOrganizationName("Daily Issue")
    return resolved


def create_runtime_viewmodel(desktop_app: Any | None = None) -> DashboardViewModel:
    """실제 DesktopApp 런타임에 연결된 기본 뷰모델을 만든다."""
    return DashboardViewModel(
        runtime_adapter=DesktopAppAdapter(desktop_app or _create_desktop_app()),
        presenter=DashboardPresenter(),
    )


def create_main_window(
    viewmodel: DashboardViewModel | None = None,
    desktop_app: Any | None = None,
) -> DashboardMainWindow:
    """대시보드 메인 윈도우를 만든다."""
    resolved_viewmodel = viewmodel or create_runtime_viewmodel(desktop_app)
    return DashboardMainWindow(resolved_viewmodel)


def launch_dashboard(
    viewmodel: DashboardViewModel | None = None,
    desktop_app: Any | None = None,
) -> int:
    """실제 DesktopApp 런타임과 연결된 대시보드를 실행한다."""
    application = create_application()
    resolved_viewmodel = viewmodel or create_runtime_viewmodel(desktop_app)
    application.aboutToQuit.connect(resolved_viewmodel.shutdown)
    window = create_main_window(resolved_viewmodel, desktop_app)
    window.show()
    return application.exec()
