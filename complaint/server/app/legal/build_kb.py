"""법령정보센터(law.go.kr) Open API에서 조문·판례 원문을 받아 지식베이스 스냅샷을 만든다.

    cd complaint/server && ../../.venv/bin/python -m app.legal.build_kb

LAW_API_OC 환경변수(법령정보센터 Open API 신청 시 등록한 이메일 ID)를 쓴다.
결과는 app/legal/data/statutes.json, precedents.json 에 저장되고 서버는 이 파일만
읽는다 — 법률 정보는 모델의 기억이 아니라 항상 이 공식 원문에서 나와야 한다.
법이 개정되면 이 스크립트를 다시 돌리면 된다.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
BASE = "https://www.law.go.kr/DRF"
OC = os.getenv("LAW_API_OC") or "test"

# (법령명, [조문번호("347", "347의2")], 태그). 법령ID는 이름으로 현행 판본을 찾아 채운다.
STATUTES = [
    (
        "형법",
        ["347", "347의2", "348", "348의2", "349", "351", "352", "353", "354"],
        ["사기"],
    ),
    ("형법", ["328"], ["친족", "고소"]),
    ("형법", ["355", "356"], ["횡령", "배임"]),
    ("형법", ["329", "330", "331", "332"], ["절도"]),
    ("형법", ["350", "350의2"], ["공갈"]),
    ("형법", ["366", "369"], ["손괴"]),
    ("형법", ["307", "308", "309", "310", "311", "312"], ["명예훼손", "모욕"]),
    ("형법", ["313", "314"], ["업무방해", "신용훼손"]),
    ("형법", ["257", "258의2", "260", "261", "262", "266"], ["폭행", "상해"]),
    ("형법", ["276"], ["감금"]),
    ("형법", ["283", "284", "285", "286"], ["협박"]),
    ("형법", ["324"], ["강요"]),
    ("형법", ["297", "298", "299", "305"], ["성범죄"]),
    ("형법", ["319", "320"], ["주거침입"]),
    ("형법", ["316", "318"], ["비밀침해"]),
    ("형법", ["231", "232의2", "234"], ["문서위조"]),
    ("형법", ["30", "37", "38"], ["공범", "경합"]),
    ("형법", ["156"], ["무고", "주의"]),
    ("특정경제범죄 가중처벌 등에 관한 법률", ["3"], ["사기", "가중처벌", "고액"]),
    ("보험사기방지 특별법", ["2", "8", "10", "11"], ["보험사기"]),
    (
        "전기통신금융사기 피해 방지 및 피해금 환급에 관한 특별법",
        ["2", "15의2"],
        ["보이스피싱", "전기통신금융사기"],
    ),
    (
        "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
        ["44의7", "48", "49", "70", "71", "72", "74"],
        ["정보통신망", "사이버"],
    ),
    (
        "성폭력범죄의 처벌 등에 관한 특례법",
        ["2", "10", "11", "13", "14", "14의2", "14의3", "15"],
        ["성범죄"],
    ),
    ("스토킹범죄의 처벌 등에 관한 법률", ["2", "18"], ["스토킹"]),
    ("근로기준법", ["36", "43", "109"], ["임금체불", "노동"]),
    ("개인정보 보호법", ["59", "71"], ["개인정보"]),
    (
        "형사소송법",
        ["223", "224", "225", "230", "232", "237", "238", "249", "252", "257"],
        ["고소", "절차", "공소시효"],
    ),
    ("소송촉진 등에 관한 특례법", ["25", "26"], ["배상명령", "피해회복"]),
    ("민법", ["750"], ["손해배상", "민사"]),
]

_FRAUD_MUST = ("사기", "편취")

# 유형별 판례: (검색어들, 판시사항에 반드시 있어야 할 말 중 하나).
# 판례 요지는 공식 원문 그대로 저장한다.
PRECEDENT_QUERIES = {
    "차용사기": (
        ["차용금 편취 변제능력", "차용금 편취의 범의", "변제할 의사나 능력"],
        _FRAUD_MUST,
    ),
    "계약금사기": (
        ["물품대금 편취 납품", "계약금 편취", "거래 대금 편취의 범의"],
        _FRAUD_MUST,
    ),
    "분양사기": (["분양대금 편취", "분양 기망 사기"], _FRAUD_MUST),
    "소송사기": (["소송사기", "허위의 주장과 증거 법원 기망"], _FRAUD_MUST),
    "아이템사기": (
        ["게임 아이템 편취", "게임머니 사기", "게임 아이템 재산상 이익"],
        _FRAUD_MUST,
    ),
    "인터넷물품사기": (
        ["인터넷 물품 판매 대금 편취", "중고거래 사기", "물품 대금 편취 사기죄"],
        _FRAUD_MUST,
    ),
    "취업사기": (
        ["취업 알선 명목 금원 편취", "취업시켜 주겠다 편취", "청탁 명목 금원 편취"],
        _FRAUD_MUST,
    ),
    "보험사기": (["보험금 편취 사기", "보험사고 가장 보험금"], _FRAUD_MUST),
    "기타사기": (
        ["기망행위 고지의무 부작위 사기", "사기죄 처분행위", "편취의 범의 판단"],
        _FRAUD_MUST,
    ),
    "횡령": (
        [
            "횡령죄 보관자 위탁관계",
            "불법영득의사 횡령",
            "목적과 용도를 정하여 위탁한 금전 횡령",
        ],
        ("횡령",),
    ),
    "배임": (["배임죄 타인의 사무를 처리하는 자", "임무위배행위 배임"], ("배임",)),
    "절도": (["절도죄 절취 점유", "절도죄 불법영득의사"], ("절도", "절취")),
    "공갈": (["공갈죄 협박 재물 교부", "공갈죄 해악의 고지"], ("공갈",)),
    "재물손괴": (["재물손괴 효용을 해하는", "손괴죄 효용"], ("손괴",)),
    "명예훼손": (
        [
            "명예훼손 공연성 전파가능성",
            "사실의 적시 명예훼손",
            "허위사실 적시 명예훼손",
        ],
        ("명예훼손",),
    ),
    "사이버명예훼손": (
        ["정보통신망 명예훼손 비방할 목적", "인터넷 게시글 명예훼손"],
        ("명예훼손",),
    ),
    "모욕": (["모욕죄 경멸적 감정", "모욕 공연성", "인터넷 댓글 모욕"], ("모욕",)),
    "폭행": (["폭행죄 유형력의 행사", "신체에 대한 폭행"], ("폭행",)),
    "상해": (["상해죄 생리적 기능 훼손", "상해 진단서 상해 인정"], ("상해",)),
    "협박": (["협박죄 해악의 고지", "협박죄 공포심"], ("협박",)),
    "체포감금": (["감금죄 신체활동의 자유", "체포 감금"], ("감금", "체포")),
    "강요": (["강요죄 의무없는 일", "강요죄 폭행 협박"], ("강요",)),
    "강제추행": (["강제추행 폭행 협박 추행", "추행의 의미 성적 수치심"], ("추행",)),
    "불법촬영": (["카메라등이용촬영 성적 욕망 수치심 신체", "촬영물 반포"], ("촬영",)),
    "통신매체음란": (
        ["통신매체이용음란 성적 수치심 도달", "통신매체 음란 메시지"],
        ("통신매체",),
    ),
    "허위영상물": (
        ["허위영상물 편집 합성 반포", "딥페이크 영상물"],
        ("허위영상물", "편집물", "합성"),
    ),
    "촬영물협박": (["촬영물 이용 협박", "성적 촬영물 유포 협박"], ("촬영물",)),
    "스토킹": (["스토킹범죄 지속적 반복적", "스토킹행위 불안감 공포심"], ("스토킹",)),
    "불안감유발": (
        [
            "공포심이나 불안감을 유발하는 문언 반복",
            "정보통신망 불안감 유발 반복적 도달",
        ],
        ("공포심", "불안감"),
    ),
    "주거침입": (["주거침입 사실상의 평온", "주거침입죄 침입"], ("주거침입", "침입")),
    "업무방해": (["업무방해 위력", "업무방해 허위사실 유포 위계"], ("업무방해",)),
    "사문서위조": (["사문서위조 명의자 승낙", "위조사문서행사"], ("위조",)),
    "정보통신망침입": (
        ["정보통신망 침입 접근권한", "타인의 아이디 비밀번호 접속"],
        ("정보통신망", "침입", "접근권한"),
    ),
    "개인정보유출": (
        ["개인정보 누설 제공", "개인정보 보호법 위반 누설"],
        ("개인정보",),
    ),
    "비밀침해": (
        ["비밀침해 전자기록 기술적 수단", "비밀장치 편지 개봉"],
        ("비밀침해", "비밀장치"),
    ),
    "임금체불": (
        ["임금 퇴직금 미지급 근로기준법 위반", "금품청산 퇴직금 지급 기일"],
        ("임금", "퇴직금"),
    ),
}

# 형사 판결 사건번호(도·고단·고합·노·고정 등)만 쓴다.
_CRIMINAL_CASE_RE = re.compile(r"\d{2,4}\s*(도|고단|고합|노|고정|고약)\s*\d+")


def _get(path: str, **params) -> dict:
    params = {"OC": OC, "type": "JSON", **params}
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 일시 오류는 재시도
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"law.go.kr 요청 실패: {url} ({last})")


def _jo_code(no: str) -> str:
    m = re.fullmatch(r"(\d+)(?:의(\d+))?", no)
    if not m:
        raise ValueError(no)
    return f"{int(m.group(1)):04d}{int(m.group(2) or 0):02d}"


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _clean(s: str) -> str:
    if isinstance(s, list):  # 여러 줄짜리 항·호·목은 문자열 목록으로 온다
        s = "\n".join(x if isinstance(x, str) else "\n".join(map(str, x)) for x in s)
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"[ \t　]+", " ", s)
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


def _article_text(unit: dict) -> str:
    lines = [_clean(unit.get("조문내용", ""))]
    for hang in _as_list(unit.get("항")):
        if isinstance(hang, dict):
            lines.append(_clean(hang.get("항내용", "")))
            for ho in _as_list(hang.get("호")):
                if isinstance(ho, dict):
                    lines.append(_clean(ho.get("호내용", "")))
                    for mok in _as_list(ho.get("목")):
                        if isinstance(mok, dict):
                            lines.append(_clean(mok.get("목내용", "")))
    return "\n".join(x for x in lines if x)


def _current_version(law_name: str) -> tuple[str, str, str]:
    """현재 시행 중인 판본의 (법령ID, 법령일련번호, 시행일자).

    target=law 로 조회하면 공포만 되고 아직 시행 전인 판본이 섞여 온다(예:
    형사소송법이 2027년 시행본으로 내려옴). 고소장은 지금 시행 중인 법을
    적용해야 하므로 시행일 기준(eflaw) 검색에서 '현행' 판본을 고른다.
    """
    d = _get("lawSearch.do", target="eflaw", query=law_name, display=100)
    for it in _as_list(d.get("LawSearch", {}).get("law")):
        if it.get("법령명한글") == law_name and it.get("현행연혁코드") == "현행":
            return it["법령ID"], it["법령일련번호"], it["시행일자"]
    raise RuntimeError(f"{law_name}의 현행 판본을 찾지 못했습니다")


def fetch_statutes() -> list[dict]:
    out = []
    versions: dict[str, tuple[str, str, str]] = {}
    for law_name, articles, tags in STATUTES:
        if law_name not in versions:
            versions[law_name] = _current_version(law_name)
        law_id, mst, ef_date = versions[law_name]
        for no in articles:
            d = _get(
                "lawService.do", target="eflaw", MST=mst, efYd=ef_date, JO=_jo_code(no)
            )
            info = d["법령"]["기본정보"]
            units = [
                u
                for u in _as_list(d["법령"].get("조문", {}).get("조문단위"))
                if u.get("조문여부") == "조문"
            ]
            if not units:
                print(f"  ! {law_name} 제{no}조 없음", file=sys.stderr)
                continue
            u = units[0]
            main_no, _, branch = no.partition("의")
            label = f"제{main_no}조의{branch}" if branch else f"제{no}조"
            out.append(
                {
                    "id": f"{law_id}-{no}",
                    "law": law_name,
                    "article": no,
                    "label": f"{law_name} {label}",
                    "title": u.get("조문제목", ""),
                    "text": _article_text(u),
                    "effective": u.get("조문시행일자") or info.get("시행일자", ""),
                    "tags": tags,
                    "url": f"https://www.law.go.kr/법령/{urllib.parse.quote(law_name)}/{label}",
                }
            )
            print(f"  ✓ {law_name} {label}({u.get('조문제목', '')})")
            time.sleep(0.2)
    return out


def _relevance(query: str, text: str) -> int:
    terms = [t for t in re.split(r"\s+", query) if len(t) >= 2]
    return sum(text.count(t) for t in terms)


_detail_cache: dict[str, dict] = {}


def _prec_detail(pid: str) -> dict:
    if pid not in _detail_cache:
        _detail_cache[pid] = _get("lawService.do", target="prec", ID=pid).get(
            "PrecService", {}
        )
        time.sleep(0.15)
    return _detail_cache[pid]


def fetch_precedents(per_crime: int = 4) -> list[dict]:
    by_id: dict[str, dict] = {}
    for crime, (queries, must) in PRECEDENT_QUERIES.items():
        scored: dict[str, tuple[int, dict]] = {}
        for q in queries:
            d = _get("lawSearch.do", target="prec", query=q, display=30, search=2)
            for it in _as_list(d.get("PrecSearch", {}).get("prec")):
                pid = it.get("판례일련번호")
                case_no = it.get("사건번호", "")
                if not pid or not _CRIMINAL_CASE_RE.search(case_no):
                    continue
                detail = _prec_detail(pid)
                summary = _clean(detail.get("판결요지", ""))
                points = _clean(detail.get("판시사항", ""))
                # 판시사항(무엇을 판단했는지) 자체가 그 죄에 관한 것이어야 한다.
                # 판결요지 어딘가에 죄명이 한 번 나오는 판례(예: 사기 유형에 섞인 범인도피)는 거른다.
                if not summary or not any(w in points for w in must):
                    continue
                # 판시사항의 검색어 일치를 가장 크게, 대법원 판결을 우선한다
                score = (
                    _relevance(q, points) * 3
                    + _relevance(q, summary)
                    + sum(points.count(w) * 2 for w in must)
                    + (5 if "대법원" in detail.get("법원명", "") else 0)
                )
                if pid not in scored or scored[pid][0] < score:
                    scored[pid] = (score, detail)
        ranked = sorted(scored.items(), key=lambda kv: -kv[1][0])[:per_crime]
        for pid, (score, detail) in ranked:
            if pid in by_id:
                if crime not in by_id[pid]["crimes"]:
                    by_id[pid]["crimes"].append(crime)
                continue
            by_id[pid] = {
                "id": pid,
                "case_no": detail.get("사건번호", ""),
                "court": detail.get("법원명", ""),
                "date": detail.get("선고일자", ""),
                "name": _clean(detail.get("사건명", "")),
                "points": _clean(detail.get("판시사항", "")),
                "summary": _clean(detail.get("판결요지", "")),
                "refs": _clean(detail.get("참조조문", "")),
                "crimes": [crime],
                "url": f"https://www.law.go.kr/precInfoP.do?precSeq={pid}",
            }
            print(
                f"  ✓ [{crime}] {by_id[pid]['court']} {by_id[pid]['case_no']} (score {score})"
            )
    # 같은 판결이 판례일련번호만 달리해 여러 번 실린 경우(예: 97도2609)를 합친다
    merged: dict[str, dict] = {}
    for p in by_id.values():
        key = re.sub(r"\s", "", p["case_no"])
        if key in merged:
            merged[key]["crimes"] = sorted(
                set(merged[key]["crimes"]) | set(p["crimes"])
            )
        else:
            merged[key] = p
    return list(merged.values())


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("법령 조문 수집…")
    statutes = fetch_statutes()
    print("판례 수집…")
    precedents = fetch_precedents()
    meta = {
        "built": date.today().isoformat(),
        "source": "국가법령정보센터 Open API (law.go.kr)",
    }
    (DATA_DIR / "statutes.json").write_text(
        json.dumps({"meta": meta, "items": statutes}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (DATA_DIR / "precedents.json").write_text(
        json.dumps({"meta": meta, "items": precedents}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"완료: 조문 {len(statutes)}개, 판례 {len(precedents)}개")


if __name__ == "__main__":
    main()
