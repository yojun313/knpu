# app/services/project_store.py
"""
분석 서버(manager/server, 통계분석 파이프라인)가 만든 결과 zip(csv_files/, graphs/,
description.txt, metadata.json 포함)을 로그인한 사용자의 "프로젝트"로 저장한다. 원본
결과는 /mnt/ssd/statistics/{uid}/{project_id}/ 아래 디스크에 두고, 프로젝트
메타데이터(이름 등)는 MongoDB(statistics-projects 컬렉션)에 둔다.

kemkim/network와 달리 통계분석 결과는 이미 "표"들의 모음이라, 분석 타입마다 다른
파서를 만드는 대신 csv_files/*.csv를 범용으로 JSON 표로 변환한다(base.json). graphs/의
PNG는 원본 zip 다운로드용으로만 두고, 뷰어는 표 데이터로 직접 인터랙티브 차트를 그린다.
"""

import io
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone

import pandas as pd

from app.db import statistics_projects_db, statistics_folders_db, get_user_names
from system.archive import UnsafeZipError, safe_extract_zip

PROJECT_ROOT = os.getenv("STATISTICS_PROJECT_ROOT", "/mnt/ssd/statistics")
os.makedirs(PROJECT_ROOT, exist_ok=True)

MAX_ROWS_PER_TABLE = 5000


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def _project_dir(uid: str, project_id: str) -> str:
    return os.path.join(PROJECT_ROOT, uid, project_id)


def _raw_dir(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "raw")


def _base_json_path(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "base.json")


# ---------------------------------------------------------------------------
# 통계분석 결과 zip -> base.json 파싱
# ---------------------------------------------------------------------------


def _find_result_root(extract_dir: str) -> str:
    """추출된 폴더에서 metadata.json이 있는 실제 결과 루트를 찾는다. zip이 폴더 하나로
    감싸져 있는 경우와 바로 풀린 경우를 모두 지원한다."""
    if os.path.exists(os.path.join(extract_dir, "metadata.json")):
        return extract_dir

    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    for entry in entries:
        candidate = os.path.join(extract_dir, entry)
        if os.path.isdir(candidate) and os.path.exists(
            os.path.join(candidate, "metadata.json")
        ):
            return candidate

    raise ValueError(
        "metadata.json을 찾지 못했습니다. 통계분석 결과 zip을 그대로 업로드해주세요."
    )


def _humanize(stem: str) -> str:
    return " ".join(w.capitalize() for w in stem.replace("-", "_").split("_"))


