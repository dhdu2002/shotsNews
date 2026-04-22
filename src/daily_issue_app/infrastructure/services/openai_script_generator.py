"""OpenAI 우선 스크립트 생성 어댑터."""

from __future__ import annotations

import html
import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from ...domain.enums import ScriptTone
from ...domain.models import IssueScriptSet, PersistedIssue


class OpenAIScriptGenerator:
    """OpenAI를 우선 사용하고, 실패 시 로컬 문구로 대체한다."""

    _DEFAULT_DURATION_SECONDS: int = 60
    _DEFAULT_STIMULATING_EMOTION: str = "충격"

    def __init__(self, model: str, api_key: str, timeout_seconds: int = 25) -> None:
        self._model: str = model
        self._api_key: str = api_key
        self._timeout_seconds: int = timeout_seconds

    def generate(self, issue: PersistedIssue) -> IssueScriptSet:
        """랭킹 이슈를 3톤(정보형/자극형/뉴스형)으로 생성한다."""
        scripts = self._generate_scripts(issue)
        return IssueScriptSet(issue_id=issue.issue_id, scripts_by_tone=scripts)

    def generate_manual(self, issue: PersistedIssue, fresh_summary: str | None = None) -> IssueScriptSet:
        """수동 생성에서는 재수집한 기사 요약을 우선 사용해 3톤 스크립트를 만든다."""
        scripts = self._generate_scripts(issue, fresh_summary=fresh_summary, manual_mode=True)
        return IssueScriptSet(issue_id=issue.issue_id, scripts_by_tone=scripts)

    def _generate_scripts(
        self,
        issue: PersistedIssue,
        fresh_summary: str | None = None,
        manual_mode: bool = False,
    ) -> dict[ScriptTone, str]:
        """기본/수동 생성 공통 로직을 수행한다."""
        use_fresh_summary = bool(fresh_summary and fresh_summary.strip())
        if self._api_key:
            generated = self._generate_with_openai(issue, fresh_summary=fresh_summary if use_fresh_summary else None)
            if generated:
                if manual_mode:
                    return self._rewrite_scripts_if_needed(issue, generated, fresh_summary=fresh_summary)
                return generated

        scripts = self._build_local_scripts(
            issue,
            fresh_summary=fresh_summary if self._can_use_fresh_summary_without_translation(fresh_summary) else None,
        )
        if manual_mode:
            return self._apply_local_naturalness_cleanup(scripts)
        return scripts

    def _generate_with_openai(
        self,
        issue: PersistedIssue,
        fresh_summary: str | None = None,
    ) -> dict[ScriptTone, str] | None:
        prompt = self._build_openai_prompt(issue, fresh_summary=fresh_summary)
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "너는 한국어 숏폼 뉴스 대본 작가다. "
                        "반드시 사람이 바로 읽을 수 있는 자연스러운 대본 초안만 작성해야 하며 "
                        "해외 기사나 영어 원문이라도 고유명사 외에는 모두 자연스러운 한국어로 풀어써야 한다. "
                        "제목 문장을 반복하지 말고 기사 본문 의미를 한국어 구어체로 재구성해야 한다. "
                        "HTML, 마크업, 디버그 문자열, JSON 설명, 모델명 노출을 절대 포함하지 않는다."
                    ),
                },
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
            return self._coerce_generated_scripts(parsed, issue, fresh_summary=fresh_summary)
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            return None

    def _build_openai_prompt(self, issue: PersistedIssue, fresh_summary: str | None = None) -> str:
        """사용자 지정 형식에 맞춘 3톤 동시 생성 프롬프트를 만든다."""
        title = self._sanitize_text(issue.title)
        core_message = self._build_core_message(issue, fresh_summary=fresh_summary)
        duration = self._DEFAULT_DURATION_SECONDS
        source_label = self._extract_source_label(issue.source_url)
        run_date = issue.run_date or "오늘"
        source_summary_section = ""
        if fresh_summary:
            source_summary_section = (
                "\n[수동 생성용 새 기사 요약]\n"
                f"- 아래 요약은 방금 source_url에서 다시 읽은 본문 기반입니다: {self._sanitize_text(fresh_summary)[:900]}\n"
                "- 저장된 key_points보다 이 요약을 우선 반영하되, 내용이 겹치면 자연스럽게 통합하세요.\n"
                "- 영어/외신 표현이 있더라도 최종 대본 문장은 모두 자연스러운 한국어여야 합니다.\n"
            )

        return f"""
아래 3가지 타입의 숏폼 대본 초안을 각각 작성하세요.
반드시 JSON 객체 하나만 반환하고 키는 informative, stimulating, news 만 사용하세요.
각 값은 순수 텍스트여야 하며, HTML/마크업/코드블록/추가 설명을 포함하면 안 됩니다.
 제목을 반복하거나 URL/도메인 소개로 문장을 채우지 말고, 기사 본문 요지를 자연스러운 한국어로 풀어쓰세요.
 해외 기사여도 최종 대본 문장은 한국어만 사용하고, 고유명사만 필요할 때 원문 표기를 남기세요.
 한국어 기사라도 어색하거나 기계적으로 들리는 표현은 구어체로 다시 다듬으세요.

[공통 뉴스 정보]
- 제목: {title}
- 핵심 메시지: {core_message}
- 출처: {source_label}
- 날짜: {run_date}
- 목표 시간: {duration}초
{source_summary_section}

[USER - TYPE 1: 뉴스형]
아래 뉴스를 바탕으로 "뉴스형" 숏폼 대본을 작성하세요.

--- 뉴스 정보 ---
제목: {title}
핵심 메시지: {core_message}
목표 시간: {duration}초
-----------------

[작성 지침]
- 어조: 차분하고 신뢰감 있는 리포터 말투
- 과장 표현, 감탄사 금지
- 숫자·출처·날짜를 반드시 포함
- 시청자를 "여러분"으로 호칭
- 첫 문장이 제목 복붙처럼 들리면 안 되고, 기사 핵심을 바로 전달해야 함

[대본 구조]
[HOOK] ← 0~3초
[BRIEFING] ← 4~15초
[DETAIL] ← 16~45초
[SIGNIFICANCE] ← 46~55초
[CLOSING] ← 56~60초

[출력 형식]
HOOK: ...
BRIEFING: ...
DETAIL: ...
SIGNIFICANCE: ...
CLOSING: ...

[USER - TYPE 2: 자극형]
아래 뉴스를 바탕으로 "자극형" 숏폼 대본을 작성하세요.

--- 뉴스 정보 ---
제목: {title}
핵심 메시지: {core_message}
감정 타깃: {self._DEFAULT_STIMULATING_EMOTION}
목표 시간: {duration}초
-----------------

[작성 지침]
- 어조: 직설적, 도발적, 감정이입 유도
- 첫 문장에서 반드시 시청자의 감정을 건드릴 것
- "이거 실화냐", "말이 됩니까", "절대 모르면 안 됨" 류 표현 적극 활용 가능
- 시청자를 "여러분" 또는 "당신"으로 호칭
- 과도한 혐오·비하·허위 사실 포함 금지
- 영어 직역투 대신 한국어 숏폼 화법으로 다시 풀어쓸 것

[대본 구조]
[HOOK] ← 0~3초
[PROVOCATION] ← 4~12초
[REVELATION] ← 13~40초
[EMPATHY] ← 41~52초
[CTA] ← 53~60초

[출력 형식]
HOOK: ...
PROVOCATION: ...
REVELATION: ...
EMPATHY: ...
CTA: ...

[USER - TYPE 3: 정보형]
아래 뉴스를 바탕으로 "정보형" 숏폼 대본을 작성하세요.

--- 뉴스 정보 ---
제목: {title}
핵심 메시지: {core_message}
목표 시간: {duration}초
-----------------

[작성 지침]
- 어조: 친근하고 명확한 설명체, 선생님·친구 말투
- "~하는 법", "~가지 방법", "몰랐죠?" 구조 선호
- 리스트·번호·순서를 적극 활용
- 시청자가 "저장해야겠다"고 느끼도록 실용성 강조
- 전문 용어는 반드시 쉬운 말로 풀어서 설명
- 제목/요약 문장을 그대로 옮기지 말고 이해하기 쉬운 한국어로 바꿔 설명할 것

[대본 구조]
[HOOK] ← 0~3초
[PROBLEM] ← 4~10초
[INFO BODY] ← 11~45초
[SUMMARY] ← 46~55초
[CTA] ← 56~60초

[출력 형식]
HOOK: ...
PROBLEM: ...
INFO BODY: ...
SUMMARY: ...
CTA: ...
""".strip()

    def _coerce_generated_scripts(
        self,
        parsed: object,
        issue: PersistedIssue,
        fresh_summary: str | None = None,
    ) -> dict[ScriptTone, str]:
        """OpenAI 응답에서 비어 있거나 누락된 톤은 로컬 대본으로 보완한다."""
        source = parsed if isinstance(parsed, dict) else None
        scripts = self._build_local_scripts(issue, fresh_summary=fresh_summary)

        if source is None:
            return scripts

        value_map = {
            ScriptTone.INFORMATIVE: self._sanitize_script_output(source.get("informative")),
            ScriptTone.STIMULATING: self._sanitize_script_output(source.get("stimulating")),
            ScriptTone.NEWS: self._sanitize_script_output(source.get("news")),
        }
        for tone, value in value_map.items():
            if value:
                scripts[tone] = value
        return scripts

    def _build_local_scripts(
        self,
        issue: PersistedIssue,
        fresh_summary: str | None = None,
    ) -> dict[ScriptTone, str]:
        """OpenAI 실패 시에도 바로 쓸 수 있는 3톤 숏폼 초안을 만든다."""
        title = self._sanitize_text(issue.title)
        core_message = self._build_core_message(issue, fresh_summary=fresh_summary)
        source_label = self._extract_source_label(issue.source_url)
        run_date = self._sanitize_text(issue.run_date or "오늘")
        numeric_facts = self._extract_numeric_facts(issue, fresh_summary=fresh_summary)
        lead_fact = numeric_facts[0] if numeric_facts else "핵심 수치가 함께 발표됐습니다"
        supporting_fact = numeric_facts[1] if len(numeric_facts) > 1 else core_message
        summary_hint = self._build_summary_hint(issue, fresh_summary=fresh_summary)

        return {
            ScriptTone.NEWS: (
                f"HOOK: 이번 소식의 핵심은 {lead_fact}입니다.\n"
                f"BRIEFING: 여러분, {run_date} 기준 {source_label} 보도를 다시 보면 {title} 이슈의 초점이 더 분명해졌습니다.\n"
                f"DETAIL: 핵심은 {core_message}입니다. 기사 내용으로는 {summary_hint} 흐름이 확인됐고, {supporting_fact} 같은 수치와 사실도 함께 언급됐습니다.\n"
                f"SIGNIFICANCE: 이것이 중요한 이유는 이 사안이 앞으로의 흐름과 판단에 직접 영향을 줄 수 있기 때문입니다. 추가 발표 여부도 함께 봐야 합니다.\n"
                f"CLOSING: 여러분, 관련 내용 계속 업데이트 드리겠습니다."
            ),
            ScriptTone.STIMULATING: (
                f"HOOK: 여러분, 이번 건은 그냥 제목만 보고 넘길 일이 아닙니다. {lead_fact}.\n"
                f"PROVOCATION: 겉으로는 단순해 보여도 실제 핵심은 {core_message}입니다. 기사 본문을 다시 보면 분위기가 훨씬 무겁습니다.\n"
                f"REVELATION: 첫째, {supporting_fact}. 둘째, 기사에는 {summary_hint} 정황이 이어집니다. 마지막으로 중요한 건 {title}이 일회성 이슈로 끝나지 않을 수 있다는 점입니다.\n"
                f"EMPATHY: 여러분이 바로 영향을 받을 수 있는 문제라서 더 민감하게 봐야 합니다. 그냥 뉴스 한 줄로 끝낼 일이 아닙니다.\n"
                f"CTA: 이 내용은 꼭 저장해 두시고, 주변에도 바로 공유해 주세요."
            ),
            ScriptTone.INFORMATIVE: (
                f"HOOK: 여러분, 이번 이슈는 세 가지만 보면 바로 이해됩니다.\n"
                f"PROBLEM: 제목만 보면 맥락이 빠지기 쉽습니다. 특히 {title} 같은 이슈는 본문 내용과 수치를 같이 봐야 전체 그림이 보입니다.\n"
                f"INFO BODY: 첫 번째, 핵심 내용은 {core_message}입니다. 두 번째, 기사에서 눈에 띄는 포인트는 {summary_hint}입니다. 세 번째, 같이 나온 수치는 {lead_fact}이고 출처는 {source_label}, 날짜는 {run_date}입니다.\n"
                f"SUMMARY: 정리하면, 핵심 메시지, 주요 수치, 출처와 날짜. 이 세 가지가 포인트입니다.\n"
                f"CTA: 나중에 다시 보기 좋게 지금 바로 저장해 두세요."
            ),
        }

    def _build_core_message(self, issue: PersistedIssue, fresh_summary: str | None = None) -> str:
        """HTML이 제거된 핵심 메시지 한 줄을 만든다."""
        cleaned_summary = self._sanitize_text(fresh_summary or "")
        if cleaned_summary:
            return cleaned_summary[:240]
        cleaned_points = self._sanitize_key_points(issue.key_points)
        if cleaned_points:
            return " / ".join(cleaned_points[:3])
        return self._sanitize_text(issue.title)

    def _build_summary_hint(self, issue: PersistedIssue, fresh_summary: str | None = None) -> str:
        """본문 기반 보조 설명을 짧게 만든다."""
        cleaned_summary = self._sanitize_text(fresh_summary or "")
        if cleaned_summary:
            sentences = self._split_summary_sentences(cleaned_summary)
            if sentences:
                return sentences[0][:160]
            return cleaned_summary[:160]
        cleaned_points = self._sanitize_key_points(issue.key_points)
        if len(cleaned_points) >= 2:
            return cleaned_points[1][:160]
        return cleaned_points[0][:160] if cleaned_points else self._sanitize_text(issue.title)

    def _sanitize_key_points(self, key_points: list[str]) -> list[str]:
        """RSS/요약 원문에서 들어온 HTML 잡음을 제거한다."""
        cleaned: list[str] = []
        for point in key_points:
            normalized = self._sanitize_text(point)
            if normalized:
                cleaned.append(normalized)
        return cleaned

    def _sanitize_text(self, value: str) -> str:
        """HTML/엔티티/과도한 공백을 제거해 대본 입력용 순수 텍스트로 정리한다."""
        unescaped = html.unescape(value or "")
        without_script = re.sub(r"<script.*?>.*?</script>", " ", unescaped, flags=re.IGNORECASE | re.DOTALL)
        without_style = re.sub(r"<style.*?>.*?</style>", " ", without_script, flags=re.IGNORECASE | re.DOTALL)
        without_tags = re.sub(r"<[^>]+>", " ", without_style)
        normalized = re.sub(r"\s+", " ", without_tags).strip()
        return normalized[:240]

    def _sanitize_script_output(self, value: object) -> str:
        """모델 출력도 HTML/여분 공백 없이 정리한다."""
        if not isinstance(value, str):
            return ""
        normalized = self._sanitize_text(value)
        return normalized.replace(" HOOK:", "\nHOOK:").replace(" BRIEFING:", "\nBRIEFING:").replace(" DETAIL:", "\nDETAIL:").replace(" SIGNIFICANCE:", "\nSIGNIFICANCE:").replace(" CLOSING:", "\nCLOSING:").replace(" PROVOCATION:", "\nPROVOCATION:").replace(" REVELATION:", "\nREVELATION:").replace(" EMPATHY:", "\nEMPATHY:").replace(" CTA:", "\nCTA:").replace(" PROBLEM:", "\nPROBLEM:").replace(" INFO BODY:", "\nINFO BODY:").replace(" SUMMARY:", "\nSUMMARY:").strip()

    def _extract_numeric_facts(self, issue: PersistedIssue, fresh_summary: str | None = None) -> list[str]:
        """핵심 포인트에서 숫자/날짜가 들어간 문장을 우선 추린다."""
        summary_sentences = self._split_summary_sentences(self._sanitize_text(fresh_summary or ""))
        facts = [point for point in summary_sentences if re.search(r"\d", point)]
        if facts:
            return facts[:3]
        facts = [point for point in self._sanitize_key_points(issue.key_points) if re.search(r"\d", point)]
        if facts:
            return facts[:3]
        fallback = self._build_core_message(issue, fresh_summary=fresh_summary)
        return [fallback] if fallback else []

    def _split_summary_sentences(self, summary: str) -> list[str]:
        """짧은 요약 문장을 대본 재료 단위로 쪼갠다."""
        if not summary:
            return []
        parts = re.split(r"(?<=[.!?。！？])\s+|\s+/\s+", summary)
        return [part.strip() for part in parts if len(part.strip()) >= 20]

    def _extract_source_label(self, source_url: str) -> str:
        """출처 URL에서 도메인 중심 짧은 라벨을 만든다."""
        if not source_url:
            return "출처 미상"
        match = re.search(r"https?://([^/]+)", source_url)
        return match.group(1) if match else source_url

    def _can_use_fresh_summary_without_translation(self, fresh_summary: str | None) -> bool:
        """OpenAI 없이도 그대로 써도 될 정도로 한국어 비중이 충분한지 본다."""
        if not fresh_summary:
            return False
        hangul_count = len(re.findall(r"[가-힣]", fresh_summary))
        latin_count = len(re.findall(r"[A-Za-z]", fresh_summary))
        return hangul_count >= max(20, latin_count)

    def _rewrite_scripts_if_needed(
        self,
        issue: PersistedIssue,
        scripts: dict[ScriptTone, str],
        fresh_summary: str | None = None,
    ) -> dict[ScriptTone, str]:
        """수동 생성 스크립트가 어색할 때만 한국어 자연스러움 보정 호출을 시도한다."""
        cleaned_scripts = self._apply_local_naturalness_cleanup(scripts)
        if not any(self._needs_naturalness_rewrite(script) for script in cleaned_scripts.values()):
            return cleaned_scripts
        rewritten = self._rewrite_with_openai(issue, cleaned_scripts, fresh_summary=fresh_summary)
        if not rewritten:
            return cleaned_scripts
        return self._apply_local_naturalness_cleanup(rewritten)

    def _rewrite_with_openai(
        self,
        issue: PersistedIssue,
        scripts: dict[ScriptTone, str],
        fresh_summary: str | None = None,
    ) -> dict[ScriptTone, str] | None:
        """영문 누수나 기계적인 표현이 보이면 한 번 더 한국어로 다듬는다."""
        payload = {
            "informative": scripts.get(ScriptTone.INFORMATIVE, ""),
            "stimulating": scripts.get(ScriptTone.STIMULATING, ""),
            "news": scripts.get(ScriptTone.NEWS, ""),
        }
        summary_hint = self._sanitize_text(fresh_summary or self._build_core_message(issue))
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "너는 이미 작성된 한국어 숏폼 뉴스 대본을 다듬는 편집자다. "
                        "반드시 JSON 객체 하나만 반환하고 키는 informative, stimulating, news 만 사용한다. "
                        "구조 라벨(HOOK, BRIEFING, DETAIL, SIGNIFICANCE, CLOSING, PROVOCATION, REVELATION, EMPATHY, CTA, PROBLEM, INFO BODY, SUMMARY)은 유지하고, "
                        "각 라벨 뒤 문장만 자연스럽고 매끈한 한국어로 고친다. "
                        "영어 문장, 번역투, 제목 복붙, AI 티 나는 표현을 제거한다. 고유명사만 필요할 때 원문 표기를 허용한다."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"기사 핵심 참고: {summary_hint}\n"
                        f"제목 참고: {self._sanitize_text(issue.title)}\n"
                        "아래 JSON 대본을 더 자연스러운 한국어로만 다듬어 주세요.\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
            "temperature": 0.3,
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
                response_payload = json.loads(response.read().decode("utf-8"))
            content = response_payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            return None
        return self._coerce_generated_scripts(parsed, issue, fresh_summary=fresh_summary)

    def _needs_naturalness_rewrite(self, script: str) -> bool:
        """영문 누수나 반복적 문장이 크면 재작성 후보로 본다."""
        body = self._script_body_only(script)
        if not body:
            return False
        if len(re.findall(r"[A-Za-z]", body)) >= 24:
            return True
        suspicious_phrases = (
            "핵심 메시지",
            "실제 핵심은",
            "제목만 보면",
            "지금 들어온 소식입니다",
            "관련 발표가 나왔습니다",
            "이 뉴스는 딱 3가지만 기억하시면 됩니다",
        )
        return any(phrase in body for phrase in suspicious_phrases)

    def _apply_local_naturalness_cleanup(self, scripts: dict[ScriptTone, str]) -> dict[ScriptTone, str]:
        """모델 호출 없이도 과하게 기계적인 표현을 조금 완화한다."""
        cleaned: dict[ScriptTone, str] = {}
        replacements = {
            "실제 핵심은": "정작 중요한 건",
            "제목만 보면": "겉으로만 보면",
            "관련 발표가 나왔습니다": "관련 소식이 전해졌습니다",
            "이 뉴스는 딱 3가지만 기억하시면 됩니다": "이번 이슈는 세 가지만 보면 이해됩니다",
            "지금 들어온 소식입니다": "이번 소식의 핵심은",
        }
        for tone, script in scripts.items():
            normalized = script
            for source, target in replacements.items():
                normalized = normalized.replace(source, target)
            normalized = re.sub(r"\s+\.", ".", normalized)
            normalized = re.sub(r"\n{3,}", "\n\n", normalized)
            cleaned[tone] = normalized.strip()
        return cleaned

    def _script_body_only(self, script: str) -> str:
        """라벨을 제외한 본문만 뽑아 자연스러움 여부를 본다."""
        return re.sub(r"\b(?:HOOK|BRIEFING|DETAIL|SIGNIFICANCE|CLOSING|PROVOCATION|REVELATION|EMPATHY|CTA|PROBLEM|INFO BODY|SUMMARY):", " ", script)
