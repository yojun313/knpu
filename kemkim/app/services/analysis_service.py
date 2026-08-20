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
    zip_path: str, uid: str, project_name: str, pid: str
) -> str | None:
    try:
        with open(zip_path, "rb") as f:
            content = f.read()
        project = project_store.create_project(
            uid, content, project_name or "KEMKIM 분석", "analysis"
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


def start_kemkim(
    option: KemKimOption,
    token_data,
    uid: str | None = None,
    project_name: str | None = None,
):

    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    option = option.model_dump()
    save_path = os.path.join(os.path.dirname(__file__), "..", "temp")

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
                    zip_path, uid, project_name, option["pid"]
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
        elif result_path == 3:
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
