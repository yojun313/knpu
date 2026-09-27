"""사건(case) 저장소 — storage/cases/<id>.json.

사건 id는 추측할 수 없는 난수(128비트)이고, 그 id를 가진 브라우저만 사건에
접근한다. 개인정보(당사자 인적사항)가 들어가므로 보존 기간이 지나면 사건 파일과
생성된 문서를 함께 지운다(COMPLAINT_RETENTION_HOURS, 기본 72시간).
"""

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

STORAGE = Path(__file__).resolve().parent.parent / "storage"
CASES_DIR = STORAGE / "cases"
DOCS_DIR = STORAGE / "docs"
CASES_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

RETENTION_SEC = float(os.getenv("COMPLAINT_RETENTION_HOURS", "72")) * 3600
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_lock = threading.RLock()


def new_id() -> str:
    return secrets.token_urlsafe(16)


def valid_id(case_id: str) -> bool:
    return bool(case_id and _ID_RE.match(case_id))


def _path(case_id: str) -> Path:
    if not valid_id(case_id):
        raise KeyError(case_id)
    return CASES_DIR / f"{case_id}.json"


def create(mode: str) -> dict:
    now = time.time()
    case = {
        "id": new_id(),
        "mode": mode,  # chat | form
        "created": now,
        "updated": now,
        "crime_type": None,
        "facts": {},
        "messages": [],  # [{role, content, ts}]
        "party": {},  # 고소인·피고소인·제출 정보 (문서 생성 시에만 채워짐)
        "analysis": None,
        "draft": None,
        "review": None,
        "files": None,
    }
    save(case)
    return case


def load(case_id: str) -> dict | None:
    try:
        path = _path(case_id)
    except KeyError:
        return None
    with _lock:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def save(case: dict) -> None:
    case["updated"] = time.time()
    path = _path(case["id"])
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)


def delete(case_id: str) -> None:
    case = load(case_id)
    with _lock:
        if case and case.get("files"):
            token = case["files"].get("token")
            for ext in ("docx", "pdf"):
                (DOCS_DIR / f"{token}.{ext}").unlink(missing_ok=True)
        try:
            _path(case_id).unlink(missing_ok=True)
        except KeyError:
            pass


def purge_expired() -> int:
    """보존 기간이 지난 사건과 문서를 지운다. 지운 파일 수를 돌려준다."""
    cutoff = time.time() - RETENTION_SEC
    removed = 0
    for d in (CASES_DIR, DOCS_DIR):
        for f in d.iterdir():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    return removed
