from app.models.analysis_model import *
from app.libs.kemkim import KimKem
from app.libs.progress import *
import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
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
    logging
)
logging.set_verbosity_error()
import os
from dotenv import load_dotenv
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from app.utils.zip import fast_zip
import gc

load_dotenv() 

kor_unsmile_pipe = None
topic_model = None
kiwi_instance = None

def get_kiwi():
    global kiwi_instance
    if kiwi_instance is None:
        kiwi_instance = Kiwi(num_workers=-1)
    return kiwi_instance

def get_hate_model():
    global kor_unsmile_pipe, topic_model
    MODEL_DIR = os.getenv("MODEL_PATH")
    
    if kor_unsmile_pipe is None:
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_model = AutoModelForSequenceClassification.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_pipe = TextClassificationPipeline(
            model=kor_unsmile_model,
            tokenizer=tokenizer,
            function_to_apply="sigmoid",
            top_k=None,
            device=0 if torch.cuda.is_available() else -1,
        )

    if topic_model is None:
        embed_model = SentenceTransformer(os.path.join(MODEL_DIR, "topic"),
                                          device="cuda" if torch.cuda.is_available() else "cpu")
        topic_model = KeyBERT(embed_model)

    return kor_unsmile_pipe, topic_model

def unload_hate_model():
    global kor_unsmile_pipe, topic_model
    kor_unsmile_pipe = None
    topic_model = None
    torch.cuda.empty_cache()
    gc.collect()

def start_kemkim(option: KemKimOption, token_data):

    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
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
            zip_path = f"{result_path}.zip"
            fast_zip(result_path, zip_path)   
            filename = os.path.basename(zip_path)

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
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "시간 가중치 오류가 발생했습니다"}
            )
        elif result_path == 3:
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "키워드가 없어 분석이 종료되었습니다"}
            )

    except Exception as e:
        # 예외 상황 메시지 응답
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
    # Kiwi 한 번만 초기화
    kiwi = get_kiwi()
    for word in include_words:
        kiwi.add_user_word(word, 'NNP', score=10)

    # 단일 str → list
    if isinstance(columns, str):
        columns = [columns]

    # 각 열을 순회
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
        send_message(pid, f"[{col}] 토큰화 완료")

    return data

def measure_hate(
    option: HateOption,
    data: pd.DataFrame,
    text_col: str | None = "Text",
    update_interval: int = 1_000,
    batch_size: int = 32,
) -> pd.DataFrame:
    """
    option.option_num
      1 → clean 제외 레이블 중 최대값 → Hate 열
      2 → 10개 레이블 모두         → 레이블명별 열
      3 → clean 확률               → Clean 열
    """

    def batch_scores(texts: list[str]) -> list[dict[str, float]]:
        """문장 리스트 → [{label: prob}, ...] (둘째 자리 반올림)"""
        pipe, _ = get_hate_model()
        outs = pipe(
            texts,
            truncation=True,
            batch_size=batch_size,
        )
        return [
            {o["label"]: round(o["score"], 2) for o in each}
            for each in outs
        ]


    pid, mode = option.pid, option.option_num

    # 대상 열 탐색 
    if text_col not in data.columns:
        for c in data.columns:
            if "text" in c.lower():
                text_col = c
                send_message(pid, f"🔍 '{text_col}' 열 자동 선택")
                break
        else:
            raise ValueError("'Text'라는 글자를 포함한 열을 찾을 수 없습니다")

    texts = data[text_col].fillna("").astype(str).tolist()
    total = len(texts)
    pipe, _ = get_hate_model()
    labels = list(pipe.model.config.id2label.values())
    
    send_message(pid, f"[혐오도 분석] '{text_col}' 처리 시작 (총 {total:,} rows)")

    # 결과 버퍼 
    if mode == 1:
        results = [0.0] * total
    elif mode == 2:
        # dict 대신 numpy array를 쓰는 것도 성능 향상에 좋음
        results = {lbl: [0.0] * total for lbl in labels}
    elif mode == 3:
        results = [0.0] * total
    else:
        raise ValueError("option_num must be 1, 2, 또는 3 이어야 합니다")

    # 미리 비어있지 않은 인덱스 필터링 
    non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
    non_empty_texts = [texts[i].strip() for i in non_empty_indices]
    total_non_empty = len(non_empty_indices)

    # 배치 추론 
    for batch_start in range(0, total_non_empty, batch_size):
        batch_end = min(batch_start + batch_size, total_non_empty)
        batch_idx = non_empty_indices[batch_start:batch_end]
        batch_txt = non_empty_texts[batch_start:batch_end]

        # 모델 한 번 호출
        scored = batch_scores(batch_txt)

        # 결과 채우기
        if mode == 1:
            for idx, sc in zip(batch_idx, scored):
                results[idx] = max(v for k, v in sc.items() if k != "clean")
        elif mode == 2:
            for idx, sc in zip(batch_idx, scored):
                for lbl in labels:
                    results[lbl][idx] = sc.get(lbl, 0.0)
        else:  # mode == 3
            for idx, sc in zip(batch_idx, scored):
                results[idx] = sc.get("clean", 0.0)

        if (batch_end % update_interval == 0) or (batch_end == total_non_empty):
            pct = round(batch_end / total_non_empty * 100, 2)
            send_message(pid, f"[혐오도 분석] {pct}% 완료 ({batch_end:,}/{total_non_empty:,})")

    # 결과 열 붙이기
    if mode == 1:
        data["Hate"] = results
    elif mode == 2:
        for lbl, vals in results.items():
            data[lbl] = vals
    else:
        data["Clean"] = results

    send_message(pid, "[혐오도 분석] 완료")
    unload_hate_model()
    return data

