"""OpenAI 우선 스크립트 생성 어댑터."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from ...domain.enums import ScriptTone
from ...domain.models import IssueScriptSet, PersistedIssue


class OpenAIScriptGenerator:
    """OpenAI를 우선 사용하고, 실패 시 로컬 문구로 대체한다."""

    def __init__(self, model: str, api_key: str, timeout_seconds: int = 25) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate(self, issue: PersistedIssue) -> IssueScriptSet:
        """랭킹 이슈를 3톤(정보형/자극형/뉴스형)으로 생성한다."""
        if self._api_key:
            generated = self._generate_with_openai(issue)
            if generated:
                return IssueScriptSet(issue_id=issue.issue_id, scripts_by_tone=generated)

        scripts = {
            ScriptTone.INFORMATIVE: self._build_placeholder(issue, ScriptTone.INFORMATIVE),
            ScriptTone.STIMULATING: self._build_placeholder(issue, ScriptTone.STIMULATING),
            ScriptTone.NEWS: self._build_placeholder(issue, ScriptTone.NEWS),
        }
        return IssueScriptSet(issue_id=issue.issue_id, scripts_by_tone=scripts)

    def _generate_with_openai(self, issue: PersistedIssue) -> dict[ScriptTone, str] | None:
        prompt = (
            "다음 이슈를 3가지 톤으로 짧게 작성하세요: 정보형, 자극형, 뉴스형. "
            "반드시 JSON 객체 하나만 반환하고 키는 informative, stimulating, news 를 사용하세요. "
            "각 값은 2~4문장으로 작성하세요.\n\n"
            f"제목: {issue.title}\n"
            f"핵심 포인트: {'; '.join(issue.key_points)}\n"
            f"출처 URL: {issue.source_url}\n"
        )
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "너는 한국어 뉴스 스크립트 작가다."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        request = Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                ScriptTone.INFORMATIVE: str(parsed["informative"]),
                ScriptTone.STIMULATING: str(parsed["stimulating"]),
                ScriptTone.NEWS: str(parsed["news"]),
            }
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            return None

    def _build_placeholder(self, issue: PersistedIssue, tone: ScriptTone) -> str:
        """외부 호출 없이 결정론적 로컬 문구를 생성한다."""
        return (
            f"[{self._model}] {tone.label} 스크립트 | "
            f"제목={issue.title} | 포인트={'; '.join(issue.key_points)}"
        )
