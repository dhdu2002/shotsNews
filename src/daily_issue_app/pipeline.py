"""UI와 분리된 일일 파이프라인 오케스트레이션."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .application.dto import DailyPipelineRequest
from .application.usecases.collect_daily_issues import CollectDailyIssuesUseCase
from .application.usecases.generate_scripts import GenerateScriptsUseCase
from .application.usecases.persist_ranked_issues import PersistRankedIssuesUseCase
from .application.usecases.rank_top_issues import RankTopIssuesUseCase
from .application.usecases.sync_to_notion import SyncToNotionUseCase
from .domain.enums import IssueCategory


class DailyIssuePipeline:
    """하루 1회 파이프라인 전체 단계를 조정한다."""

    def __init__(self, context: Any) -> None:
        self._context = context
        self._collect = CollectDailyIssuesUseCase(context.collector)
        self._rank = RankTopIssuesUseCase(context.ranking_service)
        self._persist = PersistRankedIssuesUseCase(context.repository)
        self._generate_scripts = GenerateScriptsUseCase(context.script_generator, context.repository)
        self._sync = SyncToNotionUseCase(context.repository, context.notion_sync)

    def run_for_date(
        self,
        run_date: date,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """수집→랭킹→저장→스크립트→동기화를 순차 수행한다."""
        self._emit_progress(progress_callback, 5, "실행 준비 중")
        run_id = self._context.repository.create_pipeline_run(run_date)
        request = DailyPipelineRequest(
            run_date=run_date,
            categories=(
                IssueCategory.AI_TECH,
                IssueCategory.ECONOMY,
                IssueCategory.SOCIETY,
                IssueCategory.HEALTH,
                IssueCategory.ENTERTAINMENT_TREND,
            ),
        )
        try:
            self._emit_progress(progress_callback, 15, "이슈 수집 중")
            collected = self._collect.execute(request)
            self._emit_progress(progress_callback, 35, "이슈 랭킹 계산 중")
            ranked = self._rank.execute(collected)
            self._emit_progress(progress_callback, 55, "선정 이슈 저장 중")
            persisted = self._persist.execute(request, ranked)
            self._emit_progress(progress_callback, 75, "대본 생성 중")
            self._generate_scripts.execute(persisted)
            self._emit_progress(progress_callback, 90, "Notion 동기화 중")
            sync_result = self._sync.execute(request)

            failures = []
            if hasattr(self._context.collector, "drain_failures"):
                failures = self._context.collector.drain_failures()
                for failure in failures:
                    self._context.repository.append_source_failure(run_id, failure.source_name, failure.message)

            self._context.repository.complete_pipeline_run(
                run_id,
                collected_count=len(collected.candidates),
                ranked_count=len(ranked.ranked_issues),
                script_count=len(persisted.records) * 3,
                queued_sync_count=len(sync_result.synced_issue_ids),
                failure_count=len(failures),
            )

            self._emit_progress(progress_callback, 100, "실행 완료")

            return {
                "run_id": run_id,
                "collected_count": len(collected.candidates),
                "ranked_count": len(ranked.ranked_issues),
                "persisted_count": len(persisted.records),
                "synced_count": len(sync_result.synced_issue_ids),
                "failure_count": len(failures),
            }
        except Exception:
            self._emit_progress(progress_callback, 100, "실행 실패")
            failures = []
            if hasattr(self._context.collector, "drain_failures"):
                failures = self._context.collector.drain_failures()
            self._context.repository.fail_pipeline_run(run_id, failure_count=max(1, len(failures)))
            raise

    @staticmethod
    def _emit_progress(
        progress_callback: Callable[[int, str], None] | None,
        value: int,
        message: str,
    ) -> None:
        """UI에서 사용할 단계형 진행률을 보고한다."""
        if progress_callback is not None:
            progress_callback(value, message)
