from app.models.analysis_model import *
from app.libs.kemkim import KimKem
from app.libs.progress import *
import os
import shutil
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from kiwipiepy import Kiwi
import time
import pandas as pd
import multiprocessing as mp
import re

def start_kemkim(option: KemKimOption, token_data):

    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        # 폴더와 ZIP 파일을 삭제
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    option = option.model_dump()
    save_path = os.path.join(os.path.dirname(__file__), '..', 'temp')

    kemkim_obj = KimKem(
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
        modify_kemkim=False
    )
    try:
        result_path = kemkim_obj.make_kimkem()

        if type(result_path) == str:
            zip_path = shutil.make_archive(
                result_path, "zip", root_dir=result_path)
            filename = os.path.basename(zip_path)  # 여기에 한글이 섞여 있어도 OK

            background_task = BackgroundTask(
                cleanup_folder_and_zip, result_path, zip_path)

            # 4) FileResponse에 filename= 으로 넘기기
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=filename,
                background=background_task,
            )
        elif result_path == 2:
            # ❗예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "시간 가중치 오류가 발생했습니다"}
            )
        elif result_path == 3:
            # ❗예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "키워드가 없어 분석이 종료되었습니다"}
            )

    except Exception as e:
        # ❗예외 상황 메시지 응답
        return JSONResponse(
            status_code=500,
            content={"error": "KEMKIM 분석 중 오류 발생", "message": str(e)}
        )

def tokenization(
    pid: str,
    data: pd.DataFrame,
    columns,
    processes: int | None = None,
    chunksize: int = 1_000,
    update_interval: int = 500,
) -> pd.DataFrame:
    """
    columns      : 토큰화할 열 이름 또는 열 리스트
    processes    : Pool 프로세스 수 (None => mp.cpu_count())
    chunksize    : imap_unordered 에 넘길 chunk 크기
    update_interval : 이 개수마다 진행 상황 메시지 전송
    """
    # ── 1) 보조 함수들 ──────────────────────────────────────────────
    def _init_kiwi():
        global kiwi
        kiwi = Kiwi(num_workers=-1)       # 각 프로세스마다 1회만 생성

    def _tokenize_single(text: str) -> str:
        if not isinstance(text, str):
            return ""
        text = re.sub(r"[^가-힣a-zA-Z\s]", "", text)
        tokens = kiwi.tokenize(text)
        return ", ".join(t.form for t in tokens if t.tag in ("NNG", "NNP"))

    # ── 2) 매개변수 정돈 ───────────────────────────────────────────
    if isinstance(columns, str):
        columns = [columns]

    # ── 3) 멀티프로세스 풀 생성 ──────────────────────────────────
    with mp.Pool(processes=processes, initializer=_init_kiwi) as pool:
        for col in columns:
            if col not in data.columns:
                send_message(pid, f"⚠️  열 '{col}'이(가) 존재하지 않아 건너뜁니다.")
                continue

            texts = data[col].tolist()
            total = len(texts)
            tokenized_col = []

            # ── 3-1) 진행 메시지 시작 ────────────────────────────
            send_message(pid, f"[{col}] 토큰화 시작 (총 {total:,} rows)")

            # ── 3-2) 비동기 스트리밍 처리 ───────────────────────
            for idx, tok in enumerate(
                pool.imap_unordered(_tokenize_single, texts, chunksize=chunksize), 1
            ):
                tokenized_col.append(tok)

                if idx % update_interval == 0 or idx == total:
                    progress = round(idx / total * 100, 2)
                    send_message(pid, f"[{col}] 진행률 {progress}%  ({idx:,}/{total:,})")

            # ── 3-3) DataFrame 열 덮어쓰기 & 완료 메시지 ─────────
            data[col] = tokenized_col
            send_message(pid, f"[{col}] 토큰화 완료 ✅")

    return data

