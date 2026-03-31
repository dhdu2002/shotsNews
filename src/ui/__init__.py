# pyright: reportUnknownVariableType=false

"""데일리 이슈 데스크톱용 PySide6 UI 패키지."""

from .app import create_application, create_main_window, create_runtime_viewmodel, launch_dashboard
from .models import DashboardState, SettingsState
from .runtime_bridge import DashboardPresenter, DesktopAppAdapter
from .viewmodels import DashboardViewModel, build_mock_dashboard_state, build_mock_settings_state

__all__ = [
    "DashboardPresenter",
    "DashboardState",
    "DashboardViewModel",
    "DesktopAppAdapter",
    "SettingsState",
    "build_mock_dashboard_state",
    "build_mock_settings_state",
    "create_application",
    "create_main_window",
    "create_runtime_viewmodel",
    "launch_dashboard",
]
