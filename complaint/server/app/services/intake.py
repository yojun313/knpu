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
import re
from datetime import date
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
    "어떤 일을 겪으셨는지 편하게 말씀해 주세요. 언제, 어디서, 누가, 무엇을 했는지 "
    "기억나는 대로 적어 주시면 어떤 죄에 해당할 수 있는지 살펴보고 고소장에 필요한 "
    "내용을 하나씩 정리해 드릴게요.\n\n"
    "주민등록번호 같은 개인정보는 여기서 적지 않으셔도 됩니다. 마지막 단계의 입력 양식에서 따로 받습니다."
)

STARTER_SUGGESTIONS = [
    "중고거래로 돈을 보냈는데 물건이 안 와요",
    "단체 채팅방에서 저에 대한 거짓말을 퍼뜨렸어요",
    "길에서 모르는 사람에게 맞았어요",
    "헤어진 사람이 계속 연락하고 찾아와요",
    "퇴사했는데 월급과 퇴직금을 못 받았어요",
]

_HISTORY_TURNS = 12


def _crime_catalog() -> str:
    return "\n".join(f"- {c.id} [{c.category}]: {c.summary}" for c in CRIMES.values())


_CONFUSABLE = """- 돈을 속여서 받아 갔으면 사기, 맡긴 돈을 마음대로 썼으면 횡령
- 구체적인 사실(거짓 포함)을 퍼뜨렸으면 명예훼손, 욕설·비하만 했으면 모욕. 인터넷·SNS·단체방이면 사이버명예훼손
- 다치지 않았으면 폭행, 치료가 필요한 상처가 생겼으면 상해
- 찾아오거나 따라다니는 등 접근까지 반복하면 스토킹, 공포·불안을 주는 메시지만 반복하면 불안감유발
- 성적 촬영물을 퍼뜨리겠다고 협박했으면 촬영물협박(일반 협박보다 우선)"""


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

[헷갈리기 쉬운 유형 구분]
{confusable}

[사실 항목 목록 (키: 설명)]
{facts}

[규칙]
- 반드시 JSON 객체 하나만 출력한다. 형식:
  {{"crime_type": "유형 id 또는 null", "crime_confidence": 0~1 숫자, "facts": {{"키": "값"}}}}
- facts 에는 이번 사용자 발화로 새로 알게 되었거나 바뀐 항목만 넣는다.
- 값은 기존에 정리된 내용과 새 내용을 합친 '완성된 문장'으로 쓴다(기존 내용을 지우지 말 것).
- 사용자가 말하지 않은 사실은 절대 추측해서 채우지 않는다. 모르면 넣지 않는다.
- 사용자가 '모른다', '없다'고 분명히 답한 항목은 "모름" 또는 "없음"으로 적는다.
- 상대방이 한 말·계좌·장소는 사용자가 말한 그대로 보존한다.
- 날짜는 [오늘 날짜]를 기준으로 계산한다. '지난달', '작년', '어제'처럼 상대적으로 말하면 실제 날짜로 바꾸고, 연도 없이 월·일만 말하면 오늘 이전의 가장 가까운 그 날짜로 본다. 절대 다른 연도를 지어내지 않는다. 형식은 '2026-03-02 15:00'처럼 쓰고 시각을 모르면 날짜만 쓴다.
- 금액은 사용자가 말한 단위 그대로 원화로 쓴다(예: '65만원'). 외화 표기(KRW 등)로 바꾸지 않는다.
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
                crimes=_crime_catalog(),
                confusable=_CONFUSABLE,
                facts=_facts_catalog(crime_id),
            ),
        },
        {
            "role": "user",
            "content": (
                f"[오늘 날짜] {date.today().isoformat()}\n"
                f"[현재 사건 유형] {crime_id or '미정'}\n\n"
                f"[지금까지 정리된 사실]\n{json.dumps(case['facts'], ensure_ascii=False)}\n\n"
                f"[최근 대화]\n{convo}\n\n"
                f"[이번 사용자 발화]\n{user_text}\n\n"
                "JSON만 출력하세요."
            ),
        },
    ]
    return await chat_json(messages, temperature=0.1, max_tokens=4000)


_NEGATIVE_VALUES = (
    "없음",
    "모름",
    "해당 없음",
    "해당없음",
    "없습니다",
    "모릅니다",
    "알 수 없음",
    "불상",
)
_NEGATIVE_HINT_RE = re.compile(r"없|모르|몰라|기억(이|나지)|안\s?했|안했|아니")


