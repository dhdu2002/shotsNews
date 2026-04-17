"""RSS 우선 수집기 구현(보수적 네트워크 호출)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ...domain.enums import IssueCategory
from ...domain.enums import SourceType
from ...domain.models import IssueCandidate
from ...config.source_pools import build_source_configuration_snapshot


class RSSCollector:
    """카테고리 키워드 기반 RSS 수집기."""

    def __init__(
        self,
        feed_urls: tuple[str, ...],
        default_limit: int = 20,
        timeout_seconds: int = 15,
        category_feed_urls: dict[IssueCategory, tuple[str, ...]] | None = None,
    ) -> None:
        self._feed_urls = tuple(url for url in feed_urls if url)
        self._category_feed_urls = {category: tuple(url for url in urls if url) for category, urls in (category_feed_urls or {}).items()}
        self._default_limit = default_limit
        self._timeout_seconds = timeout_seconds

    def _resolve_feed_urls(self, category: IssueCategory) -> tuple[str, ...]:
        """카테고리 전용 풀이 있으면 우선 사용하고, 없으면 공용 풀로 fallback 한다."""
        return self._category_feed_urls.get(category, self._feed_urls)

    def describe_source_config(self) -> dict[str, object]:
        """런타임 status용 RSS 소스 구성 요약을 반환한다."""
        return build_source_configuration_snapshot(
            source_name="rss",
            shared_values=self._feed_urls,
            category_values=self._category_feed_urls,
            unit_label="피드",
        )

    def _parse_pubdate(self, value: str) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return datetime.now(tz=timezone.utc)

    def _keywords_for_category(self, category: IssueCategory) -> tuple[str, ...]:
        mapping: dict[IssueCategory, tuple[str, ...]] = {
            IssueCategory.AI_TECH: ("ai", "tech", "software", "chip", "openai", "model", "반도체", "기술"),
            IssueCategory.ECONOMY: ("economy", "market", "inflation", "jobs", "price"),
            IssueCategory.SOCIETY: ("society", "education", "community", "culture", "사회", "정책"),
            IssueCategory.HEALTH: ("health", "medical", "hospital", "disease", "wellness", "건강", "의료"),
            IssueCategory.ENTERTAINMENT_TREND: (
                "entertainment",
                "celebrity",
                "music",
                "movie",
                "trend",
                "viral",
                "연예",
                "트렌드",
            ),
        }
        return mapping[category]

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        """하루/카테고리 기준 RSS 후보를 수집한다."""
        _ = target_date
        category_keywords = self._keywords_for_category(category)
        candidates: list[IssueCandidate] = []
        for feed_url in self._resolve_feed_urls(category):
            request = Request(feed_url, headers={"User-Agent": "daily-issue-desktop/0.1"})
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    xml_data = response.read()
            except (URLError, TimeoutError, ValueError):
                continue

            try:
                root = ElementTree.fromstring(xml_data)
            except ElementTree.ParseError:
                continue

            nodes = list(root.findall(".//item"))
            if not nodes:
                nodes = list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))

            for node in nodes:
                title = (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                description = (
                    node.findtext("description")
                    or node.findtext("summary")
                    or node.findtext("{http://www.w3.org/2005/Atom}summary")
                    or ""
                ).strip()
                link = (node.findtext("link") or "").strip()
                if not link:
                    atom_link = node.find("{http://www.w3.org/2005/Atom}link")
                    if atom_link is not None:
                        link = atom_link.attrib.get("href", "")
                if not title or not link:
                    continue

                text = unescape(f"{title} {description}").lower()
                if not any(keyword in text for keyword in category_keywords):
                    continue

                published_text = (
                    node.findtext("pubDate")
                    or node.findtext("published")
                    or node.findtext("updated")
                    or node.findtext("{http://www.w3.org/2005/Atom}published")
                    or node.findtext("{http://www.w3.org/2005/Atom}updated")
                    or ""
                )
                score_hint = sum(1.0 for keyword in category_keywords if keyword in text)
                candidates.append(
                    IssueCandidate(
                        category=category,
                        source_type=SourceType.RSS,
                        source_id=link,
                        title=title,
                        summary=description[:500] or title,
                        source_url=link,
                        published_at=self._parse_pubdate(published_text),
                        score_hint=score_hint,
                    )
                )
                if len(candidates) >= self._default_limit:
                    return candidates
        return candidates
