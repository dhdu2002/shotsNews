"""APScheduler 기반 실행 스케줄러 서비스."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any


class SchedulerService:
    """UI 계층이 APScheduler 구현 세부를 몰라도 되도록 감싼다."""

    def __init__(self, timezone: str) -> None:
        scheduler_module = import_module("apscheduler.schedulers.background")
        scheduler_class = getattr(scheduler_module, "BackgroundScheduler")
        self._scheduler: Any = scheduler_class(timezone=timezone)
        self._interval_job_id = "mvp-interval-job"

    def register_interval_job(self, fn: Callable[[], None], interval_minutes: int) -> None:
        """분 단위 주기 작업을 등록/교체한다."""
        self._scheduler.add_job(
            fn,
            trigger="interval",
            minutes=max(1, interval_minutes),
            id=self._interval_job_id,
            replace_existing=True,
        )

    def register_daily_job(self, job_id: str, fn: Callable[[], None], hour: int = 8) -> None:
        """일 단위 크론 작업을 등록/교체한다."""
        self._scheduler.add_job(
            fn,
            trigger="cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def start(self) -> None:
        """백그라운드 스케줄러를 시작한다."""
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        """백그라운드 스케줄러를 안전하게 종료한다."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
