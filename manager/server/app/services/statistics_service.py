import json
import os
import shutil
import uuid
from datetime import datetime

import requests
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.config import STATISTICS_VIEWER_URL
from app.libs.progress import send_message
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
    output_dir = os.path.join(
        temp_root, f"statistics_{option.pid}_{timestamp}"
    )
    os.makedirs(output_dir, exist_ok=True)

    row_count = len(data)
    _dispatch(option.category, option.platform, data, output_dir)

    metadata = {
        "category": option.category,
        "platform": option.platform,
        "source_filename": project_name or "",
        "row_count": row_count,
        "generated_at": datetime.now().isoformat(),
    }
    with open(
        os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    zip_path = f"{output_dir}.zip"
    fast_zip(output_dir, zip_path)
    filename = os.path.basename(zip_path)

    background_task = BackgroundTask(cleanup_folder_and_zip, output_dir, zip_path)

    response_headers = {}
    if uid:
        project_id = _push_to_statistics_viewer(
            zip_path, uid, project_name, option.pid
        )
        if project_id:
            response_headers["X-Statistics-Project-Id"] = project_id

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_task,
        headers=response_headers,
    )
