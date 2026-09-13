# 워드클라우드 분석 — 매니저 데스크톱 앱(manager/app/libs/analysis.py)의 wordcloud를
# 웹 파이프라인에 맞게 이식한 것. 토큰화된 CSV(쉼표로 구분된 단어들이 든 Text 열)를
# 기간 단위로 나눠 워드클라우드 PNG(graphs/)와 단어 빈도표(csv_files/)를 만든다.
import os
import re
from collections import Counter

import pandas as pd
from wordcloud import WordCloud

from app.libs.path import safe_path
from system.progress import send_message

# 기간 분할 옵션 (매니저 앱과 동일한 키)
PERIOD_CHOICES = {"total", "1d", "1w", "1m", "3m", "6m", "1y"}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _korean_font() -> str | None:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    try:
        from matplotlib import font_manager

        found = font_manager.findfont("NanumGothic", fallback_to_default=False)
        if found and os.path.exists(found):
            return found
    except Exception:
        pass
    return None


def _safe_fname(label: str) -> str:
    return re.sub(r'[\\/*?:"<>| ]', "_", str(label))


def _period_groups(data: pd.DataFrame, date_col: str, period: str):
    """(기간 라벨, 부분 DataFrame) 목록을 시간순으로 돌려준다."""
    if period == "total":
        return [("전체", data)]

    dt = pd.to_datetime(
        data[date_col].astype(str).str.split().str[0], errors="coerce"
    )
    valid = data[dt.notna()].copy()
    dt = dt.dropna()
    if valid.empty:
        raise ValueError(f"'{date_col}' 열에서 날짜를 해석할 수 없습니다.")

    if period == "1d":
        key = dt.dt.strftime("%Y-%m-%d")
    elif period == "1w":
        key = dt.dt.to_period("W").apply(
            lambda p: f"{p.start_time.strftime('%Y%m%d')}-{p.end_time.strftime('%Y%m%d')}"
        )
    elif period == "1m":
        key = dt.dt.to_period("M").astype(str)
    elif period == "3m":
        key = dt.dt.year.astype(str) + "Q" + dt.dt.quarter.astype(str)
    elif period == "6m":
        key = dt.dt.year.astype(str) + "H" + ((dt.dt.month - 1) // 6 + 1).astype(str)
    elif period == "1y":
        key = dt.dt.year.astype(str)
    else:
        raise ValueError(f"지원하지 않는 기간 단위입니다: {period}")

    valid["_period_group"] = key.values
    return sorted(valid.groupby("_period_group"), key=lambda g: str(g[0]))


def run_wordcloud(
    data: pd.DataFrame,
    output_dir: str,
    period: str = "total",
    max_words: int = 100,
    exclude_words: list[str] | None = None,
    pid: str | None = None,
) -> None:
    if period not in PERIOD_CHOICES:
        period = "total"
    max_words = max(10, min(500, int(max_words or 100)))
    exclude = {w.strip() for w in (exclude_words or []) if w and w.strip()}

    text_col = next((c for c in data.columns if "text" in str(c).lower()), None)
    if text_col is None:
        raise ValueError(
            "'Text' 열을 찾을 수 없습니다. 토큰화된 CSV(크롤링 DB의 token_ 파일)를 사용해 주세요."
        )
    date_col = next((c for c in data.columns if "date" in str(c).lower()), None)
    if period != "total" and date_col is None:
        raise ValueError("기간 분할에는 'Date' 열이 필요합니다. 기간을 '전체'로 선택해 주세요.")

    font_path = _korean_font()
    if font_path is None:
        raise ValueError("서버에 한글 폰트(NanumGothic)가 없어 워드클라우드를 만들 수 없습니다.")

    csv_dir = os.path.join(output_dir, "csv_files")
    graph_dir = os.path.join(output_dir, "graphs")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(graph_dir, exist_ok=True)

    groups = _period_groups(data, date_col, period)
    made = 0
    for i, (label, group) in enumerate(groups):
        if pid:
            send_message(
                pid, f"[워드클라우드] {label} 생성 중... ({i + 1}/{len(groups)})"
            )

        words: list[str] = []
        for cell in group[text_col]:
            if not isinstance(cell, str):
                continue
            for token in cell.split(","):
                token = token.strip()
                if token and token not in exclude:
                    words.append(token)
        if not words:
            continue

        freq = dict(Counter(words).most_common(max_words))

        wc = WordCloud(
            font_path=font_path,
            background_color="white",
            width=1200,
            height=800,
            max_words=max_words,
        ).generate_from_frequencies(freq)
        wc.to_file(
            safe_path(os.path.join(graph_dir, f"wordcloud_{_safe_fname(label)}.png"))
        )

        pd.DataFrame(
            {"word": list(freq.keys()), "count": list(freq.values())}
        ).to_csv(
            safe_path(os.path.join(csv_dir, f"wordcount_{_safe_fname(label)}.csv")),
            index=False,
            encoding="utf-8-sig",
        )
        made += 1

    if made == 0:
        raise ValueError(
            "생성할 단어가 없습니다. Text 열이 쉼표로 구분된 토큰인지 확인해 주세요."
        )
    if pid:
        send_message(pid, f"[워드클라우드] 완료 — {made}개 기간 생성")
