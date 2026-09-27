"""사건 유형 스키마 — 채팅 모드와 양식 모드가 공유하는 단일 진실 공급원.

- FACTS: 사건 사실 항목 카탈로그. 채팅 에이전트는 대화에서 이 키로 사실을 뽑고,
  양식 모드는 같은 키로 입력칸을 만든다. 그래서 두 모드의 결과가 같은 형태가 된다.
- CRIMES: 유형별 적용 법조(지식베이스 id), 필수 사실(구성요건), 양식에 보일 항목.

적용 법조 id는 data/statutes.json 의 id("법령ID-조문번호")다. 법조문 원문은 절대
여기에 적지 않는다 — 원문은 항상 build_kb.py 가 받아온 공식 데이터에서 온다.
"""

from dataclasses import dataclass, field

# ── 사실 항목 ────────────────────────────────────────────────────────────────
# type: text(한 줄) / long(여러 줄) / datetime / choice
# ask : 채팅에서 이 항목이 비어 있을 때 AI가 물어볼 방향(그대로 읽지 않고 참고만 한다)
FACTS: dict[str, dict] = {
    "incident_datetime": {
        "label": "피해 일시",
        "type": "datetime",
        "ask": "피해가 발생한 날짜와 대략적인 시각(예: 2025년 3월 2일 오후 3시경)",
        "hint": "돈이나 물건을 넘긴 날짜와 시각. 여러 번이면 첫 번째와 마지막 날짜",
    },
    "incident_place": {
        "label": "피해 장소",
        "type": "text",
        "ask": "피해가 일어난 장소(만난 장소, 또는 온라인이면 사용한 사이트·앱 이름)",
        "hint": "오프라인 장소 또는 온라인 플랫폼 이름",
    },
    "relationship": {
        "label": "피고소인과의 관계",
        "type": "text",
        "ask": "상대방과 어떤 관계인지(지인, 거래 상대, 온라인에서 처음 만난 사람 등)와 알게 된 경위",
        "hint": "예: 5년 된 직장 동료, 중고거래 앱에서 처음 알게 된 판매자",
    },
    "contact_channel": {
        "label": "연락 수단",
        "type": "text",
        "ask": "상대방과 어떤 수단으로 연락했는지(전화번호, 카카오톡 ID, 앱 채팅 등)",
        "hint": "전화, 카카오톡 ID, 오픈채팅, 앱 내 채팅 등",
    },
    "deception": {
        "label": "상대방의 거짓말(기망행위)",
        "type": "long",
        "ask": "상대방이 구체적으로 어떤 말이나 행동으로 속였는지(가능하면 실제 한 말 그대로)",
        "hint": "상대가 한 말을 따옴표로 적으면 가장 좋습니다",
    },
    "belief_reason": {
        "label": "믿게 된 이유",
        "type": "long",
        "ask": "그 말을 믿게 된 결정적인 이유나 근거(보여준 서류, 사진, 과거 신뢰 관계 등)",
        "hint": "상대가 보여준 자료, 신분, 이전 거래 경험 등",
    },
    "disposition": {
        "label": "돈·물건을 넘긴 방법",
        "type": "long",
        "ask": "돈이나 물건을 어떤 방법으로 넘겼는지(계좌이체라면 보낸 날짜·금액·받는 계좌 명의와 은행)",
        "hint": "예: 3/2 15:10 카카오뱅크 → 국민은행 홍길동 명의 계좌로 50만원 이체",
    },
    "damage_amount": {
        "label": "피해 금액·물품",
        "type": "text",
        "ask": "피해 금액(또는 넘긴 물건과 그 가치) 총액",
        "hint": "숫자로 정확히. 여러 번이면 합계와 회차",
    },
    "repayment": {
        "label": "돌려받은 금액",
        "type": "text",
        "ask": "지금까지 돌려받은 돈이 있는지, 있다면 얼마인지",
        "hint": "없으면 '없음'",
    },
    "post_conduct": {
        "label": "이후 상대방의 태도",
        "type": "long",
        "ask": "돈을 보낸 뒤 상대방이 어떻게 했는지(연락 두절, 차단, 계속된 핑계 등)",
        "hint": "연락 두절, 차단, 반복된 변명, 잠적 시점 등",
    },
    "intent_evidence": {
        "label": "처음부터 속일 생각이었다고 볼 사정",
        "type": "long",
        "ask": "상대가 처음부터 갚거나 이행할 생각·능력이 없었다고 볼 만한 사정(당시 빚, 다른 피해자, 거짓 신분 등)",
        "hint": "사기죄와 단순 채무불이행을 가르는 핵심입니다",
    },
    "other_victims": {
        "label": "다른 피해자",
        "type": "text",
        "ask": "같은 사람에게 비슷한 피해를 당한 다른 사람이 있는지",
        "hint": "알고 있다면 인원과 대략적인 피해 규모",
    },
    "evidence": {
        "label": "증거자료",
        "type": "long",
        "ask": "가지고 있는 증거(이체 내역, 대화 캡처, 계약서, 녹음, 게시글 캡처 등)",
        "hint": "이체확인증, 대화 캡처, 계약서, 녹음 파일, 판매글 캡처 등",
    },
    "suspect_description": {
        "label": "피고소인을 특정할 정보",
        "type": "long",
        "ask": "상대방의 이름·연락처를 모른다면 특정할 수 있는 정보(닉네임, 계좌 명의, 인상착의, 판매글 주소 등)",
        "hint": "닉네임, 계좌 명의, 인상착의, 차량번호 등",
    },
    "settlement": {
        "label": "합의 여부",
        "type": "choice",
        "options": ["합의하지 않음", "합의하였음"],
        "ask": "상대방과 합의했는지",
    },
    "punishment_wish": {
        "label": "처벌 의사",
        "type": "choice",
        "options": ["처벌 원함", "처벌 원하지 않음"],
        "ask": "상대방의 처벌을 원하는지",
    },
    "same_complaint": {
        "label": "동일 건 고소 사실",
        "type": "choice",
        "options": ["없음", "있음", "모름"],
        "ask": "같은 내용으로 다른 경찰서·검찰청에 고소한 적이 있는지",
    },
    "related_investigation": {
        "label": "관련 사건 수사 여부",
        "type": "choice",
        "options": ["없음", "있음", "모름"],
        "ask": "이 사건이나 공범에 대해 이미 수사가 진행 중인지",
    },
    "additional_notes": {
        "label": "기타 수사에 필요한 사항",
        "type": "long",
        "ask": "그 밖에 수사기관이 알아야 할 사항",
        "hint": "선택 사항",
    },
    # ── 유형별 항목 (기존 양식의 질문을 그대로 보존) ──
    "trade_url": {
        "label": "거래 게시글 주소",
        "type": "text",
        "ask": "거래한 판매글·게시글 주소(URL)",
        "hint": "예: 중고거래 앱 게시글 링크",
    },
    "item_name": {
        "label": "거래 물품·아이템",
        "type": "text",
        "ask": "거래하려던 물품이나 게임 아이템의 이름과 수량",
        "hint": "게임명, 서버, 아이템명까지",
    },
    "contract_details": {
        "label": "계약 내용",
        "type": "long",
        "ask": "계약 내용(공급·완공 시기, 대금, 조건 등)",
        "hint": "시기, 금액, 조건",
    },
    "contract_document": {
        "label": "계약서 작성 여부",
        "type": "choice",
        "options": ["작성함", "작성하지 않음"],
        "ask": "계약서를 작성했는지",
    },
    "counterparty_capacity": {
        "label": "상대의 자본·운영 상황 인지 여부",
        "type": "long",
        "ask": "계약 당시 상대 회사(사업)의 자금 사정을 알고 있었는지",
        "hint": "알고 있었다면 어떻게 알았는지",
    },
    "actual_performance": {
        "label": "실제 이행 여부",
        "type": "long",
        "ask": "상대가 실제로 생산·납품·공사 등을 했는지, 했다면 어디까지 했는지",
        "hint": "일부 이행 여부 포함",
    },
    "other_contractors": {
        "label": "다른 계약자",
        "type": "text",
        "ask": "고소인 외에 같은 조건으로 계약한 다른 사람이 있는지",
        "hint": "있다면 인원",
    },
    "company_name": {
        "label": "취업시켜 주겠다고 한 회사",
        "type": "text",
        "ask": "상대가 취업시켜 주겠다고 한 회사 이름",
        "hint": "",
    },
    "company_relation": {
        "label": "상대와 해당 회사의 관계",
        "type": "text",
        "ask": "상대가 그 회사와 어떤 관계라고 했는지(임원, 인사 담당자 지인 등)",
        "hint": "",
    },
    "background": {
        "label": "이야기를 나누게 된 경위",
        "type": "long",
        "ask": "처음 그 이야기를 꺼내게 된 경위",
        "hint": "",
    },
    "insurance_reason": {
        "label": "보험금 지급 사유",
        "type": "long",
        "ask": "상대에게 보험금을 지급하게 된 사유(상대가 주장한 사고 내용)",
        "hint": "보험사 입장에서 작성",
    },
    "insurance_payment": {
        "label": "보험금 지급 내역",
        "type": "long",
        "ask": "보험금을 누구에게, 언제, 어떻게 지급했는지",
        "hint": "",
    },
    "court": {
        "label": "소송이 제기된 법원",
        "type": "text",
        "ask": "상대가 소송을 제기한 법원과 사건번호",
        "hint": "예: 서울중앙지방법원 2025가단12345",
    },
    "claim": {
        "label": "청구취지",
        "type": "long",
        "ask": "상대가 제기한 소송의 청구취지(무엇을 달라고 했는지)",
        "hint": "",
    },
    "false_reason": {
        "label": "허위 소송이라고 보는 근거",
        "type": "long",
        "ask": "그 소송이 허위라고 보는 이유와 근거(위조 서류, 이미 갚은 채무 등)",
        "hint": "",
    },
    "lawsuit_motive": {
        "label": "허위 소송을 낸 이유",
        "type": "long",
        "ask": "상대가 허위 소송을 낸 이유로 생각되는 것",
        "hint": "",
    },
}


