"""고소장 생성 파이프라인.

  analyze  : 공식 조문·판례 원문을 근거로 구성요건별 충족 여부와 적용 법조를 검토
  draft    : 검토 결과를 바탕으로 고소장 각 항목 작성
  review   : 규칙 검사(조문 번호 화이트리스트, 금액·일시, 문체, 빈칸) + AI 교차 검토
  revise   : 문제가 있으면 한 번 고쳐 쓰기
  render   : 경찰청 표준 양식 docx/pdf

모델에는 당사자 인적사항(이름·주민번호·주소·연락처)을 보내지 않는다. 문서에서는
'고소인'·'피고소인'으로만 지칭하고, 인적사항은 렌더링 단계에서 양식 표에만 들어간다.
"""

import asyncio
import json
import logging
import re

from system.llm import LLMError

from app.legal import kb
from app.legal.crimes import CRIMES, FACTS, fact_keys_for
from app.services import document
from app.services.llm_io import chat_json

logger = logging.getLogger(__name__)

SECTION_KEYS = ["suspect_other", "purpose", "facts", "reasons", "evidence", "others"]
SECTION_LABELS = {
    "suspect_other": "피고소인 기타사항",
    "purpose": "3. 고소취지",
    "facts": "4. 범죄사실",
    "reasons": "5. 고소이유",
    "evidence": "6. 증거자료",
    "others": "8. 기타",
}

# 사기죄 구성요건 — 판례(대법원 2017도20682 등)가 쓰는 틀 그대로
ELEMENTS = {
    "default": [
        (
            "기망행위",
            "피고소인이 거래상 중요한 사실에 관하여 거짓말을 하거나 알려야 할 사실을 숨겼는지",
        ),
        ("착오", "고소인이 그 말을 믿어 사실과 다르게 알게 되었는지"),
        ("처분행위", "착오에 빠진 고소인이 돈·물건을 넘기는 등 재산을 처분했는지"),
        (
            "재산상 이익 취득·손해",
            "그 결과 피고소인이 재물이나 재산상 이익을 얻었는지(금액 특정)",
        ),
        (
            "편취의 고의",
            "행위 당시부터 갚거나 이행할 의사·능력이 없었다고 볼 객관적 사정이 있는지",
        ),
    ],
    "보험사기": [
        (
            "보험사기행위",
            "보험사고의 발생·원인·내용에 관하여 보험자를 기망하여 보험금을 청구했는지",
        ),
        ("보험금 취득", "그로 인해 보험금을 받거나 제3자가 받게 했는지(금액 특정)"),
        ("고의", "허위임을 알면서 청구했다고 볼 사정이 있는지"),
    ],
    "소송사기": [
        (
            "허위 주장·증거",
            "피고소인이 허위의 주장이나 조작된 증거로 법원을 속이려 했는지",
        ),
        ("소송 제기", "법원에 소를 제기하는 등 실행에 착수했는지(법원·사건번호)"),
        ("재산상 이익", "승소하면 얻게 될 재산상 이익이 무엇인지(금액)"),
        ("고의", "주장이 허위임을 알고 있었다고 볼 사정이 있는지"),
    ],
}


def _facts_for_prompt(crime_id: str, facts: dict) -> str:
    rows = []
    for k in fact_keys_for(crime_id):
        v = str(facts.get(k) or "").strip()
        if v:
            rows.append(f"- {FACTS[k]['label']}: {v}")
    return "\n".join(rows) or "(없음)"


def _statute_block(statutes: list[dict]) -> str:
    return "\n\n".join(
        f"[{s['id']}] {s['label']}({s['title']}) — 시행 {s['effective']}\n{s['text']}\n→ 검토 이유: {s.get('reason', '')}"
        for s in statutes
    )


