"""키워드 밀도 기반 카테고리 분류기."""

from __future__ import annotations

from .enums import IssueCategory

# 카테고리별 구체적인 고유 키워드 (범용 단어 제외)
_KEYWORDS: dict[IssueCategory, tuple[str, ...]] = {
    IssueCategory.AI_TECH: (
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "llm", "gpt", "gemini", "claude", "openai", "anthropic", "nvidia", "mistral",
        "semiconductor", "gpu", "cpu", "chip", "transistor", "wafer",
        "robot", "automation", "algorithm", "inference", "transformer",
        "인공지능", "머신러닝", "딥러닝", "반도체", "엔비디아", "오픈ai",
    ),
    IssueCategory.ECONOMY: (
        "gdp", "inflation", "federal reserve", "interest rate", "central bank",
        "recession", "bull market", "bear market", "tariff", "trade war",
        "earnings per share", "ipo", "hedge fund", "bond yield",
        "금리", "물가", "경기침체", "관세", "무역전쟁", "기준금리", "채권금리",
        "주가지수", "코스피", "코스닥", "나스닥",
    ),
    IssueCategory.SOCIETY: (
        "election", "congress", "senate", "legislation", "vote",
        "protest", "demonstration", "civil rights", "immigration",
        "climate change", "carbon", "environmental policy", "supreme court",
        "선거", "국회", "법안", "시위", "기후변화", "이민", "대법원", "탄핵",
    ),
    IssueCategory.HEALTH: (
        "vaccine", "clinical trial", "fda", "pandemic", "epidemic",
        "cancer", "alzheimer", "diabetes", "mental health", "surgery",
        "hospital", "drug approval", "medical research", "outbreak",
        "백신", "임상시험", "암", "정신건강", "의료", "병원", "코로나",
    ),
    IssueCategory.ENTERTAINMENT_TREND: (
        "kpop", "idol", "bts", "blackpink", "k-drama",
        "celebrity", "box office", "album release", "concert tour",
        "streaming", "netflix", "spotify", "viral", "trending",
        "아이돌", "연예인", "드라마", "뮤직비디오", "오징어", "영화 개봉",
    ),
}


def classify(title: str, summary: str, fallback: IssueCategory) -> IssueCategory:
    """제목+요약의 키워드 밀도로 가장 적합한 카테고리를 반환한다.

    동점이거나 아무 키워드도 매칭되지 않으면 수집 시 할당된 fallback 카테고리를 유지한다.
    """
    text = f"{title} {summary}".lower()
    best_category = fallback
    best_score = 0
    for category, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category
