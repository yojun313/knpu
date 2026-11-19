import pandas as pd
from app.models.analysis_model import KemKimOption
from app.libs.kemkim import KemKim
from system.progress import send_message
from app.config import KEMKIM_VIEWER_URL
from app.services import project_store
import os

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import shutil
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from app.utils.zip import fast_zip


def _save_as_project(
    zip_path: str,
    uid: str,
    project_name: str,
    pid: str,
    crawl_source: dict | None = None,
) -> str | None:
    try:
        with open(zip_path, "rb") as f:
            content = f.read()
        project = project_store.create_project(
            uid,
            content,
            project_name or "KEMKIM 분석",
            "analysis",
            crawl_source=crawl_source,
        )
        project_id = project["project_id"]
        send_message(
            pid,
            f"온라인 뷰어에 프로젝트로 저장했습니다: {KEMKIM_VIEWER_URL}/viewer/{project_id}",
        )
        return project_id
    except Exception:
        send_message(
            pid,
            "프로젝트 저장에 실패했습니다. (결과 zip은 정상적으로 받으실 수 있습니다)",
        )
    return None


def _validate_token_data(token_data) -> None:
    """KEMKIM 엔진이 요구하는 입력(Text·Date 열, 유효 날짜)을 분석 시작 전에 확인한다.

    예전에는 Date 열이 없으면 엔진 속성 미설정으로 AttributeError, 날짜가 비어 있으면
    NaT 범위 계산에서 ValueError가 그대로 나갔다. 여기서 사용자 입력 오류로 정리한다.
    """
    columns = [str(c) for c in getattr(token_data, "columns", [])]
    text_col = next((c for c in columns if "Text" in c), None)
    date_col = next((c for c in columns if "Date" in c), None)
    if text_col is None:
        raise ValueError(
            "'Text'가 들어간 열이 없습니다. 토큰화된 CSV(token_ 파일)를 사용해 주시기 바랍니다."
        )
    if date_col is None:
        raise ValueError(
            "'Date'가 들어간 열이 없습니다. 날짜 열이 있는 토큰화 CSV를 사용해 주시기 바랍니다."
        )
    if len(token_data) == 0:
        raise ValueError("분석할 데이터 행이 없습니다.")
    dates = pd.to_datetime(token_data[date_col], errors="coerce")
    if dates.notna().sum() == 0:
        raise ValueError(
            f"'{date_col}' 열에서 읽을 수 있는 날짜가 없습니다. 날짜 형식을 확인해 주시기 바랍니다."
        )
    texts = token_data[text_col].dropna().astype(str).str.strip()
    if (texts != "").sum() == 0:
        raise ValueError(f"'{text_col}' 열이 비어 있습니다.")


def start_kemkim(
    option: KemKimOption,
    token_data,
    uid: str | None = None,
    project_name: str | None = None,
    crawl_source: dict | None = None,
):

    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    option = option.model_dump()
    save_path = os.path.join(os.path.dirname(__file__), "..", "temp")
    _validate_token_data(token_data)

    kemkim_obj = KemKim(
        pid=option["pid"],
        token_data=token_data,
        csv_name=option["tokenfile_name"],
        save_path=save_path,
        startdate=option["startdate"],
        enddate=option["enddate"],
        period=option["period"],
        topword=option["topword"],
        weight=option["weight"],
        graph_wordcnt=option["graph_wordcnt"],
        split_option=option["split_option"],
        split_custom=option["split_custom"],
        filter_option=option["filter_option"],
        trace_standard=option["trace_standard"],
        ani_option=option["ani_option"],
        exception_word_list=option["exception_word_list"],
        exception_filename=option["exception_filename"],
        modify_kemkim=False,
    )
    try:
        result_path = kemkim_obj.make_kemkim()

        if type(result_path) == str:
            zip_path = f"{result_path}.zip"
            fast_zip(result_path, zip_path)
            filename = os.path.basename(zip_path)

            background_task = BackgroundTask(
                cleanup_folder_and_zip, result_path, zip_path
            )

            response_headers = {}
            if uid:
                project_id = _save_as_project(
                    zip_path, uid, project_name, option["pid"], crawl_source
                )
                if project_id:
                    response_headers["X-Kemkim-Project-Id"] = project_id

            # 4) FileResponse에 filename= 으로 넘기기
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=filename,
                background=background_task,
                headers=response_headers,
            )
        elif result_path == 2:
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={
                    "error": "KEMKIM 분석 중 오류 발생",
                    "message": "시간 가중치 오류가 발생했습니다",
                },
            )
        elif result_path in (0, 3):  # 0: make_kemkim 의 "키워드 없음 종료"
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={
                    "error": "KEMKIM 분석 중 오류 발생",
                    "message": "키워드가 없어 분석이 종료되었습니다",
                },
            )
        elif result_path == 4:
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={
                    "error": "KEMKIM 분석 중 오류 발생",
                    "message": "선택한 기간에 최소 2개 이상의 분석 구간이 필요합니다",
                },
            )

    except Exception as e:
        # 예외 상황 메시지 응답
        return JSONResponse(
            status_code=500,
            content={"error": "KEMKIM 분석 중 오류 발생", "message": str(e)},
        )
