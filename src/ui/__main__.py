# pyright: reportUnknownVariableType=false

"""PySide6 대시보드를 모듈로 실행하는 진입점."""

from .app import launch_dashboard


if __name__ == "__main__":
    raise SystemExit(launch_dashboard())
