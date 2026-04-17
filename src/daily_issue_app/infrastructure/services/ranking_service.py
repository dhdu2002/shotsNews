"""숏폼 적합도 6요인 기반 랭킹 서비스."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import ClassVar

from ...domain.enums import IssueCategory
from ...domain.enums import SourceType
from ...domain.models import IssueCandidate, RankedIssue, ShortFormScoreBreakdown


class RankingService:
    """6요인 숏폼 점수 총점 기준으로 Top-K를 선별한다."""

    _HOOK_KEYWORDS: ClassVar[tuple[str, ...]] = (
        "충격",
        "반전",
        "결국",
        "단독",
        "속보",
        "긴급",
        "파격",
        "논란",
        "공개",
        "유출",
        "viral",
        "shocking",
        "breaking",
        "exclusive",
    )
    _CONTROVERSY_KEYWORDS: ClassVar[tuple[str, ...]] = (
        "논란",
        "갈등",
        "파문",
        "비판",
        "폭로",
        "정치",
        "규제",
        "소송",
        "충돌",
        "boycott",
        "controversy",
        "backlash",
        "lawsuit",
    )
    _AD_UNFRIENDLY_KEYWORDS: ClassVar[tuple[str, ...]] = (
        "사망",
        "참사",
        "전쟁",
        "살인",
        "범죄",
        "도박",
        "마약",
        "성범죄",
        "혐오",
        "폭력",
        "자살",
        "death",
        "war",
        "crime",
        "drug",
        "sex",
    )
    _INFO_KEYWORDS: ClassVar[tuple[str, ...]] = (
        "왜",
        "원인",
        "배경",
        "분석",
        "데이터",
        "전망",
        "비교",
        "해설",
        "공개",
        "발표",
        "how",
        "why",
        "data",
        "report",
        "analysis",
    )
    _NUMBER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"\d+[\d,\.]*")

    _SOURCE_POPULARITY_BASE: ClassVar[dict[SourceType, float]] = {
        SourceType.RSS: 4.8,
        SourceType.YOUTUBE: 6.8,
        SourceType.REDDIT: 6.2,
        SourceType.TWITTER_X: 6.5,
    }

    def __init__(self, top_k: int = 5) -> None:
        self._top_k: int = top_k

    def rank(self, candidates: list[IssueCandidate]) -> list[RankedIssue]:
        """카테고리별 숏폼 총점 내림차순으로 정렬 후 랭킹 모델로 변환한다."""
        grouped: dict[IssueCategory, list[IssueCandidate]] = {category: [] for category in IssueCategory}
        for candidate in candidates:
            breakdown = self._build_breakdown(candidate)
            candidate.score_breakdown = breakdown
            candidate.short_form_score = breakdown.total
            grouped[candidate.category].append(candidate)

        ranked: list[RankedIssue] = []

        for category in IssueCategory:
            sorted_candidates = sorted(grouped[category], key=lambda item: item.total_score, reverse=True)
            for index, candidate in enumerate(sorted_candidates[: self._top_k], start=1):
                ranked.append(
                    RankedIssue(
                        rank=index,
                        category=candidate.category,
                        title=candidate.title,
                        key_points=[candidate.summary],
                        source_url=candidate.source_url,
                        score=candidate.total_score,
                        score_breakdown=candidate.score_breakdown,
                    )
                )
        return ranked

    def _build_breakdown(self, candidate: IssueCandidate) -> ShortFormScoreBreakdown:
        """후보 1건의 숏폼 적합도 6요인을 계산한다."""
        text = f"{candidate.title} {candidate.summary}".strip()
        return ShortFormScoreBreakdown(
            latestness=self._score_latestness(candidate),
            hook_strength=self._score_hook_strength(text),
            popularity=self._score_popularity(candidate, text),
            controversy=self._score_controversy(candidate, text),
            ad_friendly=self._score_ad_friendly(candidate, text),
            info_density=self._score_info_density(candidate, text),
        )

    def _score_latestness(self, candidate: IssueCandidate) -> float:
        """발행 시각 기준 최신성을 0~10으로 계산한다."""
        published_at = candidate.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        hours = max((datetime.now(tz=timezone.utc) - published_at.astimezone(timezone.utc)).total_seconds() / 3600, 0.0)
        if hours <= 6:
            return 10.0
        if hours <= 12:
            return 9.2
        if hours <= 24:
            return 8.5
        if hours <= 48:
            return 7.0
        if hours <= 72:
            return 5.5
        return self._clamp(2.5, 10.0 - ((hours - 72) / 24) * 1.1)

    def _score_hook_strength(self, text: str) -> float:
        """제목/요약의 후킹 강도를 계산한다."""
        lower_text = text.lower()
        headline = text.splitlines()[0] if text else ""
        emphasis_count = headline.count("!") + headline.count("?") + headline.count("…")
        keyword_hits = sum(1 for keyword in self._HOOK_KEYWORDS if keyword in lower_text)
        number_hits = len(self._NUMBER_PATTERN.findall(headline))
        title_length = len(headline.strip())
        length_bonus = 1.0 if 18 <= title_length <= 48 else 0.2
        return self._clamp(0.0, 3.8 + (emphasis_count * 0.7) + (keyword_hits * 1.1) + (number_hits * 0.4) + length_bonus)

    def _score_popularity(self, candidate: IssueCandidate, text: str) -> float:
        """소스 성격과 기존 힌트를 함께 반영해 대중성을 계산한다."""
        lower_text = text.lower()
        number_hits = len(self._NUMBER_PATTERN.findall(lower_text))
        social_hits = sum(
            1
            for keyword in ("조회", "구독", "댓글", "추천", "likes", "views", "subscribers", "followers", "shares")
            if keyword in lower_text
        )
        base = self._SOURCE_POPULARITY_BASE.get(candidate.source_type, 5.0)
        hint_boost = min(candidate.score_hint * 0.9, 2.5)
        return self._clamp(0.0, base + hint_boost + (number_hits * 0.25) + (social_hits * 0.55))

    def _score_controversy(self, candidate: IssueCandidate, text: str) -> float:
        """의견 충돌 가능성과 토론 유발 요소를 계산한다."""
        lower_text = text.lower()
        keyword_hits = sum(1 for keyword in self._CONTROVERSY_KEYWORDS if keyword in lower_text)
        source_bonus = 0.8 if candidate.source_type in {SourceType.REDDIT, SourceType.TWITTER_X} else 0.0
        punctuation_bonus = 0.4 if any(token in text for token in ("vs", "찬반", "공방")) else 0.0
        return self._clamp(0.0, 2.0 + (keyword_hits * 1.6) + source_bonus + punctuation_bonus)

    def _score_ad_friendly(self, candidate: IssueCandidate, text: str) -> float:
        """광고 친화성을 높게, 민감도를 낮게 평가한다."""
        lower_text = text.lower()
        penalty_hits = sum(1 for keyword in self._AD_UNFRIENDLY_KEYWORDS if keyword in lower_text)
        category_bonus = 0.4 if candidate.category in {IssueCategory.AI_TECH, IssueCategory.ECONOMY, IssueCategory.ENTERTAINMENT_TREND} else 0.0
        return self._clamp(0.0, 8.6 + category_bonus - (penalty_hits * 1.8))

    def _score_info_density(self, candidate: IssueCandidate, text: str) -> float:
        """짧은 포맷으로 요약하기 쉬운 정보 밀도를 계산한다."""
        lower_text = text.lower()
        summary_length = len(candidate.summary.strip())
        number_hits = len(self._NUMBER_PATTERN.findall(lower_text))
        keyword_hits = sum(1 for keyword in self._INFO_KEYWORDS if keyword in lower_text)
        length_bonus = 2.4 if 70 <= summary_length <= 280 else 1.2 if summary_length >= 35 else 0.4
        return self._clamp(0.0, 3.0 + length_bonus + (number_hits * 0.35) + (keyword_hits * 0.7))

    @staticmethod
    def _clamp(minimum: float, value: float, maximum: float = 10.0) -> float:
        """모든 세부 점수를 0~10 범위로 제한한다."""
        return round(max(minimum, min(value, maximum)), 2)
