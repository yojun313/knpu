"""AI 상담 채팅 — 대화하면서 고소장에 필요한 사실관계를 모으는 에이전트.

한 턴의 흐름
  1) 추출: 사용자 발화에서 사건 유형과 사실 항목(FACTS 키)을 JSON으로 뽑아 병합
  2) 계획: 유형별 필수 사실(구성요건) 중 빈 항목을 우선순위대로 고른다
  3) 검색: 지식베이스(공식 조문·판례 원문)에서 근거를 찾는다
  4) 응답: 근거 안에서만 설명하고, 다음에 필요한 질문을 1~2개 한다 (스트리밍)

법률 설명의 근거는 항상 3)에서 찾은 원문뿐이다. 모델이 조문 번호나 형량을
기억으로 말하지 않게 프롬프트로 막고, 화면에는 원문 카드를 함께 보여준다.
"""

import difflib
import json
import logging
import time

from system.llm import LLMError

from app.legal import kb
from app.legal.crimes import (
    CRIMES,
    FACTS,
    completeness,
    fact_keys_for,
    missing_required,
)
from app.services.llm_io import chat_json, stream_text

logger = logging.getLogger(__name__)

GREETING = (
    "안녕하세요, FPEI AI 고소장 작성 도우미입니다.\n\n"
    "어떤 피해를 입으셨는지 편하게 말씀해 주세요. 언제, 누구에게, 어떤 말에 속아 "
    "얼마를 보내셨는지 기억나는 대로 적어 주시면 제가 고소장에 필요한 내용을 "
    "하나씩 정리해 드릴게요.\n\n"
    "주민등록번호 같은 개인정보는 여기서 적지 않으셔도 됩니다. 마지막 단계의 입력 양식에서 따로 받습니다."
)

STARTER_SUGGESTIONS = [
    "중고거래로 돈을 보냈는데 물건이 안 와요",
    "빌려준 돈을 갚지 않고 연락이 끊겼어요",
    "게임 아이템 거래에서 사기를 당했어요",
    "취업시켜 준다며 돈을 받아 갔어요",
]

_HISTORY_TURNS = 12


def _crime_catalog() -> str:
    return "\n".join(f"- {c.id}: {c.summary}" for c in CRIMES.values())


def _facts_catalog(crime_id: str | None) -> str:
    keys = fact_keys_for(crime_id) if crime_id else list(FACTS)
    lines = []
    for k in keys:
        f = FACTS[k]
        opt = f" (다음 중 하나: {', '.join(f['options'])})" if f.get("options") else ""
        lines.append(f"- {k}: {f['label']} — {f['ask']}{opt}")
    return "\n".join(lines)


def _facts_text(facts: dict) -> str:
    rows = [
        f"- {FACTS[k]['label']}: {v}"
        for k, v in facts.items()
        if k in FACTS and str(v).strip()
    ]
    return "\n".join(rows) or "(아직 없음)"


def _normalize_choice(key: str, value: str) -> str:
    opts = FACTS[key].get("options")
    if not opts:
        return value
    if value in opts:
        return value
    v = value.replace(" ", "")
    for o in opts:
        if o.replace(" ", "") in v or v in o.replace(" ", ""):
            return o
    # "안 했어요" 같은 부정 표현
    neg = any(w in v for w in ("않", "안했", "안함", "없", "아니"))
    if key == "settlement":
        return "합의하지 않음" if neg or "합의" not in v else "합의하였음"
    if key == "punishment_wish":
        return "처벌 원하지 않음" if "원하지" in v or "원치" in v else "처벌 원함"
    close = difflib.get_close_matches(value, opts, n=1, cutoff=0.3)
    return close[0] if close else value


EXTRACT_SYSTEM = """너는 고소장 작성을 돕는 사건 정리 담당자다. 대화에서 사실관계만 뽑아 JSON으로 정리한다.

[사건 유형 목록]
{crimes}

[사실 항목 목록 (키: 설명)]
{facts}

[규칙]
- 반드시 JSON 객체 하나만 출력한다. 형식:
  {{"crime_type": "유형 id 또는 null", "crime_confidence": 0~1 숫자, "facts": {{"키": "값"}}}}
- facts 에는 이번 사용자 발화로 새로 알게 되었거나 바뀐 항목만 넣는다.
- 값은 기존에 정리된 내용과 새 내용을 합친 '완성된 문장'으로 쓴다(기존 내용을 지우지 말 것).
- 사용자가 말하지 않은 사실은 절대 추측해서 채우지 않는다. 모르면 넣지 않는다.
- 사용자가 '모른다', '없다'고 분명히 답한 항목은 "모름" 또는 "없음"으로 적는다.
- 날짜·시각·금액·계좌·말한 내용은 사용자가 말한 그대로 보존한다(날짜는 연-월-일 시:분 형식이 가능하면 그렇게).
- 선택형 항목은 제시된 보기 중 하나로만 적는다.
- crime_type 은 목록의 id 중 가장 알맞은 것. 판단할 정보가 없으면 null.
- 이름·주민등록번호·주소·전화번호 같은 개인 식별정보는 facts 에 넣지 않는다(피고소인을 특정할 닉네임·계좌 명의 등은 suspect_description 에 넣어도 된다)."""