def extract_keywords(
    pid: str,
    data: pd.DataFrame,
    text_col: str = "Text",
    top_n: int = 5,
    update_interval: int = 1_000,
) -> pd.DataFrame:
    """
    ▸ pid         : 진행 상황 메시지 전송용 ID
    ▸ data        : 원본 DataFrame
    ▸ text_col    : 키워드 추출 대상 컬럼
    ▸ top_n       : 추출할 키워드 개수
    ▸ 명사만 추출하여 후보어로 사용
    """

    import re

    def split_sentences(text, max_len=512):
        # 간단한 문장 단위 split (정제 필요시 더 정교하게 가능)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) < max_len:
                current += " " + sent
            else:
                chunks.append(current.strip())
                current = sent
        if current:
            chunks.append(current.strip())
        return chunks

    # 대상 열 탐색 
    if text_col not in data.columns:
        matches = [c for c in data.columns if "text" in c.lower()]
        if not matches:
            raise ValueError("'Text'라는 글자를 포함한 열을 찾을 수 없습니다")
        text_col = matches[0]
        send_message(pid, f"'{text_col}' 열 자동 선택")

    texts = data[text_col].fillna("").astype(str).tolist()
    total = len(texts)

    send_message(pid, f"[토픽 분석] '{text_col}' 처리 시작 (총 {total:,} rows)")

    # Kiwi 초기화
    kiwi = get_kiwi()

    keywords_col = [""] * total

    # 루프 시작 
    for idx, text in enumerate(texts, 1):
        cleaned = text.strip()
        if cleaned:
            try:
                # 긴 텍스트 문장 단위로 분할
                chunks = split_sentences(cleaned, max_len=500)

                all_keywords = []
                for chunk in chunks:
                    tokens = kiwi.tokenize(chunk, split_complex=False)
                    noun_candidates = [t.form for t in tokens if t.tag in ("NNG", "NNP")]

                    # 후보어 너무 많으면 자르기
                    noun_candidates = noun_candidates[:500]

                    if noun_candidates:
                        _, topic_model = get_hate_model()
                        kw = topic_model.extract_keywords(
                            chunk,
                            candidates=noun_candidates,
                            keyphrase_ngram_range=(1, 2),
                            stop_words=None,
                            top_n=top_n,
                            use_mmr=True,
                            diversity=0.7
                        )
                        all_keywords.extend([k[0] for k in kw])

                keywords_col[idx - 1] = ", ".join(list(dict.fromkeys(all_keywords)))  # 중복 제거
            except Exception as e:
                print(f"키워드 추출 오류 ({idx}):", e)
                keywords_col[idx - 1] = ""

        # 진행률 출력
        if idx % update_interval == 0 or idx == total:
            pct = round(idx / total * 100, 2)
            send_message(pid, f"[토픽 분석] {pct}% 완료 ({idx:,}/{total:,})")

    # 결과 열 추가
    data["Keywords"] = keywords_col
    send_message(pid, "[토픽 분석] 완료")
    unload_hate_model()
    return data

