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
    # ── 사기 외 범죄에서 쓰는 일반 항목 ──
    "act_description": {
        "label": "상대방이 한 행위",
        "type": "long",
        "ask": "상대방이 구체적으로 무엇을 했는지(행동을 순서대로)",
        "hint": "누가, 무엇으로, 어떻게 했는지 순서대로",
    },
    "words_used": {
        "label": "상대방이 한 말·글(원문)",
        "type": "long",
        "ask": "상대방이 한 말이나 올린 글·메시지를 가능한 한 그대로",
        "hint": "욕설·협박 문구도 그대로 적어야 판단할 수 있습니다",
    },
    "publicity": {
        "label": "누가 보거나 들었는지",
        "type": "long",
        "ask": "그 말이나 글을 누가 보거나 들을 수 있었는지(여러 사람이 있던 자리, 단체방 인원, 공개 게시판 등)",
        "hint": "명예훼손·모욕은 여러 사람이 알 수 있었는지(공연성)가 핵심입니다",
    },
    "identifiability": {
        "label": "피해자를 알아볼 수 있었는지",
        "type": "long",
        "ask": "이름이 나오지 않았더라도 주변 사람들이 고소인을 가리키는 것임을 알 수 있었는지와 그 이유",
        "hint": "실명·닉네임·사진·직장 등 특정할 수 있었던 정보",
    },
    "falsity": {
        "label": "사실과 다른 점",
        "type": "long",
        "ask": "상대방이 퍼뜨린 내용 중 사실과 다른 부분과 실제 사실",
        "hint": "허위라면 무엇이 어떻게 다른지",
    },
    "injury": {
        "label": "다친 부위·진단",
        "type": "text",
        "ask": "다친 부위와 병원 진단 내용(진단 주수 등)",
        "hint": "예: 코뼈 골절, 전치 3주 진단",
    },
    "weapon": {
        "label": "사용한 물건(흉기 등)",
        "type": "text",
        "ask": "상대방이 손발 외에 사용하거나 들고 있던 물건(흉기, 둔기 등)이 있었는지",
        "hint": "없으면 '없음'",
    },
    "repeated": {
        "label": "반복 횟수·기간",
        "type": "text",
        "ask": "같은 행위가 몇 번, 어느 기간 동안 반복되었는지",
        "hint": "예: 2025년 1월부터 3월까지 약 40회",
    },
    "target_property": {
        "label": "대상 물건·재산과 가치",
        "type": "text",
        "ask": "피해를 입은 물건이나 재산과 그 가치",
        "hint": "예: 자전거 1대(시가 약 80만원)",
    },
    "entrustment": {
        "label": "맡기게 된 경위",
        "type": "long",
        "ask": "상대방에게 돈이나 물건을 맡기게 된 경위와 무엇을 위해 맡겼는지",
        "hint": "횡령은 맡긴 관계(위탁)와 용도가 핵심입니다",
    },
    "duty": {
        "label": "상대방이 맡은 일(임무)",
        "type": "long",
        "ask": "상대방이 고소인을 위해 어떤 일을 맡아 처리하는 위치였는지와 그 임무를 어떻게 어겼는지",
        "hint": "예: 회사 자금 관리 담당, 부동산 처분 위임 등",
    },
    "post_url": {
        "label": "게시·전송된 곳",
        "type": "text",
        "ask": "글이나 메시지가 올라오거나 보내진 곳(게시글 주소, 채팅방 이름, 앱 등)",
        "hint": "URL, 단체방 이름과 인원 등",
    },
    "witnesses": {
        "label": "목격자·함께 있던 사람",
        "type": "text",
        "ask": "그 상황을 보거나 들은 사람이 있는지",
        "hint": "관계와 연락 가능 여부",
    },
    "victim_response": {
        "label": "거부 의사·대응",
        "type": "long",
        "ask": "상대방에게 싫다거나 그만하라는 뜻을 밝혔는지, 어떻게 대응했는지",
        "hint": "거절 메시지, 차단, 신고 이력 등",
    },
    "employment_period": {
        "label": "근무 기간·퇴사일",
        "type": "text",
        "ask": "근무를 시작한 날과 퇴사한 날(재직 중이면 재직 중)",
        "hint": "예: 2024-03-02 ~ 2025-08-31",
    },
    "wage_details": {
        "label": "받지 못한 임금 내역",
        "type": "long",
        "ask": "받지 못한 임금·퇴직금·수당의 종류와 기간별 금액",
        "hint": "월급, 퇴직금, 연장수당 등을 기간별로",
    },
    "document_details": {
        "label": "위조된 문서와 쓰인 곳",
        "type": "long",
        "ask": "어떤 문서가 고소인 명의로 위조되었는지와 그 문서가 어디에 제출·사용되었는지",
        "hint": "계약서, 차용증, 위임장 등과 사용처",
    },
    "known_date": {
        "label": "범인을 알게 된 날",
        "type": "text",
        "ask": "상대방이 범인이라는 것을 처음 알게 된 날",
        "hint": "친고죄는 이 날부터 6개월 안에 고소해야 합니다",
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
    offense_name: str = "사기"  # 고소취지에 들어갈 죄명(대검 죄명 표기)
    evidence_tips: list[str] = field(default_factory=list)
    category: str = "사기"
    elements: list[tuple[str, str]] = field(
        default_factory=list
    )  # 구성요건 (이름, 판단 기준)
    closing: str = ""  # 범죄사실 맺음 문장 형식
    notes: list[str] = field(
        default_factory=list
    )  # 절차상 꼭 알려야 할 사항(화면·AI 공용)
    sensitive: bool = False  # 성범죄 등 — 상담 말투를 더 조심스럽게


CATEGORIES = [
    "사기",
    "재산 범죄",
    "명예·모욕",
    "폭력·협박",
    "성범죄",
    "스토킹·괴롭힘",
    "주거·업무·문서",
    "사이버·개인정보",
    "노동",
]

# 사기죄 구성요건 — 판례(대법원 2017도20682 등)가 쓰는 틀 그대로
_FRAUD_ELEMENTS = [
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
]
_FRAUD_CLOSING = "피고소인은 이와 같이 고소인을 기망하여 이에 속은 고소인으로부터 금 ○○원(또는 물건)을 교부받아 이를 편취하였습니다."

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

_ANTI_WILL = "피해자가 처벌을 원하지 않는다는 뜻을 밝히면 처벌할 수 없는 반의사불벌죄입니다. 합의 여부와 처벌 의사를 분명히 적어야 합니다."
_COMPLAINT_ONLY = "고소가 있어야 처벌할 수 있는 친고죄여서 범인을 알게 된 날부터 6개월 안에 고소해야 합니다(형사소송법 제230조)."
_SEX_SUPPORT = "성폭력 피해자는 수사·재판 과정에서 국선변호사 선임과 신뢰관계인 동석 등의 지원을 받을 수 있고, 여성긴급전화 1366에서도 상담받을 수 있습니다."
_DIGITAL_SUPPORT = "촬영물이 유포되었거나 유포될 우려가 있다면 디지털성범죄피해자지원센터에 삭제 지원을 요청할 수 있습니다."

_PUBLIC = ["publicity", "identifiability"]


def _fraud(id, label, summary, statutes, required, extra, tips, offense="사기"):
    return Crime(
        id,
        label,
        summary,
        statutes,
        required,
        extra,
        offense,
        tips,
        category="사기",
        elements=_FRAUD_ELEMENTS,
        closing=_FRAUD_CLOSING,
    )


CRIMES: dict[str, Crime] = {
    c.id: c
    for c in [
        # ── 사기 ──
        _fraud(
            "차용사기",
            "차용사기",
            "돈을 빌려 가면서 갚을 의사나 능력이 없었던 경우",
            _FRAUD + ["001136-3"],
            _COMMON_REQUIRED + ["relationship", "intent_evidence"],
            ["belief_reason", "other_victims"],
            [
                "이체확인증·통장 거래내역",
                "빌려 달라고 한 메시지·녹음",
                "차용증(있다면)",
                "변제를 미룬 대화 기록",
            ],
        ),
        _fraud(
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
            [
                "계약서·발주서",
                "계약금 이체 내역",
                "납품 지연 관련 대화",
                "상대 회사 등기부등본",
            ],
        ),
        _fraud(
            "분양사기",
            "분양사기",
            "분양대금을 받고 신축·분양 의사나 능력이 없었던 경우",
            _FRAUD + ["001136-3"],
            _COMMON_REQUIRED
            + ["contract_details", "actual_performance", "intent_evidence"],
            ["contract_document", "counterparty_capacity", "other_contractors"],
            [
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
            "사기",
            [
                "소장·준비서면 사본",
                "허위임을 보여주는 원본 자료",
                "판결문(있다면)",
                "변제 영수증 등 반박 자료",
            ],
            category="사기",
            elements=[
                (
                    "허위 주장·증거",
                    "피고소인이 허위의 주장이나 조작된 증거로 법원을 속이려 했는지",
                ),
                (
                    "소송 제기",
                    "법원에 소를 제기하는 등 실행에 착수했는지(법원·사건번호)",
                ),
                ("재산상 이익", "승소하면 얻게 될 재산상 이익이 무엇인지(금액)"),
                ("고의", "주장이 허위임을 알고 있었다고 볼 사정이 있는지"),
            ],
            closing="피고소인은 이와 같이 허위의 주장과 증거로 법원을 기망하여 승소판결을 받아 재산상 이익을 취득하려 하였습니다(또는 취득하였습니다).",
        ),
        _fraud(
            "아이템사기",
            "게임 아이템 사기",
            "게임 아이템·게임머니 거래에서 돈이나 아이템만 받고 넘기지 않은 경우",
            _FRAUD + ["001692-347의2"],
            _COMMON_REQUIRED + ["item_name", "contact_channel"],
            ["trade_url", "suspect_description", "other_victims"],
            [
                "거래 게시글 캡처(URL 포함)",
                "게임 닉네임·서버 정보",
                "이체 내역",
                "거래 채팅 캡처",
            ],
        ),
        _fraud(
            "인터넷물품사기",
            "인터넷 물품 사기",
            "중고거래·온라인 판매에서 대금을 받고 물건을 보내지 않은 경우",
            _FRAUD + ["011359-2"],
            _COMMON_REQUIRED + ["item_name", "contact_channel"],
            ["trade_url", "suspect_description", "other_victims"],
            [
                "판매글 캡처(URL 포함)",
                "판매자 계좌 명의·계좌번호",
                "이체 내역",
                "거래 대화 캡처",
                "더치트 등 피해 조회 결과",
            ],
        ),
        _fraud(
            "취업사기",
            "취업 사기",
            "취업을 시켜 주겠다며 돈을 받아 간 경우",
            _FRAUD,
            _COMMON_REQUIRED + ["company_name", "company_relation", "background"],
            ["relationship", "intent_evidence", "other_victims"],
            [
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
            "보험사기방지특별법위반",
            [
                "보험금 청구서·지급 내역",
                "사고 조사 보고서",
                "진료기록·CCTV 등 허위를 보여주는 자료",
            ],
            category="사기",
            elements=[
                (
                    "보험사기행위",
                    "보험사고의 발생·원인·내용에 관하여 보험자를 기망하여 보험금을 청구했는지",
                ),
                (
                    "보험금 취득",
                    "그로 인해 보험금을 받거나 제3자가 받게 했는지(금액 특정)",
                ),
                ("고의", "허위임을 알면서 청구했다고 볼 사정이 있는지"),
            ],
            closing="피고소인은 이와 같이 보험사고의 내용에 관하여 보험자를 기망하여 보험금 합계 금 ○○원을 지급받았습니다.",
        ),
        _fraud(
            "기타사기",
            "기타 사기",
            "위 유형에 해당하지 않는 사기 피해",
            _FRAUD + ["001692-347의2", "001136-3"],
            _COMMON_REQUIRED + ["relationship", "intent_evidence"],
            ["belief_reason", "other_victims", "suspect_description"],
            ["금전 이동 내역", "속인 말이 담긴 대화·녹음", "관련 계약서·영수증"],
        ),
        # ── 재산 범죄 ──
        Crime(
            "횡령",
            "횡령",
            "맡긴 돈이나 물건을 상대가 마음대로 쓰거나 돌려주지 않는 경우",
            ["001692-355", "001692-356", "001136-3"],
            [
                "incident_datetime",
                "entrustment",
                "target_property",
                "act_description",
                "damage_amount",
                "repayment",
                "evidence",
            ],
            ["relationship", "post_conduct"],
            "횡령",
            [
                "돈을 맡긴 이체 내역·영수증",
                "맡긴 목적이 드러나는 대화·약정서",
                "반환을 요구한 메시지",
                "상대가 다른 곳에 쓴 정황 자료",
            ],
            category="재산 범죄",
            elements=[
                (
                    "위탁관계",
                    "고소인이 피고소인에게 재물을 맡겨 피고소인이 보관하는 관계였는지",
                ),
                (
                    "타인의 재물",
                    "맡긴 재물이 고소인의 소유인지(용도를 정해 맡긴 금전 포함)",
                ),
                (
                    "횡령·반환거부",
                    "피고소인이 맡은 재물을 임의로 처분하거나 반환을 거부했는지",
                ),
                ("불법영득의사", "자기 것처럼 처분하려는 의사가 드러나는지"),
            ],
            closing="피고소인은 이로써 고소인을 위하여 보관하던 ○○을 임의로 소비하여 횡령하였습니다(또는 반환을 거부하였습니다).",
        ),
        Crime(
            "배임",
            "배임",
            "고소인의 일을 맡은 사람이 임무를 어겨 손해를 입힌 경우",
            ["001692-355", "001692-356", "001136-3"],
            [
                "incident_datetime",
                "duty",
                "act_description",
                "damage_amount",
                "evidence",
            ],
            ["relationship", "repayment", "post_conduct"],
            "배임",
            [
                "업무 위임 계약서·정관",
                "임무 위반을 보여주는 거래 자료",
                "손해액 산정 자료",
            ],
            category="재산 범죄",
            elements=[
                (
                    "타인의 사무처리자",
                    "피고소인이 고소인과의 신임관계에 따라 고소인의 재산상 사무를 처리하는 지위에 있었는지",
                ),
                ("임무위배행위", "그 임무에 위배되는 행위를 했는지"),
                (
                    "재산상 이익·손해",
                    "그로 인해 피고소인 또는 제3자가 이익을 얻고 고소인에게 손해가 생겼는지(금액)",
                ),
                ("고의", "임무에 위배된다는 것을 알면서 했는지"),
            ],
            closing="피고소인은 이와 같이 그 임무에 위배하여 금 ○○원 상당의 재산상 이익을 취득(또는 제3자로 하여금 취득)하게 하고 고소인에게 같은 금액 상당의 손해를 가하였습니다.",
        ),
        Crime(
            "절도",
            "절도",
            "고소인의 물건을 몰래 가져간 경우",
            ["001692-329", "001692-330", "001692-331"],
            [
                "incident_datetime",
                "incident_place",
                "target_property",
                "act_description",
                "evidence",
            ],
            ["witnesses", "suspect_description", "repayment"],
            "절도",
            [
                "CCTV 영상(보관 기간이 짧으니 빨리 요청)",
                "도난 물건의 구매 영수증·사진",
                "목격자 진술",
            ],
            category="재산 범죄",
            elements=[
                ("타인의 재물", "가져간 물건이 고소인이 소유·점유하던 것인지"),
                ("절취", "고소인의 의사에 반해 물건을 가져가 점유를 옮겼는지"),
                ("불법영득의사", "돌려줄 생각 없이 자기 것처럼 쓰려 했는지"),
            ],
            closing="피고소인은 이로써 고소인 소유의 시가 ○○원 상당의 ○○을 가지고 가 절취하였습니다.",
        ),
        Crime(
            "공갈",
            "공갈",
            "겁을 주거나 협박해서 돈이나 이익을 받아 간 경우",
            ["001692-350", "001692-350의2", "001136-3"],
            [
                "incident_datetime",
                "incident_place",
                "words_used",
                "act_description",
                "damage_amount",
                "evidence",
            ],
            ["weapon", "relationship", "repeated"],
            "공갈",
            ["협박 메시지·녹음", "돈을 보낸 내역", "당시 상황을 아는 사람의 진술"],
            category="재산 범죄",
            elements=[
                (
                    "공갈(폭행·협박)",
                    "상대가 겁을 먹을 만한 폭행이나 해악의 고지가 있었는지",
                ),
                ("외포", "고소인이 그로 인해 겁을 먹었는지"),
                (
                    "재물 교부·이익 취득",
                    "겁을 먹은 고소인이 돈이나 재산상 이익을 넘겼는지(금액)",
                ),
            ],
            closing="피고소인은 이와 같이 고소인을 공갈하여 이에 겁을 먹은 고소인으로부터 금 ○○원을 교부받았습니다.",
        ),
        Crime(
            "재물손괴",
            "재물손괴",
            "고소인의 물건을 부수거나 못 쓰게 만든 경우",
            ["001692-366", "001692-369"],
            [
                "incident_datetime",
                "incident_place",
                "target_property",
                "act_description",
                "damage_amount",
                "evidence",
            ],
            ["weapon", "witnesses", "suspect_description"],
            "재물손괴",
            ["파손 전후 사진", "수리 견적서·영수증", "CCTV·블랙박스 영상"],
            category="재산 범죄",
            elements=[
                ("타인의 재물", "손괴된 물건이 고소인의 소유인지"),
                ("손괴·효용 침해", "부수거나 숨기는 등으로 물건의 효용을 해쳤는지"),
                ("고의", "일부러 한 것인지(실수로 한 경우는 처벌되지 않음)"),
            ],
            closing="피고소인은 이로써 고소인 소유의 ○○을 손괴하여 수리비 약 ○○원이 들도록 그 효용을 해하였습니다.",
        ),
        # ── 명예·모욕 ──
        Crime(
            "명예훼손",
            "명예훼손",
            "여러 사람 앞에서 고소인에 대한 사실이나 거짓을 퍼뜨린 경우(오프라인)",
            ["001692-307", "001692-309", "001692-310", "001692-312"],
            ["incident_datetime", "incident_place", "words_used"]
            + _PUBLIC
            + ["falsity", "evidence"],
            ["witnesses", "relationship", "repeated"],
            "명예훼손",
            ["발언 녹음", "현장에 있던 사람들의 진술서", "허위임을 보여주는 자료"],
            category="명예·모욕",
            elements=[
                (
                    "공연성",
                    "불특정 또는 여러 사람이 알 수 있었거나 전파될 가능성이 있었는지",
                ),
                (
                    "사실의 적시",
                    "구체적인 사실(또는 허위사실)을 드러냈는지(단순 욕설은 모욕)",
                ),
                (
                    "특정성",
                    "그 내용이 고소인을 가리킨다는 것을 주변 사람이 알 수 있었는지",
                ),
                ("명예 훼손", "고소인의 사회적 평가를 떨어뜨릴 만한 내용인지"),
            ],
            closing="피고소인은 이로써 공연히 사실(허위사실)을 적시하여 고소인의 명예를 훼손하였습니다.",
            notes=[
                _ANTI_WILL,
                "적시한 사실이 진실이고 오로지 공공의 이익을 위한 것이면 처벌되지 않을 수 있습니다(형법 제310조).",
            ],
        ),
        Crime(
            "사이버명예훼손",
            "사이버 명예훼손",
            "인터넷 게시글·댓글·단체방 등에서 고소인의 명예를 훼손한 경우",
            ["000030-70", "001692-307", "001692-310"],
            ["incident_datetime", "post_url", "words_used"]
            + _PUBLIC
            + ["falsity", "evidence"],
            ["repeated", "suspect_description", "relationship"],
            "정보통신망이용촉진및정보보호등에관한법률위반(명예훼손)",
            [
                "게시글·댓글 캡처(URL과 작성 시각이 보이게)",
                "단체방 대화 내보내기 파일",
                "허위임을 보여주는 자료",
                "작성자 닉네임·프로필 캡처",
            ],
            category="명예·모욕",
            elements=[
                (
                    "정보통신망 이용",
                    "인터넷·SNS·메신저 등 정보통신망을 통해 드러냈는지",
                ),
                (
                    "공공연성",
                    "여러 사람이 보거나 전파될 수 있었는지(공개 게시판, 단체방 등)",
                ),
                ("사실(거짓) 적시", "구체적인 사실이나 거짓 사실을 드러냈는지"),
                ("특정성", "고소인을 가리킨다는 것을 알 수 있었는지"),
                (
                    "비방할 목적",
                    "공익 목적이 아니라 고소인을 비방하려는 목적이 드러나는지",
                ),
            ],
            closing="피고소인은 이로써 고소인을 비방할 목적으로 정보통신망을 통하여 공공연하게 사실(거짓의 사실)을 드러내어 고소인의 명예를 훼손하였습니다.",
            notes=[
                _ANTI_WILL,
                "게시물이 지워지기 전에 URL·작성 시각이 보이도록 캡처해 두세요.",
            ],
        ),
        Crime(
            "모욕",
            "모욕",
            "여러 사람이 보는 자리나 온라인에서 욕설·경멸적 표현을 한 경우",
            ["001692-311", "001692-312"],
            ["incident_datetime", "incident_place", "words_used"]
            + _PUBLIC
            + ["known_date", "evidence"],
            ["post_url", "repeated", "suspect_description"],
            "모욕",
            [
                "욕설이 담긴 캡처·녹음(URL·시각 포함)",
                "현장·단체방에 있던 사람 명단",
                "작성자 닉네임·프로필 캡처",
            ],
            category="명예·모욕",
            elements=[
                (
                    "공연성",
                    "여러 사람이 보거나 들을 수 있었는지(1:1 대화는 해당하기 어려움)",
                ),
                ("모욕적 표현", "구체적 사실 없이 경멸적 감정을 표현한 욕설·비하인지"),
                (
                    "특정성",
                    "고소인을 가리킨다는 것을 알 수 있었는지(닉네임만 있는 경우 특히 중요)",
                ),
            ],
            closing="피고소인은 이로써 공연히 고소인을 모욕하였습니다.",
            notes=[
                "모욕죄는 " + _COMPLAINT_ONLY,
                "1:1 대화나 개인 메시지는 여러 사람이 볼 수 없어 모욕죄가 되기 어렵습니다.",
            ],
        ),
        # ── 폭력·협박 ──
        Crime(
            "폭행",
            "폭행",
            "때리거나 밀치는 등 신체에 물리적 힘을 쓴 경우(다치지 않은 경우 포함)",
            ["001692-260", "001692-261", "001692-262"],
            ["incident_datetime", "incident_place", "act_description", "evidence"],
            ["weapon", "witnesses", "relationship", "injury"],
            "폭행",
            ["CCTV·블랙박스·휴대폰 영상", "목격자 연락처", "병원 진료기록(있다면)"],
            category="폭력·협박",
            elements=[
                (
                    "폭행",
                    "사람의 신체에 대한 유형력의 행사(때림, 밀침, 멱살 잡기 등)가 있었는지",
                ),
                ("고의", "일부러 한 행위인지"),
            ],
            closing="피고소인은 이로써 고소인의 신체에 대하여 폭행을 가하였습니다.",
            notes=[
                _ANTI_WILL,
                "흉기 등 위험한 물건을 들었다면 특수폭행이 되어 더 무겁게 처벌되고, 처벌불원으로 끝나지 않습니다.",
            ],
        ),
        Crime(
            "상해",
            "상해",
            "폭행 등으로 다쳐 치료가 필요한 경우",
            ["001692-257", "001692-258의2", "001692-262"],
            [
                "incident_datetime",
                "incident_place",
                "act_description",
                "injury",
                "evidence",
            ],
            ["weapon", "witnesses", "relationship"],
            "상해",
            ["상해진단서", "다친 부위 사진(날짜별)", "CCTV·영상", "치료비 영수증"],
            category="폭력·협박",
            elements=[
                ("상해행위", "피고소인의 행위(폭행 등)가 무엇이었는지"),
                (
                    "상해의 결과",
                    "신체의 생리적 기능이 훼손되는 상처가 생겼는지(진단 내용)",
                ),
                ("인과관계", "그 상처가 피고소인의 행위로 생겼는지"),
            ],
            closing="피고소인은 이로써 고소인에게 약 ○주간의 치료가 필요한 ○○ 등의 상해를 가하였습니다.",
            notes=[
                "병원에서 상해진단서를 발급받아 두세요. 다친 부위 사진은 날짜별로 남겨 두면 좋습니다."
            ],
        ),
        Crime(
            "협박",
            "협박",
            "해를 끼치겠다고 겁을 준 경우(말·문자·메신저 포함)",
            ["001692-283", "001692-284", "001692-286"],
            ["incident_datetime", "words_used", "act_description", "evidence"],
            ["weapon", "repeated", "relationship", "contact_channel"],
            "협박",
            ["협박 문자·메신저 캡처", "통화 녹음", "당시 상황을 아는 사람의 진술"],
            category="폭력·협박",
            elements=[
                (
                    "해악의 고지",
                    "생명·신체·재산·명예 등에 해를 끼치겠다고 알렸는지(구체적 내용)",
                ),
                ("공포심", "일반적으로 사람이 겁을 먹을 만한 정도인지"),
                ("도달", "그 말이 고소인에게 전달되었는지"),
            ],
            closing="피고소인은 이로써 고소인의 생명(신체)에 위해를 가할 듯한 태도를 보여 고소인을 협박하였습니다.",
            notes=[
                _ANTI_WILL,
                "흉기 등 위험한 물건을 보이며 협박했다면 특수협박이 되어 더 무겁게 처벌됩니다.",
            ],
        ),
        Crime(
            "체포감금",
            "감금",
            "밖으로 나가지 못하게 가두거나 붙잡아 둔 경우",
            ["001692-276"],
            ["incident_datetime", "incident_place", "act_description", "evidence"],
            ["weapon", "witnesses", "injury", "relationship"],
            "감금",
            ["위치 기록·문자", "탈출 후 신고 기록", "목격자 진술"],
            category="폭력·협박",
            elements=[
                (
                    "감금",
                    "일정한 장소에서 나가지 못하게 하여 신체활동의 자유를 제한했는지",
                ),
                ("시간", "얼마 동안 그 상태가 이어졌는지"),
            ],
            closing="피고소인은 이로써 고소인을 약 ○시간 동안 ○○에서 나가지 못하게 하여 감금하였습니다.",
        ),
        Crime(
            "강요",
            "강요",
            "폭행·협박으로 하기 싫은 일을 억지로 시킨 경우",
            ["001692-324"],
            ["incident_datetime", "words_used", "act_description", "evidence"],
            ["relationship", "repeated", "weapon"],
            "강요",
            ["강요한 메시지·녹음", "억지로 한 행위의 결과물(각서 등)"],
            category="폭력·협박",
            elements=[
                ("폭행·협박", "피고소인이 폭행이나 협박을 했는지"),
                (
                    "의무 없는 일·권리행사 방해",
                    "그로 인해 고소인이 하지 않아도 될 일을 하거나 권리를 행사하지 못했는지",
                ),
            ],
            closing="피고소인은 이와 같이 고소인을 협박하여 고소인으로 하여금 의무 없는 일을 하게 하였습니다.",
        ),
        # ── 성범죄 ──
        Crime(
            "강제추행",
            "강제추행",
            "원치 않는 신체 접촉 등 추행을 당한 경우",
            ["001692-298", "001692-299", "011187-10", "011187-11"],
            [
                "incident_datetime",
                "incident_place",
                "act_description",
                "victim_response",
                "evidence",
            ],
            ["relationship", "witnesses"],
            "강제추행",
            ["사건 직후 주변에 알린 메시지", "CCTV", "진료기록", "상대와의 대화 기록"],
            category="성범죄",
            elements=[
                (
                    "폭행·협박",
                    "상대가 반항을 어렵게 하는 폭행·협박을 했거나 기습적으로 신체를 접촉했는지",
                ),
                ("추행", "성적 수치심이나 혐오감을 일으키는 신체 접촉 등이 있었는지"),
                ("의사에 반함", "고소인이 원하지 않았다는 사정"),
            ],
            closing="피고소인은 이로써 고소인을 추행하였습니다.",
            notes=[_SEX_SUPPORT],
            sensitive=True,
        ),
        Crime(
            "불법촬영",
            "불법촬영·유포",
            "동의 없이 신체를 촬영하거나 그 촬영물을 퍼뜨린 경우",
            ["011187-14", "011187-15"],
            [
                "incident_datetime",
                "incident_place",
                "act_description",
                "victim_response",
                "evidence",
            ],
            ["post_url", "relationship", "suspect_description"],
            "성폭력범죄의처벌등에관한특례법위반(카메라등이용촬영)",
            [
                "촬영·유포 사실을 보여주는 캡처(URL 포함)",
                "상대 기기에 촬영물이 있다는 정황",
                "주변 목격자",
            ],
            category="성범죄",
            elements=[
                ("촬영(또는 반포)", "카메라 등으로 촬영했거나 그 촬영물을 퍼뜨렸는지"),
                ("대상", "성적 욕망 또는 수치심을 유발할 수 있는 신체인지"),
                ("의사에 반함", "촬영이나 유포가 고소인의 의사에 반했는지"),
            ],
            closing="피고소인은 이로써 카메라를 이용하여 성적 욕망 또는 수치심을 유발할 수 있는 고소인의 신체를 고소인의 의사에 반하여 촬영하였습니다.",
            notes=[_SEX_SUPPORT, _DIGITAL_SUPPORT],
            sensitive=True,
        ),
        Crime(
            "통신매체음란",
            "통신매체 이용 음란",
            "성적인 문자·사진·영상을 원치 않게 보내온 경우",
            ["011187-13"],
            ["incident_datetime", "contact_channel", "words_used", "evidence"],
            ["repeated", "victim_response", "relationship", "suspect_description"],
            "성폭력범죄의처벌등에관한특례법위반(통신매체이용음란)",
            [
                "받은 메시지·사진 캡처(발신자·시각 포함)",
                "발신 번호·계정 정보",
                "차단·거절 기록",
            ],
            category="성범죄",
            elements=[
                ("통신매체 이용", "전화·문자·메신저·SNS 등으로 보냈는지"),
                ("음란성", "성적 수치심이나 혐오감을 일으키는 말·글·그림·영상인지"),
                ("목적", "성적 욕망을 유발하거나 만족시키려는 목적이 드러나는지"),
                ("도달", "고소인에게 도달했는지"),
            ],
            closing="피고소인은 이로써 자기의 성적 욕망을 만족시킬 목적으로 통신매체를 통하여 성적 수치심이나 혐오감을 일으키는 글(그림·영상)을 고소인에게 도달하게 하였습니다.",
            notes=[_SEX_SUPPORT],
            sensitive=True,
        ),
        Crime(
            "허위영상물",
            "딥페이크(허위영상물)",
            "얼굴·신체를 합성한 성적 영상물을 만들거나 퍼뜨린 경우",
            ["011187-14의2", "011187-15"],
            [
                "incident_datetime",
                "post_url",
                "act_description",
                "identifiability",
                "evidence",
            ],
            ["suspect_description", "relationship", "repeated"],
            "성폭력범죄의처벌등에관한특례법위반(허위영상물편집·반포등)",
            [
                "합성물이 올라온 곳의 캡처(URL 포함)",
                "원본 사진의 출처",
                "유포자 계정 정보",
            ],
            category="성범죄",
            elements=[
                ("대상", "고소인의 얼굴·신체·음성을 대상으로 한 영상물인지"),
                (
                    "편집·합성",
                    "성적 욕망 또는 수치심을 유발할 수 있는 형태로 편집·합성·가공했는지",
                ),
                ("반포 등", "그 영상물을 퍼뜨리거나 제공했는지"),
                ("의사에 반함", "고소인의 의사에 반했는지"),
            ],
            closing="피고소인은 이로써 고소인의 얼굴을 대상으로 한 영상물을 고소인의 의사에 반하여 성적 욕망 또는 수치심을 유발할 수 있는 형태로 편집·합성하고 이를 반포하였습니다.",
            notes=[_SEX_SUPPORT, _DIGITAL_SUPPORT],
            sensitive=True,
        ),
        Crime(
            "촬영물협박",
            "촬영물 이용 협박",
            "성적 촬영물을 퍼뜨리겠다고 협박한 경우",
            ["011187-14의3", "011187-15"],
            ["incident_datetime", "contact_channel", "words_used", "evidence"],
            ["damage_amount", "repeated", "relationship", "suspect_description"],
            "성폭력범죄의처벌등에관한특례법위반(촬영물등이용협박)",
            [
                "협박 메시지 캡처(발신자·시각 포함)",
                "송금 요구·송금 내역",
                "상대 계정 정보",
            ],
            category="성범죄",
            elements=[
                (
                    "촬영물",
                    "성적 욕망 또는 수치심을 유발할 수 있는 촬영물이나 편집물인지",
                ),
                ("협박", "그 촬영물을 이용해 해를 끼치겠다고(유포 등) 협박했는지"),
            ],
            closing="피고소인은 이로써 성적 욕망 또는 수치심을 유발할 수 있는 촬영물을 이용하여 고소인을 협박하였습니다.",
            notes=[
                _SEX_SUPPORT,
                _DIGITAL_SUPPORT,
                "상대의 요구에 응해 돈을 보내도 유포가 멈춘다는 보장이 없습니다. 대화 기록을 지우지 말고 바로 신고하세요.",
            ],
            sensitive=True,
        ),
        # ── 스토킹·괴롭힘 ──
        Crime(
            "스토킹",
            "스토킹",
            "원치 않는데도 따라다니거나 연락·접근을 반복하는 경우",
            ["014070-2", "014070-18"],
            [
                "incident_datetime",
                "act_description",
                "repeated",
                "victim_response",
                "evidence",
            ],
            ["contact_channel", "relationship", "words_used", "suspect_description"],
            "스토킹범죄의처벌등에관한법률위반",
            [
                "연락·방문 기록(날짜별 목록)",
                "문자·메신저 캡처",
                "CCTV·사진",
                "거절 의사를 밝힌 기록",
                "신고 이력",
            ],
            category="스토킹·괴롭힘",
            elements=[
                (
                    "스토킹행위",
                    "접근·따라다님·기다림·연락·물건 전달 등 법에서 정한 행위를 했는지",
                ),
                ("의사에 반함", "고소인의 의사에 반해 정당한 이유 없이 했는지"),
                ("불안감·공포심", "그로 인해 불안감이나 공포심을 일으켰는지"),
                ("지속성·반복성", "지속적 또는 반복적으로 이루어졌는지(날짜·횟수)"),
            ],
            closing="피고소인은 이로써 고소인의 의사에 반하여 정당한 이유 없이 지속적·반복적으로 스토킹행위를 하여 스토킹범죄를 저질렀습니다.",
            notes=[
                "지금 위험하다면 즉시 112에 신고하세요. 경찰에 접근금지 등 긴급응급조치를 요청할 수 있습니다.",
                "날짜별로 무슨 일이 있었는지 목록을 만들어 두면 반복성을 증명하는 데 큰 도움이 됩니다.",
            ],
        ),
        Crime(
            "불안감유발",
            "사이버 괴롭힘(불안감 유발)",
            "공포심·불안감을 주는 문자·메시지를 반복해서 보내는 경우",
            ["000030-44의7", "000030-74"],
            [
                "incident_datetime",
                "contact_channel",
                "words_used",
                "repeated",
                "evidence",
            ],
            ["victim_response", "relationship", "suspect_description"],
            "정보통신망이용촉진및정보보호등에관한법률위반",
            [
                "받은 메시지 전체 캡처(발신자·시각 포함)",
                "날짜별 수신 목록",
                "차단·거절 기록",
            ],
            category="스토킹·괴롭힘",
            elements=[
                ("정보통신망 이용", "문자·메신저·이메일 등으로 보냈는지"),
                ("공포심·불안감 유발", "내용이 공포심이나 불안감을 유발하는 것인지"),
                ("반복성", "반복적으로 고소인에게 도달했는지(횟수·기간)"),
            ],
            closing="피고소인은 이로써 정보통신망을 통하여 공포심이나 불안감을 유발하는 글(음향·영상)을 반복적으로 고소인에게 도달하게 하였습니다.",
            notes=[
                "상대가 직접 찾아오거나 따라다니는 행위까지 있다면 스토킹으로 고소하는 것이 더 적합할 수 있습니다."
            ],
        ),
        # ── 주거·업무·문서 ──
        Crime(
            "주거침입",
            "주거침입",
            "허락 없이 집·사무실 등에 들어온 경우",
            ["001692-319", "001692-320"],
            ["incident_datetime", "incident_place", "act_description", "evidence"],
            ["weapon", "witnesses", "relationship", "suspect_description"],
            "주거침입",
            ["도어락 출입 기록", "CCTV·현관 카메라 영상", "목격자 진술"],
            category="주거·업무·문서",
            elements=[
                ("주거 등", "사람이 사는 집이나 관리하는 건조물·방실인지"),
                ("침입", "거주자의 의사에 반해 들어가 사실상의 평온을 해쳤는지"),
            ],
            closing="피고소인은 이로써 고소인의 주거에 침입하였습니다.",
        ),
        Crime(
            "업무방해",
            "업무방해",
            "거짓 소문·위력으로 가게·회사 등의 업무를 방해한 경우",
            ["001692-314", "001692-313"],
            [
                "incident_datetime",
                "incident_place",
                "act_description",
                "damage_amount",
                "evidence",
            ],
            ["words_used", "witnesses", "repeated", "post_url"],
            "업무방해",
            ["방해 당시 영상·녹음", "매출 감소 등 피해 자료", "허위 게시물 캡처"],
            category="주거·업무·문서",
            elements=[
                ("업무", "고소인이 계속해서 하는 사업·직업상 업무인지"),
                (
                    "방해 수단",
                    "허위사실 유포·위계(속임수)·위력(소란, 협박 등)을 썼는지",
                ),
                ("방해 위험", "업무가 방해되었거나 방해될 위험이 있었는지"),
            ],
            closing="피고소인은 이로써 위력(위계)으로 고소인의 ○○ 업무를 방해하였습니다.",
        ),
        Crime(
            "사문서위조",
            "문서위조",
            "고소인 명의의 계약서·위임장 등을 몰래 만들어 쓴 경우",
            ["001692-231", "001692-234", "001692-232의2"],
            ["incident_datetime", "document_details", "act_description", "evidence"],
            ["damage_amount", "relationship"],
            "사문서위조, 위조사문서행사",
            [
                "위조된 문서 사본",
                "고소인이 작성하지 않았음을 보여주는 자료(필적·인감 등)",
                "문서가 제출된 기관의 확인",
            ],
            category="주거·업무·문서",
            elements=[
                (
                    "권리의무·사실증명 문서",
                    "위조된 것이 권리·의무나 사실을 증명하는 문서인지",
                ),
                ("위조", "작성 권한 없이 고소인 명의로 문서를 만들었는지"),
                (
                    "행사할 목적·행사",
                    "그 문서를 진짜처럼 쓰려는 목적으로 만들고 실제로 제출했는지",
                ),
            ],
            closing="피고소인은 이로써 행사할 목적으로 권리의무에 관한 사문서인 고소인 명의의 ○○ 1장을 위조하고, 이를 ○○에 제출하여 행사하였습니다.",
        ),
        # ── 사이버·개인정보 ──
        Crime(
            "정보통신망침입",
            "해킹·계정 도용",
            "허락 없이 계정·컴퓨터에 접속하거나 정보를 빼간 경우",
            ["000030-48", "000030-49", "000030-71", "000030-72"],
            ["incident_datetime", "act_description", "evidence"],
            ["post_url", "damage_amount", "suspect_description", "relationship"],
            "정보통신망이용촉진및정보보호등에관한법률위반(정보통신망침해등)",
            [
                "접속 기록(로그인 알림, 접속 IP)",
                "변경된 설정·삭제된 자료 캡처",
                "서비스 회사에 신고한 기록",
            ],
            category="사이버·개인정보",
            elements=[
                (
                    "정보통신망 침입",
                    "정당한 접근권한 없이(또는 권한을 넘어) 계정·시스템에 접속했는지",
                ),
                (
                    "정보 훼손·도용",
                    "타인의 정보를 훼손하거나 비밀을 침해·도용·누설했는지(해당하면)",
                ),
            ],
            closing="피고소인은 이로써 정당한 접근권한 없이 정보통신망에 침입하였습니다.",
            notes=[
                "비밀번호를 바로 바꾸고, 서비스 회사에 접속 기록(IP 등) 보존을 요청해 두세요."
            ],
        ),
        Crime(
            "개인정보유출",
            "개인정보 유출",
            "업무로 알게 된 고소인의 개인정보를 동의 없이 퍼뜨리거나 넘긴 경우",
            ["011357-59", "011357-71"],
            ["incident_datetime", "act_description", "evidence"],
            ["post_url", "relationship", "damage_amount"],
            "개인정보보호법위반",
            [
                "유출된 정보가 담긴 캡처",
                "상대가 그 정보를 알게 된 경위를 보여주는 자료",
            ],
            category="사이버·개인정보",
            elements=[
                ("개인정보", "고소인을 알아볼 수 있는 정보(이름·연락처·주소 등)인지"),
                (
                    "취급 지위",
                    "상대가 업무상 그 정보를 알게 되었거나 처리하던 사람인지",
                ),
                ("누설·제공", "동의 없이 다른 사람에게 알리거나 넘겼는지"),
            ],
            closing="피고소인은 이로써 업무상 알게 된 고소인의 개인정보를 고소인의 동의 없이 제3자에게 누설(제공)하였습니다.",
        ),
        Crime(
            "비밀침해",
            "비밀침해",
            "잠겨 있는 편지·휴대폰·파일 등을 몰래 열어 본 경우",
            ["001692-316", "001692-318"],
            ["incident_datetime", "act_description", "known_date", "evidence"],
            ["relationship", "witnesses"],
            "비밀침해",
            ["잠금 해제·열람 흔적", "상대가 내용을 알고 있다는 정황(메시지 등)"],
            category="사이버·개인정보",
            elements=[
                (
                    "비밀장치",
                    "봉함하거나 비밀번호 등으로 잠가 둔 편지·문서·전자기록인지",
                ),
                (
                    "개봉·기술적 수단",
                    "그 장치를 풀거나 기술적 수단으로 내용을 알아냈는지",
                ),
            ],
            closing="피고소인은 이로써 비밀장치한 고소인의 ○○을 기술적 수단을 이용하여 그 내용을 알아내었습니다.",
            notes=["비밀침해죄는 " + _COMPLAINT_ONLY],
        ),
        # ── 노동 ──
        Crime(
            "임금체불",
            "임금·퇴직금 체불",
            "일한 대가(임금·퇴직금)를 받지 못한 경우",
            ["001872-36", "001872-43", "001872-109"],
            ["employment_period", "wage_details", "damage_amount", "evidence"],
            ["relationship", "post_conduct"],
            "근로기준법위반",
            [
                "근로계약서",
                "급여명세서·통장 입금 내역",
                "출퇴근 기록",
                "임금 지급을 요구한 메시지",
            ],
            category="노동",
            elements=[
                ("근로자", "고소인이 사용자에게 고용되어 임금을 받는 근로자였는지"),
                ("임금 미지급", "지급해야 할 임금·퇴직금을 지급하지 않았는지(금액)"),
                ("지급 기한 경과", "퇴직 후 14일 등 지급 기한이 지났는지"),
            ],
            closing="피고소인은 이로써 고소인의 임금(퇴직금) 합계 금 ○○원을 지급 사유가 발생한 때부터 14일 이내에 지급하지 아니하였습니다.",
            notes=[
                "임금체불은 보통 사업장 관할 지방고용노동청에 진정 또는 고소합니다. 제출처를 고용노동청으로 하는 것을 고려하세요."
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
        "categories": CATEGORIES,
        "crimes": [
            {
                "id": c.id,
                "label": c.label,
                "summary": c.summary,
                "category": c.category,
                "fields": fact_keys_for(c.id),
                "required": required_keys_for(c.id),
                "evidence_tips": c.evidence_tips,
                "notes": c.notes,
                "sensitive": c.sensitive,
            }
            for c in CRIMES.values()
        ],
    }