# csv_files/{id}.csv 표 이름 -> 사람이 읽는 설명. manager/server의
# app/libs/statistics_analysis.py(10개 분석 함수)가 만드는 표 이름은 대부분 겹치므로,
# 분석 함수마다 따로 만들지 않고 표 이름 하나로 전체 분석 종류를 커버한다.
TABLE_DESCRIPTIONS: dict[str, str] = {
    "basic_stats": "원본 데이터의 각 열에 대한 기초 통계량(개수·평균·표준편차·사분위수 등)입니다.",
    "time_analysis": "월 단위로 집계한 게시물/댓글 수 추이입니다.",
    "day_analysis": "일 단위로 집계한 게시물/댓글 수 추이입니다. 특정 날짜에 몰린 급증 패턴을 확인할 때 유용합니다.",
    "monthly_analysis": "월별 집계 추이입니다.",
    "month_analysis": "월별 집계 추이입니다.",
    "weekly_analysis": "주 단위 집계 추이입니다.",
    "daily_analysis": "일 단위 집계 추이입니다.",
    "article_day_analysis": "일 단위 게시물 수 추이입니다.",
    "article_type_analysis": "기사/게시물 유형별 개수와 유형당 평균 반응(댓글 수)입니다.",
    "press_analysis": "게시물 수 상위 10개 언론사의 기사 수와 언론사별 반응(댓글) 수입니다.",
    "day_of_week_analysis": "요일별 게시물 수와 평균 반응 수입니다. 어느 요일에 발행이 몰리는지 보여줍니다.",
    "hour_analysis": "시간대(0~23시)별 게시물 수와 평균 반응 수입니다.",
    "channel_analysis": "채널(운영 주체)별 게시물 수와 반응 수입니다.",
    "writer_analysis": "작성자별 게시물 수 상위 항목입니다.",
    "writer_reply_count": "댓글을 가장 많이 남긴 작성자 상위 목록입니다.",
    "writer_rereply_count": "대댓글을 가장 많이 남긴 작성자 상위 목록입니다.",
    "top_10_writers": "게시물/댓글 수 기준 상위 10명의 작성자입니다.",
    "top_10_articles": "반응(댓글) 수 기준 상위 10개 게시물입니다.",
    "top_10_videos": "조회수/반응 기준 상위 10개 영상입니다.",
    "top_10_liked_replies": "좋아요 수 기준 상위 10개 댓글입니다.",
    "top_10_liked_rereplies": "좋아요 수 기준 상위 10개 대댓글입니다.",
    "top_10_percent_users": "활동량 상위 10% 사용자 그룹의 통계입니다.",
    "top_controversial_replies": "찬반(공감/비공감)이 크게 엇갈린, 논쟁적인 댓글 상위 목록입니다.",
    "top_articles_by_demographic": "특정 독자층(성별/연령대)의 반응이 두드러진 게시물 상위 목록입니다.",
    "top10_days": "값이 가장 높았던 상위 10개 날짜입니다.",
    "top10_months": "값이 가장 높았던 상위 10개월입니다.",
    "user_activity": "사용자별 활동량(댓글/대댓글 작성 수) 통계입니다.",
    "user_activity_with_score": "사용자별 활동량과 점수(좋아요 등 반응 포함)를 함께 정리한 표입니다.",
    "user_activity_correlation": "사용자 활동 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "correlation": "주요 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "correlation_matrix": "주요 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "gender_reply_count": "성별에 따른 댓글 작성 수 비교입니다.",
    "age_group_reply_count": "연령대별 댓글 작성 수 비교입니다.",
    "type_demographic": "게시물 유형별 독자 인구통계(성별/연령대) 분포입니다.",
    "sentiment_counts": "감성(긍정/부정/중립 등) 분류별 개수입니다.",
    "article_analysis": "게시물 단위 핵심 지표 요약입니다.",
    "cafe_analysis": "카페 게시물 핵심 지표 요약입니다.",
    "daily_mean": "일별 평균 수치입니다.",
    "monthly_mean": "월별 평균 수치입니다.",
    "rolling7_mean": "7일 이동평균으로 완만하게 다듬은 추세입니다. 일별 변동폭이 크더라도 전체 흐름을 파악하기 쉽습니다.",
    "hour_dow_heatmap": "요일×시간대별 게시물 빈도를 색상 농도로 보여주는 히트맵입니다. 짙을수록 해당 요일·시간대에 게시물이 많이 올라왔다는 뜻입니다.",
}


def _fallback_description(stem: str, columns: list[str]) -> str:
    if stem.endswith("_trend"):
        base = stem[: -len("_trend")]
        base_label = TABLE_DESCRIPTIONS.get(base, _humanize(base))
        return (
            f"{base_label} 원본 수치와 7기간 이동평균을 함께 보여줍니다. "
            "값의 급등락을 제외한 전체적인 추세를 파악할 때 유용합니다."
        )
    if stem.endswith("_cumulative"):
        base = stem[: -len("_cumulative")]
        base_label = TABLE_DESCRIPTIONS.get(base, _humanize(base))
        return f"{base_label} 값을 시간순으로 누적 합산한 추이입니다. 전체 누적 성장 규모를 보여줍니다."
    label_col = columns[0] if columns else None
    numeric_cols = columns[1:] if len(columns) > 1 else []
    if label_col and numeric_cols:
        return f"{label_col}별 {', '.join(numeric_cols[:3])} 집계 표입니다."
    return "분석 결과 표입니다."