def resolve_crime_id(value) -> str | None:
    """모델이 돌려준 유형 표기(id·표시 이름·공백·유사 표기)를 사건 유형 id로 맞춘다."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v in CRIMES:
        return v
    squash = lambda x: re.sub(r"[\s·\-_()]", "", x)
    table = {}
    for c in CRIMES.values():
        table[squash(c.id)] = c.id
        table[squash(c.label)] = c.id
    if squash(v) in table:
        return table[squash(v)]
    close = difflib.get_close_matches(squash(v), list(table), n=1, cutoff=0.75)
    return table[close[0]] if close else None


# 모델이 유형을 정하지 못했을 때 쓰는 키워드 분류(앞에 있을수록 우선)
_CRIME_KEYWORDS = [
    ("촬영물협박", ("유포하겠", "뿌리겠", "퍼뜨리겠")),
    ("허위영상물", ("딥페이크", "합성")),
    ("불법촬영", ("몰카", "몰래 촬영", "몰래 찍", "도촬", "불법촬영")),
    ("통신매체음란", ("음란", "성적인 메시지", "야한 사진", "성기 사진")),
    ("강제추행", ("추행", "만졌", "더듬")),
    ("스토킹", ("스토킹", "따라다니", "집 앞에 찾아", "계속 찾아")),
    ("보험사기", ("보험금",)),
    ("소송사기", ("소송", "허위 소장")),
    ("분양사기", ("분양",)),
    ("취업사기", ("취업", "입사시켜")),
    ("아이템사기", ("아이템", "게임머니")),
    (
        "인터넷물품사기",
        ("당근", "중고", "번개장터", "중고나라", "택배", "판매자", "구매"),
    ),
    ("계약금사기", ("계약금", "납품", "발주")),
    ("차용사기", ("빌려", "차용", "돈을 갚", "안 갚")),
    ("횡령", ("맡긴", "맡겼", "보관", "횡령")),
    ("배임", ("배임",)),
    ("임금체불", ("월급", "임금", "퇴직금", "급여")),
    ("정보통신망침입", ("해킹", "계정", "로그인", "비밀번호")),
    ("개인정보유출", ("개인정보",)),
    (
        "사이버명예훼손",
        ("단톡", "단체방", "커뮤니티", "게시글", "댓글", "SNS", "인스타"),
    ),
    ("명예훼손", ("소문", "명예")),
    ("모욕", ("욕", "모욕")),
    ("상해", ("다쳤", "진단", "골절", "피가")),
    ("폭행", ("때렸", "맞았", "폭행", "밀쳤")),
    ("협박", ("협박", "죽이겠", "가만두지")),
    ("주거침입", ("무단으로 들어", "침입")),
    ("재물손괴", ("부쉈", "파손", "망가뜨")),
    ("절도", ("훔쳐", "도난", "절도", "훔친")),
]


def guess_crime(text: str) -> str | None:
    for crime_id, words in _CRIME_KEYWORDS:
        if any(w in text for w in words):
            # 사이버 명예훼손은 명예훼손성 내용이 있을 때만(욕설만이면 모욕)
            if crime_id == "사이버명예훼손" and not re.search(
                r"소문|거짓|허위|사실|퍼뜨|명예", text
            ):
                continue
            return crime_id
    return None


# 모델이 사용자가 말하지 않은 내용을 채우기 쉬운 항목: 대화에 관련 단어가 있어야 받는다
_GROUNDING = {
    "evidence": (
        "캡처",
        "스크린샷",
        "녹음",
        "내역",
        "확인증",
        "계약서",
        "사진",
        "영상",
        "증거",
        "문자",
        "메시지",
        "기록",
        "진단서",
        "영수증",
        "CCTV",
        "cctv",
    ),
    "settlement": ("합의",),
    "punishment_wish": ("처벌",),
    "same_complaint": ("고소", "신고"),
    "related_investigation": ("수사", "조사", "재판"),
    "repayment": ("돌려", "갚", "환불", "변제", "받았", "못 받", "못받"),
    "other_victims": ("다른 사람", "다른 피해", "피해자", "여러 명", "더치트"),
    "witnesses": ("목격", "봤", "같이 있", "함께 있", "옆에"),
    "weapon": ("칼", "흉기", "몽둥이", "병", "둔기", "물건", "도구", "들고"),
    "injury": ("다쳤", "상처", "진단", "골절", "멍", "피", "병원", "치료"),
    "known_date": ("알게", "알았", "확인"),
}
_HANGUL_RE = re.compile(r"[가-힣]{2,}")
_QUOTE_RE = re.compile(r"[‘'\"“]([^‘’'\"“”]{4,150})[’'\"”]")


def _grounded(key: str, value: str, corpus: str) -> bool:
    words = _GROUNDING.get(key)
    if words is not None:
        return any(w in corpus for w in words)
    if FACTS[key].get("options"):
        return True
    # 자유 서술 항목은 사용자가 쓴 한국어 낱말과 겹치는 부분이 있어야 한다.
    # 날짜·금액처럼 모델이 형식을 바꾼 숫자는 비교하지 않는다(지난달 3월 2일 → 2026-03-02).
    toks = {t for t in _HANGUL_RE.findall(value)}
    return not toks or any(t[:2] in corpus for t in toks)


_DATE_RE = re.compile(
    r"(?:(?P<y>\d{4})\s*년\s*|(?P<rel>작년|지난해|올해|이번\s*해)\s*)?(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일"
    r"(?:\s*(?P<ap>오전|오후|새벽|밤|저녁|아침)?\s*(?P<h>\d{1,2})\s*시(?:\s*(?P<mi>\d{1,2})\s*분|\s*반)?)?"
)


def parse_korean_datetime(text: str, today: date | None = None) -> str | None:
    """'지난달 3월 2일 오후 3시쯤', '2025년 3월 2일 15시' 같은 표현을 '2026-03-02 15:00'으로.

    연도가 없으면 오늘 이전의 가장 가까운 그 날짜로 본다(미래 날짜를 만들지 않는다).
    """
    today = today or date.today()
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    mo, d = int(m.group("m")), int(m.group("d"))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    if m.group("y"):
        y = int(m.group("y"))
    elif m.group("rel") in ("작년", "지난해"):
        y = today.year - 1
    else:
        y = today.year if (mo, d) <= (today.month, today.day) else today.year - 1
    try:
        date(y, mo, d)
    except ValueError:
        return None
    out = f"{y:04d}-{mo:02d}-{d:02d}"
    if m.group("h"):
        h = int(m.group("h"))
        if m.group("ap") in ("오후", "밤", "저녁") and h < 12:
            h += 12
        mi = 30 if "반" in m.group(0) and not m.group("mi") else int(m.group("mi") or 0)
        if 0 <= h <= 23 and 0 <= mi <= 59:
            out += f" {h:02d}:{mi:02d}"
    return out


def merge_extraction(
    case: dict, data: dict, user_text: str = "", asked: list[str] | None = None
) -> list[str]:
    """추출 결과를 사건에 반영하고, 바뀐 사실 키 목록을 돌려준다.

    - 사실은 판정된 사건 유형에 해당하는 항목만 받는다(유형이 없으면 공통 항목만).
    - '없음/모름' 같은 값은 사용자가 실제로 부정·모름을 말했고, 직전에 물어본 항목이거나
      선택형 항목일 때만 받는다. 모델이 모든 항목을 '없음'으로 채우는 것을 막는다.
    """
    changed = []
    corpus = (
        " ".join(
            m["content"] for m in case.get("messages", []) if m.get("role") == "user"
        )
        + " "
        + (user_text or "")
    )
    current = case.get("crime_type")
    # 모델이 유형을 못 정했으면(아직 유형이 없을 때만) 키워드로 분류한다
    ct = resolve_crime_id(data.get("crime_type")) or (
        None if current else guess_crime(corpus)
    )
    if ct and ct != current:
        try:
            conf = float(data.get("crime_confidence") or 0)
        except (TypeError, ValueError):
            conf = 0.0
        # 이미 유형이 정해졌다면 확신이 높을 때만 바꾼다(대화 중 흔들림 방지)
        if not current or conf >= 0.75:
            case["crime_type"] = ct
            changed.append("crime_type")

    allowed = set(fact_keys_for(case.get("crime_type")))
    asked = set(asked or [])
    says_negative = bool(_NEGATIVE_HINT_RE.search(user_text or ""))
    facts = data.get("facts") or {}
    if isinstance(facts, dict):
        for k, v in facts.items():
            if k not in FACTS or k not in allowed or v is None:
                continue
            v = str(v).strip()
            if not v or v.lower() in ("null", "none", "n/a"):
                continue
            is_negative = v.rstrip(".") in _NEGATIVE_VALUES
            if is_negative and not (
                says_negative and (k in asked or FACTS[k].get("options"))
            ):
                continue
            if not is_negative and not _grounded(k, v, corpus):
                logger.info("대화에 근거가 없는 추출 값 무시: %s=%s", k, v[:40])
                continue
            v = _normalize_choice(k, v)[:4000]
            if case["facts"].get(k) != v:
                case["facts"][k] = v
                changed.append(k)
    # 날짜는 고소장의 핵심인데 모델이 가끔 빠뜨린다 — 사용자가 쓴 날짜 표현을 직접 읽어 채운다
    if "incident_datetime" in allowed and not case["facts"].get("incident_datetime"):
        dt = parse_korean_datetime(corpus)
        if dt:
            case["facts"]["incident_datetime"] = dt
            changed.append("incident_datetime")
    # 사기 유형은 '상대방이 한 말'이 곧 기망행위다. 모델이 이 칸을 비워 두는 일이 잦아
    # (1) 모델이 words_used 로 뽑은 말, (2) 사용자가 따옴표로 인용한 말 순으로 채운다.
    crime = CRIMES.get(case.get("crime_type") or "")
    if crime and crime.category == "사기" and not case["facts"].get("deception"):
        said = str((data.get("facts") or {}).get("words_used") or "").strip()
        quotes = list(dict.fromkeys(q.strip() for q in _QUOTE_RE.findall(corpus)))
        if said and _grounded("words_used", said, corpus):
            case["facts"]["deception"] = said
        elif quotes:
            case["facts"]["deception"] = " ".join(
                f"피고소인은 “{q.strip()}”라고 말하였습니다." for q in quotes[:3]
            )
        if case["facts"].get("deception"):
            changed.append("deception")
    return changed


def suggestions_for(case: dict, missing: list[str]) -> list[str]:
    if not case.get("crime_type") and not case["facts"]:
        return STARTER_SUGGESTIONS
    if missing:
        f = FACTS[missing[0]]
        if f.get("options"):
            return list(f["options"])
        quick = {
            "repayment": ["없음", "일부 돌려받았어요"],
            "other_victims": ["없음", "모름", "있어요"],
            "weapon": ["없었어요", "물건을 들고 있었어요"],
            "witnesses": ["없었어요", "함께 있던 사람이 있어요"],
            "victim_response": ["그만하라고 분명히 말했어요", "연락을 차단했어요"],
            "evidence": ["캡처가 있어요", "녹음이 있어요", "증거가 없어요"],
        }
        return quick.get(missing[0], ["잘 모르겠어요"])
    return []


def case_state(case: dict) -> dict:
    """화면 오른쪽 '사건 정리' 패널에 보낼 상태."""
    crime_id = case.get("crime_type")
    missing = missing_required(crime_id, case["facts"])
    statutes = kb.statutes_for_case(crime_id, case["facts"]) if crime_id else []
    query = kb.case_query(case["facts"])
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


REPLY_SYSTEM = """너는 경찰청 표준 고소장 작성을 돕는 'FPEI AI 고소장 작성 도우미'다. 범죄 피해자와 대화하며 어떤 죄에 해당할 수 있는지 살피고, 고소장에 필요한 사실을 빠짐없이 모은다.

