"""데스크톱 UI를 실행하는 실제 앱 진입점."""

from __future__ import annotations

from src.ui.app import launch_dashboard
from .app import DesktopApp


def main() -> int:
    """DesktopApp 런타임에 연결된 PySide6 대시보드를 실행한다."""
    return launch_dashboard(desktop_app=DesktopApp())


if __name__ == "__main__":
    raise SystemExit(main())
