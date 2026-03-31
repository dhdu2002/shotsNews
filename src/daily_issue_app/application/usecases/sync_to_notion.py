"""유스케이스: 로컬 저장 이슈를 Notion으로 동기화."""

from __future__ import annotations

from ..dto import DailyPipelineRequest, SyncResult
from ...domain.interfaces import IssueRepositoryPort, NotionSyncPort


class SyncToNotionUseCase:
    """대기 이슈를 동기화하고 로컬 상태를 갱신한다."""

    def __init__(self, repository: IssueRepositoryPort, notion_sync: NotionSyncPort) -> None:
        self._repository = repository
        self._notion_sync = notion_sync

    def execute(self, request: DailyPipelineRequest) -> SyncResult:
        """대상 날짜의 Notion 동기화를 수행한다."""
        pending = self._repository.list_pending_sync(request.run_date)
        if not self._notion_sync.is_ready():
            return SyncResult(synced_issue_ids=[])

        synced_issue_ids = self._notion_sync.sync(pending)
        failed_issue_ids = [item.issue_id for item in pending if item.issue_id not in set(synced_issue_ids)]
        if synced_issue_ids:
            self._repository.mark_synced(synced_issue_ids)
        if failed_issue_ids:
            self._repository.mark_sync_failed(failed_issue_ids, "notion sync deferred or failed")
        return SyncResult(synced_issue_ids=synced_issue_ids)
