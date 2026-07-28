"""csv_files/*.csv 표 하나하나가 통계뷰어(manager/statistics)의 브라우저 화면에서
어떤 차트로 그려지는지 그대로 재현해, 결과 zip의 graphs/에도 같은 그래프를 채워 넣는
보조 모듈.

manager/statistics의 뷰어(viewer.js)는 서버가 만든 그래프 이미지를 쓰지 않고
csv_files의 표 데이터를 그대로 읽어 Chart.js/캔버스로 즉석에서 인터랙티브 차트를
그린다(project_store.py 상단 docstring 참고. PNG는 원본 zip 다운로드용으로만
쓴다). 그런데 zip에 담기는 graphs/*.png는 오래전부터 카테고리별 10개 분석 함수
(statistics_analysis.py)가 수작업으로 만든 것만 있었다. spss_analysis.py가 나중에
추가한 표들(빈도분석·교차분석·평균비교·상관/회귀/PCA/신뢰도/군집분석)과, 원본
데이터에서 바로 계산하는 요일×시간대 히트맵·추세·누적 표들에는 대응하는 이미지가
없어서, 화면에는 그래프가 보이는데 zip 다운로드에는 표만 있고 그래프가 빠지는
문제가 있었다.

이 모듈은 뷰어의 표->차트 변환 규칙을 그대로 따라 한다:
- 히트맵 여부 판정은 project_store.py의 _is_heatmap_table과 동일한 규칙.
- 막대/선 차트 선택은 viewer.js의 planChart와 동일한 규칙(날짜 열이 있으면 선,
  아니면 첫 비수치 열을 라벨로 막대 — 단 basic_stats/상관표는 뷰어에서도 차트를
  그리지 않으므로 여기서도 건너뛴다).

이렇게 표 이름을 하드코딩하지 않고 표의 "모양"만 보고 판단하므로, 나중에 어떤
분석 함수가 표를 새로 추가하더라도(카테고리별 10개 함수든 spss_analysis.py든)
따로 그래프 코드를 추가할 필요 없이 zip에는 항상 화면에서 보이는 만큼의 그래프가
들어간다. 이미 분석 함수가 같은 이름(stem)으로 직접 그려둔 그래프는 건드리지
않는다 — 그런 경우는 대개 여러 표를 합쳐서 보여주거나 더 다듬은 그래프이기 때문.
"""

import os
import re

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from app.libs.path import safe_path

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

# viewer.js planChart와 동일한 상한: 카테고리가 너무 많으면 막대 대신 표만 보여준다
MAX_BAR_CATEGORIES = 50
# 모든 열이 숫자일 때 첫 열을 라벨로 쓸지 판단하는 상한(viewer.js와 동일)
MAX_LABEL_UNIQUE_FALLBACK = 40


def _calculate_figsize(
    n: int, base_width: float = 10, height: float = 6, max_width: float = 32
):
    width = min(base_width + (n / 20), max_width)
    return (max(width, 5), height)


def _humanize(stem: str) -> str:
    if stem.startswith("spss_"):
        stem = stem[len("spss_") :]
    return " ".join(w.capitalize() for w in stem.replace("-", "_").split("_"))


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _is_heatmap_table(stem: str, df: pd.DataFrame) -> bool:
    """app/services/project_store.py(_is_heatmap_table)와 반드시 동일하게 유지할 것 —
    뷰어가 히트맵으로 그리는 표는 여기서도 히트맵으로 그려야 zip과 화면이 일치한다."""
    if stem == "hour_dow_heatmap":
        return True
    if stem.startswith("spss_crosstab_") or stem == "spss_pca_loadings":
        return True
    if "pvalue" in stem:
        return False
    if "correlation" in stem or "corr" in stem:
        numeric_cols = df.select_dtypes(include="number").columns
        return len(numeric_cols) >= 2 and abs(len(numeric_cols) - len(df)) <= 1
    return False


