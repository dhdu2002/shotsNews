"""Notion 동기화 어댑터."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...domain.models import PersistedIssue


class NotionSyncService:
    """자격정보가 없을 때도 안전하게 동작하는 Notion 동기화 서비스."""

    def __init__(self, database_id: str, notion_token: str, enabled: bool, timeout_seconds: int = 15) -> None:
        self._database_id = database_id
        self._notion_token = notion_token
        self._enabled = enabled or bool(database_id and notion_token)
        self._timeout_seconds = timeout_seconds

    def _is_ready(self) -> bool:
        return bool(self._enabled and self._database_id and self._notion_token)

    def is_ready(self) -> bool:
        """오케스트레이션에서 대기 큐 유지 판단에 사용한다."""
        return self._is_ready()

    def sync(self, issues: list[PersistedIssue]) -> list[str]:
        """Notion 페이지 생성 후 성공한 이슈 ID 목록을 반환한다."""
        if not self._is_ready():
            return []

        synced_issue_ids: list[str] = []
        for issue in issues:
            payload = {
                "parent": {"database_id": self._database_id},
                "properties": {
                    "Title": {"title": [{"text": {"content": issue.title[:200]}}]},
                    "Rank": {"number": issue.rank},
                    "Category": {"rich_text": [{"text": {"content": issue.category.value}}]},
                    "SourceURL": {"url": issue.source_url},
                    "IssueId": {"rich_text": [{"text": {"content": issue.issue_id}}]},
                },
            }
            request = Request(
                url="https://api.notion.com/v1/pages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self._notion_token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self._timeout_seconds):
                    synced_issue_ids.append(issue.issue_id)
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue

        return synced_issue_ids
