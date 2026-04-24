"""숏폼 스크립트 공통 프롬프트 자산과 조립 함수를 모아둔다."""

from __future__ import annotations

import html
import re

from ..domain.enums import ScriptTone
from ..domain.models import PersistedIssue


def build_tone_prompts(issue: PersistedIssue, fresh_summary: str | None = None) -> dict[ScriptTone, str]:
    """정보형/자극형/뉴스형 공통 프롬프트를 한 곳에서 조립한다."""
    title = _sanitize_prompt_text(issue.title)
    core_message = _build_prompt_core_message(issue, fresh_summary=fresh_summary)
    source_label = _extract_prompt_source_label(issue.source_url)
    run_date = issue.run_date or "오늘"
    source_summary_section = ""
    if fresh_summary:
        source_summary_section = (
            "\n[수동 생성용 새 기사 요약]\n"
            f"- 아래 요약은 방금 source_url에서 다시 읽은 본문 기반입니다: {_sanitize_prompt_text(fresh_summary)[:900]}\n"
            "- 저장된 key_points보다 이 요약을 우선 반영하되, 내용이 겹치면 자연스럽게 통합하세요.\n"
            "- 영어/외신 표현이 있더라도 최종 대본 문장은 모두 자연스러운 한국어여야 합니다.\n"
        )

    common_header = (
        "제목을 반복하거나 URL/도메인 소개로 문장을 채우지 말고, 기사 본문 요지를 자연스러운 한국어로 풀어쓰세요.\n"
        "해외 기사여도 최종 대본 문장은 한국어만 사용하고, 고유명사만 필요할 때 원문 표기를 남기세요.\n"
        "한국어 기사라도 어색하거나 기계적으로 들리는 표현은 구어체로 다시 다듬으세요.\n\n"
        "[다양성 원칙 — 반드시 준수]\n"
        "- 3개 타입 각각의 첫 문장 진입 방식, 섹션 수, 문장 호흡을 이슈 성격에 맞게 스스로 판단해서 선택하세요.\n"
        "- '여러분 이번 이슈는', '세 가지만 보면', '제목만 보면', '핵심은 ~입니다' 같은 상투어로 시작하지 마세요.\n"
        "- 섹션 라벨(HOOK 등)은 형식 유지를 위한 구분자일 뿐이며, 라벨 뒤 문장 내용·길이·톤은 매번 다르게 작성하세요.\n"
        "- 이슈 밀도가 낮으면 섹션을 줄이고, 높으면 핵심 섹션을 충분히 늘리세요.\n\n"
        "[공통 뉴스 정보]\n"
        f"- 제목: {title}\n"
        f"- 핵심 메시지: {core_message}\n"
        f"- 출처: {source_label}\n"
        f"- 날짜: {run_date}\n"
        f"{source_summary_section}"
    )

    return {
        ScriptTone.NEWS: (
            f"{common_header}\n"
            "[USER - TYPE 1: 뉴스형]\n"
            '아래 뉴스를 바탕으로 "뉴스형" 숏폼 대본을 작성하세요.\n\n'
            f"--- 뉴스 정보 ---\n제목: {title}\n핵심 메시지: {core_message}\n-----------------\n\n"
            "[작성 지침]\n"
            "- 어조: 차분하고 신뢰감 있는 리포터 말투. 과장·감탄사 금지.\n"
            "- 숫자·출처·날짜를 반드시 포함하고, 시청자는 \"여러분\"으로 호칭.\n"
            "- 첫 문장 진입 방식을 아래 중 이슈 성격에 맞게 하나 선택하세요.\n"
            "  A) 숫자직격형: 핵심 수치나 날짜로 바로 시작\n"
            "  B) 현장묘사형: 사건 현장·배경 분위기로 시작\n"
            "  C) 결과선언형: 최종 결과·결정 사항을 먼저 제시\n"
            "- 이슈 정보량에 따라 아래 구조에서 필요 없는 섹션은 과감히 생략하고, 각 섹션 길이도 내용에 맞게 자유롭게 조절하세요.\n\n"
            "[대본 구조 — 이슈 밀도에 따라 섹션 수·길이 자율 조정]\n"
            "HOOK (필수, 2~4초) — 진입 방식 A/B/C 중 선택\n"
            "BRIEFING (권장, 5~15초) — 핵심 팩트 압축\n"
            "DETAIL (필수, 15~35초) — 수치·배경·흐름 설명\n"
            "SIGNIFICANCE (선택, 5~10초) — 파급 의미\n"
            "CLOSING (필수, 3~5초) — 마무리\n\n"
            "[출력 형식]\n"
            "HOOK: ...\nBRIEFING: ...\nDETAIL: ...\nSIGNIFICANCE: ...\nCLOSING: ...\n\n"
            f"{_VIDEO_COMPOSITION_RULES[ScriptTone.NEWS]}"
        ),
        ScriptTone.STIMULATING: (
            f"{common_header}\n"
            "[USER - TYPE 2: 자극형]\n"
            '아래 뉴스를 바탕으로 "자극형" 숏폼 대본을 작성하세요.\n\n'
            f"--- 뉴스 정보 ---\n제목: {title}\n핵심 메시지: {core_message}\n-----------------\n\n"
            "[작성 지침]\n"
            "- 어조: 직설적·도발적, 감정이입 유도. 과도한 혐오·비하·허위 사실 금지.\n"
            "- 첫 문장은 스크롤을 멈추게 할 정도로 강해야 하지만 사실과 어긋나면 안 됩니다.\n"
            "- 감정 타깃을 이슈 성격에 맞게 하나 선택하세요: 충격 / 분노 / 불안 / 궁금증\n"
            "- HOOK 진입 방식도 이슈에 맞게 하나 선택하세요.\n"
            "  A) 반전선언형: \"이거 실화입니다\" 류, 예상과 다른 사실 선언\n"
            "  B) 질문폭격형: 시청자가 당연하다고 생각한 것을 흔드는 질문\n"
            "  C) 수치충격형: 예상 밖 숫자로 바로 시작\n"
            "  D) 경고형: \"모르면 손해\", \"지금 바로 확인해야 할\" 류\n"
            "- 이슈 강도에 따라 섹션 수와 길이를 자유롭게 조절하세요.\n"
            "- 영어 직역투 대신 한국어 숏폼 화법으로 풀어쓰세요.\n\n"
            "[대본 구조 — 이슈 강도에 따라 섹션 수·길이 자율 조정]\n"
            "HOOK (필수, 2~4초) — 진입 방식 A/B/C/D 중 선택\n"
            "PROVOCATION (권장, 5~12초) — 긴장감 고조\n"
            "REVELATION (필수, 10~30초) — 핵심 사실 폭로·전개\n"
            "EMPATHY (선택, 5~10초) — 시청자와 연결\n"
            "CTA (필수, 3~5초) — 행동 유도\n\n"
            "[출력 형식]\n"
            "HOOK: ...\nPROVOCATION: ...\nREVELATION: ...\nEMPATHY: ...\nCTA: ...\n\n"
            f"{_VIDEO_COMPOSITION_RULES[ScriptTone.STIMULATING]}"
        ),
        ScriptTone.INFORMATIVE: (
            f"{common_header}\n"
            "[USER - TYPE 3: 정보형]\n"
            '아래 뉴스를 바탕으로 "정보형" 숏폼 대본을 작성하세요.\n\n'
            f"--- 뉴스 정보 ---\n제목: {title}\n핵심 메시지: {core_message}\n-----------------\n\n"
            "[작성 지침]\n"
            "- 어조: 친근하고 명확한 설명체. 선생님·친구 말투.\n"
            "- 전문 용어는 반드시 쉬운 말로 풀고, 제목/요약 문장을 그대로 옮기지 마세요.\n"
            "- 시청자가 \"저장해야겠다\"고 느끼도록 실용성 강조.\n"
            "- 도입부 방식을 이슈에 맞게 하나 선택하세요.\n"
            "  A) 질문형: \"혹시 이거 알고 계셨나요?\" 류\n"
            "  B) 수치직격형: 핵심 숫자로 바로 진입\n"
            "  C) 비교형: Before/After, 과거vs현재 대비로 시작\n"
            "- 포인트 수는 2~4개 사이에서 자율 결정하고 길이도 조절하세요.\n\n"
            "[대본 구조 — 이슈 밀도에 따라 섹션 수·길이 자율 조정]\n"
            "HOOK (필수, 2~4초) — 도입 방식 A/B/C 중 선택\n"
            "PROBLEM (권장, 4~8초) — 왜 알아야 하는지\n"
            "INFO BODY (필수, 15~35초) — 핵심 포인트 2~4개\n"
            "SUMMARY (권장, 4~8초) — 한 줄 정리\n"
            "CTA (필수, 3~5초) — 저장·공유 유도\n\n"
            "[출력 형식]\n"
            "HOOK: ...\nPROBLEM: ...\nINFO BODY: ...\nSUMMARY: ...\nCTA: ...\n\n"
            f"{_VIDEO_COMPOSITION_RULES[ScriptTone.INFORMATIVE]}"
        ),
    }


