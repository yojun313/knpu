import time
import uuid

STAGE_TTL_SECONDS = 3600

_staged: dict[str, dict] = {}


def stage(uid: str, content: bytes, filename: str) -> str:
    return _put(uid, filename, kind="content", content=content)


def stage_ref(uid: str, ref: dict, filename: str) -> str:
    """파일 내용 대신 '어디서 읽으면 되는지'만 올려 둔다.

    크롤링 DB 선택처럼 원본이 이미 서버 디스크에 있는 경우, 수 GB를 메모리로
    복사할 이유가 없다. 실제 읽기는 작업 워커가 한다.
    """
    return _put(uid, filename, kind="ref", ref=dict(ref))


def pop(uid: str, stage_id: str) -> tuple[bytes, str]:
    entry = pop_any(uid, stage_id)
    if entry["kind"] != "content":
        raise ValueError("업로드한 파일이 아닙니다.")
    return entry["content"], entry["filename"]


def pop_any(uid: str, stage_id: str) -> dict:
    """올려 둔 항목을 꺼낸다. kind 가 'content'면 content, 'ref'면 ref 를 쓴다."""
    entry = _staged.pop(stage_id, None)
    if not entry or entry["uid"] != uid:
        raise ValueError("업로드한 파일을 찾을 수 없습니다. 다시 업로드해주세요.")
    return entry


def _put(uid: str, filename: str, **extra) -> str:
    _cleanup_expired()
    stage_id = uuid.uuid4().hex
    _staged[stage_id] = {
        "uid": uid,
        "filename": filename,
        "ts": time.time(),
        "content": None,
        "ref": None,
        **extra,
    }
    return stage_id


def _cleanup_expired():
    now = time.time()
    for k in [k for k, v in _staged.items() if now - v["ts"] > STAGE_TTL_SECONDS]:
        _staged.pop(k, None)
