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

MAX_BAR_CATEGORIES = 50
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
            plt.close("all")
            continue
