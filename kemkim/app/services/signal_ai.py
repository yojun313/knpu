"""KEMKIM 신호 AI 해석.

  1) 신호 단계 판정(결정적): 기간마다 단어의 빈도(DoV/DoD)와 직전 기간 대비 증가율을
     같은 기간 전체 단어의 중앙값과 비교해 강한/약한/잠재/알려진 신호로 분류하고,
     같은 단계가 이어지는 구간을 '국면'으로 묶는다.
  2) 맥락 추출(결정적): 원본 기사를 기간에 매핑해 국면별로 두드러진 연관어(전체 대비
     향상도)와 대표 문맥을 뽑는다. 문맥마다 번호(S1, S2 …)를 붙인다.
  3) AI 해석: 국면별 맥락이 어떻게 달라졌는지 서술하게 하되, 근거는 반드시 문맥 번호로
     인용하게 한다. 화면은 그 번호로 실제 기사를 보여 주므로 근거를 지어낼 수 없다.

AI 호출은 공통 모듈(system.llm)을 그대로 쓴다.
"""

import json
import math
import re
import statistics
from collections import Counter, defaultdict

import pandas as pd

import logging

from system.llm import LLMError, achat, user_llm

logger = logging.getLogger(__name__)

SIGNAL_LABEL = {
    "strong_signal": "강한 신호",
    "weak_signal": "약한 신호",
    "latent_signal": "잠재 신호",
    "well_known_signal": "알려진 신호",
}
_ABSENT = "absent"

_WINDOW = 160
_MAX_SNIPPETS_PER_PHASE = 6
_MAX_SNIPPETS_TOTAL = 36

# 연관어 추출에서 뺄 말: 조사가 붙은 흔한 어형, 기사 상투어
_STOPWORDS = set(
    """
있다 있는 있어 있을 있고 없다 없는 했다 한다 하는 하고 하며 하기 해서 했다고 한다고 된다 되는 됐다 되고
이번 지난 오는 이날 당시 현재 최근 올해 지난해 내년 오전 오후 이후 이전 등을 등이 등의 위해 위한 대한 대해
통해 관련 관한 따라 따른 이라고 이라며 라고 라며 밝혔다 말했다 전했다 설명했다 강조했다 덧붙였다 보인다 것으로
것이 것을 것은 그러나 하지만 또한 이어 특히 다만 한편 가운데 이에 이를 이와 그는 그녀 이들 우리 모든 여러
기자 뉴스 연합뉴스 무단 전재 재배포 금지 저작권 사진 제공 기사 영상 네이버 구독 뉴시스 뉴스1 동아일보 조선일보
중앙일보 한겨레 경향신문 머니투데이 이데일리 매일경제 한국경제 서울신문 국민일보 세계일보 헤럴드경제 아시아경제
""".split()
)
_JOSA = (
    "에서는",
    "으로는",
    "에게서",
    "으로서",
    "으로써",
    "에서",
    "에게",
    "으로",
    "까지",
    "부터",
    "처럼",
    "보다",
    "과의",
    "와의",
    "이라",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "와",
    "과",
    "도",
    "만",
    "로",
)
_TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9]{2,}")


def _norm_token(t: str) -> str:
    if re.fullmatch(r"[가-힣]+", t):
        for j in _JOSA:
            if not t.endswith(j) or len(t) - len(j) < 2:
                continue
            # '이'·'가'는 명사 끝 글자와 겹치는 일이 많아(오토바이, 아이) 세 글자 어형에서만 뗀다
            if j in ("이", "가") and len(t) != 3:
                continue
            return t[: -len(j)]
    return t.lower()


# '~다', '~니다', '~였다'처럼 끝나는 서술어 어형은 맥락어가 아니다
_PREDICATE_RE = re.compile(r"(다|니다|요)$")


def _tokens(text: str, exclude: str = "") -> set[str]:
    out = set()
    for t in _TOKEN_RE.findall(text or ""):
        if _PREDICATE_RE.search(t):
            continue
        n = _norm_token(t)
        if len(n) < 2 or n in _STOPWORDS:
            continue
        if exclude and (exclude in n or n in exclude):
            continue  # 분석 단어 자신과 그 활용형(검거 → 검거된, 검거율)
        out.add(n)
    return out


