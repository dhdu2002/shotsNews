"""이슈 파이프라인 도메인 열거형 정의."""

from __future__ import annotations

from enum import Enum


class IssueCategory(str, Enum):
    """숏폼 후보를 분류하는 카테고리 목록."""

    AI_TECH = "ai_tech"
    ECONOMY = "economy"
    SOCIETY = "society"
    HEALTH = "health"
    ENTERTAINMENT_TREND = "entertainment_trend"
    SNS = "sns"

    @property
    def label(self) -> str:
        """UI/출력용 한글 표시명."""
        labels = {
            IssueCategory.AI_TECH: "AI/테크",
            IssueCategory.ECONOMY: "경제",
            IssueCategory.SOCIETY: "사회",
            IssueCategory.HEALTH: "건강",
            IssueCategory.ENTERTAINMENT_TREND: "연예/트렌드",
            IssueCategory.SNS: "SNS",
        }
        return labels[self]


class SourceType(str, Enum):
    """수집 소스 타입."""

    RSS = "rss"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    TWITTER_X = "twitter_x"


class ScriptTone(str, Enum):
    """스크립트 3톤 정의(정보형/자극형/뉴스형)."""

    INFORMATIVE = "informative"
    STIMULATING = "stimulating"
    NEWS = "news"

    @property
    def label(self) -> str:
        """UI/출력용 한글 표시명."""
        labels = {
            ScriptTone.INFORMATIVE: "정보형",
            ScriptTone.STIMULATING: "자극형",
            ScriptTone.NEWS: "뉴스형",
        }
        return labels[self]


class NewsRegion(str, Enum):
    """기사 수집 지역 구분."""

    DOMESTIC = "domestic"
    INTERNATIONAL = "international"

    @property
    def label(self) -> str:
        return {"domestic": "국내", "international": "국외"}[self.value]


class RecordSyncStatus(str, Enum):
    """Notion 동기화 상태."""

    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
