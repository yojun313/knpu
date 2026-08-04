import time
import uuid

STAGE_TTL_SECONDS = 3600

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
