"""수동 대본 생성용 원문 재수집/요약 서비스."""

from __future__ import annotations

import html
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SourceContentFetcher:
    """기사 URL에서 본문을 다시 읽어 짧은 요약으로 정리한다."""

    _USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )

    def __init__(self, timeout_seconds: int = 15) -> None:
        self._timeout_seconds: int = timeout_seconds

    def fetch_summary(self, source_url: str) -> str | None:
        """기사 본문을 다시 가져와 수동 생성용 짧은 요약을 반환한다."""
        normalized_url = source_url.strip()
        if not normalized_url:
            return None

        request = Request(
            url=normalized_url,
            headers={
                "User-Agent": self._USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.5",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    return None
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError):
            return None

        document = raw.decode(charset, errors="ignore")
        extracted_text = self._extract_readable_text(document)
        if len(extracted_text) < 120:
            return None
        summarized = self._summarize_text(extracted_text)
        return summarized or None

    def _extract_readable_text(self, document: str) -> str:
        """HTML에서 기사 본문 후보를 최대한 읽기 좋은 텍스트로 정리한다."""
        cleaned_document = re.sub(r"<!--.*?-->", " ", document, flags=re.DOTALL)
        cleaned_document = re.sub(
            r"<(script|style|noscript|svg|iframe).*?>.*?</\1>",
            " ",
            cleaned_document,
            flags=re.IGNORECASE | re.DOTALL,
        )

        article_match = re.search(r"<article\b[^>]*>(.*?)</article>", cleaned_document, flags=re.IGNORECASE | re.DOTALL)
        scoped_document = article_match.group(1) if article_match else cleaned_document

        paragraphs = re.findall(r"<(p|h1|h2|h3|li)\b[^>]*>(.*?)</\1>", scoped_document, flags=re.IGNORECASE | re.DOTALL)
        candidates: list[str] = []

        meta_description = self._extract_meta_description(cleaned_document)
        if meta_description:
            candidates.append(meta_description)

        for _, fragment in paragraphs:
            normalized = self._strip_tags(fragment)
            if len(normalized) >= 35:
                candidates.append(normalized)

        if not candidates:
            fallback = self._strip_tags(scoped_document)
            if fallback:
                candidates.append(fallback)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            normalized = re.sub(r"\s+", " ", item).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
            if len(" ".join(deduped)) >= 5000:
                break

        return " ".join(deduped)[:5000]

    def _extract_meta_description(self, document: str) -> str:
        """메타 설명을 먼저 확보해 기사 핵심을 보강한다."""
        patterns = (
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, document, flags=re.IGNORECASE | re.DOTALL)
            if match is None:
                continue
            normalized = self._strip_tags(match.group(1))
            if len(normalized) >= 40:
                return normalized
        return ""

    def _summarize_text(self, text: str) -> str:
        """문장 기반 가벼운 규칙 요약으로 생성기 입력 길이를 줄인다."""
        normalized = re.sub(r"\s+", " ", text).strip()
        sentences = self._split_sentences(normalized)
        if not sentences:
            return normalized[:900]

        scored: list[tuple[float, int, str]] = []
        for index, sentence in enumerate(sentences):
            score = 0.0
            if re.search(r"\d", sentence):
                score += 2.2
            length = len(sentence)
            if 45 <= length <= 180:
                score += 1.5
            elif 25 <= length <= 220:
                score += 0.8
            if re.search(r"발표|보도|전했다|밝혔|according|said|announced|reported|statement", sentence, flags=re.IGNORECASE):
                score += 1.1
            if re.search(r"시장|정책|실적|출시|규제|건강|연구|trend|market|policy|launch|study", sentence, flags=re.IGNORECASE):
                score += 0.7
            scored.append((score, index, sentence))

        best_sentences = sorted(scored, key=lambda item: (-item[0], item[1]))[:5]
        best_sentences.sort(key=lambda item: item[1])
        summary = " ".join(sentence for _, _, sentence in best_sentences).strip()
        if not summary:
            return normalized[:900]
        return summary[:900]

    def _split_sentences(self, text: str) -> list[str]:
        """한글/영문 혼합 기사에서도 대략적인 문장 경계를 분리한다."""
        parts = re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+", text)
        sentences: list[str] = []
        for part in parts:
            normalized = re.sub(r"\s+", " ", part).strip(" ·-\t\n\r")
            if len(normalized) >= 25:
                sentences.append(normalized)
        return sentences

    def _strip_tags(self, value: str) -> str:
        """태그/엔티티/과도한 공백을 제거한다."""
        unescaped = html.unescape(value)
        without_tags = re.sub(r"<[^>]+>", " ", unescaped)
        normalized = re.sub(r"\s+", " ", without_tags).strip()
        return normalized
