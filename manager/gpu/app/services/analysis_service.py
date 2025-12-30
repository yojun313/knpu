import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"
from app.models.analysis_model import *
from app.libs.progress import *
import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import pandas as pd
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TextClassificationPipeline,
    logging
)
logging.set_verbosity_error()
import os
from faster_whisper import WhisperModel
from dotenv import load_dotenv
import gc

load_dotenv() 
MODEL_DIR = os.getenv("MODEL_PATH")

kor_unsmile_pipe = None
_whisper_models = {}

WHISPER_MODEL_MAP = {
    1: {
        "name": "faster-whisper-small",
        "compute": "int8_float16",
    },
    2: {
        "name": "faster-whisper-medium",
        "compute": "int8_float16",
    },
    3: {
        "name": "faster-whisper-large-v3",
        "compute": "float16",
    },
}



whisper_model = WhisperModel(
    os.path.join(MODEL_DIR, "faster-whisper-large-v3"),
    device="cuda",
    compute_type="float16",
    local_files_only=True,
)

def get_hate_model():
    global kor_unsmile_pipe
    
    if kor_unsmile_pipe is None:
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_model = AutoModelForSequenceClassification.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_pipe = TextClassificationPipeline(
            model=kor_unsmile_model,
            tokenizer=tokenizer,
            function_to_apply="sigmoid",
            top_k=None,
            device=1 if torch.cuda.is_available() else -1,
        )

    return kor_unsmile_pipe

def get_whisper_model(level: int):
    if level not in WHISPER_MODEL_MAP:
        level = 2  # 기본값 medium

    cfg = WHISPER_MODEL_MAP[level]

    key = f"{cfg['name']}::{cfg['compute']}"

    if key not in _whisper_models:
        _whisper_models[key] = WhisperModel(
            os.path.join(MODEL_DIR, cfg["name"]),
            device="cuda",
            compute_type=cfg["compute"],
            local_files_only=True,
        )

    return _whisper_models[key]


def unload_hate_model():
    global kor_unsmile_pipe
    kor_unsmile_pipe = None
    torch.cuda.empty_cache()
    gc.collect()

def measure_hate(
    option: HateOption,
    data: pd.DataFrame,
    text_col: str | None = "Text",
    update_interval: int = 1_000,
    batch_size: int = 64,
) -> pd.DataFrame:
    """
    option.option_num
      1 → clean 제외 레이블 중 최대값 → Hate 열
      2 → 10개 레이블 모두         → 레이블명별 열
      3 → clean 확률               → Clean 열
    """

    def batch_scores(texts: list[str]) -> list[dict[str, float]]:
        """문장 리스트 → [{label: prob}, ...] (둘째 자리 반올림)"""
        pipe = get_hate_model()
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
    pipe = get_hate_model()
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

def format_paragraphs(segments, max_len=120):
    paragraphs = []
    buf = ""

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        if len(buf) + len(text) <= max_len:
            buf += " " + text
        else:
            paragraphs.append(buf.strip())
            buf = text

    if buf:
        paragraphs.append(buf.strip())

    return "\n\n".join(paragraphs)


def format_with_timestamps(segments):
    def ts(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for seg in segments:
        line = f"[{ts(seg.start)} - {ts(seg.end)}] {seg.text.strip()}"
        lines.append(line)

    return "\n".join(lines)


def transcribe_audio(
    audio_path: str,
    language: str = "ko",
    model_level: int = 2,
    pid = None,
):
    send_message(pid, f"[음성 인식] {WHISPER_MODEL_MAP[model_level]['name']} 모델 로드 중")
    model = get_whisper_model(model_level)

    send_message(pid, "[음성 인식] Audio -> Text 변환 중")
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1 if model_level < 3 else 5,
        vad_filter=True,
    )

    segments = list(segments)

    text_paragraph = format_paragraphs(segments)
    text_with_time = format_with_timestamps(segments)
    
    send_message(pid, "[음성 인식] 완료")
    return {
        "language": info.language,
        "duration": info.duration,
        "model_level": model_level,
        "text": text_paragraph,
        "text_with_time": text_with_time,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            }
            for seg in segments
        ],
    }