async def extract(case: dict, user_text: str) -> dict:
    crime_id = case.get("crime_type")
    history = case["messages"][-6:]
    convo = "\n".join(
        f"{'사용자' if m['role'] == 'user' else '상담원'}: {m['content']}"
        for m in history
    )
    messages = [
        {
            "role": "system",
            "content": EXTRACT_SYSTEM.format(
                crimes=_crime_catalog(), facts=_facts_catalog(crime_id)
            ),
        },
        {
            "role": "user",
            "content": (
                f"[현재 사건 유형] {crime_id or '미정'}\n\n"
                f"[지금까지 정리된 사실]\n{json.dumps(case['facts'], ensure_ascii=False)}\n\n"
                f"[최근 대화]\n{convo}\n\n"
                f"[이번 사용자 발화]\n{user_text}\n\n"
                "JSON만 출력하세요."
            ),
        },
    ]
    return await chat_json(messages, temperature=0.1, max_tokens=1500)


def merge_extraction(case: dict, data: dict) -> list[str]:
    """추출 결과를 사건에 반영하고, 바뀐 사실 키 목록을 돌려준다."""
    changed = []
    ct = data.get("crime_type")
    try:
        conf = float(data.get("crime_confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if isinstance(ct, str) and ct in CRIMES and ct != case.get("crime_type"):
        # 이미 유형이 정해졌다면 확신이 높을 때만 바꾼다(대화 중 흔들림 방지)
        if not case.get("crime_type") or conf >= 0.75:
            case["crime_type"] = ct
            changed.append("crime_type")
    facts = data.get("facts") or {}
    if isinstance(facts, dict):
        for k, v in facts.items():
            if k not in FACTS or v is None:
                continue
            v = str(v).strip()
            if not v or v.lower() in ("null", "none"):
                continue
            v = _normalize_choice(k, v)[:4000]
            if case["facts"].get(k) != v:
                case["facts"][k] = v
                changed.append(k)
    return changed


def suggestions_for(case: dict, missing: list[str]) -> list[str]:
    if not case.get("crime_type") and not case["facts"]:
        return STARTER_SUGGESTIONS
    if missing:
        f = FACTS[missing[0]]
        if f.get("options"):
            return list(f["options"])
        if missing[0] in ("repayment", "other_victims"):
            return (
                ["없음", "일부 돌려받았어요"]
                if missing[0] == "repayment"
                else ["없음", "모름", "있어요"]
            )
        return ["잘 모르겠어요"]
    return []


def case_state(case: dict) -> dict:
    """화면 오른쪽 '사건 정리' 패널에 보낼 상태."""
    crime_id = case.get("crime_type")
    missing = missing_required(crime_id, case["facts"])
    statutes = kb.statutes_for_case(crime_id, case["facts"]) if crime_id else []
    query = " ".join(
        str(case["facts"].get(k, ""))
        for k in ("deception", "intent_evidence", "post_conduct", "disposition")
    )
    precedents = kb.search_precedents(query, crime_id, k=3) if crime_id else []
    return {
        "crime_type": crime_id,
        "crime_label": CRIMES[crime_id].label if crime_id in CRIMES else None,
        "facts": case["facts"],
        "fields": fact_keys_for(crime_id),
        "missing": missing,
        "completeness": completeness(crime_id, case["facts"]),
        "ready": bool(crime_id) and not missing,
        "statutes": [_statute_card(s) for s in statutes],
        "precedents": [_precedent_card(p) for p in precedents],
        "suggestions": suggestions_for(case, missing),
    }


def _statute_card(s: dict) -> dict:
    return {
        k: s.get(k)
        for k in ("id", "label", "title", "text", "effective", "url", "reason", "role")
    }


def _precedent_card(p: dict) -> dict:
    return {
        k: p.get(k)
        for k in ("id", "case_no", "court", "date", "points", "summary", "url")
    }


REPLY_SYSTEM = """너는 경찰청 표준 고소장 작성을 돕는 'FPEI AI 고소장 작성 도우미'다. 사기 피해자와 대화하며 고소장에 필요한 사실을 빠짐없이 모은다.

[말투와 형식]
- 한국어 존댓말. 따뜻하지만 간결하게, 3~6문장.
- 먼저 사용자가 방금 말한 핵심을 한 문장으로 확인한다.
- 그다음 [다음에 물어볼 항목]의 첫 번째(필요하면 두 번째까지)만 자연스럽게 묻는다. 여러 개를 한꺼번에 나열하지 않는다.
- 굵게(**)만 쓸 수 있다. 표·제목·코드블록은 쓰지 않는다.

[법률 설명 규칙 — 매우 중요]
- 법 조문·형량·판례는 아래 [참고 법령]·[참고 판례]에 적힌 원문에 있는 내용만 말한다. 거기에 없는 조문 번호·형량·판례 번호는 절대 지어내지 않는다.
- 범죄 성립을 단정하지 않는다("사기죄에 해당할 수 있습니다" 처럼 말한다).
- 돈을 빌려준 뒤 못 받은 사건은, 빌릴 당시부터 갚을 의사나 능력이 없었다는 사정이 있어야 사기죄가 되고 그렇지 않으면 민사상 채무불이행일 수 있다는 점을 필요할 때 부드럽게 설명하고 그 사정을 묻는다.
- 법률 설명은 사용자가 묻거나 꼭 필요할 때만 1~2문장으로.

[그 밖의 규칙]
- 이름·주민등록번호·주소·전화번호는 묻지 않는다(다음 단계 양식에서 받는다).
- 보이스피싱 등으로 지금도 돈이 빠져나가고 있거나 위험이 진행 중이면, 즉시 112 신고와 송금 은행에 지급정지를 요청하라고 가장 먼저 안내한다.
- 필수 항목이 모두 모였다면 더 묻지 말고, 정리가 끝났으니 '고소장 작성하기' 버튼으로 다음 단계(당사자 정보 입력)로 넘어가면 된다고 안내한다. 추가로 적고 싶은 내용이 있으면 계속 말해도 된다고 덧붙인다.
- 사기와 무관한 질문에는 이 서비스가 사기 피해 고소장 작성을 돕는다고 짧게 안내한다."""


def _context_block(state: dict) -> str:
    crime = state["crime_label"] or "미정 (대화에서 파악 필요)"
    missing = state["missing"]
    if not state["crime_type"]:
        todo = (
            "- 어떤 피해인지(사건 유형), 언제 누구에게 어떤 말에 속아 얼마를 넘겼는지"
        )
    elif missing:
        todo = "\n".join(
            f"- {FACTS[k]['label']}: {FACTS[k]['ask']}" for k in missing[:3]
        )
    else:
        todo = "(필수 항목이 모두 채워졌음)"
    statutes = (
        "\n".join(
            f"- {s['label']}({s['title']}): {' '.join(s['text'].splitlines()[1:3])[:260]}"
            for s in state["statutes"][:4]
        )
        or "(없음)"
    )
    precedents = (
        "\n".join(
            f"- {p['court']} {p['case_no']}: {p['summary'][:220]}"
            for p in state["precedents"][:2]
        )
        or "(없음)"
    )
    return (
        f"[현재 사건 유형] {crime}\n"
        f"[정리된 사실]\n{_facts_text(state['facts'])}\n"
        f"[다음에 물어볼 항목]\n{todo}\n"
        f"[참고 법령]\n{statutes}\n"
        f"[참고 판례]\n{precedents}"
    )


async def chat_turn(case: dict, user_text: str):
    """NDJSON 이벤트 dict를 흘려보내는 async 제너레이터. case는 제자리에서 갱신된다."""
    case["messages"].append({"role": "user", "content": user_text, "ts": time.time()})

    yield {"type": "status", "text": "말씀하신 내용을 정리하고 있어요"}
    changed: list[str] = []
    try:
        data = await extract(case, user_text)
        changed = merge_extraction(case, data)
    except LLMError as e:
        logger.warning("사실 추출 실패: %s", e)

    state = case_state(case)
    yield {"type": "state", "changed": changed, **state}

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in case["messages"][-_HISTORY_TURNS:]
        if m["role"] in ("user", "assistant")
    ]
    messages = [
        {"role": "system", "content": REPLY_SYSTEM},
        {"role": "system", "content": _context_block(state)},
        *history,
    ]
    reply = ""
    try:
        async for piece in stream_text(messages, temperature=0.4, max_tokens=900):
            reply += piece
            yield {"type": "delta", "text": piece}
    except LLMError as e:
        logger.error("응답 생성 실패: %s", e)
        if not reply:
            yield {
                "type": "error",
                "message": "AI 서버에 연결하지 못했어요. 잠시 후 다시 보내 주세요.",
            }
            # 사용자 발화는 남겨 두되, 재전송 시 중복되지 않게 뺀다
            case["messages"].pop()
            return
    case["messages"].append(
        {"role": "assistant", "content": reply.strip(), "ts": time.time()}
    )
    yield {"type": "done"}