def _precedent_block(precs: list[dict]) -> str:
    return (
        "\n\n".join(
            f"[{p['court']} {p['case_no']}] 판시사항: {p['points'][:300]}\n판결요지: {p['summary'][:700]}"
            for p in precs
        )
        or "(없음)"
    )


ANALYZE_SYSTEM = """너는 형사 고소 사건을 검토하는 법률 전문가다. 아래 [사실관계]를 [법령 원문]과 [판례 원문]에 비추어 검토한다.

반드시 아래 형식의 JSON 객체 하나만 출력한다.
{
  "offense": "고소취지에 쓸 죄명(예: 사기)",
  "applicable": [{"id": "법령 원문 목록의 [id]", "why": "이 사건에 적용되는 이유 1~2문장"}],
  "elements": [{"name": "구성요건 이름", "status": "충족|보완필요|불명확", "basis": "그렇게 판단한 사실 근거", "advice": "보완이 필요하면 무엇을 더 적거나 준비할지"}],
  "civil_risk": "단순 민사(채무불이행 등)로 판단될 위험과 그 이유, 없으면 빈 문자열",
  "strengths": ["고소에 유리한 사정"],
  "weaknesses": ["부족하거나 불리한 사정"],
  "evidence_tips": ["추가로 준비하면 좋은 증거"]
}

[규칙]
- applicable 의 id 는 반드시 [법령 원문]에 있는 [id] 중에서만 고른다. 목록에 없는 법조는 쓰지 않는다.
- 판단 근거는 제공된 사실에서만 찾는다. 사실을 지어내지 않는다.
- elements 는 [검토할 구성요건] 순서대로 모두 포함한다.
- 법적 판단은 단정하지 않는다."""


