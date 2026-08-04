import itertools
import os
import re
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.outliers_influence import variance_inflation_factor

from app.libs.path import safe_path

warnings.filterwarnings("ignore")

MIN_ROWS = 10
MAX_NUMERIC_COLUMNS = 10
MAX_CATEGORICAL_COLUMNS = 6
MAX_DETAIL_TABLES = (
    8  # 유의한 조합에 대해서만 만드는 상세표(집단평균/사후검정/교차표)의 최대 개수
)


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------


def _save(df: pd.DataFrame | None, csv_dir: str, stem: str) -> None:
    if df is None or df.empty:
        return
    df.to_csv(
        safe_path(os.path.join(csv_dir, f"{stem}.csv")),
        index=False,
        encoding="utf-8-sig",
    )


def _sanitize(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", str(name)).strip("_")[:40] or "col"


def _looks_like_id_or_text(col, series: pd.Series, row_count: int) -> bool:
    name = str(col).lower()
    tokens = re.split(r"[^a-z0-9가-힣]+", name)
    if any(t in ("id", "uid", "url", "link", "번호") for t in tokens if t):
        return True
    if any(
        k in name
        for k in ("url", "link", "text", "content", "html", "title", "본문", "제목")
    ):
        return True
    if pd.api.types.is_string_dtype(series) and not isinstance(
        series.dtype, pd.CategoricalDtype
    ):
        nunique = series.nunique(dropna=True)
        if nunique > 0 and nunique >= row_count * 0.9:
            return True
    return False


def _select_columns(data: pd.DataFrame):
    row_count = len(data)
    numeric_cols, categorical_cols = [], []
    for col in data.columns:
        series = data[col]
        if _looks_like_id_or_text(col, series, row_count):
            continue
        if pd.api.types.is_bool_dtype(series):
            if 2 <= series.nunique(dropna=True) <= 20:
                categorical_cols.append(col)
            continue
        if pd.api.types.is_numeric_dtype(series):
            if series.nunique(dropna=True) <= 1:
                continue
            numeric_cols.append(col)
        elif pd.api.types.is_string_dtype(series) or isinstance(
            series.dtype, pd.CategoricalDtype
        ):
            nunique = series.nunique(dropna=True)
            if 2 <= nunique <= 20:
                categorical_cols.append(col)
    return numeric_cols[:MAX_NUMERIC_COLUMNS], categorical_cols[
        :MAX_CATEGORICAL_COLUMNS
    ]


# ---------------------------------------------------------------------------
# 1. 기술통계 / 정규성 검정
# ---------------------------------------------------------------------------


def _descriptives(data: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
    rows = []
    for col in numeric_cols:
        s = pd.to_numeric(data[col], errors="coerce").dropna()
        n = len(s)
        if n < 3:
            continue
        mean, std = s.mean(), s.std(ddof=1)
        se = std / np.sqrt(n) if n > 0 else np.nan
        ci_low, ci_high = (
            stats.t.interval(0.95, n - 1, loc=mean, scale=se)
            if se and se > 0
            else (mean, mean)
        )
        rows.append(
            {
                "변수": col,
                "N": n,
                "평균": round(mean, 3),
                "표준편차": round(std, 3),
                "표준오차": round(se, 3) if pd.notna(se) else None,
                "최소값": round(s.min(), 3),
                "1사분위(Q1)": round(s.quantile(0.25), 3),
                "중앙값": round(s.median(), 3),
                "3사분위(Q3)": round(s.quantile(0.75), 3),
                "최대값": round(s.max(), 3),
                "왜도(Skewness)": round(s.skew(), 3),
                "첨도(Kurtosis)": round(s.kurt(), 3),
                "95% CI 하한": round(ci_low, 3),
                "95% CI 상한": round(ci_high, 3),
            }
        )
    return pd.DataFrame(rows)


def _normality(data: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
    rows = []
    for col in numeric_cols:
        s = pd.to_numeric(data[col], errors="coerce").dropna()
        n = len(s)
        if n < 8:
            continue
        if n <= 5000:
            stat, p = stats.shapiro(s)
            method = "Shapiro-Wilk"
        else:
            sample = s.sample(5000, random_state=42)
            stat, p = stats.kstest(
                sample, "norm", args=(sample.mean(), sample.std(ddof=1))
            )
            method = "Kolmogorov-Smirnov"
        rows.append(
            {
                "변수": col,
                "검정방법": method,
                "N": n,
                "통계량": round(stat, 4),
                "p-value": round(p, 4),
                "정규분포 여부(α=.05)": "정규분포를 따름"
                if p >= 0.05
                else "정규분포를 따르지 않음",
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. 빈도분석
# ---------------------------------------------------------------------------


def _frequency_table(data: pd.DataFrame, col: str) -> pd.DataFrame | None:
    s = data[col].dropna().astype(str)
    if s.empty:
        return None
    vc = s.value_counts()
    total = int(vc.sum())
    if total == 0:
        return None
    df = vc.rename_axis(col).reset_index(name="빈도")
    df["퍼센트(%)"] = (df["빈도"] / total * 100).round(2)
    df["누적 퍼센트(%)"] = df["퍼센트(%)"].cumsum().round(2)
    return df


# ---------------------------------------------------------------------------
# 3. 상관분석
# ---------------------------------------------------------------------------


def _correlation_matrix(data: pd.DataFrame, numeric_cols: list, method: str):
    sub = data[numeric_cols].apply(pd.to_numeric, errors="coerce")
    n = len(numeric_cols)
    corr = pd.DataFrame(np.eye(n), index=numeric_cols, columns=numeric_cols)
    pval = pd.DataFrame(np.zeros((n, n)), index=numeric_cols, columns=numeric_cols)
    func = stats.pearsonr if method == "pearson" else stats.spearmanr
    for i, a in enumerate(numeric_cols):
        for j, b in enumerate(numeric_cols):
            if j <= i:
                continue
            pair = sub[[a, b]].dropna()
            r, p = func(pair[a], pair[b]) if len(pair) >= 3 else (np.nan, np.nan)
            corr.iloc[i, j] = corr.iloc[j, i] = r
            pval.iloc[i, j] = pval.iloc[j, i] = p
    corr = corr.round(3).reset_index().rename(columns={"index": "변수"})
    pval = pval.round(4).reset_index().rename(columns={"index": "변수"})
    return corr, pval


# ---------------------------------------------------------------------------
# 4. 교차분석 / 카이제곱
# ---------------------------------------------------------------------------


def _crosstabs(data: pd.DataFrame, categorical_cols: list, csv_dir: str) -> None:
    summary_rows = []
    detail_count = 0
    for a, b in itertools.combinations(categorical_cols, 2):
        sub = data[[a, b]].dropna()
        if len(sub) < MIN_ROWS:
            continue
        ct = pd.crosstab(sub[a].astype(str), sub[b].astype(str))
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            continue
        chi2, p, dof, expected = stats.chi2_contingency(ct)
        n = ct.values.sum()
        min_dim = min(ct.shape) - 1
        cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else np.nan
        summary_rows.append(
            {
                "변수1": a,
                "변수2": b,
                "카이제곱": round(chi2, 3),
                "자유도": int(dof),
                "p-value": round(p, 4),
                "Cramer's V": round(cramers_v, 3) if pd.notna(cramers_v) else None,
                "유의성(α=.05)": "유의함" if p < 0.05 else "유의하지 않음",
                "기대빈도<5 비율(%)": round((expected < 5).mean() * 100, 1),
            }
        )
        if detail_count < MAX_DETAIL_TABLES:
            _save(
                ct.reset_index(),
                csv_dir,
                f"spss_crosstab_{_sanitize(a)}__{_sanitize(b)}",
            )
            detail_count += 1
    _save(pd.DataFrame(summary_rows), csv_dir, "spss_chisquare_summary")


# ---------------------------------------------------------------------------
# 5. 평균 비교 (독립표본 t-검정 / 일원배치 분산분석 + 비모수 대응 + 사후검정)
# ---------------------------------------------------------------------------


def _group_summary(groups: dict, group_values: list) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "그룹": list(groups.keys()),
            "N": [len(v) for v in group_values],
            "평균": [round(float(np.mean(v)), 3) for v in group_values],
            "표준편차": [round(float(np.std(v, ddof=1)), 3) for v in group_values],
        }
    )


def _mean_comparisons(
    data: pd.DataFrame, numeric_cols: list, categorical_cols: list, csv_dir: str
) -> None:
    summary_rows = []
    detail_count = 0
    for num_col, cat_col in itertools.product(numeric_cols, categorical_cols):
        sub = data[[num_col, cat_col]].copy()
        sub[num_col] = pd.to_numeric(sub[num_col], errors="coerce")
        sub = sub.dropna()
        if sub.empty:
            continue
        groups = {k: g[num_col].values for k, g in sub.groupby(cat_col) if len(g) >= 5}
        k = len(groups)
        if k < 2:
            continue
        group_values = list(groups.values())
        n_total = sum(len(v) for v in group_values)
        if n_total < MIN_ROWS:
            continue

        if k == 2:
            a, b = group_values
            _, levene_p = stats.levene(a, b)
            equal_var = levene_p >= 0.05
            t_stat, t_p = stats.ttest_ind(a, b, equal_var=equal_var)
            pooled_std = np.sqrt(
                ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
                / (len(a) + len(b) - 2)
            )
            cohens_d = (
                (np.mean(a) - np.mean(b)) / pooled_std if pooled_std > 0 else np.nan
            )
            u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
            summary_rows.append(
                {
                    "수치변수": num_col,
                    "범주변수": cat_col,
                    "그룹수": k,
                    "검정방법": "독립표본 t-검정"
                    + (" (등분산)" if equal_var else " (Welch)"),
                    "통계량": round(t_stat, 3),
                    "자유도/표본수": f"{len(a) + len(b) - 2}",
                    "p-value": round(t_p, 4),
                    "효과크기(Cohen's d)": round(cohens_d, 3)
                    if pd.notna(cohens_d)
                    else None,
                    "비모수검정": "Mann-Whitney U",
                    "비모수 p-value": round(u_p, 4),
                    "유의성(α=.05)": "유의함" if t_p < 0.05 else "유의하지 않음",
                }
            )
            if t_p < 0.05 and detail_count < MAX_DETAIL_TABLES:
                _save(
                    _group_summary(groups, group_values),
                    csv_dir,
                    f"spss_groupmeans_{_sanitize(num_col)}__{_sanitize(cat_col)}",
                )
                detail_count += 1
        elif 3 <= k <= 10:
            f_stat, f_p = stats.f_oneway(*group_values)
            all_values = np.concatenate(group_values)
            grand_mean = all_values.mean()
            ss_between = sum(
                len(v) * (np.mean(v) - grand_mean) ** 2 for v in group_values
            )
            ss_total = float(((all_values - grand_mean) ** 2).sum())
            eta_sq = ss_between / ss_total if ss_total > 0 else np.nan
            h_stat, h_p = stats.kruskal(*group_values)
            summary_rows.append(
                {
                    "수치변수": num_col,
                    "범주변수": cat_col,
                    "그룹수": k,
                    "검정방법": "일원배치 분산분석(ANOVA)",
                    "통계량": round(f_stat, 3),
                    "자유도/표본수": f"{k - 1}, {n_total - k}",
                    "p-value": round(f_p, 4),
                    "효과크기(eta²)": round(eta_sq, 3) if pd.notna(eta_sq) else None,
                    "비모수검정": "Kruskal-Wallis",
                    "비모수 p-value": round(h_p, 4),
                    "유의성(α=.05)": "유의함" if f_p < 0.05 else "유의하지 않음",
                }
            )
            if f_p < 0.05 and detail_count < MAX_DETAIL_TABLES:
                _save(
                    _group_summary(groups, group_values),
                    csv_dir,
                    f"spss_groupmeans_{_sanitize(num_col)}__{_sanitize(cat_col)}",
                )
                detail_count += 1
                try:
                    tukey = pairwise_tukeyhsd(
                        sub[num_col].values, sub[cat_col].astype(str).values
                    )
                    tukey_df = pd.DataFrame(
                        tukey.summary().data[1:], columns=tukey.summary().data[0]
                    )
                    tukey_df = tukey_df.rename(
                        columns={
                            "group1": "그룹1",
                            "group2": "그룹2",
                            "meandiff": "평균차",
                            "p-adj": "조정된 p-value",
                            "lower": "하한",
                            "upper": "상한",
                            "reject": "유의함",
                        }
                    )
                    _save(
                        tukey_df,
                        csv_dir,
                        f"spss_posthoc_tukey_{_sanitize(num_col)}__{_sanitize(cat_col)}",
                    )
                except Exception:
                    pass
    _save(pd.DataFrame(summary_rows), csv_dir, "spss_mean_comparison_summary")


# ---------------------------------------------------------------------------
# 6. 회귀분석
# ---------------------------------------------------------------------------


def _pick_regression_target(data: pd.DataFrame, numeric_cols: list) -> str:
    priority_keywords = ("replycnt", "reply", "like", "view", "count", "cnt")
    for col in numeric_cols:
        low = str(col).lower().replace(" ", "")
        if any(k in low for k in priority_keywords):
            return col
    variances = {c: pd.to_numeric(data[c], errors="coerce").var() for c in numeric_cols}
    return max(variances, key=lambda k: variances[k] if pd.notna(variances[k]) else -1)


def _regression(data: pd.DataFrame, numeric_cols: list, csv_dir: str) -> None:
    if len(numeric_cols) < 2:
        return
    target = _pick_regression_target(data, numeric_cols)
    candidates = [c for c in numeric_cols if c != target]
    sub_all = data[[target] + candidates].apply(pd.to_numeric, errors="coerce")
    if len(candidates) > 6:
        corrs = (
            sub_all[candidates]
            .corrwith(sub_all[target])
            .abs()
            .sort_values(ascending=False)
        )
        candidates = [c for c in corrs.head(6).index]

    sub = sub_all[[target] + candidates].dropna()
    if len(sub) < max(30, (len(candidates) + 1) * 10):
        return

    y = sub[target]
    X = sm.add_constant(sub[candidates])
    model = sm.OLS(y, X).fit()

    std = sub.std(ddof=0)
    std_ok = bool((std > 0).all())
    z_model = None
    if std_ok:
        z = (sub - sub.mean()) / std
        z_model = sm.OLS(z[target], sm.add_constant(z[candidates])).fit()

    coef_rows = []
    for name in X.columns:
        beta = (
            z_model.params.get(name)
            if (z_model is not None and name != "const")
            else None
        )
        coef_rows.append(
            {
                "변수": "(상수)" if name == "const" else name,
                "B(비표준화계수)": round(model.params[name], 4),
                "표준오차": round(model.bse[name], 4),
                "베타(표준화계수)": round(beta, 4)
                if beta is not None and pd.notna(beta)
                else None,
                "t": round(model.tvalues[name], 3),
                "p-value": round(model.pvalues[name], 4),
                "유의성(α=.05)": "유의함"
                if model.pvalues[name] < 0.05
                else "유의하지 않음",
            }
        )
    _save(pd.DataFrame(coef_rows), csv_dir, "spss_regression_coefficients")

    if len(candidates) >= 2:
        vif_rows = []
        X_vals = X.values
        for i, name in enumerate(candidates):
            try:
                vif = variance_inflation_factor(X_vals, i + 1)
            except Exception:
                vif = np.nan
            vif_rows.append(
                {
                    "변수": name,
                    "VIF(분산팽창지수)": round(vif, 3) if pd.notna(vif) else None,
                }
            )
        _save(pd.DataFrame(vif_rows), csv_dir, "spss_regression_vif")

    _save(
        pd.DataFrame(
            [
                {
                    "종속변수": target,
                    "예측변수 수": len(candidates),
                    "N": int(model.nobs),
                    "R": round(np.sqrt(max(model.rsquared, 0)), 4),
                    "R²": round(model.rsquared, 4),
                    "수정된 R²": round(model.rsquared_adj, 4),
                    "F": round(model.fvalue, 3),
                    "p-value": round(model.f_pvalue, 4),
                    "잔차 표준오차": round(np.sqrt(model.mse_resid), 4),
                }
            ]
        ),
        csv_dir,
        "spss_regression_summary",
    )


# ---------------------------------------------------------------------------
# 7. 요인분석 (PCA)
# ---------------------------------------------------------------------------


def _pca(data: pd.DataFrame, numeric_cols: list, csv_dir: str) -> None:
    if len(numeric_cols) < 3:
        return
    sub = data[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < max(30, len(numeric_cols) * 5):
        return
    X = StandardScaler().fit_transform(sub)
    n_components = min(len(numeric_cols), 5)
    pca = PCA(n_components=n_components)
    pca.fit(X)

    var_rows = []
    cum = 0.0
    for i, ratio in enumerate(pca.explained_variance_ratio_, start=1):
        cum += ratio
        var_rows.append(
            {
                "성분": f"성분 {i}",
                "고유값(Eigenvalue)": round(float(pca.explained_variance_[i - 1]), 3),
                "설명 분산(%)": round(ratio * 100, 2),
                "누적 분산(%)": round(cum * 100, 2),
            }
        )
    _save(pd.DataFrame(var_rows), csv_dir, "spss_pca_variance")

    loadings = pd.DataFrame(
        pca.components_.T * np.sqrt(pca.explained_variance_),
        index=numeric_cols,
        columns=[f"성분 {i}" for i in range(1, n_components + 1)],
    ).round(3)
    _save(
        loadings.reset_index().rename(columns={"index": "변수"}),
        csv_dir,
        "spss_pca_loadings",
    )


# ---------------------------------------------------------------------------
# 8. 신뢰도분석 (Cronbach's Alpha)
# ---------------------------------------------------------------------------


def _cronbach_alpha(df: pd.DataFrame) -> float | None:
    k = df.shape[1]
    if k < 2:
        return None
    total_var = df.sum(axis=1).var(ddof=1)
    if total_var <= 0:
        return None
    return (k / (k - 1)) * (1 - df.var(ddof=1).sum() / total_var)


def _reliability(data: pd.DataFrame, numeric_cols: list, csv_dir: str) -> None:
    if len(numeric_cols) < 3:
        return
    sub = data[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 10:
        return
    alpha = _cronbach_alpha(sub)
    if alpha is None:
        return

    rows = []
    for col in numeric_cols:
        rest = sub.drop(columns=[col])
        corr = sub[col].corr(rest.sum(axis=1))
        alpha_wo = _cronbach_alpha(rest)
        rows.append(
            {
                "항목": col,
                "항목-전체 상관": round(corr, 3) if pd.notna(corr) else None,
                "해당 항목 제거 시 alpha": round(alpha_wo, 3)
                if alpha_wo is not None
                else None,
            }
        )
    _save(pd.DataFrame(rows), csv_dir, "spss_reliability_items")
    _save(
        pd.DataFrame(
            [
                {
                    "항목 수": len(numeric_cols),
                    "N": len(sub),
                    "Cronbach's Alpha": round(alpha, 3),
                }
            ]
        ),
        csv_dir,
        "spss_reliability_summary",
    )


# ---------------------------------------------------------------------------
# 9. 군집분석 (K-means)
# ---------------------------------------------------------------------------


def _cluster_analysis(data: pd.DataFrame, numeric_cols: list, csv_dir: str) -> None:
    if len(numeric_cols) < 2:
        return
    sub = data[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 30:
        return
    X = StandardScaler().fit_transform(sub)

    max_k = min(6, len(sub) // 10)
    if max_k < 2:
        return
    best_k, best_score, best_labels = None, -1.0, None
    for k in range(2, max_k + 1):
        try:
            labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(X)
            score = silhouette_score(X, labels)
        except Exception:
            continue
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels
    if best_k is None:
        return

    sub = sub.copy()
    sub["군집"] = [f"군집 {i + 1}" for i in best_labels]
    sizes = sub.groupby("군집").size().rename("N")
    profile = (
        sub.groupby("군집")[numeric_cols].mean().round(3).join(sizes).reset_index()
    )
    _save(profile, csv_dir, "spss_cluster_profile")
    _save(
        pd.DataFrame(
            [
                {
                    "최적 군집 수(k)": best_k,
                    "실루엣 계수": round(best_score, 3),
                    "N": len(sub),
                }
            ]
        ),
        csv_dir,
        "spss_cluster_summary",
    )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def run(data: pd.DataFrame, csv_dir: str) -> None:
    os.makedirs(csv_dir, exist_ok=True)
    if len(data) < MIN_ROWS:
        return

    numeric_cols, categorical_cols = _select_columns(data)

    def safe(fn, *args):
        try:
            fn(*args)
        except Exception:
            pass

    if numeric_cols:
        safe(
            lambda: _save(
                _descriptives(data, numeric_cols), csv_dir, "spss_descriptives"
            )
        )
        safe(lambda: _save(_normality(data, numeric_cols), csv_dir, "spss_normality"))

    for col in categorical_cols:
        safe(
            lambda c=col: _save(
                _frequency_table(data, c), csv_dir, f"spss_frequencies_{_sanitize(c)}"
            )
        )

    if len(numeric_cols) >= 2:

        def _corr(method, stem):
            corr_out, pval_out = _correlation_matrix(data, numeric_cols, method)
            _save(corr_out, csv_dir, stem)
            _save(pval_out, csv_dir, f"{stem}_pvalues")

        safe(_corr, "pearson", "spss_correlation_pearson")
        safe(_corr, "spearman", "spss_correlation_spearman")
        safe(_regression, data, numeric_cols, csv_dir)
        safe(_cluster_analysis, data, numeric_cols, csv_dir)

    if len(numeric_cols) >= 3:
        safe(_pca, data, numeric_cols, csv_dir)
        safe(_reliability, data, numeric_cols, csv_dir)

    if len(categorical_cols) >= 2:
        safe(_crosstabs, data, categorical_cols, csv_dir)

    if numeric_cols and categorical_cols:
        safe(_mean_comparisons, data, numeric_cols, categorical_cols, csv_dir)