# manager/server의 app/libs/spss_analysis.py(SPSS 스타일 범용 통계 스위트)가 만드는
# 표들 — 열 이름에 원본 변수명이 그대로 들어가 stem이 매번 달라지므로 TABLE_DESCRIPTIONS처럼
# 정적 dict로 못 만들고, 접두사 패턴으로 제목/설명을 만든다.
def _spss_title(stem: str) -> str | None:
    if stem == "spss_descriptives":
        return "기술통계량"
    if stem == "spss_normality":
        return "정규성 검정"
    if stem.startswith("spss_frequencies_"):
        return f"빈도분석 · {stem[len('spss_frequencies_') :].replace('_', ' ')}"
    if stem == "spss_correlation_pearson":
        return "상관분석 (Pearson)"
    if stem == "spss_correlation_pearson_pvalues":
        return "상관분석 (Pearson) · 유의확률"
    if stem == "spss_correlation_spearman":
        return "상관분석 (Spearman)"
    if stem == "spss_correlation_spearman_pvalues":
        return "상관분석 (Spearman) · 유의확률"
    if stem.startswith("spss_crosstab_"):
        a, _, b = stem[len("spss_crosstab_") :].partition("__")
        return f"교차표 · {a.replace('_', ' ')} × {b.replace('_', ' ')}"
    if stem == "spss_chisquare_summary":
        return "카이제곱 검정 요약"
    if stem.startswith("spss_groupmeans_"):
        a, _, b = stem[len("spss_groupmeans_") :].partition("__")
        return f"집단별 평균 · {a.replace('_', ' ')} by {b.replace('_', ' ')}"
    if stem.startswith("spss_posthoc_tukey_"):
        a, _, b = stem[len("spss_posthoc_tukey_") :].partition("__")
        return f"사후검정(Tukey HSD) · {a.replace('_', ' ')} by {b.replace('_', ' ')}"
    if stem == "spss_mean_comparison_summary":
        return "평균 비교 요약 (t-검정/분산분석)"
    if stem == "spss_regression_coefficients":
        return "회귀계수"
    if stem == "spss_regression_summary":
        return "회귀모형 요약"
    if stem == "spss_regression_vif":
        return "다중공선성 (VIF)"
    if stem == "spss_pca_variance":
        return "요인분석(PCA) · 설명 분산"
    if stem == "spss_pca_loadings":
        return "요인분석(PCA) · 성분 적재값"
    if stem == "spss_reliability_summary":
        return "신뢰도분석 (Cronbach's α)"
    if stem == "spss_reliability_items":
        return "신뢰도분석 · 항목별 분석"
    if stem == "spss_cluster_summary":
        return "군집분석 요약"
    if stem == "spss_cluster_profile":
        return "군집분석 · 군집별 프로파일"
    return None


def _spss_description(stem: str) -> str | None:
    if stem == "spss_descriptives":
        return "각 수치형 변수의 평균·표준편차·사분위수·왜도·첨도 등 기술통계량입니다."
    if stem == "spss_normality":
        return (
            "각 수치형 변수가 정규분포를 따르는지 검정한 결과입니다(Shapiro-Wilk 또는 표본이 "
            "많으면 Kolmogorov-Smirnov). p<.05이면 정규분포를 따르지 않는다고 봅니다."
        )
    if stem.startswith("spss_frequencies_"):
        return "해당 범주형 변수의 값별 빈도, 퍼센트, 누적 퍼센트입니다."
    if stem in ("spss_correlation_pearson", "spss_correlation_spearman"):
        method = "Pearson" if "pearson" in stem else "Spearman"
        return (
            f"수치형 변수들 사이의 {method} 상관계수 행렬입니다. 1에 가까울수록 강한 양의 상관, "
            "-1에 가까울수록 강한 음의 상관입니다."
        )
    if stem.endswith("_pvalues"):
        return "왼쪽 상관계수 행렬의 유의확률(p-value)입니다. 0.05보다 작으면 통계적으로 유의한 상관관계로 봅니다."
    if stem.startswith("spss_crosstab_"):
        return "두 범주형 변수의 교차표(빈도)입니다. 카이제곱 검정 결과는 '카이제곱 검정 요약' 표에서 확인할 수 있습니다."
    if stem == "spss_chisquare_summary":
        return (
            "범주형 변수 쌍마다 독립성을 검정한 카이제곱 검정 결과입니다. p<.05이면 두 변수가 "
            "서로 관련이 있다고(독립이 아니라고) 봅니다. Cramer's V는 연관성의 크기(0~1)입니다."
        )
    if stem.startswith("spss_groupmeans_"):
        return "범주별 평균·표준편차입니다. 평균 비교 요약표에서 유의한 차이가 발견된 조합에 대해서만 자동으로 생성됩니다."
    if stem.startswith("spss_posthoc_tukey_"):
        return "분산분석(ANOVA)에서 유의한 차이가 발견됐을 때, 어느 집단 쌍 사이에 실제로 차이가 있는지 확인하는 Tukey HSD 사후검정 결과입니다."
    if stem == "spss_mean_comparison_summary":
        return (
            "수치형 변수와 범주형 변수의 모든 조합에 대해 집단 간 평균 차이를 검정한 요약입니다 "
            "(그룹 2개는 t-검정, 3개 이상은 분산분석). 정규성이 의심되는 경우를 대비해 "
            "비모수검정(Mann-Whitney U/Kruskal-Wallis) 결과도 함께 제공합니다."
        )
    if stem == "spss_regression_coefficients":
        return (
            "다중회귀분석의 회귀계수입니다. p<.05인 변수가 종속변수에 통계적으로 유의한 영향을 미치는 "
            "예측변수입니다. 베타는 변수 간 영향력 크기를 표준화해 비교할 수 있게 해줍니다."
        )
    if stem == "spss_regression_summary":
        return "회귀모형 전체의 설명력(R²)과 통계적 유의성(F검정)을 보여줍니다."
    if stem == "spss_regression_vif":
        return "예측변수들 사이의 다중공선성 지표(VIF)입니다. 일반적으로 10을 넘으면 다중공선성 문제를 의심합니다."
    if stem == "spss_pca_variance":
        return "주성분분석(PCA)으로 수치형 변수들을 몇 개의 성분으로 압축했을 때 각 성분이 설명하는 분산 비율입니다. 고유값이 1보다 큰 성분을 주로 해석합니다."
    if stem == "spss_pca_loadings":
        return "각 성분에 원래 변수들이 얼마나 기여하는지 보여주는 적재값(loading)입니다. 절댓값이 클수록 해당 성분을 대표하는 변수입니다."
    if stem == "spss_reliability_summary":
        return (
            "선택된 수치형 변수들을 하나의 척도로 봤을 때의 내적 일관성 신뢰도(Cronbach's Alpha)입니다. "
            "통상 0.7 이상이면 신뢰할 만하다고 봅니다. 설문 척도 데이터가 아닌 경우 참고용으로만 활용하세요."
        )
    if stem == "spss_reliability_items":
        return "각 변수를 제외했을 때 신뢰도(alpha)가 어떻게 바뀌는지, 그리고 나머지 변수 합계와의 상관을 보여줍니다."
    if stem == "spss_cluster_summary":
        return "K-means 군집분석에서 자동으로 선택된 최적 군집 수와 군집 분리 품질(실루엣 계수, -1~1, 클수록 좋음)입니다."
    if stem == "spss_cluster_profile":
        return "각 군집에 속한 데이터의 개수와 군집별 수치형 변수 평균값입니다. 군집 간 값 차이로 각 군집의 성격을 해석할 수 있습니다."
    return None


