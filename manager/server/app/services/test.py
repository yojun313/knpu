import torch
import numpy as np
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
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_DIR, local_files_only=True)
pipe = TextClassificationPipeline(
    model=model,
    tokenizer=tokenizer,
    function_to_apply="sigmoid",
    top_k=None,                                # 전체 레이블 확률 반환
    device=0 if torch.cuda.is_available() else -1,
)

# clean 제외한 8개 혐오·악플 레이블
hate_labels = [lbl for lbl in model.config.id2label.values() if lbl != "clean"]


def hatefulness(text: str) -> float:
    """
    한국어 문장의 혐오도를 0~1 사이 실수로 반환
    - clean을 제외한 레이블 중 최대 확률
    """
    outputs = pipe(text, truncation=True)[
        0]         # [{'label':…, 'score':…}, …]
    scores = {o["label"]: o["score"] for o in outputs}

    import json

    print(json.dumps(scores, ensure_ascii=False, indent=2))
    hate_prob = max(scores[lbl] for lbl in hate_labels)   # 0.0 ~ 1.0
    return hate_prob


# ===== 예시 =====
if __name__ == "__main__":
    sents = [
        "와 진짜 멋지다!",
        "저 여자들은 운전을 못 해.",
        "늙은이들은 시대착오적이야.",
    ]
    for s in sents:
        print(f"{s:30s} → 혐오도: {hatefulness(s):.2f}")