def build_combined_generation_prompt(issue: PersistedIssue, fresh_summary: str | None = None) -> str:
    """3톤 동시 생성용 상위 OpenAI 사용자 프롬프트를 만든다."""
    prompts = build_tone_prompts(issue, fresh_summary=fresh_summary)
    ordered_keys = (
        ("informative", ScriptTone.INFORMATIVE),
        ("stimulating", ScriptTone.STIMULATING),
        ("news", ScriptTone.NEWS),
    )
    prompt_blocks = "\n\n".join(f"[{key}]\n{prompts[tone]}" for key, tone in ordered_keys)
    return (
        "아래 3가지 타입의 숏폼 대본 초안을 각각 작성하세요.\n"
        "반드시 JSON 객체 하나만 반환하고 키는 informative, stimulating, news 만 사용하세요.\n"
        "각 값은 순수 텍스트여야 하며, HTML/마크업/코드블록/추가 설명을 포함하면 안 됩니다.\n"
        "각 타입은 아래에 제공된 동일한 공통 프롬프트 규칙을 따르되, 최종 출력은 JSON 값에 대본과 영상 구성안을 함께 담아야 합니다.\n\n"
        f"{prompt_blocks}"
    )


def build_tone_prompt_payload(issue: PersistedIssue, fresh_summary: str | None = None) -> dict[str, str]:
    """UI/runtime이 바로 소비할 수 있는 문자열 키 기반 프롬프트 payload를 만든다."""
    prompts = build_tone_prompts(issue, fresh_summary=fresh_summary)
    return {tone.value: prompts.get(tone, "") for tone in ScriptTone}


