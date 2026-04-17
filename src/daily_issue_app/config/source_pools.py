"""카테고리별 소스 풀 설정 로더와 요약 헬퍼."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from ..domain.enums import IssueCategory

_SOURCE_ALIASES = {
    "rss": "rss",
    "youtube": "youtube",
    "youtube_feed_urls": "youtube",
    "reddit": "reddit",
    "subreddits": "reddit",
    "twitter": "twitter_x",
    "twitter_x": "twitter_x",
    "x": "twitter_x",
}


@dataclass(slots=True, frozen=True)
class CategorySourcePools:
    """카테고리 전용 소스 풀을 읽기 전용으로 보관한다."""

    path: str
    rss: dict[IssueCategory, tuple[str, ...]] = field(default_factory=dict)
    youtube: dict[IssueCategory, tuple[str, ...]] = field(default_factory=dict)
    reddit: dict[IssueCategory, tuple[str, ...]] = field(default_factory=dict)
    twitter_x: dict[IssueCategory, tuple[str, ...]] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        """하나 이상의 카테고리 전용 풀이 설정되었는지 반환한다."""
        return any((self.rss, self.youtube, self.reddit, self.twitter_x))

    def for_source(self, source_name: str, category: IssueCategory) -> tuple[str, ...]:
        """특정 소스/카테고리에 대응하는 전용 풀을 반환한다."""
        normalized = _SOURCE_ALIASES.get(source_name, source_name)
        mapping = getattr(self, normalized, {})
        return tuple(mapping.get(category, ()))

    def categories_for_source(self, source_name: str) -> dict[IssueCategory, tuple[str, ...]]:
        """특정 소스의 카테고리별 전용 풀 전체를 반환한다."""
        normalized = _SOURCE_ALIASES.get(source_name, source_name)
        mapping = getattr(self, normalized, {})
        return dict(mapping)


def load_category_source_pools(root: Path) -> CategorySourcePools:
    """`config/source_pools.json`이 있으면 카테고리별 소스 풀을 읽는다."""
    config_path = root / "config" / "source_pools.json"
    if not config_path.exists():
        return CategorySourcePools(path=str(config_path))

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CategorySourcePools(path=str(config_path))

    category_payloads = _extract_category_payloads(payload)
    parsed = {
        "rss": {},
        "youtube": {},
        "reddit": {},
        "twitter_x": {},
    }

    for raw_category_key, source_payload in category_payloads.items():
        category = _parse_category(raw_category_key)
        if category is None or not isinstance(source_payload, dict):
            continue

        for raw_source_name, raw_values in source_payload.items():
            source_name = _SOURCE_ALIASES.get(str(raw_source_name).strip().lower())
            if source_name is None:
                continue
            normalized_values = _normalize_source_values(source_name, raw_values)
            if normalized_values:
                parsed[source_name][category] = normalized_values

    return CategorySourcePools(
        path=str(config_path),
        rss=parsed["rss"],
        youtube=parsed["youtube"],
        reddit=parsed["reddit"],
        twitter_x=parsed["twitter_x"],
    )


def build_source_configuration_snapshot(
    *,
    source_name: str,
    shared_values: tuple[str, ...],
    category_values: dict[IssueCategory, tuple[str, ...]],
    unit_label: str,
    configured: bool | None = None,
    extra_note: str = "",
) -> dict[str, object]:
    """런타임 status 탭에 보여줄 소스 구성 요약을 만든다."""
    dedicated_total = sum(len(values) for values in category_values.values())
    configured_count = len(shared_values) + dedicated_total
    pool_categories = [category for category in IssueCategory if category in category_values]
    fallback_categories = [category.label for category in IssueCategory if category not in category_values]

    note_parts: list[str] = []
    if shared_values:
        note_parts.append(f"공용 {unit_label} {len(shared_values)}개")
    else:
        note_parts.append(f"공용 {unit_label} 없음")

    if pool_categories:
        scoped = ", ".join(f"{category.label} {len(category_values[category])}개" for category in pool_categories)
        note_parts.append(f"카테고리 전용 {dedicated_total}개 ({scoped})")
    else:
        note_parts.append("카테고리 전용 설정 없음")

    if fallback_categories:
        fallback_label = "공용 fallback" if shared_values else "미설정 카테고리"
        note_parts.append(f"{fallback_label}: {', '.join(fallback_categories)}")

    if extra_note:
        note_parts.append(extra_note)

    return {
        "name": source_name,
        "configured_count": configured_count,
        "configured": configured if configured is not None else configured_count > 0,
        "note": " · ".join(note_parts),
        "shared_count": len(shared_values),
        "category_pool_count": len(pool_categories),
        "source_pools_enabled": bool(pool_categories),
    }


def _extract_category_payloads(payload: Any) -> dict[str, Any]:
    """최상위 JSON 또는 `categories` 래퍼를 모두 허용한다."""
    if not isinstance(payload, dict):
        return {}
    categories = payload.get("categories")
    if isinstance(categories, dict):
        return categories
    return payload


def _parse_category(value: Any) -> IssueCategory | None:
    """문자열 카테고리 키를 IssueCategory로 변환한다."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    for category in IssueCategory:
        if normalized == category.value:
            return category
    return None


def _normalize_source_values(source_name: str, raw_values: Any) -> tuple[str, ...]:
    """JSON 값 형태 차이를 흡수해 문자열 튜플로 정규화한다."""
    if source_name == "twitter_x" and isinstance(raw_values, dict):
        raw_values = raw_values.get("queries") or raw_values.get("query") or ()

    if isinstance(raw_values, str):
        normalized = raw_values.strip()
        return (normalized,) if normalized else ()

    if isinstance(raw_values, (list, tuple)):
        values: list[str] = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized:
                values.append(normalized)
        return tuple(values)

    return ()
