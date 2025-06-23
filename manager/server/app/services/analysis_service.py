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

import re, time, pandas as pd
from kiwipiepy import Kiwi

def tokenization(
    pid: str,
    data: pd.DataFrame,
    columns,
    update_interval: int = 500,
) -> pd.DataFrame:
    """
    ▸ pid            : 진행 상황을 send_message(pid, …)로 전달할 때 사용
    ▸ data           : 원본 DataFrame (in-place 수정)
    ▸ columns        : 토큰화할 열 이름 또는 이름 리스트
    ▸ update_interval: 이 개수마다 진행률 메시지 전송
    """
    # 1) Kiwi 한 번만 초기화
    kiwi = Kiwi(num_workers=-1)

    # 2) 단일 str → list
    if isinstance(columns, str):
        columns = [columns]

    # 3) 각 열을 순회
    for col in columns:
        if col not in data.columns:
            send_message(pid, f"⚠️  열 '{col}'이(가) 존재하지 않습니다 → 건너뜀")
            continue

        texts        = data[col].tolist()
        total        = len(texts)
        tokenized_col = []

        send_message(pid, f"[{col}] 토큰화 시작 (총 {total:,} rows)")

        total_time = 0.0
        for idx, text in enumerate(texts, 1):
            start = time.time()

            if isinstance(text, str):
                # 전처리
                cleaned = re.sub(r"[^가-힣a-zA-Z\s]", "", text)
                # splitComplex=False → 복합어를 분해하지 않고 처리
                tokens   = kiwi.tokenize(cleaned, splitComplex=False)
                nouns    = [t.form for t in tokens if t.tag in ("NNG", "NNP")]
                tokenized_col.append(", ".join(nouns))
            else:
                tokenized_col.append("")

            # 진행률 계산
            total_time += time.time() - start
            if idx % update_interval == 0 or idx == total:
                pct   = round(idx / total * 100, 2)
                avg   = total_time / idx
                remain_sec = avg * (total - idx)
                m, s  = divmod(int(remain_sec), 60)
                send_message(
                    pid,
                    f"[{col}] 진행률 {pct}% ({idx:,}/{total:,}) • 예상 남은 시간 {m}분 {s}초"
                )

        # 열 덮어쓰기
        data[col] = tokenized_col
        send_message(pid, f"[{col}] 토큰화 완료 ✅")

    return data