def _section_for_stem(stem: str) -> str:
    if not stem.startswith("spss_"):
        return "핵심 지표"
    if stem in ("spss_descriptives", "spss_normality"):
        return "기술통계"
    if stem.startswith("spss_frequencies_"):
        return "빈도분석"
    if stem.startswith("spss_crosstab_") or stem.startswith("spss_chisquare"):
        return "교차분석 (카이제곱)"
    if (
        stem.startswith("spss_groupmeans_")
        or stem.startswith("spss_posthoc_")
        or stem == "spss_mean_comparison_summary"
    ):
        return "평균 비교 (t-검정/분산분석)"
    if stem.startswith("spss_correlation_"):
        return "상관분석"
    if stem.startswith("spss_regression_"):
        return "회귀분석"
    if stem.startswith("spss_pca_"):
        return "요인분석 (PCA)"
    if stem.startswith("spss_reliability_"):
        return "신뢰도분석"
    if stem.startswith("spss_cluster_"):
        return "군집분석"
    return "고급 통계"


def _describe_table(stem: str, columns: list[str]) -> str:
    return (
        TABLE_DESCRIPTIONS.get(stem)
        or _spss_description(stem)
        or _fallback_description(stem, columns)
    )


def _is_heatmap_table(stem: str, df: pd.DataFrame) -> bool:
    if stem == "hour_dow_heatmap":
        return True
    if stem.startswith("spss_crosstab_") or stem == "spss_pca_loadings":
        return True
    if "pvalue" in stem:
        return False
    if "correlation" in stem or "corr" in stem:
        # 상관행렬은 (라벨 열 + 숫자 열들)이고, 숫자 열 이름들이 각 행의 라벨과
        # 대체로 일치하는 정사각형 행렬이다.
        numeric_cols = df.select_dtypes(include="number").columns
        return len(numeric_cols) >= 2 and abs(len(numeric_cols) - len(df)) <= 1
    return False


