# app/services/kemkim_analysis.py
"""
"해석"(원본 문서에서 키워드 컨텍스트 추출 + AI 주제 요약)의 순수 계산 로직.
manager/server의 무거운 KEMKIM 파이프라인(server/app/libs/kemkim.py)을 다시 호출하지
않고 이 서비스 안에서 직접 처리한다 — kemkim.py에는 없고 데스크톱 UI 레이어
(app/pages/page_analysis.py의 interpret_kemkim/extract_surrounding_text)에만 있던
로직을 이식한 것이다.

"조정"(제외어 재분류)은 더 이상 서버에서 재계산하지 않는다 — 웹에서는 base.json의
좌표/신호를 그대로 두고 프론트엔드(viewer.js)가 사분면·단어 단위로 표시만 껐다 켠다.
"""

import re
from datetime import datetime, timezone

import pandas as pd
import requests

_CONTEXT_WINDOW = 200


# ---------------------------------------------------------------------------
# 해석 (interpret)
# ---------------------------------------------------------------------------


def _detect_column(columns, hint: str) -> str | None:
    return next((c for c in columns if hint in c), None)


def _extract_surrounding_text(text: str, keyword: str, window: int = _CONTEXT_WINDOW) -> str | None:
    match = re.search(re.escape(keyword), text)
    if not match:
        return None
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start : match.start()] + f"_____{keyword}_____" + text[match.end() : end]


def run_interpretation(
    source_df: pd.DataFrame,
    metadata: dict,
    keywords: list,
    match_mode: str = "or",
) -> dict:
    date_col = _detect_column(source_df.columns, "Date")
    text_col = _detect_column(source_df.columns, "Text")
    title_col = _detect_column(source_df.columns, "Title")

    if not date_col or not text_col:
        raise ValueError("원본 CSV에서 Date/Text 열을 찾을 수 없습니다.")

    df = source_df.copy()
    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str.split().str[0], format="%Y-%m-%d", errors="coerce"
    )

    start_raw = metadata.get("start_date")
    end_raw = metadata.get("end_date")
    if start_raw and end_raw:
        start = pd.to_datetime(str(start_raw), format="%Y%m%d", errors="coerce")
        end = pd.to_datetime(str(end_raw), format="%Y%m%d", errors="coerce")
        if pd.notna(start) and pd.notna(end):
            df = df[df[date_col].between(start, end)]

    def _matches(text) -> bool:
        if not isinstance(text, str):
            return False
        hits = [kw in text for kw in keywords]
        return all(hits) if match_mode == "and" else any(hits)

    df = df[df[text_col].apply(_matches)]

    per_keyword = []
    for keyword in keywords:
        matches = []
        for _, row in df.iterrows():
            text = row.get(text_col)
            if not isinstance(text, str) or keyword not in text:
                continue
            snippet = _extract_surrounding_text(text, keyword)
            if not snippet:
                continue
            date_val = row.get(date_col)
            matches.append(
                {
                    "title": row.get(title_col) if title_col else None,
                    "date": date_val.strftime("%Y-%m-%d") if pd.notna(date_val) else None,
                    "context": snippet,
                    "full_text": text,
                }
            )
        per_keyword.append({"keyword": keyword, "count": len(matches), "matches": matches})

    titles = []
    if title_col:
        titles = [t for t in df[title_col].dropna().astype(str).tolist()]

    return {
        "date_col": date_col,
        "text_col": text_col,
        "title_col": title_col,
        "matched_documents": len(df),
        "results": per_keyword,
        "titles": titles,
    }


def build_topic_prompt(topic_hint: str, titles: list) -> str:
    sample = titles[:50]
    titles_block = "\n".join(f"- {t}" for t in sample)
    return (
        f"다음은 '{topic_hint}'와 관련해 검색된 뉴스 기사 제목 {len(sample)}개입니다.\n"
        f"이 제목들에서 공통적으로 드러나는 주제를 1개에서 5개 사이로 추출하고, "
        f"각 주제를 한두 문장으로 설명해주세요.\n\n{titles_block}"
    )


def request_ai_topics(manager_server_api: str, session_token: str, prompt: str) -> str:
    resp = requests.post(
        f"{manager_server_api}/llm/v1/openai/chat/completions",
        headers={
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-5-mini",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
