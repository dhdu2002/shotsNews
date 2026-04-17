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
        domestic_feed_urls: dict[IssueCategory, tuple[str, ...]] | None = None,
        international_feed_urls: dict[IssueCategory, tuple[str, ...]] | None = None,
    ) -> None:
        self._feed_urls = tuple(url for url in feed_urls if url)
        self._category_feed_urls = {category: tuple(url for url in urls if url) for category, urls in (category_feed_urls or {}).items()}
        self._domestic_feed_urls = {category: tuple(url for url in urls if url) for category, urls in (domestic_feed_urls or {}).items()}
        self._international_feed_urls = {category: tuple(url for url in urls if url) for category, urls in (international_feed_urls or {}).items()}
        self._default_limit = default_limit
        self._timeout_seconds = timeout_seconds

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
        # 각 카테고리 피드에서 완전히 무관한 기사를 제거하는 1차 필터용 키워드.
        # 범용 단어(price, market, tech 등)는 제외하고 카테고리 특성이 뚜렷한 단어만 포함한다.
        mapping: dict[IssueCategory, tuple[str, ...]] = {
            IssueCategory.AI_TECH: (
                "ai", "llm", "gpu", "chip", "openai", "nvidia", "robot",
                "software", "hardware", "semiconductor", "algorithm",
                "인공지능", "반도체", "엔비디아",
            ),
            IssueCategory.ECONOMY: (
                "gdp", "inflation", "recession", "fed", "tariff", "stock",
                "earnings", "bond", "interest rate",
                "금리", "물가", "경기", "관세", "주가", "채권",
            ),
            IssueCategory.SOCIETY: (
                "election", "policy", "government", "court", "protest",
                "climate", "immigration", "legislation",
                "선거", "정책", "정부", "법원", "시위", "기후",
            ),
            IssueCategory.HEALTH: (
                "vaccine", "hospital", "disease", "cancer", "clinical",
                "fda", "pandemic", "mental health",
                "백신", "병원", "의료", "암", "임상",
            ),
            IssueCategory.ENTERTAINMENT_TREND: (
                "kpop", "idol", "celebrity", "movie", "album", "concert",
                "viral", "streaming", "netflix",
                "연예", "아이돌", "영화", "드라마",
            ),
        }
        return mapping[category]

    def collect(self, target_date: date, category: IssueCategory) -> list[IssueCandidate]:
        """하루/카테고리 기준 RSS 후보를 국내/국외 구분하여 수집한다."""
        _ = target_date
        category_keywords = self._keywords_for_category(category)
        candidates: list[IssueCandidate] = []

        domestic_urls = self._domestic_feed_urls.get(category, ())
        international_urls = self._international_feed_urls.get(category, self._category_feed_urls.get(category, self._feed_urls))

        for region_label, feed_urls in (("domestic", domestic_urls), ("international", international_urls)):
            region_candidates: list[IssueCandidate] = []
            for feed_url in feed_urls:
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
                    region_candidates.append(
                        IssueCandidate(
                            category=category,
                            source_type=SourceType.RSS,
                            source_id=link,
                            title=title,
                            summary=description[:500] or title,
                            source_url=link,
                            published_at=self._parse_pubdate(published_text),
                            score_hint=score_hint,
                            region=region_label,
                        )
                    )
                    if len(region_candidates) >= self._default_limit:
                        break
                if len(region_candidates) >= self._default_limit:
                    break

            candidates.extend(region_candidates)
        return candidates