async def analyze(
    crime_id: str, facts: dict, statutes: list[dict], precedents: list[dict]
) -> dict:
    crime = CRIMES[crime_id]
    elements = ELEMENTS.get(crime_id, ELEMENTS["default"])
    user = (
        f"[사건 유형] {crime.label} — {crime.summary}\n\n"
        f"[사실관계]\n{_facts_for_prompt(crime_id, facts)}\n\n"
        f"[검토할 구성요건]\n" + "\n".join(f"- {n}: {d}" for n, d in elements) + "\n\n"
        f"[법령 원문]\n{_statute_block(statutes)}\n\n"
        f"[판례 원문]\n{_precedent_block(precedents)}\n\nJSON만 출력하세요."
    )
    data = await chat_json(
        [
            {"role": "system", "content": ANALYZE_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.15,
        max_tokens=2500,
    )
    return _clean_analysis(data, crime, statutes, elements)


def _clean_analysis(data: dict, crime, statutes: list[dict], elements) -> dict:
    allowed = {s["id"]: s for s in statutes}
    applicable = []
    for a in data.get("applicable") or []:
        if (
            isinstance(a, dict)
            and a.get("id") in allowed
            and a["id"] not in [x["id"] for x in applicable]
        ):
            s = allowed[a["id"]]
            applicable.append(
                {
                    "id": s["id"],
                    "label": s["label"],
                    "title": s["title"],
                    "why": str(a.get("why", ""))[:400],
                    "url": s["url"],
                }
            )
    if not applicable and crime.statutes and crime.statutes[0] in allowed:
        s = allowed[crime.statutes[0]]
        applicable.append(
            {
                "id": s["id"],
                "label": s["label"],
                "title": s["title"],
                "why": "이 사건 유형의 기본 처벌 규정입니다.",
                "url": s["url"],
            }
        )

    by_name = {
        str(e.get("name", "")).strip(): e
        for e in (data.get("elements") or [])
        if isinstance(e, dict)
    }
    els = []
    for name, desc in elements:
        e = by_name.get(name) or next(
            (v for k, v in by_name.items() if name[:2] in k), {}
        )
        status = str(e.get("status", "불명확"))
        if status not in ("충족", "보완필요", "불명확"):
            status = "불명확"
        els.append(
            {
                "name": name,
                "desc": desc,
                "status": status,
                "basis": str(e.get("basis", ""))[:500],
                "advice": str(e.get("advice", ""))[:500],
            }
        )

    def str_list(key, n=6):
        return [str(x)[:300] for x in (data.get(key) or []) if str(x).strip()][:n]

    offense = (
        str(data.get("offense") or crime.offense_name).strip()[:40]
        or crime.offense_name
    )
    return {
        "offense": offense,
        "applicable": applicable,
        "elements": els,
        "civil_risk": str(data.get("civil_risk") or "")[:800],
        "strengths": str_list("strengths"),
        "weaknesses": str_list("weaknesses"),
        "evidence_tips": str_list("evidence_tips") or crime.evidence_tips,
    }


DRAFT_SYSTEM = """너는 경찰청 표준 고소장 양식에 맞춰 고소장을 쓰는 법률 문서 작성자다. 변호사가 쓴 것처럼 정확하고 구체적으로 쓴다.

반드시 아래 키를 가진 JSON 객체 하나만 출력한다(값은 문자열, 줄바꿈은 \\n).
{"suspect_other": "...", "purpose": "...", "facts": "...", "reasons": "...", "evidence": "...", "others": "..."}

[항목별 작성법]
- suspect_other(피고소인 기타사항): 고소인과의 관계, 피고소인을 특정할 수 있는 정보(닉네임·계좌 명의·인상착의·연락 수단 등). 이름·주민번호·주소·전화·이메일은 쓰지 않는다.
- purpose(고소취지): "고소인은 피고소인을 {죄명}({적용 법조}) 혐의로 고소하오니, 철저히 수사하여 엄중히 처벌하여 주시기 바랍니다." 형식. 적용 법조는 [적용 법조]에 있는 것만 쓴다.
- facts(범죄사실): 일시(시각 포함, 모르면 '경' 또는 '불상'), 장소, 기망 내용(피고소인이 한 말은 큰따옴표로 인용), 고소인이 속은 경위, 처분행위(이체 일시·금액·계좌 등), 피해 결과를 시간 순서대로 쓴다. 편취의 고의를 보여주는 사정(당시 변제능력 없음, 연락 두절, 다른 피해자 등)이 있으면 포함한다. 마지막 문장은 "피고소인은 이와 같이 고소인을 기망하여 이에 속은 고소인으로부터 ○○을 교부받아 이를 편취하였습니다." 형태로 맺되 ○○은 실제 금액·물건으로 쓴다.
- reasons(고소이유): 범행 경위와 정황, 편취의 고의를 뒷받침하는 사정, 고소하게 된 동기. 마지막에 합의 여부와 처벌 의사를 반드시 쓴다(예: "피고소인과는 합의하지 않았으며, 피고소인의 처벌을 원합니다.").
- evidence(증거자료): "1. ...\\n2. ..." 번호 목록. 사실에 언급된 증거만 쓴다. 없으면 빈 문자열.
- others(기타): 수사에 필요한 추가 사항. 없으면 빈 문자열.

[반드시 지킬 것]
- 모든 문장은 '~습니다/~입니다' 체로 끝낸다.
- 고소인 자신은 '고소인', 상대방은 '피고소인'으로만 지칭한다.
- [사실관계]에 없는 사실(날짜·금액·장소·말)을 절대 지어내지 않는다. 모르는 부분은 '불상'으로 쓴다.
- 금액은 '금 3,000,000원'처럼 숫자와 쉼표로 쓴다.
- 법조문 번호는 [적용 법조]에 있는 것만 쓴다."""


async def draft(
    crime_id: str, facts: dict, analysis: dict, statutes: list[dict]
) -> dict:
    applicable = analysis["applicable"] or [
        {"label": s["label"], "title": s["title"]} for s in statutes[:1]
    ]
    law_line = ", ".join(f"{a['label']}({a['title']})" for a in applicable)
    weak = "\n".join(f"- {e['name']}: {e['basis']}" for e in analysis["elements"])
    user = (
        f"[죄명] {analysis['offense']}\n[적용 법조] {law_line}\n\n"
        f"[사실관계]\n{_facts_for_prompt(crime_id, facts)}\n\n"
        f"[구성요건 검토 결과 — 범죄사실에 각 요건의 사실이 드러나게 쓸 것]\n{weak}\n\nJSON만 출력하세요."
    )
    data = await chat_json(
        [
            {"role": "system", "content": DRAFT_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.25,
        max_tokens=3500,
    )
    return {k: str(data.get(k) or "").strip() for k in SECTION_KEYS}


# ── 검증 ─────────────────────────────────────────────────────────────────────
_ARTICLE_RE = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")
_PLACEHOLDER_RE = re.compile(r"○○|OO|XXX|\[[^\]]{0,20}\]|\{[^}]{0,20}\}|\(예시")
_PLAIN_END_RE = re.compile(r"(?<![니요])다\.\s*$")


def rule_check(sections: dict, facts: dict, allowed_articles: set[str]) -> list[dict]:
    issues = []
    whole = "\n".join(sections.get(k, "") for k in SECTION_KEYS)

    for m in _ARTICLE_RE.finditer(whole):
        art = m.group(1) + (f"의{m.group(2)}" if m.group(2) else "")
        if art not in allowed_articles:
            issues.append(
                {
                    "section": "전체",
                    "level": "error",
                    "problem": f"검토하지 않은 조문(제{art}조)이 인용되었습니다.",
                    "fix": "적용 법조 목록에 있는 조문만 인용하세요.",
                }
            )

    amount = kb.parse_krw(facts.get("damage_amount", ""))
    if amount:
        found = kb.parse_krw(sections.get("facts", ""))
        text_digits = re.sub(r"[^\d]", "", sections.get("facts", ""))
        if not found or (str(amount) not in text_digits and found < amount):
            issues.append(
                {
                    "section": "4. 범죄사실",
                    "level": "warn",
                    "problem": f"피해 금액({kb.format_krw(amount)})이 범죄사실에 정확히 드러나지 않습니다.",
                    "fix": "범죄사실에 피해 금액을 숫자로 명시하세요.",
                }
            )

    if len(sections.get("facts", "")) < 120:
        issues.append(
            {
                "section": "4. 범죄사실",
                "level": "error",
                "problem": "범죄사실이 너무 짧습니다.",
                "fix": "일시·장소·기망 내용·처분행위·결과를 모두 적으세요.",
            }
        )

    for k in ("purpose", "facts", "reasons"):
        text = sections.get(k, "")
        if _PLACEHOLDER_RE.search(text):
            issues.append(
                {
                    "section": SECTION_LABELS[k],
                    "level": "error",
                    "problem": "빈칸 표시(○○ 등)가 남아 있습니다.",
                    "fix": "실제 내용으로 채우거나 '불상'으로 쓰세요.",
                }
            )
        bad = [ln for ln in re.split(r"(?<=[.])\s+", text) if _PLAIN_END_RE.search(ln)]
        if bad:
            issues.append(
                {
                    "section": SECTION_LABELS[k],
                    "level": "warn",
                    "problem": "평어체(~다.)로 끝나는 문장이 있습니다.",
                    "fix": "'~습니다'체로 통일하세요.",
                }
            )

    if facts.get("punishment_wish") and "처벌" not in sections.get("reasons", ""):
        issues.append(
            {
                "section": "5. 고소이유",
                "level": "warn",
                "problem": "처벌 의사 문장이 없습니다.",
                "fix": "고소이유 끝에 합의 여부와 처벌 의사를 적으세요.",
            }
        )
    return issues


REVIEW_SYSTEM = """너는 경찰 수사관의 시각으로 고소장 초안을 검토하는 검토자다.
[사실관계]와 [초안]을 비교해 다음을 확인한다.
1) 초안에 사실관계에 없는 내용(지어낸 날짜·금액·말·장소)이 들어갔는지
2) 사실관계에 있는 중요한 사실(특히 기망 내용, 이체 내역, 편취 고의 정황)이 빠졌는지
3) 일시·금액·당사자 지칭이 정확하고 일관되는지
4) [규칙 검사 결과]에 나온 문제

반드시 아래 형식의 JSON 하나만 출력한다.
{"issues": [{"section": "항목 이름", "problem": "문제", "fix": "고칠 방법"}],
 "revised": {"suspect_other": "...", "purpose": "...", "facts": "...", "reasons": "...", "evidence": "...", "others": "..."}}
- 문제가 없으면 issues 는 [] 이고 revised 는 null 이다.
- 문제가 있으면 revised 에 모든 항목을 고친 최종본을 넣는다. 고칠 때도 사실을 지어내지 않고, 조문 번호는 초안에 이미 있던 것만 쓴다."""


async def review(
    crime_id: str, facts: dict, sections: dict, rule_issues: list[dict]
) -> dict:
    user = (
        f"[사실관계]\n{_facts_for_prompt(crime_id, facts)}\n\n"
        f"[초안]\n{json.dumps(sections, ensure_ascii=False)}\n\n"
        f"[규칙 검사 결과]\n"
        + (
            "\n".join(f"- {i['section']}: {i['problem']}" for i in rule_issues)
            or "(문제 없음)"
        )
        + "\n\nJSON만 출력하세요."
    )
    data = await chat_json(
        [
            {"role": "system", "content": REVIEW_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=4000,
    )
    issues = [
        {
            "section": str(i.get("section", ""))[:40],
            "level": "warn",
            "problem": str(i.get("problem", ""))[:300],
            "fix": str(i.get("fix", ""))[:300],
        }
        for i in (data.get("issues") or [])
        if isinstance(i, dict) and i.get("problem")
    ]
    revised = data.get("revised")
    if isinstance(revised, dict) and all(
        isinstance(revised.get(k, ""), str) for k in SECTION_KEYS
    ):
        revised = {
            k: str(revised.get(k) or sections.get(k, "")).strip() for k in SECTION_KEYS
        }
    else:
        revised = None
    return {"issues": issues, "revised": revised}


def allowed_articles(statutes: list[dict]) -> set[str]:
    arts = {s.get("article") or s["id"].split("-", 1)[-1] for s in statutes}
    arts |= {s["article"] for s in kb.procedure_statutes()}
    return arts


def limitation_note(crime_id: str, analysis: dict, facts: dict) -> str:
    """참고용 공소시효 안내 — 지식베이스 원문의 법정형으로 계산한다."""
    core = next(
        (
            kb.STATUTE_BY_ID[a["id"]]
            for a in analysis["applicable"]
            if a["id"] in kb.STATUTE_BY_ID
        ),
        None,
    )
    if not core:
        return ""
    years = kb.limitation_years(core)
    if not years:
        return ""
    when = facts.get("incident_datetime", "")
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", when)
    until = (
        f" 범행일({m.group(1)}년 {int(m.group(2))}월 {int(m.group(3))}일)로부터 계산하면 {int(m.group(1)) + years}년 {int(m.group(2))}월경까지입니다."
        if m
        else ""
    )
    return (
        f"{core['label']}의 법정형 기준 공소시효는 형사소송법 제249조 제1항에 따라 {years}년입니다.{until} "
        "피해액·가중처벌 여부·범행 종료 시점에 따라 달라질 수 있으니 참고용으로만 보세요."
    )


async def generate(case: dict):
    """NDJSON 이벤트를 흘려보내며 case를 채운다. 마지막에 result 이벤트."""
    crime_id = case["crime_type"]
    facts = case["facts"]
    crime = CRIMES[crime_id]

    yield {"type": "step", "step": "research", "status": "start"}
    statutes = kb.statutes_for_case(crime_id, facts)
    query = " ".join(
        str(facts.get(k, "")) for k in ("deception", "intent_evidence", "post_conduct")
    )
    precedents = kb.search_precedents(query, crime_id, k=3)
    live = await asyncio.to_thread(
        kb.live_precedents, f"{crime.label} {facts.get('deception', '')[:40]}", 2
    )
    precedents = (
        precedents + [p for p in live if p["id"] not in {x["id"] for x in precedents}]
    )[:4]
    yield {
        "type": "step",
        "step": "research",
        "status": "done",
        "detail": f"법령 {len(statutes)}개 · 판례 {len(precedents)}건 검토",
    }

    yield {"type": "step", "step": "analyze", "status": "start"}
    analysis = await analyze(crime_id, facts, statutes, precedents)
    analysis["limitation"] = limitation_note(crime_id, analysis, facts)
    analysis["precedents"] = [
        {k: p.get(k) for k in ("case_no", "court", "date", "points", "summary", "url")}
        for p in precedents
    ]
    analysis["statutes"] = [
        {
            k: s.get(k)
            for k in (
                "id",
                "article",
                "label",
                "title",
                "text",
                "effective",
                "url",
                "reason",
                "role",
            )
        }
        for s in statutes
    ]
    analysis["procedure"] = [
        {k: s.get(k) for k in ("id", "label", "title", "text", "effective", "url")}
        for s in kb.procedure_statutes()
        + [kb.STATUTE_BY_ID[i] for i in ("001215-26",) if i in kb.STATUTE_BY_ID]
    ]
    ok = sum(1 for e in analysis["elements"] if e["status"] == "충족")
    yield {
        "type": "step",
        "step": "analyze",
        "status": "done",
        "detail": f"구성요건 {len(analysis['elements'])}개 중 {ok}개 충족",
    }

    yield {"type": "step", "step": "draft", "status": "start"}
    sections = await draft(crime_id, facts, analysis, statutes)
    yield {"type": "step", "step": "draft", "status": "done"}

    yield {"type": "step", "step": "review", "status": "start"}
    allowed = allowed_articles(statutes)
    issues = rule_check(sections, facts, allowed)
    try:
        rv = await review(crime_id, facts, sections, issues)
    except LLMError as e:
        logger.warning("교차 검토 실패(초안 유지): %s", e)
        rv = {"issues": [], "revised": None}
    revised_applied = False
    if rv["revised"]:
        new_issues = rule_check(rv["revised"], facts, allowed)
        # 고친 판이 규칙 검사에서 더 나빠지지 않을 때만 채택한다
        if sum(i["level"] == "error" for i in new_issues) <= sum(
            i["level"] == "error" for i in issues
        ):
            sections, issues, revised_applied = rv["revised"], new_issues, True
    # 끝까지 남은 조문 오류는 기계적으로 제거하지 않고 사용자에게 보여준다
    final_issues = issues + ([] if revised_applied else rv["issues"])
    yield {
        "type": "step",
        "step": "review",
        "status": "done",
        "detail": (
            "검토 의견을 반영해 수정했습니다" if revised_applied else "검토 완료"
        )
        + (f" · 확인 필요 {len(final_issues)}건" if final_issues else ""),
    }

    yield {"type": "step", "step": "render", "status": "start"}
    files = await asyncio.to_thread(
        document.render, case["party"], facts, sections, analysis["offense"]
    )
    yield {"type": "step", "step": "render", "status": "done"}

    case["analysis"] = analysis
    case["draft"] = sections
    case["review"] = {"issues": final_issues, "revised": revised_applied}
    case["files"] = files
    yield {
        "type": "result",
        "analysis": analysis,
        "draft": sections,
        "review": case["review"],
        "files": files,
    }
