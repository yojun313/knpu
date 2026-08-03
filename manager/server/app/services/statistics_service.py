import json
import os
import shutil
import uuid
from datetime import datetime

import pandas as pd
import requests
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.config import STATISTICS_VIEWER_URL
from app.libs import spss_analysis
from app.libs.auto_chart import fill_missing_graphs
from system.progress import send_message
from app.libs.statistics_analysis import StatisticsAnalysis
from app.models.analysis_model import StatisticsOption
from app.utils.zip import fast_zip

statistics_analysis = StatisticsAnalysis()


def _push_to_statistics_viewer(
    zip_path: str, uid: str, project_name: str, pid: str
) -> str | None:
    """분석 결과 zip을 온라인 뷰어(manager/statistics)의 사용자 프로젝트로 곧바로 밀어 넣는다.
    실패해도 분석 자체를 실패시키지 않는다 — zip 다운로드는 항상 그대로 내려간다."""
    internal_key = os.getenv("INTERNAL_API_KEY", "")
    try:
        with open(zip_path, "rb") as f:
            resp = requests.post(
                f"{STATISTICS_VIEWER_URL}/api/internal/projects/ingest",
                headers={"X-Internal-Key": internal_key},
                data={"uid": uid, "name": project_name or "통계 분석"},
                files={"file": (os.path.basename(zip_path), f, "application/zip")},
                timeout=60,
            )
        if resp.status_code == 200:
            project_id = resp.json().get("project_id")
            send_message(
                pid,
                f"온라인 뷰어에 프로젝트로 저장했습니다: {STATISTICS_VIEWER_URL}/viewer/{project_id}",
            )
            return project_id
        send_message(
            pid,
            "온라인 뷰어 자동 업로드에 실패했습니다. (결과 zip은 정상적으로 받으실 수 있습니다)",
        )
    except Exception:
        send_message(
            pid,
            "온라인 뷰어 서버에 연결할 수 없습니다. (결과 zip은 정상적으로 받으실 수 있습니다)",
        )
    return None


_DAY_NAMES_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _find_date_column(columns) -> str | None:
    return next((c for c in columns if "date" in str(c).lower()), None)


def _add_derived_time_series_tables(csv_dir: str) -> None:
    """분석 함수가 만든 표들 중 날짜 축을 가진 것들에 '7기간 이동평균'과 '누적' 표를
    추가로 만들어준다 — 원본 표를 건드리지 않고 새 표(=뷰어의 새 카드)로 분리해서,
    추세와 누적 성장 같은 지표를 따로 확인할 수 있게 한다."""
    if not os.path.isdir(csv_dir):
        return
    for fname in list(os.listdir(csv_dir)):
        if not fname.endswith(".csv"):
            continue
        stem = fname[:-4]
        # basic_stats류(describe() 출력)는 "Article Date" 등이 열 이름으로만 등장할 뿐
        # 실제 날짜값이 아니므로 제외한다.
        if stem.endswith(("_trend", "_cumulative")) or stem in (
            "hour_dow_heatmap",
            "basic_stats",
        ):
            continue
        path = os.path.join(csv_dir, fname)
        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        date_col = _find_date_column(df.columns)
        if not date_col:
            continue
        # 열 이름에 "date"가 들어 있어도 실제로 날짜값이 아닐 수 있으므로
        # (예: describe() 출력의 열 라벨) 파싱 성공률로 한 번 더 검증한다.
        parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
        if parsed_dates.notna().mean() < 0.9:
            continue
        numeric_cols = [
            c
            for c in df.columns
            if c != date_col and pd.api.types.is_numeric_dtype(df[c])
        ]
        if not numeric_cols or not (8 <= len(df) <= 400):
            continue
        metric = numeric_cols[0]

        trend_df = df[[date_col, metric]].copy()
        trend_df[f"{metric} (7기간 이동평균)"] = (
            trend_df[metric].rolling(7, min_periods=1).mean().round(2)
        )
        trend_df.to_csv(
            os.path.join(csv_dir, f"{stem}_trend.csv"),
            index=False,
            encoding="utf-8-sig",
        )

        cumulative_df = df[[date_col]].copy()
        cumulative_df[f"{metric} (누적)"] = df[metric].cumsum()
        cumulative_df.to_csv(
            os.path.join(csv_dir, f"{stem}_cumulative.csv"),
            index=False,
            encoding="utf-8-sig",
        )


