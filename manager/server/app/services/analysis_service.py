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
import re
from kiwipiepy import Kiwi
import torch, numpy as np
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TextClassificationPipeline,
)
import os
from dotenv import load_dotenv

load_dotenv() 

MODEL_DIR = os.getenv("MODEL_PATH")  # .env 파일에서 읽기

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, local_files_only=True)
pipe = TextClassificationPipeline(
    model=model,
    tokenizer=tokenizer,
    function_to_apply="sigmoid",
    top_k=None,                                # 전체 레이블 확률 반환
    device=0 if torch.cuda.is_available() else -1,
)

# clean 제외한 8개 혐오·악플 레이블
hate_labels = [lbl for lbl in model.config.id2label.values() if lbl != "clean"]


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
    include_words: list = None,
    update_interval: int = 3000,
) -> pd.DataFrame:
    """
    ▸ pid            : 진행 상황을 send_message(pid, …)로 전달할 때 사용
    ▸ data           : 원본 DataFrame (in-place 수정)
    ▸ columns        : 토큰화할 열 이름 또는 이름 리스트
    ▸ update_interval: 이 개수마다 진행률 메시지 전송
    """
    # 1) Kiwi 한 번만 초기화
    kiwi = Kiwi(num_workers=-1)
    for word in include_words:
        kiwi.add_user_word(word, 'NNP', score=10)

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
                tokens   = kiwi.tokenize(cleaned, split_complex=False)
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

def measure_hate(
    option: HateOption,
    data: pd.DataFrame,
    text_col: str | None = "Text",
    update_interval: int = 1000,
    batch_size: int = 32,           # ← 추가: 배치 크기
) -> pd.DataFrame:
    """
    옵션 1: Hate  / 2: Clean  / 3: 모든 레이블
    확률은 소수 둘째 자리로 반올림
    """

    # ───── 내부 헬퍼 ─────────────────────────────────────────
    def outputs_to_scores(outputs):
        """ pipeline 출력(list[dict]) → {label: rounded_prob} """
        return {o["label"]: round(o["score"], 2) for o in outputs}
    # ───────────────────────────────────────────────────────

    pid, mode = option.pid, option.option_num

    # ① 대상 열 확인 / 자동 탐색
    if text_col not in data.columns:
        cand = [c for c in data.columns if "text" in c.lower()]
        if not cand:
            raise ValueError("'Text' 포함 열을 찾을 수 없습니다")
        text_col = cand[0]
        send_message(pid, f"🔍 '{text_col}' 열을 자동 선택했습니다")

    total = len(data)
    send_message(pid, f"[혐오도 분석] '{text_col}' 처리 시작 (총 {total:,} rows)")

    # ② 결과 버퍼 초기화
    all_labels = list(model.config.id2label.values())
    if mode == 1:
        hate_vals = [0.0] * total
    elif mode == 2:
        clean_vals = [0.0] * total
    else:  # mode == 3
        scores_dict = {lbl: [0.0] * total for lbl in all_labels}

    # ③ 배치 처리
    texts = data[text_col].fillna("").tolist()
    processed = 0

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)

        # 비어 있지 않은 행만 추려서 추론
        idxs, batch_txts = [], []
        for i in range(start, end):
            t = texts[i]
            if isinstance(t, str) and t.strip():
                idxs.append(i)
                batch_txts.append(t)

        if batch_txts:
            batch_outputs = pipe(
                batch_txts,
                truncation=True,
                batch_size=batch_size,
            )
            for i, outs in zip(idxs, batch_outputs):
                scores = outputs_to_scores(outs)
                if mode == 1:
                    hate_vals[i] = max(v for k, v in scores.items() if k != "clean")
                elif mode == 2:
                    clean_vals[i] = scores.get("clean", 0.0)
                else:  # mode == 3
                    for lbl in scores_dict:
                        scores_dict[lbl][i] = scores.get(lbl, 0.0)

        processed += (end - start)
        if processed % update_interval == 0 or processed == total:
            pct = round(processed / total * 100, 2)
            send_message(pid, f"[혐오도 분석] {pct}% 완료 ({processed:,}/{total:,})")

    # ④ 결과 열 추가
    if mode == 1:
        data["Hate"] = hate_vals
    elif mode == 2:
        data["Clean"] = clean_vals
    else:
        for lbl, vals in scores_dict.items():
            data[lbl] = vals

    send_message(pid, "[혐오도 분석] 완료 ✅")
    return data