def _plan_chart(stem: str, df: pd.DataFrame):
    """app/static/js/viewer.js(planChart)와 반드시 동일하게 유지할 것.
    None을 반환하면 뷰어에서도 차트 없이 표만 보여주는 경우다."""
    if stem == "basic_stats" or "corr" in stem:
        return None
    if df.empty:
        return None

    cols = list(df.columns)
    numeric_flags = {c: _is_numeric(df[c]) for c in cols}

    date_col = next((c for c in cols if re.search("date", str(c), re.I)), None)
    if date_col is not None and not numeric_flags[date_col]:
        mode, label_col = "line", date_col
    else:
        label_col = next((c for c in cols if not numeric_flags[c]), None)
        if label_col is None:
            # 모든 열이 숫자인 경우 — 첫 열이 행 수만큼 서로 다른 값을 가지는
            # 소규모 카테고리처럼 보이면 그 열을 라벨(x축)로 쓴다.
            first_col = cols[0]
            unique_count = df[first_col].nunique(dropna=True)
            if unique_count == len(df) and unique_count <= MAX_LABEL_UNIQUE_FALLBACK:
                label_col = first_col
            else:
                return None
        mode = "bar"
        if len(df) > MAX_BAR_CATEGORIES:
            return None

    numeric_cols = [c for c in cols if c != label_col and numeric_flags[c]][:3]
    if not numeric_cols:
        return None
    return {"mode": mode, "label_col": label_col, "numeric_cols": numeric_cols}


def _render_heatmap(df: pd.DataFrame, stem: str, out_path: str) -> None:
    index_col = df.columns[0]
    matrix = df.set_index(index_col).apply(pd.to_numeric, errors="coerce")
    is_corr = "correlation" in stem or "corr" in stem

    plt.figure(
        figsize=_calculate_figsize(
            max(len(matrix.columns), len(matrix)), height=max(6, len(matrix) * 0.4)
        )
    )
    sns.heatmap(
        matrix,
        annot=matrix.shape[1] <= 25,
        fmt=".2f",
        cmap="coolwarm" if is_corr else "YlGnBu",
        vmin=-1 if is_corr else None,
        vmax=1 if is_corr else None,
    )
    plt.title(_humanize(stem))
    plt.tight_layout()
    plt.savefig(safe_path(out_path))
    plt.close()


def _render_line(df: pd.DataFrame, plan: dict, stem: str, out_path: str) -> None:
    label_col, numeric_cols = plan["label_col"], plan["numeric_cols"]
    plt.figure(figsize=_calculate_figsize(len(df)))
    for col in numeric_cols:
        sns.lineplot(data=df, x=label_col, y=col, label=col)
    plt.title(_humanize(stem))
    plt.xlabel(label_col)
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(safe_path(out_path))
    plt.close()


def _render_bar(df: pd.DataFrame, plan: dict, stem: str, out_path: str) -> None:
    label_col, numeric_cols = plan["label_col"], plan["numeric_cols"]
    plt.figure(figsize=_calculate_figsize(len(df)))
    if len(numeric_cols) == 1:
        sns.barplot(x=label_col, y=numeric_cols[0], data=df, palette="pastel")
        plt.ylabel(numeric_cols[0])
    else:
        long_df = df[[label_col] + numeric_cols].melt(
            id_vars=label_col, var_name="지표", value_name="값"
        )
        sns.barplot(x=label_col, y="값", hue="지표", data=long_df, palette="pastel")
    plt.title(_humanize(stem))
    plt.xlabel(label_col)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(safe_path(out_path))
    plt.close()


def fill_missing_graphs(csv_dir: str, graph_dir: str) -> None:
    """csv_dir의 표마다 뷰어가 그리는 것과 같은 차트를 재현해, graph_dir에 같은
    이름(stem)의 PNG가 아직 없는 표만 새로 그려 넣는다. 이미 분석 함수가 같은
    이름으로 직접 그려둔 그래프는 그대로 둔다."""
    if not os.path.isdir(csv_dir):
        return
    os.makedirs(graph_dir, exist_ok=True)

    existing = {
        os.path.splitext(f)[0]
        for f in os.listdir(graph_dir)
        if f.lower().endswith(".png")
    }

    for fname in sorted(os.listdir(csv_dir)):
        if not fname.lower().endswith(".csv"):
            continue
        stem = os.path.splitext(fname)[0]
        if stem in existing:
            continue

        try:
            df = pd.read_csv(os.path.join(csv_dir, fname), encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty:
            continue

        out_path = os.path.join(graph_dir, f"{stem}.png")
        try:
            if _is_heatmap_table(stem, df):
                _render_heatmap(df, stem, out_path)
                continue
            plan = _plan_chart(stem, df)
            if not plan:
                continue
            if plan["mode"] == "line":
                _render_line(df, plan, stem, out_path)
            else:
                _render_bar(df, plan, stem, out_path)
        except Exception:
            # 표 하나의 그래프 생성 실패가 나머지 표나 전체 분석 결과 저장을
            # 막아서는 안 된다(spss_analysis.py의 safe() 패턴과 동일한 이유).
            plt.close("all")
            continue