def _add_hour_dow_heatmap(data, csv_dir: str) -> None:
    """원본 데이터의 날짜 열로부터 요일×시간대 히트맵(투고 빈도) 표를 만든다.
    특정 분석 함수에 종속되지 않는 범용 지표라 원본 데이터에서 바로 계산한다."""
    date_col = _find_date_column(data.columns)
    if not date_col:
        return
    dt = pd.to_datetime(data[date_col], errors="coerce").dropna()
    if len(dt) < 20:
        return

    counts = pd.DataFrame({"dow": dt.dt.dayofweek, "hour": dt.dt.hour})
    pivot = (
        counts.groupby(["dow", "hour"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=range(7), columns=range(24), fill_value=0)
    )
    pivot.index = _DAY_NAMES_KR
    pivot.columns = [f"{h}시" for h in range(24)]
    pivot = pivot.reset_index().rename(columns={"index": "요일"})

    os.makedirs(csv_dir, exist_ok=True)
    pivot.to_csv(
        os.path.join(csv_dir, "hour_dow_heatmap.csv"),
        index=False,
        encoding="utf-8-sig",
    )


# StatisticsOption.category / .platform 조합 -> StatisticsAnalysis 메서드
def _dispatch(category: str, platform: str, data, output_dir: str) -> None:
    match (category, platform):
        case ("article 분석", "Naver News"):
            statistics_analysis.NaverNewsArticleAnalysis(data, output_dir)
        case ("statistics 분석", "Naver News"):
            statistics_analysis.NaverNewsStatisticsAnalysis(data, output_dir)
        case ("reply 분석", "Naver News"):
            statistics_analysis.NaverNewsReplyAnalysis(data, output_dir)
        case ("rereply 분석", "Naver News"):
            statistics_analysis.NaverNewsRereplyAnalysis(data, output_dir)
        case ("article 분석", "Naver Cafe"):
            statistics_analysis.NaverCafeArticleAnalysis(data, output_dir)
        case ("reply 분석", "Naver Cafe"):
            statistics_analysis.NaverCafeReplyAnalysis(data, output_dir)
        case ("article 분석", "Google YouTube"):
            statistics_analysis.YouTubeArticleAnalysis(data, output_dir)
        case ("reply 분석", "Google YouTube"):
            statistics_analysis.YouTubeReplyAnalysis(data, output_dir)
        case ("rereply 분석", "Google YouTube"):
            statistics_analysis.YouTubeRereplyAnalysis(data, output_dir)
        case (o, _) if o.lower().startswith("hate") or "혐오" in o:
            statistics_analysis.HateAnalysis(data, output_dir)
        case _:
            raise ValueError(f"지원되지 않는 옵션입니다: {category} / {platform}")


def run_statistics_analysis(
    option: StatisticsOption,
    data,
    uid: str | None = None,
    project_name: str | None = None,
):
    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    temp_root = os.path.join(os.path.dirname(__file__), "..", "temp")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(temp_root, f"statistics_{option.pid}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    row_count = len(data)
    _dispatch(option.category, option.platform, data, output_dir)

    csv_dir = os.path.join(output_dir, "csv_files")
    _add_hour_dow_heatmap(data, csv_dir)
    _add_derived_time_series_tables(csv_dir)
    spss_analysis.run(data, csv_dir)

    # 뷰어(manager/statistics)는 csv_files의 모든 표를 브라우저에서 즉석 차트로
    # 그려 보여주는데, 그중 spss_analysis.py가 만든 표들과 위의 파생 표(히트맵/
    # 추세/누적)는 여기 있는 10개 분석 함수와 달리 대응하는 그래프 이미지가 없어
    # zip 다운로드에서만 빠지는 문제가 있었다. 화면에 이미 잘 그려지는 표들과 같은
    # 규칙으로 그래프를 자동 생성해 graphs/에 채워 넣어 zip과 화면을 일치시킨다.
    graph_dir = os.path.join(output_dir, "graphs")
    fill_missing_graphs(csv_dir, graph_dir)

    metadata = {
        "category": option.category,
        "platform": option.platform,
        "source_filename": project_name or "",
        "row_count": row_count,
        "generated_at": datetime.now().isoformat(),
    }
    with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    zip_path = f"{output_dir}.zip"
    fast_zip(output_dir, zip_path)
    filename = os.path.basename(zip_path)

    background_task = BackgroundTask(cleanup_folder_and_zip, output_dir, zip_path)

    response_headers = {}
    if uid:
        project_id = _push_to_statistics_viewer(zip_path, uid, project_name, option.pid)
        if project_id:
            response_headers["X-Statistics-Project-Id"] = project_id

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_task,
        headers=response_headers,
    )