@dataclass
class Crime:
    id: str
    label: str
    summary: str
    statutes: list[str]  # 지식베이스 조문 id (앞일수록 핵심)
    required: list[str]  # 고소장에 꼭 필요한 사실(구성요건)
    extra: list[str] = field(default_factory=list)  # 있으면 좋은 유형별 사실
    offense_name: str = "사기"  # 고소취지에 들어갈 죄명
    evidence_tips: list[str] = field(default_factory=list)


_FRAUD = ["001692-347", "001692-352"]
_PROCEDURE = ["001671-223", "001671-237", "001671-249", "001671-257", "001215-25"]
_COMMON_REQUIRED = [
    "incident_datetime",
    "incident_place",
    "deception",
    "disposition",
    "damage_amount",
    "repayment",
    "post_conduct",
    "evidence",
]
_CLOSING = ["settlement", "punishment_wish", "same_complaint", "related_investigation"]

CRIMES: dict[str, Crime] = {
    c.id: c
    for c in [
        Crime(
            "차용사기",
            "차용사기",
            "돈을 빌려 가면서 갚을 의사나 능력이 없었던 경우",
            _FRAUD + ["001136-3"],
            _COMMON_REQUIRED + ["relationship", "intent_evidence"],
            ["belief_reason", "other_victims"],
            evidence_tips=[
                "이체확인증·통장 거래내역",
                "빌려 달라고 한 메시지·녹음",
                "차용증(있다면)",
                "변제를 미룬 대화 기록",
            ],
        ),
        Crime(
            "계약금사기",
            "계약금·물품대금 사기",
            "공급·납품 계약금을 받고 이행할 의사나 능력이 없었던 경우",
            _FRAUD + ["001136-3", "001692-355"],
            _COMMON_REQUIRED
            + ["contract_details", "actual_performance", "intent_evidence"],
            [
                "contract_document",
                "counterparty_capacity",
                "other_contractors",
                "relationship",
            ],
            evidence_tips=[
                "계약서·발주서",
                "계약금 이체 내역",
                "납품 지연 관련 대화",
                "상대 회사 등기부등본",
            ],
        ),
        Crime(
            "분양사기",
            "분양사기",
            "분양대금을 받고 신축·분양 의사나 능력이 없었던 경우",
            _FRAUD + ["001136-3"],
            _COMMON_REQUIRED
            + ["contract_details", "actual_performance", "intent_evidence"],
            ["contract_document", "counterparty_capacity", "other_contractors"],
            evidence_tips=[
                "분양계약서",
                "분양대금 납부 내역",
                "분양 광고·홍보물",
                "건축허가·등기 현황",
            ],
        ),
        Crime(
            "소송사기",
            "소송사기",
            "허위 주장이나 증거로 법원을 속여 재산상 이익을 얻으려 한 경우",
            _FRAUD + ["001136-3"],
            [
                "incident_datetime",
                "court",
                "claim",
                "false_reason",
                "damage_amount",
                "evidence",
                "post_conduct",
            ],
            ["lawsuit_motive", "relationship"],
            evidence_tips=[
                "소장·준비서면 사본",
                "허위임을 보여주는 원본 자료",
                "판결문(있다면)",
                "변제 영수증 등 반박 자료",
            ],
        ),
        Crime(
            "아이템사기",
            "게임 아이템 사기",
            "게임 아이템·게임머니 거래에서 돈이나 아이템만 받고 넘기지 않은 경우",
            _FRAUD + ["001692-347의2"],
            _COMMON_REQUIRED + ["item_name", "contact_channel"],
            ["trade_url", "suspect_description", "other_victims"],
            evidence_tips=[
                "거래 게시글 캡처(URL 포함)",
                "게임 닉네임·서버 정보",
                "이체 내역",
                "거래 채팅 캡처",
            ],
        ),
        Crime(
            "인터넷물품사기",
            "인터넷 물품 사기",
            "중고거래·온라인 판매에서 대금을 받고 물건을 보내지 않은 경우",
            _FRAUD + ["011359-2"],
            _COMMON_REQUIRED + ["item_name", "contact_channel"],
            ["trade_url", "suspect_description", "other_victims"],
            evidence_tips=[
                "판매글 캡처(URL 포함)",
                "판매자 계좌 명의·계좌번호",
                "이체 내역",
                "거래 대화 캡처",
                "더치트 등 피해 조회 결과",
            ],
        ),
        Crime(
            "취업사기",
            "취업 사기",
            "취업을 시켜 주겠다며 돈을 받아 간 경우",
            _FRAUD,
            _COMMON_REQUIRED + ["company_name", "company_relation", "background"],
            ["relationship", "intent_evidence", "other_victims"],
            evidence_tips=[
                "돈을 요구한 메시지·녹음",
                "이체 내역",
                "상대가 보여준 명함·서류",
                "해당 회사에 확인한 결과",
            ],
        ),
        Crime(
            "보험사기",
            "보험사기",
            "보험사고를 가장하거나 부풀려 보험금을 받아 간 경우(보험사·피해자 측)",
            ["012521-8", "012521-2", "012521-10", "012521-11"] + _FRAUD,
            [
                "incident_datetime",
                "insurance_reason",
                "deception",
                "insurance_payment",
                "damage_amount",
                "evidence",
                "repayment",
            ],
            ["intent_evidence", "other_victims"],
            offense_name="보험사기",
            evidence_tips=[
                "보험금 청구서·지급 내역",
                "사고 조사 보고서",
                "진료기록·CCTV 등 허위를 보여주는 자료",
            ],
        ),
        Crime(
            "기타사기",
            "기타 사기",
            "위 유형에 해당하지 않는 사기 피해",
            _FRAUD + ["001692-347의2", "001136-3"],
            _COMMON_REQUIRED + ["relationship", "intent_evidence"],
            ["belief_reason", "other_victims", "suspect_description"],
            evidence_tips=[
                "금전 이동 내역",
                "속인 말이 담긴 대화·녹음",
                "관련 계약서·영수증",
            ],
        ),
    ]
}

