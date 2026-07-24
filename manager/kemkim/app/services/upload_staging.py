# app/services/upload_staging.py
"""
업로드 진행률을 보여주기 위해 파일 전송과 '프로젝트 만들기(이름 확정/분석 시작)'를
두 단계로 나눈다. 1단계에서 올라온 바이트를 잠깐 들고 있다가, 2단계에서 이름/옵션과
함께 실제 처리로 넘긴다. 오래 방치된 항목은 주기적으로 정리한다.
"""
import time
import uuid

STAGE_TTL_SECONDS = 3600  # 1시간 넘게 방치되면 정리

_staged: dict[str, dict] = {}


def stage(uid: str, content: bytes, filename: str) -> str:
    _cleanup_expired()
    stage_id = uuid.uuid4().hex
    _staged[stage_id] = {
        "uid": uid,
        "content": content,
        "filename": filename,
        "ts": time.time(),
    }
    return stage_id


def pop(uid: str, stage_id: str) -> tuple[bytes, str]:
    entry = _staged.pop(stage_id, None)
    if not entry or entry["uid"] != uid:
        raise ValueError("업로드한 파일을 찾을 수 없습니다. 다시 업로드해주세요.")
    return entry["content"], entry["filename"]


def _cleanup_expired():
    now = time.time()
    for k in [k for k, v in _staged.items() if now - v["ts"] > STAGE_TTL_SECONDS]:
        _staged.pop(k, None)