# ── 기간 키 ↔ 날짜 ─────────────────────────────────────────────────────────
def _period_mapper(keys: list[str]):
    """KEMKIM 기간 키 형식(kemkim.divide_period)에 맞춰 날짜 → 기간 키 함수를 만든다."""
    if not keys:
        return lambda d: None
    k = keys[0]
    if re.fullmatch(r"\d{4}", k):
        return lambda d: f"{d.year}"
    if re.fullmatch(r"\d{4}-\d{2}", k):
        return lambda d: f"{d.year}-{d.month:02d}"
    if re.fullmatch(r"\d{4}Q\d", k):
        return lambda d: f"{d.year}Q{(d.month - 1) // 3 + 1}"
    if re.fullmatch(r"\d{4}H\d", k):
        return lambda d: f"{d.year}H{(d.month - 1) // 6 + 1}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k):
        return lambda d: d.strftime("%Y-%m-%d")
    if re.fullmatch(r"\d{8}-\d{8}", k):
        ranges = []
        for key in keys:
            a, b = key.split("-")
            ranges.append((pd.Timestamp(a), pd.Timestamp(b), key))

        def weekly(d):
            for a, b, key in ranges:
                if a <= d <= b + pd.Timedelta(hours=23, minutes=59):
                    return key
            return None

        return weekly
    return lambda d: None


def _period_end(key: str):
    try:
        if re.fullmatch(r"\d{4}", key):
            return pd.Timestamp(f"{key}-12-31")
        if re.fullmatch(r"\d{4}-\d{2}", key):
            return pd.Timestamp(f"{key}-01") + pd.offsets.MonthEnd(0)
        if re.fullmatch(r"\d{4}Q\d", key):
            y, q = int(key[:4]), int(key[-1])
            return pd.Timestamp(f"{y}-{q * 3:02d}-01") + pd.offsets.MonthEnd(0)
        if re.fullmatch(r"\d{4}H\d", key):
            y, h = int(key[:4]), int(key[-1])
            return pd.Timestamp(f"{y}-{h * 6:02d}-01") + pd.offsets.MonthEnd(0)
        if re.fullmatch(r"\d{8}-\d{8}", key):
            return pd.Timestamp(key.split("-")[1])
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", key):
            return pd.Timestamp(key)
    except (ValueError, TypeError):
        return None
    return None


def partial_periods(keys: list[str], metadata: dict) -> set[str]:
    """분석 종료일이 기간 중간에 끝나 집계가 덜 된 기간(보통 마지막 기간)."""
    end = pd.to_datetime(
        str((metadata or {}).get("end_date") or ""), format="%Y%m%d", errors="coerce"
    )
    if pd.isna(end) or not keys:
        return set()
    last = keys[-1]
    pe = _period_end(last)
    return {last} if pe is not None and end < pe - pd.Timedelta(days=1) else set()


def period_label(key: str) -> str:
    if re.fullmatch(r"\d{8}-\d{8}", key):
        a, b = key.split("-")
        return f"{a[:4]}.{a[4:6]}.{a[6:]}~{b[4:6]}.{b[6:]}"
    return key


# ── 1) 신호 단계 판정 ──────────────────────────────────────────────────────
def _growth(now: float | None, prev: float | None) -> float | None:
    if now is None or now <= 0:
        return None
    if prev is None or prev <= 0:
        return math.inf  # 이번 기간에 새로 나타남
    return (now / prev - 1) * 100


def _stage_series(periods: dict, keys: list[str], word: str, metric: str) -> list[dict]:
    out = []
    for i, pk in enumerate(keys):
        cur = (periods.get(pk) or {}).get(metric) or {}
        x = cur.get(word)
        row = {"period": pk, "value": x, "growth": None, "stage": _ABSENT}
        if x is None or x <= 0:
            out.append(row)
            continue
        vals = [v for v in cur.values() if v and v > 0]
        med_x = statistics.median(vals) if vals else 0
        if i == 0:
            # 첫 기간은 증가율을 알 수 없으므로 빈도만으로 본다
            row["stage"] = "well_known_signal" if x >= med_x else "latent_signal"
            out.append(row)
            continue
        prev = (periods.get(keys[i - 1]) or {}).get(metric) or {}
        g = _growth(x, prev.get(word))
        growths = [
            gg
            for w, v in cur.items()
            if (gg := _growth(v, prev.get(w))) is not None and gg != math.inf
        ]
        med_g = statistics.median(growths) if growths else 0
        high_x = x >= med_x
        high_g = g is not None and (g == math.inf or g >= med_g)
        row["growth"] = None if g == math.inf else round(g, 1)
        row["new"] = g == math.inf  # 직전 기간에는 없던 단어
        if high_x:
            row["stage"] = "strong_signal" if high_g else "well_known_signal"
        else:
            row["stage"] = "weak_signal" if high_g else "latent_signal"
        out.append(row)
    return out


def _smooth(stages: list[dict], partial: set[str]) -> None:
    """앞뒤 기간 다수결로 한 기간짜리 출렁임을 걸러낸다. 원래 판정은 raw_stage 에 남긴다.

    미완결 기간은 증가율이 낮게 잡히므로 직전 단계를 이어받고 partial 로 표시한다.
    """
    raw = [r["stage"] for r in stages]
    for i, r in enumerate(stages):
        r["raw_stage"] = raw[i]
        if r["period"] in partial:
            r["partial"] = True
            prev = next(
                (
                    stages[j]["stage"]
                    for j in range(i - 1, -1, -1)
                    if stages[j]["stage"] != _ABSENT
                ),
                None,
            )
            if prev and raw[i] != _ABSENT:
                r["stage"] = prev
            continue
        if raw[i] == _ABSENT or 0 < i < len(raw) - 1 and raw[i - 1] == _ABSENT:
            continue
        if (
            0 < i < len(raw) - 1
            and raw[i - 1] == raw[i + 1] != raw[i]
            and raw[i + 1] != _ABSENT
        ):
            r["stage"] = raw[i - 1]