def _table_from_csv(path: str) -> dict:
    stem = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path, encoding="utf-8-sig")
    is_heatmap = _is_heatmap_table(stem, df)
    truncated = len(df) > MAX_ROWS_PER_TABLE
    if truncated:
        df = df.head(MAX_ROWS_PER_TABLE)
    # NaN -> None (엄격한 JSON 직렬화를 위해)
    df = df.astype(object).where(pd.notnull(df), None)
    # pandas가 이름 없는 인덱스 열에 붙이는 "Unnamed: 0" 같은 헤더를 사람이 읽기 좋게 치환
    columns = ["항목" if str(c).startswith("Unnamed:") else str(c) for c in df.columns]
    return {
        "id": stem,
        "title": _spss_title(stem) or _humanize(stem),
        "description": _describe_table(stem, columns),
        "section": _section_for_stem(stem),
        "columns": columns,
        "rows": df.values.tolist(),
        "row_count": len(df),
        "truncated": truncated,
        "is_heatmap": is_heatmap,
    }


def _build_base_json(root: str) -> dict:
    metadata_path = os.path.join(root, "metadata.json")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    description = ""
    desc_path = os.path.join(root, "description.txt")
    if os.path.exists(desc_path):
        with open(desc_path, "r", encoding="utf-8", errors="ignore") as f:
            description = f.read()

    tables = []
    csv_dir = os.path.join(root, "csv_files")
    if os.path.isdir(csv_dir):
        for fname in sorted(os.listdir(csv_dir)):
            if fname.lower().endswith(".csv"):
                try:
                    tables.append(_table_from_csv(os.path.join(csv_dir, fname)))
                except Exception:
                    continue

    graphs = []
    graph_dir = os.path.join(root, "graphs")
    if os.path.isdir(graph_dir):
        graphs = sorted(f for f in os.listdir(graph_dir) if f.lower().endswith(".png"))

    return {
        "metadata": metadata,
        "description": description,
        "tables": tables,
        "graphs": graphs,
    }