[말투와 형식]
- 한국어 존댓말. 따뜻하지만 간결하게, 3~6문장.
- 사용자를 '당신'이라고 부르지 않는다(주어를 생략하거나 '고소인님'도 쓰지 않고 자연스럽게 말한다).
- 인사는 대화의 첫 답변에서만 한다. 이미 대화가 진행 중이면 '안녕하세요'로 시작하지 않는다.
- 먼저 사용자가 방금 말한 핵심을 한 문장으로 받아서 정리한다. 되묻는 형태('~상황이신가요?')가 아니라 확인하는 평서문('~하셨군요.')으로 쓴다.
- 그다음 [다음에 물어볼 항목]의 첫 번째(필요하면 두 번째까지)만 자연스럽게 묻는다. 여러 개를 한꺼번에 나열하지 않는다.
- 굵게(**)만 쓸 수 있다. 표·제목·코드블록은 쓰지 않는다.

[법률 설명 규칙 — 매우 중요]
- 법 조문·형량·판례는 아래 [참고 법령]·[참고 판례]·[유의사항]에 적힌 내용만 말한다. 거기에 없는 조문 번호·형량·판례 번호는 절대 지어내지 않는다.
- 범죄 성립을 단정하지 않는다("○○죄에 해당할 수 있습니다" 처럼 말한다).
- 사건 유형이 정해지면 어떤 죄로 볼 수 있는지 한 번 짧게 알려 준다. 판단에 꼭 필요한 요건이 빠져 있으면(예: 모욕의 공연성, 사기의 편취 고의) 그 요건이 왜 중요한지 한 문장으로 설명하고 묻는다.
- 민사 문제일 가능성이 크면(예: 빌려준 돈을 못 받았지만 빌릴 때는 갚을 능력이 있었던 경우) 부드럽게 그 가능성도 알려 준다.
- [유의사항]에 고소 기한·반의사불벌 같은 내용이 있으면 대화 중 적절한 때 한 번 안내한다.