_MAX_PHASES = 5


def _phases(stages: list[dict]) -> list[dict]:
    """같은 단계가 이어지는 기간을 국면으로 묶는다(미등장 구간은 제외)."""
    phases, cur = [], None
    for r in stages:
        if r["stage"] == _ABSENT:
            cur = None
            continue
        if cur and cur["stage"] == r["stage"]:
            cur["periods"].append(r["period"])
        else:
            cur = {"stage": r["stage"], "periods": [r["period"]]}
            phases.append(cur)
    # 국면이 너무 많으면 가장 짧은 국면을 이웃 중 더 긴 국면에 합친다
    while len(phases) > _MAX_PHASES:
        i = min(range(len(phases)), key=lambda k: (len(phases[k]["periods"]), -k))
        if i == 0:
            j = 1
        elif i == len(phases) - 1:
            j = i - 1
        else:
            j = (
                i - 1
                if len(phases[i - 1]["periods"]) >= len(phases[i + 1]["periods"])
                else i + 1
            )
        a, b = sorted((i, j))
        keep = phases[j]["stage"]
        phases[a : b + 1] = [
            {"stage": keep, "periods": phases[a]["periods"] + phases[b]["periods"]}
        ]
    for i, p in enumerate(phases):
        p["id"] = i
        p["label"] = SIGNAL_LABEL.get(p["stage"], p["stage"])
        p["range"] = period_label(p["periods"][0]) + (
            "" if len(p["periods"]) == 1 else " ~ " + period_label(p["periods"][-1])
        )
    return phases


def final_membership(graph: dict, word: str) -> dict:
    out = {}
    for key, sig in (
        ("final", graph.get("final_signal") or {}),
        ("kem", (graph.get("dov") or {}).get("signal") or {}),
        ("kim", (graph.get("dod") or {}).get("signal") or {}),
    ):
        out[key] = next((s for s, ws in sig.items() if word in (ws or [])), None)
    return out


def signal_profile(graph: dict, word: str) -> dict:
    periods = graph.get("periods") or {}
    keys = sorted(periods.keys())
    partial = partial_periods(keys, graph.get("metadata") or {})
    series = []
    for pk in keys:
        pd_ = periods[pk]
        series.append(
            {
                "period": pk,
                "label": period_label(pk),
                **{
                    m: (pd_.get(m) or {}).get(word)
                    for m in ("TF", "DF", "TF-IDF", "DoV", "DoD")
                },
            }
        )
    kem = _stage_series(periods, keys, word, "DoV")
    kim = _stage_series(periods, keys, word, "DoD")
    _smooth(kem, partial)
    _smooth(kim, partial)
    return {
        "word": word,
        "periods": keys,
        "partial": sorted(partial),
        "series": series,
        "stages": {"kem": kem, "kim": kim},
        "phases": _phases(kem),
        "membership": final_membership(graph, word),
        "coordinates": {
            "kem": ((graph.get("dov") or {}).get("coordinates") or {}).get(word),
            "kim": ((graph.get("dod") or {}).get("coordinates") or {}).get(word),
        },
    }


# ── 2) 맥락 추출 ───────────────────────────────────────────────────────────
def _detect(columns, hint):
    return next((c for c in columns if hint in c), None)


def prepare_source(source_df: pd.DataFrame, graph: dict) -> pd.DataFrame:
    date_col = _detect(source_df.columns, "Date")
    text_col = _detect(source_df.columns, "Text")
    title_col = _detect(source_df.columns, "Title")
    if not date_col or not text_col:
        raise ValueError("원본 CSV에서 Date/Text 열을 찾을 수 없습니다.")
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                source_df[date_col].astype(str).str.split().str[0],
                format="%Y-%m-%d",
                errors="coerce",
            ),
            "text": source_df[text_col].astype(str),
            "title": source_df[title_col].astype(str) if title_col else "",
        }
    )
    df = df[df["date"].notna()]
    keys = sorted((graph.get("periods") or {}).keys())
    mapper = _period_mapper(keys)
    df["period"] = df["date"].map(mapper)
    return df[df["period"].isin(set(keys))].reset_index(drop=True)


def _snippet(text: str, word: str) -> str:
    i = text.find(word)
    if i < 0:
        return ""
    a, b = max(0, i - _WINDOW), min(len(text), i + len(word) + _WINDOW)
    return (
        ("…" if a > 0 else "")
        + text[a:b].replace("\n", " ").strip()
        + ("…" if b < len(text) else "")
    )


