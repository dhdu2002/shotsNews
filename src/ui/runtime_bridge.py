# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportExplicitAny=false, reportUnusedVariable=false

"""DesktopApp 런타임을 UI 상태로 변환하는 어댑터와 프리젠터."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from importlib import import_module
import json
from typing import Any
from urllib.parse import quote_plus
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import DashboardState, LinkedStatusStep, LogEntry, SettingsField, SettingsState, SourceStatusRow, TopIssueRow

_SOURCE_LABELS = {
    "rss": "RSS",
    "youtube": "YouTube",
    "reddit": "Reddit",
    "twitter_x": "X / Twitter",
}

_CATEGORY_LABELS = {
    "ai_tech": "AI/테크",
    "economy": "경제",
    "society": "사회",
    "health": "건강",
    "entertainment_trend": "연예/트렌드",
}

_SCORE_BREAKDOWN_LABELS = {
    "impact": "파급력",
    "timeliness": "시의성",
    "freshness": "신선도",
    "novelty": "신선도",
    "shareability": "확산성",
    "trend": "트렌드성",
    "relevance": "관련성",
    "fit": "숏폼 적합도",
    "short_form_fit": "숏폼 적합도",
    "clarity": "명확성",
    "source": "출처 신뢰도",
    "credibility": "출처 신뢰도",
}

_SYNC_LABELS = {
    "pending": "대기",
    "synced": "완료",
    "failed": "실패",
}

_TITLE_TRANSLATION_CACHE: dict[str, str] = {}


def _create_desktop_app() -> Any:
    """실행 환경에 맞는 DesktopApp 인스턴스를 생성한다."""
    try:
        module = import_module("daily_issue_app")
    except ModuleNotFoundError:
        module = import_module("src.daily_issue_app")
    desktop_app_cls = getattr(module, "DesktopApp")
    return desktop_app_cls()


@dataclass(slots=True)
class DesktopAppAdapter:
    """UI가 DesktopApp을 안전하게 호출하도록 감싸는 얇은 어댑터."""

    desktop_app: Any = field(default_factory=_create_desktop_app)

    def load_status(self) -> dict[str, Any]:
        """런타임을 시작한 뒤 최신 상태 스냅샷을 반환한다."""
        self.desktop_app.start()
        return self.desktop_app.status()

    def run_now(self, progress_callback: Any = None) -> dict[str, Any]:
        """수동 실행을 시작하고 요약 결과를 반환한다."""
        self.desktop_app.start()
        return self.desktop_app.run_now(progress_callback=progress_callback)

    def stop(self) -> None:
        """앱 종료 시 런타임을 정리한다."""
        self.desktop_app.stop()

    def save_settings(self, values: dict[str, str]) -> str:
        """설정값을 저장하고 런타임을 재적용한다."""
        return self.desktop_app.save_settings(values)


class DashboardPresenter:
    """DesktopApp 상태 딕셔너리를 화면용 상태 객체로 변환한다."""

    def present_dashboard(
        self,
        runtime_status: dict[str, Any],
        interaction_logs: tuple[LogEntry, ...] = (),
    ) -> DashboardState:
        """런타임 상태를 대시보드 상태로 변환한다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        sources = runtime_status.get("sources") or []
        top_issues = runtime_status.get("top_issues") or []

        overall_status, overall_detail = self._present_overall_status(latest_run, source_failures)
        linked_steps = self._build_linked_steps(runtime_status)
        source_rows = self._build_source_rows(sources, source_failures, latest_run)
        top_issue_rows = self._build_top_issue_rows(top_issues)
        runtime_logs = self._build_runtime_logs(runtime_status)
        logs = tuple([*interaction_logs, *runtime_logs][:8])

        return DashboardState(
            window_title="데일리 이슈 데스크톱",
            dashboard_title="운영 대시보드",
            dashboard_subtitle="오늘의 수집 상태와 Top 5, Notion 대기 현황을 간단하게 확인합니다.",
            overall_status=overall_status,
            overall_detail=overall_detail,
            next_run_label=self._build_next_run_label(runtime_status),
            last_run_label=self._build_last_run_label(latest_run),
            notion_sync_status=self._build_notion_status(runtime_status),
            notion_sync_detail=self._build_notion_detail(runtime_status),
            linked_steps=linked_steps,
            source_rows=source_rows,
            top_issue_rows=top_issue_rows,
            log_entries=logs,
        )

    def present_settings(self, runtime_status: dict[str, Any]) -> SettingsState:
        """런타임 상태를 설정 탭의 편집 가능 정보로 변환한다."""
        interval_minutes = int(runtime_status.get("scheduler_interval_minutes") or 0)
        notion_enabled = bool(runtime_status.get("notion_enabled"))

        return SettingsState(
            heading="런타임 연결 정보",
            description=(
                "현재 데스크톱 셸이 읽어 온 런타임 구성입니다. "
                "수정 후 저장하면 `config/app.env`에 반영되고 런타임을 다시 불러옵니다."
            ),
            fields=(
                SettingsField(
                    "APP_NAME",
                    "앱 이름",
                    str(runtime_status.get("app_name") or "DailyIssueDesktop"),
                    "DesktopApp 시작 시 로드된 런타임 이름입니다.",
                ),
                SettingsField(
                    "APP_SCHEDULER_INTERVAL_MINUTES",
                    "실행 주기",
                    str(interval_minutes or 60),
                    "백그라운드 스케줄러가 이 분 단위로 파이프라인을 반복합니다.",
                ),
                SettingsField(
                    "APP_RSS_URLS",
                    "RSS 피드",
                    str(runtime_status.get("rss_urls") or ""),
                    "쉼표(,)로 구분된 RSS 피드 주소 목록입니다.",
                ),
                SettingsField(
                    "APP_YOUTUBE_FEED_URLS",
                    "YouTube 피드",
                    str(runtime_status.get("youtube_feed_urls") or ""),
                    "쉼표(,)로 구분된 YouTube 채널 피드 주소 목록입니다.",
                ),
                SettingsField(
                    "APP_REDDIT_SUBREDDITS",
                    "Reddit 서브레딧",
                    str(runtime_status.get("reddit_subreddits") or ""),
                    "쉼표(,)로 구분된 subreddit 이름 목록입니다.",
                ),
                SettingsField(
                    "TWITTER_QUERY",
                    "X 검색어",
                    str(runtime_status.get("twitter_query") or ""),
                    "X / Twitter 수집 시 사용할 검색어입니다.",
                ),
                SettingsField(
                    "NOTION_ENABLED",
                    "Notion 연동",
                    "true" if notion_enabled else "false",
                    "true 또는 false 로 입력합니다.",
                ),
                SettingsField(
                    "NOTION_DATABASE_ID",
                    "Notion DB ID",
                    str(runtime_status.get("notion_database_id") or ""),
                    "결과를 저장할 Notion 데이터베이스 ID입니다.",
                    secret=True,
                ),
                SettingsField(
                    "NOTION_TOKEN",
                    "Notion 토큰",
                    str(runtime_status.get("notion_token_masked") or ""),
                    "실제 저장 시 별표만 입력된 값은 유지됩니다.",
                    secret=True,
                ),
                SettingsField(
                    "OPENAI_MODEL",
                    "스크립트 모델",
                    str(runtime_status.get("openai_model") or "gpt-4.1-mini"),
                    "OpenAI API에서 실제로 호출 가능한 모델명을 넣어야 합니다.",
                ),
                SettingsField(
                    "OPENAI_API_KEY",
                    "OpenAI API 키",
                    str(runtime_status.get("openai_api_key_masked") or ""),
                    "ChatGPT Plus 구독과 별개이며, OpenAI Platform API 키가 필요합니다.",
                    secret=True,
                ),
                SettingsField(
                    "TWITTER_BEARER_TOKEN",
                    "X Bearer 토큰",
                    str(runtime_status.get("twitter_bearer_token_masked") or ""),
                    "비어 있으면 X 수집은 비활성처럼 동작합니다.",
                    secret=True,
                ),
                SettingsField(
                    "SQLITE_PATH",
                    "SQLite 경로",
                    str(runtime_status.get("db_path") or ""),
                    "파이프라인 실행 결과와 동기화 대기 정보가 저장되는 위치입니다.",
                    editable=False,
                ),
                SettingsField(
                    "DATA_DIR",
                    "데이터 폴더",
                    str(runtime_status.get("data_dir") or ""),
                    "로그와 캐시를 포함한 로컬 런타임 작업 폴더입니다.",
                    editable=False,
                ),
                SettingsField(
                    "SOURCE_POOLS_JSON",
                    "카테고리별 소스 풀 파일",
                    str(runtime_status.get("source_pools_path") or ""),
                    str(
                        runtime_status.get("source_pool_summary")
                        or "파일이 없으면 공용 환경변수 소스를 그대로 사용합니다."
                    ),
                    editable=False,
                ),
            ),
        )

    def _present_overall_status(
        self,
        latest_run: dict[str, Any],
        source_failures: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """상단 상태 카드의 문구를 결정한다."""
        if not latest_run:
            return (
                "실행 대기",
                "런타임은 시작되었지만 아직 완료된 파이프라인 실행 기록이 없습니다.",
            )

        status = str(latest_run.get("status") or "")
        collected = int(latest_run.get("collected_count") or 0)
        ranked = int(latest_run.get("ranked_count") or 0)
        queued = int(latest_run.get("queued_sync_count") or 0)
        failure_count = int(latest_run.get("failure_count") or 0)

        if status == "failed":
            return (
                "실행 실패",
                f"최근 실행에서 실패가 발생했습니다. 수집 {collected}건, 실패 기록 {max(1, failure_count)}건입니다.",
            )
        if source_failures or failure_count:
            dedupe_summary = self._build_dedupe_summary(latest_run)
            detail = f"최근 실행은 완료되었지만 소스 경고 {max(len(source_failures), failure_count)}건이 남아 있습니다."
            if dedupe_summary:
                detail = f"{detail} {dedupe_summary}"
            return (
                "주의 필요",
                detail,
            )
        dedupe_summary = self._build_dedupe_summary(latest_run)
        detail = f"최근 실행에서 {collected}건 수집, {ranked}건 Top 이슈 선정, {queued}건 동기화 대기 상태입니다."
        if dedupe_summary:
            detail = f"{detail} {dedupe_summary}"
        return (
            "정상",
            detail,
        )

    def _build_linked_steps(self, runtime_status: dict[str, Any]) -> tuple[LinkedStatusStep, ...]:
        """단순 연결 상태 표시용 단계 목록을 만든다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        notion_enabled = bool(runtime_status.get("notion_enabled"))

        ranked_count = int(latest_run.get("ranked_count") or 0)
        pending_sync = int(queue.get("pending") or 0)
        dedupe_summary = self._build_dedupe_summary(latest_run)

        source_detail = "아직 실행 기록이 없습니다."
        if latest_run:
            source_detail = f"최근 실행 기준 경고 {len(source_failures)}건"
            if dedupe_summary:
                source_detail = f"{source_detail} · {dedupe_summary}"

        notion_detail = "Notion 연동이 꺼져 있습니다."
        notion_healthy = True
        if notion_enabled:
            notion_detail = f"대기 {pending_sync}건"
            notion_healthy = pending_sync == 0

        return (
            LinkedStatusStep("소스 수집", source_detail, healthy=not source_failures),
            LinkedStatusStep(
                "오늘의 Top 5",
                f"선정 {ranked_count}건" if ranked_count else "아직 선정 결과가 없습니다.",
                healthy=ranked_count > 0,
            ),
            LinkedStatusStep("Notion 동기화", notion_detail, healthy=notion_healthy),
        )

    def _build_source_rows(
        self,
        sources: list[dict[str, Any]],
        source_failures: list[dict[str, Any]],
        latest_run: dict[str, Any],
    ) -> tuple[SourceStatusRow, ...]:
        """수집원 상태 표를 구성한다."""
        failure_by_name = {str(item.get("source_name")): item for item in source_failures}
        checked_label = self._build_last_run_label(latest_run)
        rows: list[SourceStatusRow] = []

        for source in sources:
            source_name = str(source.get("name") or "")
            configured = bool(source.get("configured"))
            configured_count = int(source.get("configured_count") or 0)
            note = str(source.get("note") or "")
            failure = failure_by_name.get(source_name)

            if not configured:
                rows.append(
                    SourceStatusRow(
                        source_name=_SOURCE_LABELS.get(source_name, source_name),
                        health="미설정",
                        last_checked="아직 없음",
                        pending_items=0,
                        note=note,
                    )
                )
                continue

            if failure is not None:
                rows.append(
                    SourceStatusRow(
                        source_name=_SOURCE_LABELS.get(source_name, source_name),
                        health="주의",
                        last_checked=self._format_timestamp(str(failure.get("created_at") or "")),
                        pending_items=1,
                        note=str(failure.get("message") or "최근 실행에서 오류가 기록되었습니다."),
                    )
                )
                continue

            rows.append(
                SourceStatusRow(
                    source_name=_SOURCE_LABELS.get(source_name, source_name),
                    health="정상" if latest_run else "대기",
                    last_checked=checked_label,
                    pending_items=0,
                    note=f"연결 항목 {configured_count}개 · {note}",
                )
            )

        return tuple(rows)

    def _build_top_issue_rows(self, top_issues: list[dict[str, Any]]) -> tuple[TopIssueRow, ...]:
        """분류별 Top 5 표 데이터를 구성한다."""
        rows: list[TopIssueRow] = []
        for issue in top_issues:
            category = self._resolve_issue_category(issue)
            title = str(issue.get("title") or "제목 없음")
            source_url = self._resolve_issue_source_url(issue)
            score_label, score_tooltip = self._build_score_display(issue)
            rows.append(
                TopIssueRow(
                    rank=int(issue.get("rank") or 0),
                    title=title,
                    translated_title=self._translate_title(title),
                    source_name=self._build_issue_source_label(issue, source_url),
                    source_url=source_url,
                    category_key=category,
                    severity=self._label_for_category(category),
                    score=score_label,
                    readiness=_SYNC_LABELS.get(str(issue.get("sync_status") or ""), "대기"),
                    category_tooltip=self._build_category_tooltip(issue, category),
                    score_tooltip=score_tooltip,
                    status_tooltip=self._build_status_tooltip(issue),
                )
            )
        return tuple(rows)

    def _resolve_issue_category(self, issue: dict[str, Any]) -> str:
        """최종 분류 우선 규칙으로 카테고리 키를 고른다."""
        for key in ("final_category", "category", "initial_category"):
            value = str(issue.get(key) or "").strip()
            if value:
                return value
        return ""

    def _resolve_issue_source_url(self, issue: dict[str, Any]) -> str:
        """중복 정리 이후에도 대표 링크를 우선 열 수 있도록 URL 후보를 고른다."""
        for key in ("source_url", "canonical_source_url", "url"):
            value = str(issue.get(key) or "").strip()
            if value:
                return value
        return ""

    def _build_issue_source_label(self, issue: dict[str, Any], source_url: str) -> str:
        """명시적 출처명이 있으면 사용하고, 없으면 URL에서 짧은 이름을 만든다."""
        for key in ("source_name", "canonical_source_name"):
            value = str(issue.get(key) or "").strip()
            if value:
                return value
        return self._build_source_label_from_url(source_url)

    def _build_category_tooltip(self, issue: dict[str, Any], category: str) -> str:
        """최종/초기 분류와 중복 메타데이터를 분류 셀 툴팁으로 정리한다."""
        final_category = str(issue.get("final_category") or category or "").strip()
        initial_category = str(issue.get("initial_category") or "").strip()
        duplicate_count = self._to_int(issue.get("duplicate_count"))
        tooltip_lines = [f"분류: {self._label_for_category(category)}"]

        if final_category:
            tooltip_lines.append(f"최종 분류: {self._label_for_category(final_category)}")

        if initial_category and initial_category != final_category:
            tooltip_lines.append(f"초기 분류: {self._label_for_category(initial_category)}")

        if duplicate_count > 0:
            tooltip_lines.append(f"중복 묶음: {duplicate_count}건")

        if self._is_canonical_issue(issue):
            tooltip_lines.append("대표 이슈 기준으로 유지된 항목입니다.")

        return "\n".join(tooltip_lines)

    def _build_status_tooltip(self, issue: dict[str, Any]) -> str:
        """상태 셀 툴팁에 동기화/중복 관련 보조 정보를 붙인다."""
        sync_status = _SYNC_LABELS.get(str(issue.get("sync_status") or ""), "대기")
        duplicate_count = self._to_int(issue.get("duplicate_count"))
        tooltip_lines = [f"동기화 상태: {sync_status}"]

        if duplicate_count > 0:
            tooltip_lines.append(f"중복 정리된 관련 항목: {duplicate_count}건")

        if self._is_canonical_issue(issue):
            tooltip_lines.append("이 항목은 대표(canonical) 이슈입니다.")

        return "\n".join(tooltip_lines)

    def _build_score_display(self, issue: dict[str, Any]) -> tuple[str, str]:
        """숏폼 점수와 breakdown 툴팁을 UI 표시용으로 정리한다."""
        score_payload = issue.get("score")
        breakdown_payload = (
            issue.get("score_breakdown")
            or issue.get("score_details")
            or issue.get("score_detail")
            or issue.get("breakdown")
        )
        summary_payload = issue.get("score_summary")

        if isinstance(score_payload, dict):
            breakdown_payload = (
                breakdown_payload
                or score_payload.get("breakdown")
                or score_payload.get("details")
                or score_payload.get("components")
            )
            summary_payload = summary_payload or score_payload.get("summary")
            score_value = (
                score_payload.get("label")
                or score_payload.get("short_label")
                or score_payload.get("value")
                or score_payload.get("score")
                or score_payload.get("total")
            )
        else:
            score_value = score_payload

        score_label = self._format_score_value(score_value)
        tooltip_lines = [f"숏폼 점수: {score_label}"]

        if summary_payload:
            tooltip_lines.append(str(summary_payload))

        breakdown_lines = self._format_score_breakdown_lines(breakdown_payload)
        if breakdown_lines:
            tooltip_lines.append("")
            tooltip_lines.append("세부 점수")
            tooltip_lines.extend(breakdown_lines)

        return score_label, "\n".join(tooltip_lines)

    def _format_score_value(self, value: object) -> str:
        """점수 원본값을 표 셀에 맞는 짧은 문자열로 바꾼다."""
        if value is None or value == "":
            return "-"
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "-"
            try:
                return f"{float(stripped):.1f}점"
            except ValueError:
                return stripped
        if isinstance(value, (int, float)):
            return f"{float(value):.1f}점"
        return str(value)

    def _format_score_breakdown_lines(self, breakdown: object) -> list[str]:
        """런타임 breakdown payload를 툴팁 줄 목록으로 정리한다."""
        if isinstance(breakdown, dict):
            lines: list[str] = []
            for key, value in breakdown.items():
                if value in (None, ""):
                    continue
                label = _SCORE_BREAKDOWN_LABELS.get(str(key), self._prettify_breakdown_key(str(key)))
                lines.append(f"• {label}: {self._format_breakdown_value(value)}")
            return lines

        if isinstance(breakdown, list):
            lines = []
            for item in breakdown:
                if isinstance(item, dict):
                    label = str(item.get("label") or item.get("name") or item.get("key") or "항목")
                    value = item.get("value") or item.get("score") or item.get("total")
                    if value in (None, ""):
                        continue
                    lines.append(f"• {label}: {self._format_breakdown_value(value)}")
                    continue
                if item not in (None, ""):
                    lines.append(f"• {item}")
            return lines

        if breakdown in (None, ""):
            return []
        return [f"• {breakdown}"]

    def _format_breakdown_value(self, value: object) -> str:
        """breakdown 내부 값을 읽기 쉬운 짧은 텍스트로 바꾼다."""
        if isinstance(value, (int, float)):
            return f"{float(value):.1f}"
        return str(value)

    def _label_for_category(self, category: str) -> str:
        """UI 표시에 맞는 카테고리 라벨을 반환한다."""
        normalized = category.strip()
        if not normalized:
            return "미분류"
        return _CATEGORY_LABELS.get(normalized, normalized.replace("_", "/"))

    def _build_dedupe_summary(self, latest_run: dict[str, Any]) -> str:
        """실행 요약에 붙일 중복 정리 보조 문구를 만든다."""
        duplicate_count = self._to_int(
            latest_run.get("duplicate_count")
            or latest_run.get("deduped_count")
            or latest_run.get("duplicates_removed_count")
        )
        canonical_count = self._to_int(latest_run.get("canonical_count"))
        summary_parts: list[str] = []

        if duplicate_count > 0:
            summary_parts.append(f"중복 정리 {duplicate_count}건")

        if canonical_count > 0:
            summary_parts.append(f"대표 이슈 {canonical_count}건")

        return " · ".join(summary_parts)

    def _is_canonical_issue(self, issue: dict[str, Any]) -> bool:
        """대표(canonical) 이슈 표식이 있으면 True를 반환한다."""
        return any(
            self._to_bool(issue.get(key))
            for key in ("is_canonical", "canonical", "canonical_marker")
        )

    @staticmethod
    def _to_bool(value: object) -> bool:
        """런타임 payload의 다양한 불리언 표현을 안전하게 해석한다."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    @staticmethod
    def _to_int(value: object) -> int:
        """문자열/실수로 들어온 카운트 값도 정수로 정규화한다."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0
            try:
                return int(float(stripped))
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _prettify_breakdown_key(value: str) -> str:
        """breakdown 키를 간단한 라벨 형태로 정리한다."""
        return value.replace("_", " ").strip().title()

    def _translate_title(self, title: str) -> str:
        """영문 제목은 간단히 한국어로 번역해 표시한다."""
        if not title:
            return "제목 없음"
        if title in _TITLE_TRANSLATION_CACHE:
            return _TITLE_TRANSLATION_CACHE[title]
        if self._looks_korean(title):
            _TITLE_TRANSLATION_CACHE[title] = title
            return title

        translated = title
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=auto&tl=ko&dt=t&q={quote_plus(title)}"
            )
            request = Request(url, headers={"User-Agent": "shotsNews/0.1"})
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0]).strip() or title
        except Exception:
            translated = title

        _TITLE_TRANSLATION_CACHE[title] = translated
        return translated

    @staticmethod
    def _looks_korean(value: str) -> bool:
        """문자열에 한글이 포함되어 있는지 확인한다."""
        return any("가" <= char <= "힣" for char in value)

    def _build_runtime_logs(self, runtime_status: dict[str, Any]) -> tuple[LogEntry, ...]:
        """런타임 스냅샷에서 최근 로그 패널용 메시지를 만든다."""
        latest_run = runtime_status.get("latest_run") or {}
        queue = runtime_status.get("queue") or {}
        source_failures = runtime_status.get("source_failures") or []
        logs: list[LogEntry] = []

        if latest_run:
            logs.append(
                LogEntry(
                    self._build_last_run_label(latest_run),
                    "안내",
                    (
                        f"최근 실행 상태: {latest_run.get('status', 'unknown')} · "
                        f"수집 {latest_run.get('collected_count', 0)}건 · "
                        f"Top {latest_run.get('ranked_count', 0)}건"
                        f"{self._build_runtime_log_suffix(latest_run)}"
                    ),
                )
            )

        pending_count = int(queue.get("pending") or 0)
        logs.append(
            LogEntry(
                self._format_timestamp(str(runtime_status.get("started_at") or "")),
                "안내",
                f"현재 Notion 동기화 대기 {pending_count}건을 확인했습니다.",
            )
        )

        for failure in source_failures[:3]:
            logs.append(
                LogEntry(
                    self._format_timestamp(str(failure.get("created_at") or "")),
                    "주의",
                    f"{_SOURCE_LABELS.get(str(failure.get('source_name') or ''), str(failure.get('source_name') or '소스'))}: {failure.get('message', '')}",
                )
            )

        if not logs:
            logs.append(LogEntry("지금", "안내", "런타임이 시작되었고 첫 상태 갱신을 기다리는 중입니다."))

        return tuple(logs)

    def _build_runtime_log_suffix(self, latest_run: dict[str, Any]) -> str:
        """최근 실행 로그 뒤에 붙일 dedupe 보조 문구를 만든다."""
        summary = self._build_dedupe_summary(latest_run)
        if not summary:
            return ""
        return f" · {summary}"

    def _build_next_run_label(self, runtime_status: dict[str, Any]) -> str:
        """다음 실행 예상 시각을 문자열로 만든다."""
        interval_minutes = int(runtime_status.get("scheduler_interval_minutes") or 0)
        latest_run = runtime_status.get("latest_run") or {}
        reference_text = str(
            latest_run.get("finished_at")
            or latest_run.get("started_at")
            or runtime_status.get("started_at")
            or ""
        )
        reference = self._parse_datetime(reference_text)
        if reference is None:
            return f"{interval_minutes}분 주기" if interval_minutes else "대기 중"
        return (reference + timedelta(minutes=interval_minutes)).strftime("%m-%d %H:%M") if interval_minutes else "대기 중"

    def _build_last_run_label(self, latest_run: dict[str, Any]) -> str:
        """최근 실행 시각 레이블을 만든다."""
        if not latest_run:
            return "아직 없음"
        return self._format_timestamp(str(latest_run.get("finished_at") or latest_run.get("started_at") or ""))

    def _build_notion_status(self, runtime_status: dict[str, Any]) -> str:
        """Notion 상태 카드의 핵심 문구를 만든다."""
        if not bool(runtime_status.get("notion_enabled")):
            return "사용 안 함"
        queue = runtime_status.get("queue") or {}
        pending = int(queue.get("pending") or 0)
        if pending:
            return f"대기 {pending}건"
        return "처리 완료"

    def _build_notion_detail(self, runtime_status: dict[str, Any]) -> str:
        """Notion 상태 카드의 보조 설명을 만든다."""
        if not bool(runtime_status.get("notion_enabled")):
            return "설정에서 연동이 꺼져 있어 UI에는 상태만 표시합니다."
        queue = runtime_status.get("queue") or {}
        return (
            f"완료 {int(queue.get('synced') or 0)}건 · 실패 {int(queue.get('failed') or 0)}건 · "
            f"대기 {int(queue.get('pending') or 0)}건"
        )

    @staticmethod
    def _build_source_label_from_url(url: str) -> str:
        """출처 URL을 짧은 표시 이름으로 바꾼다."""
        if not url:
            return "출처 없음"
        host = urlparse(url).netloc.replace("www.", "")
        return host or "출처 없음"

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        """SQLite/ISO 날짜 문자열을 datetime으로 변환한다."""
        if not value:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

    def _format_timestamp(self, value: str) -> str:
        """UI용 간단한 날짜/시간 문자열을 만든다."""
        parsed = self._parse_datetime(value)
        if parsed is None:
            return "지금" if not value else value
        return parsed.strftime("%m-%d %H:%M")
