"""데스크톱 UI를 실행하는 실제 앱 진입점."""

from __future__ import annotations

from importlib import import_module
from typing import Callable

from .app import DesktopApp


def _load_launch_dashboard() -> Callable[..., int]:
    """실행 환경에 맞는 대시보드 진입 함수를 불러온다."""
    try:
        module = import_module("ui.app")
    except ModuleNotFoundError:
        module = import_module("src.ui.app")
    return getattr(module, "launch_dashboard")


def main() -> int:
    """DesktopApp 런타임에 연결된 PySide6 대시보드를 실행한다."""
    return _load_launch_dashboard()(desktop_app=DesktopApp())


if __name__ == "__main__":
    raise SystemExit(main())
