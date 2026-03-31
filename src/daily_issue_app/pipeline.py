"""UI와 분리된 일일 파이프라인 오케스트레이션."""

from __future__ import annotations

from datetime import date
from typing import Any

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

    def run_for_date(self, run_date: date) -> dict[str, Any]:
        """수집→랭킹→저장→스크립트→동기화를 순차 수행한다."""
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
            collected = self._collect.execute(request)
            ranked = self._rank.execute(collected)
            persisted = self._persist.execute(request, ranked)
            self._generate_scripts.execute(persisted)
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

            return {
                "run_id": run_id,
                "collected_count": len(collected.candidates),
                "ranked_count": len(ranked.ranked_issues),
                "persisted_count": len(persisted.records),
                "synced_count": len(sync_result.synced_issue_ids),
                "failure_count": len(failures),
            }
        except Exception:
            failures = []
            if hasattr(self._context.collector, "drain_failures"):
                failures = self._context.collector.drain_failures()
            self._context.repository.fail_pipeline_run(run_id, failure_count=max(1, len(failures)))
            raise
