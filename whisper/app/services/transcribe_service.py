import json
import os
import threading
import traceback
from datetime import datetime

import httpx

from app.config import DATA_PATH, GPU_SERVER_URL
from app.db import notes_db

# GPU는 한 번에 하나의 전사만 처리하게 직렬화한다 (여러 개를 동시에 밀어넣으면
# VRAM을 나눠 쓰며 서로 느려질 뿐이다). 초과분은 이 락 앞에서 "대기 중"으로 줄을 선다.
_gpu_lock = threading.Semaphore(1)


def audio_path(doc: dict) -> str:
    return os.path.join(DATA_PATH, f"{doc['uid']}{doc['ext']}")


def _update(uid: str, fields: dict):
    notes_db.update_one({"uid": uid}, {"$set": fields})


def _format_paragraphs(segments, max_len=120):
    # manager/gpu analysis_service.transcribe_audio의 문단 구성 규칙과 동일
    paragraphs = []
    buf = ""
    for seg in segments:
        text = (seg.get("text") or "").strip()
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


def _run(uid: str):
    doc = notes_db.find_one({"uid": uid})
    if not doc:
        return

    path = audio_path(doc)
    if not os.path.isfile(path):
        _update(
            uid,
            {
                "status": "error",
                "stage": "오류",
                "error": "업로드된 파일을 찾을 수 없습니다",
            },
        )
        return

    _update(uid, {"status": "queued", "stage": "변환 대기 중", "progress": 0})

    with _gpu_lock:
        try:
            _update(uid, {"status": "processing", "stage": "음성 인식 서버에 연결 중"})

            option = {
                "language": doc.get("language", "ko"),
                "model": doc.get("model", 2),
            }
            duration = 0.0
            seg_count = 0

            with open(path, "rb") as f:
                with httpx.stream(
                    "POST",
                    f"{GPU_SERVER_URL}/analysis/whisper/stream",
                    data={"option": json.dumps(option)},
                    files={
                        "file": (doc.get("origFilename") or f"audio{doc['ext']}", f)
                    },
                    timeout=httpx.Timeout(None, connect=30),
                ) as res:
                    res.raise_for_status()
                    for line in res.iter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        etype = event.get("type")

                        if etype == "status":
                            _update(uid, {"stage": event.get("message") or "처리 중"})

                        elif etype == "info":
                            duration = float(event.get("duration") or 0)
                            _update(
                                uid,
                                {
                                    "duration": duration,
                                    "detectedLanguage": event.get("language"),
                                    "stage": "음성 인식 중",
                                },
                            )

                        elif etype == "segment":
                            seg = {
                                "start": event.get("start", 0),
                                "end": event.get("end", 0),
                                "text": event.get("text", ""),
                            }
                            seg_count += 1
                            progress = 0
                            if duration > 0:
                                progress = min(99, round(seg["end"] / duration * 100))
                            notes_db.update_one(
                                {"uid": uid},
                                {
                                    "$push": {"segments": seg},
                                    "$set": {
                                        "progress": progress,
                                        "stage": "음성 인식 중",
                                        "segCount": seg_count,
                                    },
                                },
                            )

                        elif etype == "error":
                            raise RuntimeError(event.get("message") or "GPU 서버 오류")

                        elif etype == "done":
                            break

            final = notes_db.find_one({"uid": uid}, {"segments": 1}) or {}
            segments = final.get("segments", [])
            _update(
                uid,
                {
                    "status": "done",
                    "progress": 100,
                    "stage": "완료",
                    "text": _format_paragraphs(segments),
                    "finishedAt": datetime.now(),
                },
            )

        except Exception as e:
            print(
                f"[WHISPER] transcription failed for {uid}:\n{traceback.format_exc()}"
            )
            msg = str(e) or type(e).__name__
            if isinstance(e, httpx.ConnectError):
                msg = "음성 인식 서버(GPU)에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
            _update(uid, {"status": "error", "stage": "오류", "error": msg[:500]})


def start_transcription(uid: str):
    # 재시도 시 이전 결과가 섞이지 않도록 세그먼트를 비우고 시작한다
    notes_db.update_one(
        {"uid": uid},
        {
            "$set": {
                "status": "queued",
                "stage": "변환 대기 중",
                "progress": 0,
                "segments": [],
                "segCount": 0,
                "error": None,
            }
        },
    )
    threading.Thread(target=_run, args=(uid,), daemon=True).start()


def requeue_interrupted():
    """서버 재시작으로 끊긴 작업을 자동으로 다시 돌린다 (파일이 남아 있으면)."""
    for doc in notes_db.find({"status": {"$in": ["queued", "processing"]}}):
        if os.path.isfile(audio_path(doc)):
            start_transcription(doc["uid"])
        else:
            _update(
                doc["uid"],
                {
                    "status": "error",
                    "stage": "오류",
                    "error": "서버 재시작으로 작업이 중단되었습니다. 파일을 다시 업로드해 주세요.",
                },
            )