def _extract_zip_and_build(root: str, upload_bytes: bytes) -> dict:
    """zip을 root/raw 에 풀고 base.json을 만들어 반환한다."""
    raw_dir = os.path.join(root, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
            safe_extract_zip(zf, raw_dir)
    except zipfile.BadZipFile:
        raise ValueError("zip 파일이 아니거나 손상되었습니다.")
    except UnsafeZipError as e:
        raise ValueError(str(e))

    result_root = _find_result_root(raw_dir)
    base = _build_base_json(result_root)

    with open(os.path.join(root, "base.json"), "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False)

    return base


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def _iso(dt) -> str:
    return dt.isoformat() if hasattr(dt, "isoformat") else dt


def _doc_out(doc: dict) -> dict:
    return {
        "project_id": doc["_id"],
        "name": doc["name"],
        "created_at": _iso(doc["created_at"]),
        "updated_at": _iso(doc["updated_at"]),
        "source": doc.get("source", "upload"),
        "category": doc.get("category"),
        "platform": doc.get("platform"),
        "summary": doc.get("summary", {}),
        "folder_id": doc.get("folder_id"),
    }


def create_project(
    uid: str, upload_bytes: bytes, name: str, source: str = "upload"
) -> dict:
    project_id = uuid.uuid4().hex
    root = _project_dir(uid, project_id)
    os.makedirs(root, exist_ok=True)

    try:
        base = _extract_zip_and_build(root, upload_bytes)
    except ValueError:
        shutil.rmtree(root, ignore_errors=True)
        raise

    metadata = base.get("metadata", {})
    summary = {
        "table_count": len(base.get("tables", [])),
        "row_count": metadata.get("row_count"),
        "source_filename": metadata.get("source_filename"),
    }

    now = datetime.now(timezone.utc)
    doc = {
        "_id": project_id,
        "uid": uid,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "category": metadata.get("category"),
        "platform": metadata.get("platform"),
        "summary": summary,
    }
    statistics_projects_db.insert_one(doc)
    return _doc_out(doc)


def list_projects(uid: str) -> list:
    docs = statistics_projects_db.find({"uid": uid}).sort("created_at", -1)
    return [_doc_out(d) for d in docs]


def list_all_projects() -> list:
    """관리자용: 모든 사용자의 프로젝트를 소유자 이름과 함께 반환한다."""
    docs = list(statistics_projects_db.find({}).sort("created_at", -1))
    names = get_user_names([d["uid"] for d in docs])
    out = []
    for d in docs:
        item = _doc_out(d)
        item["owner_uid"] = d["uid"]
        item["owner_name"] = names.get(d["uid"], d["uid"])
        out.append(item)
    return out


def _get_owned_doc(uid: str, project_id: str, is_admin: bool = False) -> dict:
    doc = statistics_projects_db.find_one({"_id": project_id})
    if not doc:
        raise NotFound("프로젝트를 찾을 수 없습니다.")
    if doc["uid"] != uid and not is_admin:
        raise Forbidden("이 프로젝트에 접근할 권한이 없습니다.")
    return doc


def get_project(uid: str, project_id: str, is_admin: bool = False) -> dict:
    return _doc_out(_get_owned_doc(uid, project_id, is_admin))


def rename_project(uid: str, project_id: str, new_name: str) -> dict:
    _get_owned_doc(uid, project_id)
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("이름을 입력해주세요.")
    statistics_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(_get_owned_doc(uid, project_id))


def delete_project(uid: str, project_id: str):
    _get_owned_doc(uid, project_id)
    statistics_projects_db.delete_one({"_id": project_id})
    shutil.rmtree(_project_dir(uid, project_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 폴더 (사이드바 프로젝트 정리용 — 각자 자기 폴더만 관리한다)
# ---------------------------------------------------------------------------


def _folder_out(doc: dict) -> dict:
    return {
        "folder_id": doc["_id"],
        "name": doc["name"],
        "created_at": _iso(doc["created_at"]),
        "updated_at": _iso(doc["updated_at"]),
    }


def list_folders(uid: str) -> list:
    docs = statistics_folders_db.find({"uid": uid}).sort("name", 1)
    return [_folder_out(d) for d in docs]


def list_all_folders() -> list:
    docs = list(statistics_folders_db.find({}).sort("name", 1))
    names = get_user_names([d["uid"] for d in docs])
    out = []
    for d in docs:
        item = _folder_out(d)
        item["owner_uid"] = d["uid"]
        item["owner_name"] = names.get(d["uid"], d["uid"])
        out.append(item)
    return out


def create_folder(uid: str, name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("폴더 이름을 입력해주세요.")
    folder_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    doc = {"_id": folder_id, "uid": uid, "name": name, "created_at": now, "updated_at": now}
    statistics_folders_db.insert_one(doc)
    return _folder_out(doc)


def _get_owned_folder(uid: str, folder_id: str) -> dict:
    doc = statistics_folders_db.find_one({"_id": folder_id})
    if not doc:
        raise NotFound("폴더를 찾을 수 없습니다.")
    if doc["uid"] != uid:
        raise Forbidden("이 폴더에 접근할 권한이 없습니다.")
    return doc


def rename_folder(uid: str, folder_id: str, new_name: str) -> dict:
    _get_owned_folder(uid, folder_id)
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("이름을 입력해주세요.")
    statistics_folders_db.update_one(
        {"_id": folder_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _folder_out(_get_owned_folder(uid, folder_id))


def delete_folder(uid: str, folder_id: str):
    _get_owned_folder(uid, folder_id)
    statistics_folders_db.delete_one({"_id": folder_id})
    # 폴더 안에 있던 프로젝트는 삭제하지 않고 미분류(폴더 없음) 상태로 되돌린다.
    statistics_projects_db.update_many(
        {"uid": uid, "folder_id": folder_id},
        {"$set": {"folder_id": None, "updated_at": datetime.now(timezone.utc)}},
    )


def move_project_folder(uid: str, project_id: str, folder_id: str | None) -> dict:
    doc = _get_owned_doc(uid, project_id)
    if folder_id:
        _get_owned_folder(uid, folder_id)
    statistics_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"folder_id": folder_id, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(statistics_projects_db.find_one({"_id": project_id}))


# ---------------------------------------------------------------------------
# 분석 결과 (표 + 설명)
# ---------------------------------------------------------------------------


def load_base(uid: str, project_id: str, is_admin: bool = False) -> dict:
    doc = _get_owned_doc(uid, project_id, is_admin)
    path = _base_json_path(doc["uid"], project_id)
    if not os.path.exists(path):
        raise NotFound("분석 결과를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 원본 zip 재다운로드
# ---------------------------------------------------------------------------


def zip_raw(uid: str, project_id: str, is_admin: bool = False) -> str:
    """raw/ 폴더를 즉석에서 압축해 zip 경로를 반환한다 (호출자가 응답 후 삭제 책임)."""
    doc = _get_owned_doc(uid, project_id, is_admin)
    owner_uid = doc["uid"]
    raw_dir = _raw_dir(owner_uid, project_id)
    if not os.path.isdir(raw_dir):
        raise NotFound("원본 분석 결과를 찾을 수 없습니다.")
    tmp_base = os.path.join(
        _project_dir(owner_uid, project_id), f"download_{uuid.uuid4().hex}"
    )
    archive_path = shutil.make_archive(tmp_base, "zip", raw_dir)
    return archive_path
