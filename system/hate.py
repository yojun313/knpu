import os
import threading

from dotenv import load_dotenv

load_dotenv()

MODEL_DIR = os.getenv("MODEL_PATH") or "/home/lab/models"
MODEL_NAME = os.getenv("HATE_MODEL_NAME") or "kor_unsmile"
HATE_DEVICE = (os.getenv("HATE_DEVICE") or "auto").strip().lower()

# GPU 서버 구현(manager/gpu)과 같은 기본값. 바꾸면 추론 속도/메모리가 함께 바뀐다.
BATCH_SIZE = int(os.getenv("HATE_BATCH_SIZE") or 64)

# kor-unsmile 이 내는 레이블 10종. statistics 의 HateAnalysis 가 이 이름을 그대로 쓴다.
LABELS = [
    "여성/가족",
    "남성",
    "성소수자",
    "인종/국적",
    "연령",
    "지역",
    "종교",
    "기타 혐오",
    "악플/욕설",
    "clean",
]

_pipe = None
_pipe_lock = threading.Lock()


class HateModelError(RuntimeError):
    """모델을 준비하지 못했을 때(파일 없음·의존성 없음 등)."""


def model_path() -> str:
    return os.path.join(MODEL_DIR, MODEL_NAME)


def is_available() -> bool:
    """로컬에서 바로 측정할 수 있는 상태인지(모델 파일이 있는지)."""
    path = model_path()
    return os.path.isdir(path) and os.path.exists(os.path.join(path, "config.json"))


def resolve_device() -> int:
    """transformers pipeline 의 device 값. 0 이상이면 그 번호의 GPU, -1 이면 CPU.

    HATE_DEVICE=auto  : GPU 가 쓸 수 있으면 GPU, 아니면 CPU
    HATE_DEVICE=cpu   : 항상 CPU
    HATE_DEVICE=cuda  : GPU (못 쓰면 CPU 로 내려감)
    HATE_DEVICE=cuda:1: 특정 GPU 번호
    """
    if HATE_DEVICE == "cpu":
        return -1
    try:
        import torch

        if not torch.cuda.is_available():
            return -1
    except Exception:
        return -1
    if HATE_DEVICE.startswith("cuda:"):
        try:
            return int(HATE_DEVICE.split(":", 1)[1])
        except ValueError:
            return 0
    return 0


def device_label() -> str:
    """로그에 보여 줄 장치 이름."""
    dev = resolve_device()
    if dev < 0:
        return "CPU"
    try:
        import torch

        return f"GPU {dev} ({torch.cuda.get_device_name(dev)})"
    except Exception:
        return f"GPU {dev}"


def load_pipeline():
    global _pipe
    with _pipe_lock:
        if _pipe is not None:
            return _pipe
        if not is_available():
            raise HateModelError(
                f"혐오도 모델을 찾을 수 없습니다: {model_path()}\n"
                "HuggingFace 의 smilegate-ai/kor_unsmile 을 이 경로에 내려받아 주세요."
            )
        try:
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                TextClassificationPipeline,
            )
        except Exception as e:
            raise HateModelError(f"transformers 를 불러오지 못했습니다: {e}") from e

        path = model_path()
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True
        )
        _pipe = TextClassificationPipeline(
            model=model,
            tokenizer=tokenizer,
            function_to_apply="sigmoid",
            top_k=None,
            device=resolve_device(),
        )
        return _pipe


def unload() -> None:
    """모델을 메모리에서 내린다(GPU 메모리 반환)."""
    global _pipe
    with _pipe_lock:
        _pipe = None
    try:
        import gc

        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
    except Exception:
        pass


def measure(
    data,
    text_col: str | None = None,
    log=None,
    batch_size: int | None = None,
    update_interval: int = 1000,
):
    """댓글 텍스트의 혐오도 레이블 점수 10종을 측정해 열로 붙인 DataFrame 을 돌려준다.

    GPU 서버의 measure_hate(option_num=2) 와 같은 결과를 내도록 맞춰 두었다
    (같은 모델·같은 sigmoid·같은 소수점 2자리 반올림).
    """
    say = log or (lambda _text: None)
    batch_size = batch_size or BATCH_SIZE

    if text_col is None or text_col not in data.columns:
        text_col = next((c for c in data.columns if "text" in str(c).lower()), None)
    if text_col is None:
        raise HateModelError(
            "혐오도 측정에는 'Text' 가 들어간 열이 필요합니다 (원본 크롤링 CSV를 사용해 주세요)."
        )

    pipe = load_pipeline()
    labels = list(pipe.model.config.id2label.values())

    texts = data[text_col].fillna("").astype(str).tolist()
    total = len(texts)
    results = {label: [0.0] * total for label in labels}

    # 빈 댓글은 모델에 넣지 않는다(점수 0 으로 남는다)
    targets = [(i, t.strip()) for i, t in enumerate(texts) if t.strip()]
    say(
        f"[혐오도 분석] 로컬 {device_label()} 로 측정 시작 — "
        f"'{text_col}' 열, {len(targets):,}/{total:,}행"
    )

    # 파이프라인을 배치마다 따로 부르면 호출 비용이 매번 붙는다(GPU 가 놀게 된다).
    # 진행률을 보고할 구간만큼 한 번에 넘기고, 그 안에서 batch_size 로 쪼개게 둔다.
    window = max(update_interval, batch_size)
    done = 0
    for start in range(0, len(targets), window):
        chunk = targets[start : start + window]
        scored = pipe(
            [text for _, text in chunk], truncation=True, batch_size=batch_size
        )
        for (idx, _), row in zip(chunk, scored):
            for item in row:
                label = item["label"]
                if label in results:
                    results[label][idx] = round(item["score"], 2)
        done += len(chunk)
        pct = done / len(targets) * 100 if targets else 100
        say(f"[혐오도 분석] {pct:.1f}% 완료 ({done:,}/{len(targets):,})")

    for label, values in results.items():
        data[label] = values
    say("[혐오도 분석] 완료")
    unload()
    return data