def word_contexts(df: pd.DataFrame, profile: dict) -> dict:
    """국면별 연관어·대표 문맥과 기간별 문서 수·연관어."""
    word = profile["word"]
    hits = df[df["text"].str.contains(word, regex=False, na=False)]
    if hits.empty:
        return {
            "total_docs": 0,
            "by_period": {},
            "phases": [],
            "snippets": [],
            "first_seen": None,
        }

    tok = [_tokens(t, word) for t in hits["text"]]
    hits = hits.assign(toks=tok)
    overall = Counter(t for ts in tok for t in ts)
    n_all = len(hits)

    def distinct_terms(sub, k=10, prev_top=None):
        n = len(sub)
        if not n:
            return []
        c = Counter(t for ts in sub["toks"] for t in ts)
        scored = []
        for t, f in c.items():
            if f < 2 and n >= 5:
                continue
            # 관련 기사의 80% 이상에 나오는 말(크롤링 검색어 등)은 맥락을 구분해 주지 못한다
            if n_all >= 10 and overall[t] / n_all >= 0.8:
                continue
            lift = (f / n) / (overall[t] / n_all)
            scored.append((f * lift, t, f))
        scored.sort(reverse=True)
        return [
            {
                "term": t,
                "docs": f,
                "new": bool(prev_top is not None and t not in prev_top),
            }
            for _, t, f in scored[:k]
        ]

    by_period = {}
    seen_top: set[str] = set()
    for pk in profile["periods"]:
        sub = hits[hits["period"] == pk]
        terms = distinct_terms(sub, 8, seen_top if by_period else None)
        by_period[pk] = {"docs": int(len(sub)), "terms": terms}
        seen_top |= {t["term"] for t in terms}

    snippets, phases_ctx = [], []
    budget = _MAX_SNIPPETS_TOTAL
    for ph in profile["phases"]:
        sub = hits[hits["period"].isin(ph["periods"])]
        terms = distinct_terms(sub, 10)
        term_set = {t["term"] for t in terms}
        # 국면의 대표 연관어를 많이 담은 기사부터, 제목이 겹치지 않게 고른다
        ranked = sorted(sub.itertuples(), key=lambda r: -len(r.toks & term_set))
        picked, titles = [], set()
        per_phase = min(
            _MAX_SNIPPETS_PER_PHASE,
            max(2, budget // max(1, len(profile["phases"]) - ph["id"])),
        )
        for r in ranked:
            if len(picked) >= per_phase:
                break
            key = (r.title or "")[:40]
            if key in titles:
                continue
            snip = _snippet(r.text, word)
            if not snip:
                continue
            titles.add(key)
            sid = f"S{len(snippets) + 1}"
            snippets.append(
                {
                    "id": sid,
                    "phase": ph["id"],
                    "period": r.period,
                    "date": r.date.strftime("%Y-%m-%d"),
                    "title": r.title if r.title and r.title != "nan" else "",
                    "context": snip,
                }
            )
            picked.append(sid)
        budget -= len(picked)
        phases_ctx.append(
            {
                "id": ph["id"],
                "docs": int(len(sub)),
                "terms": terms,
                "snippet_ids": picked,
            }
        )

    first = hits["date"].min()
    return {
        "total_docs": int(n_all),
        "first_seen": first.strftime("%Y-%m-%d") if pd.notna(first) else None,
        "overall_terms": [{"term": t, "docs": f} for t, f in overall.most_common(15)],
        "by_period": by_period,
        "phases": phases_ctx,
        "snippets": snippets,
    }


# ── 3) AI 해석 ─────────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : i + 1]
                    for cand in (chunk, re.sub(r",\s*([}\]])", r"\1", chunk)):
                        try:
                            return json.loads(cand)
                        except json.JSONDecodeError:
                            pass
                    break
        start = text.find("{", start + 1)
    raise ValueError("AI 응답에서 JSON을 찾지 못했습니다.")


async def _ask_json(
    system: str,
    user: str,
    max_tokens: int = 8000,
    uid: str | None = None,
    purpose: str = "",
) -> tuple[dict, dict]:
    """사용자 LLM 설정 순서대로(로컬 → 내 GPT API 등) JSON 답을 받는다.

    대상마다 한 번 호출하고, JSON이 깨졌으면 같은 대상에 한 번 고쳐 달라고 한 뒤,
    그래도 안 되면 다음 대상으로 넘어간다. (답, 사용 정보)를 돌려준다.
    """
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    targets, note = user_llm.plan(uid, msgs, max_tokens)
    notes = [note] if note else []
    total_cost = 0.0
    last_err = None
    for t in targets:
        try:
            res = await achat(msgs, temperature=0.3, max_tokens=max_tokens, **t.kwargs)
            total_cost += user_llm.record_usage(uid, t, res, purpose)
            try:
                data = _parse_json(res.text)
            except ValueError:
                retry = msgs + [
                    {"role": "assistant", "content": res.text[:6000]},
                    {
                        "role": "user",
                        "content": "설명 없이 올바른 JSON 객체 하나만 다시 출력하세요.",
                    },
                ]
                res2 = await achat(
                    retry, temperature=0, max_tokens=max_tokens, **t.kwargs
                )
                total_cost += user_llm.record_usage(
                    uid, t, res2, purpose + " (형식 재요청)"
                )
                data = _parse_json(res2.text)
            return data, {
                "used": t.label,
                "provider": t.provider,
                "cost_usd": round(total_cost, 5),
                "notes": notes,
            }
        except (LLMError, ValueError) as e:
            last_err = e
            notes.append(f"{t.label}: {e}")
            logger.warning("신호 해석 LLM 실패(%s): %s", t.label, e)
    raise LLMError(
        " / ".join(notes) or str(last_err or "사용할 수 있는 LLM이 없습니다.")
    )


WORD_SYSTEM = """너는 뉴스 빅데이터로 미래 이슈의 징후를 찾는 KEMKIM(Keyword Emergence Map / Keyword Issue Map) 분석 전문가다.
KEMKIM에서 약한 신호는 아직 빈도는 낮지만 빠르게 늘고 있는 단어, 강한 신호는 빈도와 증가율이 모두 높은 단어,
잠재 신호는 빈도와 증가율이 모두 낮은 단어, 알려진 신호는 빈도는 높지만 증가율이 낮은(이미 익숙해진) 단어다.

주어진 [신호 국면]과 국면별 [연관어]·[대표 문맥]만 근거로, 이 단어가 처음 어떤 맥락에서 등장했고
신호가 커지면서 어떤 맥락으로 옮겨 갔는지 해석한다.

반드시 아래 형식의 JSON 객체 하나만 출력한다.
{
  "headline": "한 문장 핵심 요약(30자 안팎)",
  "summary": "3~5문장 종합 해석",
  "phases": [{"id": 국면번호, "context": "이 국면에서 단어가 쓰인 맥락 2~3문장", "key_terms": ["이 국면을 대표하는 연관어"], "evidence": ["S번호"]}],
  "transition": "맥락이 어떻게 이동했는지 한 문장 (예: '규제 논의 → 실제 피해 사례 → 제도 개선 요구')",
  "drivers": ["신호를 키운 계기나 사건 — 문맥에 근거가 있는 것만"],
  "outlook": "앞으로 주목할 방향 2~3문장. 추측임을 드러내 쓴다",
  "watch_terms": ["함께 추적하면 좋은 연관어"],
  "caveats": "데이터나 해석의 한계 1~2문장"
}

[규칙]
- phases 는 주어진 국면 번호마다 하나씩, 같은 순서로 쓴다.
- evidence 에는 주어진 문맥 번호(S1, S2 …)만 쓴다. 번호가 없는 주장은 하지 않는다.
- key_terms, watch_terms 는 주어진 연관어에서 고른다.
- 문맥에 없는 사건·수치·기관을 지어내지 않는다."""


def _word_user_prompt(profile: dict, ctx: dict, analysis_meta: dict) -> str:
    mem = profile["membership"]
    lines = [
        f"[분석 단어] {profile['word']}",
        f"[분석 자료] {analysis_meta.get('csv_name', '')} · {analysis_meta.get('start_date', '')}~{analysis_meta.get('end_date', '')} · 기간 단위 {analysis_meta.get('period', '')}",
        f"[최종 판정] 최종 {SIGNAL_LABEL.get(mem.get('final'), '해당 없음')} / KEM {SIGNAL_LABEL.get(mem.get('kem'), '해당 없음')} / KIM {SIGNAL_LABEL.get(mem.get('kim'), '해당 없음')}",
        f"[처음 등장] {ctx.get('first_seen') or '알 수 없음'} · 관련 기사 {ctx.get('total_docs', 0)}건",
        "",
        "[기간별 수치] 기간 | 기사 수 | TF | DoV | 직전 대비 증가율 | 단계",
    ]
    kem = {r["period"]: r for r in profile["stages"]["kem"]}
    for s in profile["series"]:
        r = kem.get(s["period"], {})
        g = r.get("growth")
        gtxt = "신규" if r.get("new") else (f"{g:+.0f}%" if g is not None else "-")
        if r.get("partial"):
            gtxt += "(집계 중인 기간이라 감소처럼 보일 수 있음)"
        lines.append(
            f"{s['label']} | {ctx['by_period'].get(s['period'], {}).get('docs', 0)} | "
            f"{s['TF'] if s['TF'] is not None else '-'} | {round(s['DoV'], 3) if s['DoV'] is not None else '-'} | "
            f"{gtxt} | {SIGNAL_LABEL.get(r.get('stage'), '미등장')}"
        )
    snip_by_id = {s["id"]: s for s in ctx["snippets"]}
    for ph, pc in zip(profile["phases"], ctx["phases"]):
        lines += [
            "",
            f"[신호 국면 {ph['id']}] {ph['range']} · {ph['label']} · 기사 {pc['docs']}건",
            "연관어(이 국면에서 두드러짐): "
            + ", ".join(t["term"] for t in pc["terms"]),
        ]
        for sid in pc["snippet_ids"]:
            s = snip_by_id[sid]
            lines.append(
                f"  {sid} [{s['date']}] {s['title'][:60]} :: {s['context'][:300]}"
            )
    lines.append("\nJSON만 출력하세요.")
    return "\n".join(lines)


def _clean_word_ai(data: dict, profile: dict, ctx: dict) -> dict:
    valid_ids = {s["id"] for s in ctx["snippets"]}
    terms_pool = {t["term"] for pc in ctx["phases"] for t in pc["terms"]} | {
        t["term"] for t in ctx.get("overall_terms", [])
    }

    def ids(v):
        return [x for x in (v or []) if isinstance(x, str) and x in valid_ids][:6]

    def terms(v):
        return [x for x in (v or []) if isinstance(x, str) and x in terms_pool][:10]

    by_id = {p.get("id"): p for p in (data.get("phases") or []) if isinstance(p, dict)}
    phases = []
    for ph in profile["phases"]:
        p = by_id.get(ph["id"]) or {}
        phases.append(
            {
                "id": ph["id"],
                "context": str(p.get("context") or "")[:800],
                "key_terms": terms(p.get("key_terms")),
                "evidence": ids(p.get("evidence")),
            }
        )
    return {
        "headline": str(data.get("headline") or "")[:120],
        "summary": str(data.get("summary") or "")[:1500],
        "phases": phases,
        "transition": str(data.get("transition") or "")[:300],
        "drivers": [str(x)[:300] for x in (data.get("drivers") or [])][:5],
        "outlook": str(data.get("outlook") or "")[:800],
        "watch_terms": terms(data.get("watch_terms")),
        "caveats": str(data.get("caveats") or "")[:500],
    }


def _noop(*_a, **_k):
    pass


async def analyze_word(
    graph: dict,
    source_df: pd.DataFrame | None,
    word: str,
    progress=_noop,
    uid: str | None = None,
) -> dict:
    """progress(stage, prompt=None): 진행 단계와(만들어졌다면) AI에 보낼 프롬프트를 알린다."""
    import asyncio

    progress("기간별 신호 단계를 계산하고 있어요")
    profile = signal_profile(graph, word)
    if not any(s["DoV"] is not None or s["DoD"] is not None for s in profile["series"]):
        raise ValueError(f"'{word}'은(는) 이 분석의 기간별 데이터에 없는 단어입니다.")
    result = {
        "kind": "signal",
        "word": word,
        "profile": profile,
        "context": None,
        "ai": None,
        "ai_error": None,
        "prompt": None,
    }
    if source_df is None:
        result["ai_error"] = (
            "원본 CSV가 없어 맥락 해석은 건너뛰었습니다. 원본을 첨부하면 AI 해석을 받을 수 있습니다."
        )
        return result
    progress("원본 기사에서 기간별 맥락과 연관어를 뽑고 있어요")
    df = await asyncio.to_thread(prepare_source, source_df, graph)
    ctx = await asyncio.to_thread(word_contexts, df, profile)
    result["context"] = ctx
    if not ctx["total_docs"]:
        result["ai_error"] = "원본 기사에서 이 단어가 들어간 문서를 찾지 못했습니다."
        return result
    prompt = {
        "system": WORD_SYSTEM,
        "user": _word_user_prompt(profile, ctx, graph.get("metadata") or {}),
    }
    result["prompt"] = prompt
    progress("AI가 국면별 맥락을 해석하고 있어요", prompt)
    try:
        data, used = await _ask_json(
            prompt["system"],
            prompt["user"],
            uid=uid,
            purpose=f"KEMKIM 신호 해석: {word}",
        )
        result["ai"] = _clean_word_ai(data, profile, ctx)
        result["llm"] = used
    except (LLMError, ValueError) as e:
        result["ai_error"] = f"AI 해석 요청에 실패했습니다: {e}"
    return result


# ── 신호군 종합 해석 ────────────────────────────────────────────────────────
GROUP_SYSTEM = """너는 KEMKIM 분석 전문가다. 같은 신호군(예: 약한 신호)에 속한 단어들과 각 단어의 연관어·대표 문맥을 보고,
이 단어들이 어떤 '떠오르는 이슈' 몇 개로 묶이는지 정리한다.

반드시 아래 형식의 JSON 객체 하나만 출력한다.
{
  "summary": "이 신호군 전체가 말해 주는 흐름 3~4문장",
  "themes": [{"name": "이슈 이름(15자 이내)", "words": ["속한 단어"], "description": "무엇에 관한 이슈인지 2~3문장", "evidence": ["S번호"]}],
  "priority": [{"word": "가장 주목할 단어", "reason": "이유 1문장"}],
  "caveats": "해석의 한계 1문장"
}
[규칙]
- themes 는 2~6개. words 는 주어진 단어에서만 고르고, 한 단어는 한 테마에만 넣는다.
- evidence 는 주어진 문맥 번호만 쓴다. 문맥에 없는 사실을 지어내지 않는다.
- priority 는 최대 3개."""


def _group_contexts(
    df: pd.DataFrame, graph: dict, words: list[str]
) -> tuple[list[dict], list[dict]]:
    items, snippets = [], []
    for w in words:
        hits = df[df["text"].str.contains(w, regex=False, na=False)]
        prof = signal_profile(graph, w)
        first = next((s["label"] for s in prof["series"] if s["DoV"]), None)
        peak = (
            max(prof["series"], key=lambda s: s["DoV"] or 0)["label"]
            if prof["series"]
            else None
        )
        if hits.empty:
            items.append(
                {
                    "word": w,
                    "docs": 0,
                    "terms": [],
                    "first": first,
                    "peak": peak,
                    "snippet": None,
                }
            )
            continue
        c = Counter(t for tx in hits["text"].head(400) for t in _tokens(tx, w))
        best = hits.sort_values("date").iloc[-1]
        sid = f"S{len(snippets) + 1}"
        snippets.append(
            {
                "id": sid,
                "word": w,
                "date": best["date"].strftime("%Y-%m-%d"),
                "title": best["title"] if best["title"] != "nan" else "",
                "context": _snippet(best["text"], w),
            }
        )
        items.append(
            {
                "word": w,
                "docs": int(len(hits)),
                "terms": [t for t, _ in c.most_common(6)],
                "first": first,
                "peak": peak,
                "snippet": sid,
            }
        )
    return items, snippets


async def analyze_group(
    graph: dict,
    source_df: pd.DataFrame,
    signal: str,
    basis: str,
    progress=_noop,
    uid: str | None = None,
) -> dict:
    import asyncio

    src = {
        "final": graph.get("final_signal") or {},
        "kem": (graph.get("dov") or {}).get("signal") or {},
        "kim": (graph.get("dod") or {}).get("signal") or {},
    }.get(basis) or {}
    words = list(src.get(signal) or [])
    if not words:
        raise ValueError("선택한 신호군에 단어가 없습니다.")
    words = words[:40]
    progress(f"신호군 단어 {len(words)}개의 맥락을 모으고 있어요")
    df = await asyncio.to_thread(prepare_source, source_df, graph)
    items, snippets = await asyncio.to_thread(_group_contexts, df, graph, words)
    lines = [
        f"[신호군] {({'final': '최종', 'kem': 'KEM', 'kim': 'KIM'})[basis]} {SIGNAL_LABEL.get(signal, signal)} · {len(words)}개 단어",
        "",
    ]
    snip = {s["id"]: s for s in snippets}
    # 원본 기사에 한 번도 나오지 않은 단어는 AI가 근거 없이 추측하게 되므로 입력에서 뺀다
    missing = [it["word"] for it in items if not it["docs"]]
    if missing:
        lines.insert(
            1,
            f"(원본 기사에서 찾지 못해 제외한 단어 {len(missing)}개는 테마에 넣지 마세요)",
        )
    if len(missing) == len(items):
        raise ValueError(
            "원본 기사에서 이 신호군의 단어를 하나도 찾지 못했습니다. 원본 CSV가 분석 데이터와 같은지 확인해 주세요."
        )
    for it in items:
        if not it["docs"]:
            continue
        lines.append(
            f"- {it['word']} (기사 {it['docs']}건, 처음 {it['first'] or '-'}, 정점 {it['peak'] or '-'}) 연관어: {', '.join(it['terms'])}"
        )
        if it["snippet"]:
            s = snip[it["snippet"]]
            lines.append(
                f"    {s['id']} [{s['date']}] {s['title'][:50]} :: {s['context'][:220]}"
            )
    lines.append("\nJSON만 출력하세요.")
    result = {
        "kind": "signal_group",
        "signal": signal,
        "basis": basis,
        "words": words,
        "items": items,
        "snippets": snippets,
        "ai": None,
        "ai_error": None,
    }
    prompt = {"system": GROUP_SYSTEM, "user": "\n".join(lines)}
    result["prompt"] = prompt
    progress("AI가 떠오르는 이슈를 묶고 있어요", prompt)
    try:
        data, used = await _ask_json(
            prompt["system"],
            prompt["user"],
            max_tokens=6000,
            uid=uid,
            purpose=f"KEMKIM 신호군 해석: {SIGNAL_LABEL.get(signal, signal)}",
        )
        result["llm"] = used
        wordset, used = set(words), set()
        themes = []
        for t in (data.get("themes") or [])[:6]:
            if not isinstance(t, dict):
                continue
            ws = [w for w in (t.get("words") or []) if w in wordset and w not in used]
            used |= set(ws)
            if not ws:
                continue
            themes.append(
                {
                    "name": str(t.get("name") or "")[:40],
                    "words": ws,
                    "description": str(t.get("description") or "")[:600],
                    "evidence": [e for e in (t.get("evidence") or []) if e in snip][:5],
                }
            )
        result["ai"] = {
            "summary": str(data.get("summary") or "")[:1200],
            "themes": themes,
            "unassigned": [w for w in words if w not in used and w not in missing],
            "not_in_source": missing,
            "priority": [
                {"word": p.get("word"), "reason": str(p.get("reason") or "")[:300]}
                for p in (data.get("priority") or [])
                if isinstance(p, dict) and p.get("word") in wordset
            ][:3],
            "caveats": str(data.get("caveats") or "")[:400],
        }
    except (LLMError, ValueError) as e:
        result["ai_error"] = f"AI 해석 요청에 실패했습니다: {e}"
    return result


# ── 보고서 내보내기 ─────────────────────────────────────────────────────────
def markdown_report(it: dict) -> str:
    L = []
    snips = {
        x["id"]: x
        for x in ((it.get("context") or {}).get("snippets") or it.get("snippets") or [])
    }

    def cite(ids):
        return "".join(
            f"\n  - [{sid}] {snips[sid]['date']} {snips[sid].get('title', '')} — {snips[sid]['context'][:200]}"
            for sid in ids
            if sid in snips
        )

    ai = it.get("ai") or {}
    if it.get("kind") == "signal":
        prof = it["profile"]
        L += [f"# '{it['word']}' 신호 진화 해석", ""]
        mem = prof.get("membership") or {}
        L.append(
            f"- 최종 판정: {SIGNAL_LABEL.get(mem.get('final'), '해당 없음')} (KEM {SIGNAL_LABEL.get(mem.get('kem'), '-')}, KIM {SIGNAL_LABEL.get(mem.get('kim'), '-')})"
        )
        if ai.get("headline"):
            L += [f"- 핵심: {ai['headline']}", "", ai.get("summary", ""), ""]
        if ai.get("transition"):
            L += [f"**맥락 이동**: {ai['transition']}", ""]
        L += ["## 국면별 해석", ""]
        ai_ph = {p["id"]: p for p in ai.get("phases", [])}
        for ph in prof.get("phases", []):
            p = ai_ph.get(ph["id"], {})
            L.append(f"### {ph['range']} · {ph['label']}")
            if p.get("context"):
                L.append(p["context"])
            if p.get("key_terms"):
                L.append("연관어: " + ", ".join(p["key_terms"]))
            if p.get("evidence"):
                L.append("근거:" + cite(p["evidence"]))
            L.append("")
        if ai.get("drivers"):
            L += ["## 신호를 키운 계기", *[f"- {d}" for d in ai["drivers"]], ""]
        if ai.get("outlook"):
            L += ["## 전망", ai["outlook"], ""]
        if ai.get("watch_terms"):
            L += ["함께 볼 연관어: " + ", ".join(ai["watch_terms"]), ""]
        L += [
            "## 기간별 수치",
            "",
            "| 기간 | TF | DF | DoV | DoD | KEM 단계 |",
            "|---|---|---|---|---|---|",
        ]
        kem = {r["period"]: r for r in prof["stages"]["kem"]}
        for r in prof["series"]:
            st = kem.get(r["period"], {})
            L.append(
                f"| {r['label']} | {r['TF'] or '-'} | {r['DF'] or '-'} | {round(r['DoV'], 3) if r['DoV'] else '-'} | "
                f"{round(r['DoD'], 3) if r['DoD'] else '-'} | {SIGNAL_LABEL.get(st.get('stage'), '미등장')}{' (집계 중)' if st.get('partial') else ''} |"
            )
    else:
        L += [f"# {it['keywords'][0]} 신호군 종합 해석", "", ai.get("summary", ""), ""]
        for t in ai.get("themes", []):
            L += [
                f"## {t['name']}",
                "단어: " + ", ".join(t["words"]),
                t.get("description", ""),
            ]
            if t.get("evidence"):
                L.append("근거:" + cite(t["evidence"]))
            L.append("")
        if ai.get("priority"):
            L += [
                "## 주목할 단어",
                *[f"- **{p['word']}**: {p['reason']}" for p in ai["priority"]],
                "",
            ]
    if ai.get("caveats"):
        L += ["", f"> 한계: {ai['caveats']}"]
    if it.get("ai_error"):
        L += ["", f"> {it['ai_error']}"]
    return "\n".join(L) + "\n"