def merge_tone_prompt_payload(
    prompts_by_tone: dict[ScriptTone, str],
    issue: PersistedIssue,
    fresh_summary: str | None = None,
) -> dict[str, str]:
    """생성 결과가 일부 비어 있어도 공용 프롬프트 payload를 안정적으로 맞춘다."""
    prompt_payload = build_tone_prompt_payload(issue, fresh_summary=fresh_summary)
    for tone in ScriptTone:
        prompt_text = str(prompts_by_tone.get(tone) or "").strip()
        if prompt_text:
            prompt_payload[tone.value] = prompt_text
    return prompt_payload


_VIDEO_COMPOSITION_RULES: dict[ScriptTone, str] = {
    ScriptTone.NEWS: (
        "[쇼츠 영상 구성 규칙]\n"
        "대본 출력 후 바로 아래에 영상 구성안을 출력하세요.\n"
        "전체 권장 길이는 이슈 밀도에 따라 30~60초 사이에서 자율 결정하세요.\n"
        "구간 수는 3~6개 사이에서 대본 흐름에 맞게 자율 설정하세요. 모든 구간을 같은 길이로 나누지 말고 섹션 비중에 따라 불균등하게 배분하세요.\n"
        "각 구간마다 시작~끝 초 / 화면 소재 / 자막 처리 방식을 한 줄로 작성하세요.\n"
        "화면 소재는 앵커직캠·L자막바·헤드라인자막컷·수치카드·B-roll·현장사진·인터뷰클립 중 구간별로 다르게 선택하고 같은 형식을 연속 반복하지 마세요.\n"
        "자막은 한줄속보형·L자막고정형·포인트분절형·결론안정형·숫자카운트업형 중 구간별로 다르게 지정하세요.\n"
        "BGM 및 편집 주의사항을 마지막에 한 줄로 작성하세요.\n"
        "설명이나 메모 없이 구성안 본문만 출력하세요."
    ),
    ScriptTone.STIMULATING: (
        "[쇼츠 영상 구성 규칙]\n"
        "대본 출력 후 바로 아래에 영상 구성안을 출력하세요.\n"
        "전체 권장 길이는 이슈 강도에 따라 30~60초 사이에서 자율 결정하세요.\n"
        "구간 수는 3~6개 사이에서 대본 흐름에 맞게 자율 설정하세요. 충격→전개→반전→마무리 호흡에 따라 구간 길이를 불균등하게 배분하세요.\n"
        "각 구간마다 시작~끝 초 / 화면 소재 / 자막 처리 방식을 한 줄로 작성하세요.\n"
        "화면 소재는 풀스크린강조자막·수치충격카드·B-roll·헤드라인컷·비교슬라이드·키워드애니메이션·반응형GIF 중 구간별로 다르게 선택하고 같은 형식을 연속 반복하지 마세요.\n"
        "자막은 한줄강조형·키워드점멸형·포인트분절형·결론안정형·카운트다운형 중 구간별로 다르게 지정하세요.\n"
        "BGM 및 편집 주의사항을 마지막에 한 줄로 작성하세요.\n"
        "설명이나 메모 없이 구성안 본문만 출력하세요."
    ),
    ScriptTone.INFORMATIVE: (
        "[쇼츠 영상 구성 규칙]\n"
        "대본 출력 후 바로 아래에 영상 구성안을 출력하세요.\n"
        "전체 권장 길이는 이슈 정보량에 따라 30~60초 사이에서 자율 결정하세요.\n"
        "구간 수는 3~6개 사이에서 대본 흐름에 맞게 자율 설정하세요. 포인트 수에 따라 구간 길이를 불균등하게 배분하세요.\n"
        "각 구간마다 시작~끝 초 / 화면 소재 / 자막 처리 방식을 한 줄로 작성하세요.\n"
        "화면 소재는 정보카드·수치인포그래픽·비교슬라이드·체크리스트애니메이션·B-roll·풀스크린키워드·요약카드 중 구간별로 다르게 선택하고 같은 형식을 연속 반복하지 마세요.\n"
        "자막은 포인트분절형·숫자카운트업형·한줄강조형·결론안정형·키워드순차노출형 중 구간별로 다르게 지정하세요.\n"
        "BGM 및 편집 주의사항을 마지막에 한 줄로 작성하세요.\n"
        "설명이나 메모 없이 구성안 본문만 출력하세요."
    ),
}


def _sanitize_prompt_text(value: str) -> str:
    """공통 프롬프트 조합용 간단 텍스트 정제 함수다."""
    unescaped = html.unescape(value or "")
    without_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", without_tags).strip()[:900]


def _build_prompt_core_message(issue: PersistedIssue, fresh_summary: str | None = None) -> str:
    """공통 프롬프트용 핵심 메시지를 만든다."""
    cleaned_summary = _sanitize_prompt_text(fresh_summary or "")
    if cleaned_summary:
        return cleaned_summary[:240]
    cleaned_points = [_sanitize_prompt_text(point) for point in issue.key_points if _sanitize_prompt_text(point)]
    if cleaned_points:
        return " / ".join(cleaned_points[:3])
    return _sanitize_prompt_text(issue.title)


def _extract_prompt_source_label(source_url: str) -> str:
    """공통 프롬프트용 출처 라벨을 만든다."""
    if not source_url:
        return "출처 미상"
    match = re.search(r"https?://([^/]+)", source_url)
    return match.group(1) if match else source_url
