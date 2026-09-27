"""법률 지식베이스 검색 — 공식 원문 스냅샷(data/*.json) + 선택적 실시간 판례 검색.

검색은 한국어 문자 bigram BM25에 사건 유형 태그 가중치를 더한다. 지식베이스가
작고(조문 수십 개, 판례 수십 개) 도메인이 좁아서 임베딩 없이도 정확하고, 무엇보다
결과가 결정적이라 같은 사건이면 같은 근거가 나온다.

LAW_API_OC 가 설정되어 있으면 생성 단계에서 법령정보센터 판례를 실시간으로
추가 검색한다(실패해도 스냅샷만으로 동작).
"""

import json
import logging
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.legal.crimes import CRIMES, PROCEDURE_STATUTES

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
LAW_API_OC = (os.getenv("LAW_API_OC") or "").strip()


def _load(name: str) -> tuple[dict, list[dict]]:
    path = DATA_DIR / name
    if not path.exists():
        logger.error("지식베이스 파일이 없습니다: %s (build_kb.py 실행 필요)", path)
        return {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("meta", {}), data.get("items", [])


STAT_META, STATUTES = _load("statutes.json")
PREC_META, PRECEDENTS = _load("precedents.json")
STATUTE_BY_ID = {s["id"]: s for s in STATUTES}


# ── 토크나이저 · BM25 ─────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[가-힣]+|[a-zA-Z]+|\d+")


def _tokens(text: str) -> list[str]:
    out = []
    for w in _WORD_RE.findall(text or ""):
        if re.fullmatch(r"[가-힣]+", w):
            if len(w) == 1:
                out.append(w)
            out.extend(w[i : i + 2] for i in range(len(w) - 1))
        else:
            out.append(w.lower())
    return out


class _BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.72):
        self.k1, self.b = k1, b
        self.tfs = [Counter(_tokens(d)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        q = Counter(_tokens(query))
        out = []
        for tf, ln in zip(self.tfs, self.lens):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                s += (
                    self.idf.get(t, 0)
                    * f
                    * (self.k1 + 1)
                    / (f + self.k1 * (1 - self.b + self.b * ln / self.avg))
                )
            out.append(s)
        return out


_stat_index = _BM25(
    [f"{s['label']} {s['title']} {s['text']} {' '.join(s['tags'])}" for s in STATUTES]
)
_prec_index = _BM25([f"{p['name']} {p['points']} {p['summary']}" for p in PRECEDENTS])


# ── 금액 파싱 ────────────────────────────────────────────────────────────────
_UNITS = {"조": 10**12, "억": 10**8, "만": 10**4, "천": 10**3, "백": 10**2}


def parse_krw(text: str) -> int | None:
    """'1억 2천만원', '5,000,000원', '50만 원' 같은 금액을 원 단위 정수로. 없으면 None.

    단위(만·억 등)나 '원'이 붙은 숫자만 금액으로 본다 — '2025년 3월' 같은 날짜
    숫자를 금액으로 읽지 않기 위해서다. 여러 금액이 있으면 가장 큰 값(보통 합계).
    """
    if not text:
        return None
    t = str(text).replace(" ", "")
    best = None
    for m in re.finditer(r"(?:\d[\d,]*(?:\.\d+)?(?:조|억|천만|백만|만|천)?)+(원)?", t):
        chunk = m.group(0)
        has_unit = bool(re.search(r"(조|억|만|천)", chunk))
        if not (has_unit or m.group(1)):
            continue
        chunk = chunk.rstrip("원").replace(",", "")
        total = 0.0
        for part in re.finditer(r"(\d+(?:\.\d+)?)(조|억|천만|백만|만|천)?", chunk):
            n = float(part.group(1))
            unit = part.group(2)
            if not unit:
                total += n
            elif unit in ("천만", "백만"):
                total += n * _UNITS[unit[0]] * 10**4
            else:
                total += n * _UNITS[unit]
        value = int(total)
        if value >= 1000 and (best is None or value > best):
            best = value
    return best


def format_krw(n: int | None) -> str:
    if n is None:
        return ""
    eok, rest = divmod(n, 10**8)
    man, won = divmod(rest, 10**4)
    parts = []
    if eok:
        parts.append(f"{eok:,}억")
    if man:
        parts.append(f"{man:,}만")
    if won or not parts:
        parts.append(f"{won:,}")
    return " ".join(parts) + "원"


# ── 사실에 따른 추가 법조 ──────────────────────────────────────────────────────
_KIN_WORDS = (
    "부모",
    "아버지",
    "어머니",
    "자녀",
    "아들",
    "딸",
    "배우자",
    "남편",
    "아내",
    "형제",
    "자매",
    "오빠",
    "언니",
    "누나",
    "동생",
    "삼촌",
    "이모",
    "고모",
    "외삼촌",
    "사촌",
    "친척",
    "조카",
    "할머니",
    "할아버지",
    "사위",
    "며느리",
    "시어머니",
    "장모",
    "장인",
)
_PHISHING_WORDS = (
    "보이스피싱",
    "검찰 사칭",
    "검사 사칭",
    "경찰 사칭",
    "금감원",
    "대출 알선",
    "저금리 대출",
    "기관 사칭",
    "메신저피싱",
    "문자피싱",
    "스미싱",
    "엄마 나야",
    "자녀 사칭",
)


def contextual_statutes(crime_id: str | None, facts: dict) -> list[tuple[str, str]]:
    """사실관계를 보고 추가로 검토해야 할 법조를 (조문 id, 이유)로 돌려준다."""
    out: list[tuple[str, str]] = []
    amount = parse_krw(facts.get("damage_amount", ""))
    if amount is not None and amount >= 5 * 10**8:
        out.append(
            (
                "001136-3",
                f"피해액이 {format_krw(amount)}으로 5억원 이상이어서 가중처벌 대상이 될 수 있습니다.",
            )
        )
        if crime_id == "보험사기":
            out.append(
                (
                    "012521-11",
                    "보험사기이득액이 5억원 이상이면 가중처벌 대상이 될 수 있습니다.",
                )
            )
    rel = f"{facts.get('relationship', '')} {facts.get('suspect_description', '')}"
    if any(w in rel for w in _KIN_WORDS):
        out.append(
            (
                "001692-354",
                "친족 사이의 사기는 형법 제354조에 따라 제328조(친족 사이의 범행과 고소)가 준용됩니다.",
            )
        )
        out.append(
            (
                "001692-328",
                "친족 관계에 따라 고소가 있어야 공소를 제기할 수 있는 등 특칙이 적용될 수 있습니다.",
            )
        )
    blob = " ".join(str(v) for v in facts.values())
    if any(w in blob for w in _PHISHING_WORDS):
        out.append(
            (
                "011359-15의2",
                "전화·문자 등을 이용한 기관 사칭·대출 빙자 사기는 전기통신금융사기에 해당할 수 있습니다.",
            )
        )
        out.append(("011359-2", "전기통신금융사기의 정의 규정입니다."))
    if crime_id in ("계약금사기", "기타사기") and any(
        w in blob for w in ("보관", "위탁", "맡긴", "맡겼")
    ):
        out.append(
            (
                "001692-355",
                "돈을 맡긴(위탁) 경우라면 사기가 아니라 횡령에 해당할 수 있어 구별이 필요합니다.",
            )
        )
    return [(sid, why) for sid, why in out if sid in STATUTE_BY_ID]


def statutes_for_case(crime_id: str | None, facts: dict, limit: int = 8) -> list[dict]:
    """사건에 적용·검토할 조문 목록. [{..조문, reason, role}]"""
    picked: list[dict] = []
    seen = set()

    def add(sid: str, reason: str, role: str):
        if sid in seen or sid not in STATUTE_BY_ID:
            return
        seen.add(sid)
        picked.append({**STATUTE_BY_ID[sid], "reason": reason, "role": role})

    crime = CRIMES.get(crime_id or "")
    if crime:
        for i, sid in enumerate(crime.statutes):
            add(
                sid,
                "이 사건 유형의 핵심 처벌 규정입니다."
                if i == 0
                else "관련 규정입니다.",
                "core" if i == 0 else "related",
            )
    for sid, why in contextual_statutes(crime_id, facts):
        add(sid, why, "context")
    # 특경법은 5억 미만이면 굳이 보여주지 않는다
    amount = parse_krw(facts.get("damage_amount", ""))
    picked = [
        p
        for p in picked
        if not (p["id"] == "001136-3" and (amount is None or amount < 5 * 10**8))
    ]
    return picked[:limit]


def procedure_statutes() -> list[dict]:
    return [STATUTE_BY_ID[s] for s in PROCEDURE_STATUTES if s in STATUTE_BY_ID]


def search_precedents(
    query: str, crime_id: str | None = None, k: int = 3
) -> list[dict]:
    if not PRECEDENTS:
        return []
    scores = _prec_index.scores(query or "")
    ranked = []
    for p, s in zip(PRECEDENTS, scores):
        if crime_id and crime_id in p["crimes"]:
            s = s * 1.5 + 4.0
        elif "기타사기" in p["crimes"]:
            # 기망·편취 고의 같은 일반 법리 판례 — 유형별 판례가 부족할 때 보완
            s += 2.0
        if "대법원" in p.get("court", ""):
            s += 1.0
        ranked.append((s, p))
    ranked.sort(key=lambda x: -x[0])
    return [p for s, p in ranked[:k] if s > 0]


def search_statutes(query: str, k: int = 5) -> list[dict]:
    scores = _stat_index.scores(query or "")
    ranked = sorted(zip(scores, STATUTES), key=lambda x: -x[0])
    return [s for sc, s in ranked[:k] if sc > 0]


# ── 공소시효 (참고용 계산) ──────────────────────────────────────────────────────
def limitation_years(statute: dict) -> int | None:
    """법정형(장기)으로 형사소송법 제249조 제1항의 공소시효 기간을 고른다.

    지식베이스의 조문 원문에서 법정형을 읽는다. 무기징역이 있으면 15년, 장기
    10년 이상이면 10년, 10년 미만 7년, 5년 미만 5년.
    """
    text = statute.get("text", "")
    first = text.split("\n")[1] if "\n" in text else text
    if "무기" in first:
        return 15
    m = re.search(r"(\d+)년 이하의 징역", first)
    if m:
        years = int(m.group(1))
        return 10 if years >= 10 else (7 if years >= 5 else 5)
    if re.search(r"\d+년 이상의 (유기)?징역", first):
        return 10  # 유기징역 상한(30년)이 장기가 된다
    return None


# ── 실시간 판례 검색 (선택) ────────────────────────────────────────────────────
_live_cache: dict[str, tuple[float, list[dict]]] = {}
_live_lock = threading.Lock()
_CRIMINAL_CASE_RE = re.compile(r"\d{2,4}\s*(도|고단|고합|노|고정)\s*\d+")


def _law_get(path: str, timeout: float, **params) -> dict:
    params = {"OC": LAW_API_OC, "type": "JSON", **params}
    url = f"https://www.law.go.kr/DRF/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def live_precedents(query: str, k: int = 2, timeout: float = 5.0) -> list[dict]:
    """법령정보센터에서 형사 판례를 실시간 검색. 설정이 없거나 실패하면 빈 목록."""
    if not LAW_API_OC or not query.strip():
        return []
    with _live_lock:
        hit = _live_cache.get(query)
        if hit and time.time() - hit[0] < 86400:
            return hit[1]
    out: list[dict] = []
    try:
        d = _law_get(
            "lawSearch.do", timeout, target="prec", query=query, display=20, search=2
        )
        items = d.get("PrecSearch", {}).get("prec") or []
        items = items if isinstance(items, list) else [items]
        for it in items:
            if len(out) >= k:
                break
            if not _CRIMINAL_CASE_RE.search(it.get("사건번호", "")):
                continue
            det = _law_get(
                "lawService.do", timeout, target="prec", ID=it["판례일련번호"]
            ).get("PrecService", {})
            summary = re.sub(r"<[^>]+>", "", det.get("판결요지", "") or "").strip()
            if not summary or not any(w in summary for w in ("사기", "편취", "기망")):
                continue
            out.append(
                {
                    "id": it["판례일련번호"],
                    "case_no": det.get("사건번호", ""),
                    "court": det.get("법원명", ""),
                    "date": det.get("선고일자", ""),
                    "name": det.get("사건명", ""),
                    "points": re.sub(
                        r"<[^>]+>", "", det.get("판시사항", "") or ""
                    ).strip(),
                    "summary": summary,
                    "crimes": [],
                    "url": f"https://www.law.go.kr/precInfoP.do?precSeq={it['판례일련번호']}",
                    "live": True,
                }
            )
    except Exception as e:
        logger.warning("실시간 판례 검색 실패: %s", e)
    with _live_lock:
        _live_cache[query] = (time.time(), out)
    return out


@lru_cache(maxsize=1)
def meta() -> dict:
    return {
        "statutes": len(STATUTES),
        "precedents": len(PRECEDENTS),
        "built": STAT_META.get("built", ""),
        "source": STAT_META.get("source", ""),
        "live_search": bool(LAW_API_OC),
    }
