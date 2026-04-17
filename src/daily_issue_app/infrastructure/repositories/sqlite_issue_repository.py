"""이슈/스크립트/런/동기화큐를 관리하는 SQLite 리포지토리."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ...domain.enums import IssueCategory, RecordSyncStatus, ScriptTone
from ...domain.models import IssueScriptSet, PersistedIssue, RankedIssue, ShortFormScoreBreakdown
from ..db.sqlite import connect_sqlite


class SqliteIssueRepository:
    """도메인 저장 포트를 SQLite로 구현한다."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path: Path = Path(db_path)

    def save_ranked_issues(self, run_date: date, issues: list[RankedIssue]) -> list[PersistedIssue]:
        """랭킹 이슈를 저장하고 PersistedIssue 목록을 반환한다."""
        persisted: list[PersistedIssue] = []
        with connect_sqlite(self._db_path) as conn:
            _ = conn.execute("DELETE FROM issues WHERE run_date = ?", (run_date.isoformat(),))
            for item in issues:
                issue_id = str(uuid4())
                _ = conn.execute(
                    """
                    INSERT INTO issues(
                        issue_id, run_date, rank, category, title,
                        score, score_breakdown_json, key_points_json, source_url, sync_status, region
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        issue_id,
                        run_date.isoformat(),
                        item.rank,
                        item.category.value,
                        item.title,
                        item.score,
                        self._serialize_score_breakdown(item.score_breakdown),
                        json.dumps(item.key_points, ensure_ascii=False),
                        item.source_url,
                        RecordSyncStatus.PENDING.value,
                        item.region,
                    ),
                )
                _ = conn.execute(
                    """
                    INSERT INTO notion_sync_queue(issue_id, run_date, status)
                    VALUES (?, ?, ?)
                    """,
                    (issue_id, run_date.isoformat(), RecordSyncStatus.PENDING.value),
                )
                persisted.append(
                    PersistedIssue(
                        issue_id=issue_id,
                        run_date=run_date.isoformat(),
                        rank=item.rank,
                        category=item.category,
                        title=item.title,
                        key_points=item.key_points,
                        source_url=item.source_url,
                        score=item.score,
                        score_breakdown=item.score_breakdown,
                        sync_status=RecordSyncStatus.PENDING,
                        region=item.region,
                    )
                )
            conn.commit()
        return persisted

    def save_scripts(self, scripts: list[IssueScriptSet]) -> None:
        """이슈/톤 기준으로 생성 스크립트를 저장한다."""
        with connect_sqlite(self._db_path) as conn:
            for script_set in scripts:
                for tone, script_text in script_set.scripts_by_tone.items():
                    _ = conn.execute(
                        """
                        INSERT INTO issue_scripts(issue_id, tone, script_text)
                        VALUES (?, ?, ?)
                        ON CONFLICT(issue_id, tone) DO UPDATE SET
                            script_text=excluded.script_text
                        """,
                        (script_set.issue_id, tone.value, script_text),
                    )
            conn.commit()

    def list_pending_sync(self, run_date: date) -> list[PersistedIssue]:
        """실행일 기준 동기화 대기/실패 이슈를 조회한다."""
        with connect_sqlite(self._db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                """
                SELECT issue_id, run_date, rank, category, title,
                       score, score_breakdown_json, key_points_json, source_url, sync_status
                FROM issues
                WHERE issue_id IN (
                    SELECT issue_id
                    FROM notion_sync_queue
                    WHERE run_date = ? AND status IN (?, ?)
                )
                ORDER BY rank ASC
                """,
                (
                    run_date.isoformat(),
                    RecordSyncStatus.PENDING.value,
                    RecordSyncStatus.FAILED.value,
                ),
                ).fetchall(),
            )

        return [
            PersistedIssue(
                issue_id=str(row["issue_id"]),
                run_date=str(row["run_date"]),
                rank=int(row["rank"]),
                category=IssueCategory(str(row["category"])),
                title=str(row["title"]),
                key_points=self._deserialize_key_points(row["key_points_json"]),
                source_url=str(row["source_url"]),
                score=float(row["score"] or 0.0),
                score_breakdown=self._deserialize_score_breakdown(row["score_breakdown_json"]),
                sync_status=RecordSyncStatus(str(row["sync_status"])),
            )
            for row in rows
        ]

    def mark_synced(self, issue_ids: list[str]) -> None:
        """Notion 성공 건을 동기화 완료로 표시한다."""
        if not issue_ids:
            return

        with connect_sqlite(self._db_path) as conn:
            _ = conn.executemany(
                """
                UPDATE issues
                SET sync_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE issue_id = ?
                """,
                [(RecordSyncStatus.SYNCED.value, issue_id) for issue_id in issue_ids],
            )
            _ = conn.executemany(
                """
                UPDATE notion_sync_queue
                SET status = ?, attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
                WHERE issue_id = ?
                """,
                [(RecordSyncStatus.SYNCED.value, issue_id) for issue_id in issue_ids],
            )
            conn.commit()

    def mark_sync_failed(self, issue_ids: list[str], error: str) -> None:
        """선택한 이슈의 동기화 실패 상태와 오류를 기록한다."""
        if not issue_ids:
            return
        with connect_sqlite(self._db_path) as conn:
            _ = conn.executemany(
                """
                UPDATE issues
                SET sync_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE issue_id = ?
                """,
                [(RecordSyncStatus.FAILED.value, issue_id) for issue_id in issue_ids],
            )
            _ = conn.executemany(
                """
                UPDATE notion_sync_queue
                SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE issue_id = ?
                """,
                [(RecordSyncStatus.FAILED.value, error[:300], issue_id) for issue_id in issue_ids],
            )
            conn.commit()

    def create_pipeline_run(self, run_date: date) -> str:
        """파이프라인 1회 실행(run) 레코드를 생성한다."""
        run_id = str(uuid4())
        with connect_sqlite(self._db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO pipeline_runs(run_id, run_date, status)
                VALUES (?, ?, ?)
                """,
                (run_id, run_date.isoformat(), "running"),
            )
            conn.commit()
        return run_id

    def complete_pipeline_run(
        self,
        run_id: str,
        collected_count: int,
        ranked_count: int,
        script_count: int,
        queued_sync_count: int,
        failure_count: int,
    ) -> None:
        """파이프라인 실행 결과 지표를 완료 상태로 확정한다."""
        with connect_sqlite(self._db_path) as conn:
            _ = conn.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = CURRENT_TIMESTAMP,
                    status = ?,
                    collected_count = ?,
                    ranked_count = ?,
                    script_count = ?,
                    queued_sync_count = ?,
                    failure_count = ?
                WHERE run_id = ?
                """,
                ("completed", collected_count, ranked_count, script_count, queued_sync_count, failure_count, run_id),
            )
            conn.commit()

    def fail_pipeline_run(self, run_id: str, failure_count: int) -> None:
        """파이프라인 실행을 실패 상태로 마감한다."""
        with connect_sqlite(self._db_path) as conn:
            _ = conn.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = CURRENT_TIMESTAMP,
                    status = ?,
                    failure_count = ?
                WHERE run_id = ?
                """,
                ("failed", failure_count, run_id),
            )
            conn.commit()

    def append_source_failure(self, run_id: str, source_name: str, message: str) -> None:
        """소스 실패 1건을 저장한다."""
        with connect_sqlite(self._db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO source_failures(run_id, source_name, message)
                VALUES (?, ?, ?)
                """,
                (run_id, source_name, message[:300]),
            )
            conn.commit()

    def get_latest_run_summary(self) -> dict[str, str | int] | None:
        """가장 최근 실행 요약 레코드를 반환한다."""
        with connect_sqlite(self._db_path) as conn:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone(),
            )
        if row is None:
            return None
        return {
            "run_id": str(row["run_id"]),
            "run_date": str(row["run_date"]),
            "started_at": str(row["started_at"]),
            "finished_at": str(row["finished_at"]) if row["finished_at"] is not None else "",
            "status": str(row["status"]),
            "collected_count": int(row["collected_count"]),
            "ranked_count": int(row["ranked_count"]),
            "script_count": int(row["script_count"]),
            "queued_sync_count": int(row["queued_sync_count"]),
            "failure_count": int(row["failure_count"]),
        }

    def list_ranked_issue_summaries(self, run_date: date, limit: int = 5) -> list[dict[str, Any]]:
        """지정한 날짜의 상위 이슈 요약 목록을 반환한다."""
        with connect_sqlite(self._db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                """
                SELECT rank, title, category, source_url, sync_status
                       , score, score_breakdown_json
                       , COALESCE(region, 'international') as region
                FROM issues
                WHERE run_date = ?
                ORDER BY region ASC, rank ASC
                LIMIT ?
                """,
                (run_date.isoformat(), limit),
                ).fetchall(),
            )

        return [
            {
                "rank": row["rank"],
                "title": str(row["title"]),
                "category": str(row["category"]),
                "source_url": str(row["source_url"]),
                "sync_status": str(row["sync_status"]),
                "score": float(row["score"] or 0.0),
                "score_breakdown": self._deserialize_score_breakdown(row["score_breakdown_json"]).to_dict(),
                "region": str(row["region"]),
            }
            for row in rows
        ]

    @staticmethod
    def _serialize_score_breakdown(score_breakdown: ShortFormScoreBreakdown | None) -> str:
        """점수 세부항목을 안전한 JSON 문자열로 저장한다."""
        if score_breakdown is None:
            return "{}"
        return json.dumps(score_breakdown.to_dict(), ensure_ascii=False)

    @staticmethod
    def _deserialize_score_breakdown(payload: object) -> ShortFormScoreBreakdown:
        """비어 있거나 손상된 저장값도 기본 점수 구조로 복원한다."""
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                return ShortFormScoreBreakdown()
            if isinstance(parsed, dict):
                return ShortFormScoreBreakdown.from_dict(cast(dict[str, object], parsed))
            return ShortFormScoreBreakdown()
        if isinstance(payload, dict):
            return ShortFormScoreBreakdown.from_dict(cast(dict[str, object], payload))
        return ShortFormScoreBreakdown()

    @staticmethod
    def _deserialize_key_points(payload: object) -> list[str]:
        """저장된 핵심 포인트 JSON을 문자열 목록으로 복원한다."""
        if not isinstance(payload, str):
            return []
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    def list_source_failures_for_run(self, run_id: str) -> list[dict[str, str]]:
        """실행 단위로 기록된 소스 실패 목록을 반환한다."""
        with connect_sqlite(self._db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                """
                SELECT source_name, message, created_at
                FROM source_failures
                WHERE run_id = ?
                ORDER BY created_at DESC, failure_id DESC
                """,
                (run_id,),
                ).fetchall(),
            )

        return [
            {
                "source_name": row["source_name"],
                "message": row["message"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_scripts_for_issue(self, issue_id: str) -> dict[ScriptTone, str]:
        """이슈 ID 기준 스크립트를 톤 키로 반환한다."""
        with connect_sqlite(self._db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                "SELECT tone, script_text FROM issue_scripts WHERE issue_id = ?",
                (issue_id,),
                ).fetchall(),
            )

        return {ScriptTone(str(row["tone"])): str(row["script_text"]) for row in rows}