[그 밖의 규칙]
- 이름·주민등록번호·주소·전화번호는 묻지 않는다(다음 단계 양식에서 받는다).
- 지금도 위험이 이어지고 있으면(폭행·스토킹·협박이 진행 중, 보이스피싱으로 돈이 빠져나가는 중 등) 무엇보다 먼저 112 신고를 안내한다. 보이스피싱이면 송금 은행에 지급정지 요청도 안내한다.
- 필수 항목이 모두 모였다면 더 묻지 말고, 정리가 끝났으니 '고소장 작성하기' 버튼으로 다음 단계(당사자 정보 입력)로 넘어가면 된다고 안내한다. 추가로 적고 싶은 내용이 있으면 계속 말해도 된다고 덧붙인다.
- 범죄 피해와 무관한 질문에는 이 서비스가 형사 고소장 작성을 돕는다고 짧게 안내한다."""

SENSITIVE_GUIDE = """[민감한 사건 — 반드시 지킬 것]
- 성범죄 피해자와 대화하고 있다. 피해자를 탓하거나 의심하는 표현(왜 거절하지 않았는지, 왜 그 자리에 갔는지 등)은 절대 쓰지 않는다.
- 고소장에 꼭 필요한 만큼만 묻고, 필요 이상으로 자세한 신체 묘사를 요구하지 않는다. 말하기 힘들면 '기억나는 만큼만' 적어도 된다고 먼저 알린다.
- 대화 초반에 [유의사항]의 지원 제도(국선변호사, 1366 상담 등)를 한 번 안내한다."""


def _context_block(state: dict) -> str:
    crime = state["crime_label"] or "미정 (대화에서 파악 필요)"
    missing = state["missing"]
    if not state["crime_type"]:
        todo = (
            "- 어떤 일을 겪었는지(언제, 어디서, 누가, 무엇을 했는지)와 그로 인한 피해"
        )
    elif missing:
        todo = "\n".join(
            f"- {FACTS[k]['label']}: {FACTS[k]['ask']}" for k in missing[:3]
        )
    else:
        todo = "(필수 항목이 모두 채워졌음)"
    statutes = (
        "\n".join(
            f"- {s['label']}({s['title']}): {' '.join(s['text'].split())[:280]}"
            for s in state["statutes"][:4]
        )
        or "(없음)"
    )
    crime_obj = CRIMES.get(state["crime_type"] or "")
    notes = (
        "\n".join(f"- {n}" for n in crime_obj.notes)
        if crime_obj and crime_obj.notes
        else "(없음)"
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
        f"[참고 판례]\n{precedents}\n"
        f"[유의사항]\n{notes}"
    )


async def chat_turn(case: dict, user_text: str):
    """NDJSON 이벤트 dict를 흘려보내는 async 제너레이터. case는 제자리에서 갱신된다."""
    case["messages"].append({"role": "user", "content": user_text, "ts": time.time()})

    yield {"type": "status", "text": "말씀하신 내용을 정리하고 있어요"}
    changed: list[str] = []
    try:
        asked = (
            missing_required(case.get("crime_type"), case["facts"])[:3]
            if case.get("crime_type")
            else []
        )
        data = await extract(case, user_text)
        changed = merge_extraction(case, data, user_text, asked)
    except Exception as e:  # 추출이 실패해도 대화는 이어간다
        logger.warning("사실 추출 실패: %s", e)

    state = case_state(case)
    yield {"type": "state", "changed": changed, **state}

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in case["messages"][-_HISTORY_TURNS:]
        if m["role"] in ("user", "assistant")
    ]
    crime_obj = CRIMES.get(state["crime_type"] or "")
    system = REPLY_SYSTEM + (
        "\n\n" + SENSITIVE_GUIDE if crime_obj and crime_obj.sensitive else ""
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": _context_block(state)},
        *history,
    ]
    reply = ""
    try:
        async for piece in stream_text(messages, temperature=0.4, max_tokens=3000):
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