PROCEDURE_STATUTES = _PROCEDURE + ["001692-156"]


def fact_keys_for(crime_id: str | None) -> list[str]:
    """해당 유형에서 묻고 보여줄 사실 항목(필수 → 유형별 → 마무리 순)."""
    crime = CRIMES.get(crime_id or "")
    keys = (
        list(crime.required + crime.extra)
        if crime
        else [
            "incident_datetime",
            "incident_place",
            "deception",
            "disposition",
            "damage_amount",
        ]
    )
    keys += ["suspect_description", "additional_notes"] + _CLOSING
    seen, out = set(), []
    for k in keys:
        if k not in seen and k in FACTS:
            seen.add(k)
            out.append(k)
    return out


def required_keys_for(crime_id: str | None) -> list[str]:
    crime = CRIMES.get(crime_id or "")
    base = (
        crime.required
        if crime
        else ["incident_datetime", "deception", "disposition", "damage_amount"]
    )
    return list(dict.fromkeys(base + ["settlement", "punishment_wish"]))


def missing_required(crime_id: str | None, facts: dict) -> list[str]:
    return [
        k for k in required_keys_for(crime_id) if not str(facts.get(k) or "").strip()
    ]


def completeness(crime_id: str | None, facts: dict) -> float:
    req = required_keys_for(crime_id)
    if not crime_id:
        return 0.0
    done = sum(1 for k in req if str(facts.get(k) or "").strip())
    return round(done / len(req), 3) if req else 1.0


def schema() -> dict:
    """프론트엔드용 스키마(양식 입력칸·채팅 체크리스트 공용)."""
    return {
        "facts": FACTS,
        "crimes": [
            {
                "id": c.id,
                "label": c.label,
                "summary": c.summary,
                "fields": fact_keys_for(c.id),
                "required": required_keys_for(c.id),
                "evidence_tips": c.evidence_tips,
            }
            for c in CRIMES.values()
        ],
    }
