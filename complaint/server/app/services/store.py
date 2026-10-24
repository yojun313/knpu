"""사건(case) 저장소 — storage/cases/<id>.enc, storage/docs/<token>.<ext>.enc.

사건마다 256비트 키를 새로 만들어 브라우저에 한 번만 돌려주고, 서버에는 키를 남기지
않는다. 사건 내용과 생성된 문서는 그 키로 AES-256-GCM 암호화해 저장하므로, 키를
메모리에만 들고 있는 브라우저 탭이 닫히면 서버에 남은 파일도 다시 열 수 없다.
마지막 활동 후 보존 시간(COMPLAINT_RETENTION_HOURS, 기본 3시간)이 지나면 지운다.
"""

import base64
import binascii
import json
import os
import re
import secrets
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

STORAGE = Path(__file__).resolve().parent.parent / "storage"
CASES_DIR = STORAGE / "cases"
DOCS_DIR = STORAGE / "docs"
for _d in (STORAGE, CASES_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
    os.chmod(_d, 0o700)

RETENTION_SEC = float(os.getenv("COMPLAINT_RETENTION_HOURS", "3")) * 3600
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_NONCE = 12
_lock = threading.RLock()

# 평문이 디스크에 닿아야 하는 작업(LibreOffice 변환)은 가능하면 메모리 파일시스템에서 한다
_SCRATCH = (
    "/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None
)


def new_id() -> str:
    return secrets.token_urlsafe(16)


def new_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encode_key(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).rstrip(b"=").decode()


def decode_key(value: str | None) -> bytes | None:
    if not value or len(value) > 64:
        return None
    try:
        key = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None
    return key if len(key) == 32 else None


def valid_id(case_id: str) -> bool:
    return bool(case_id and _ID_RE.match(case_id))


def _path(case_id: str) -> Path:
    if not valid_id(case_id):
        raise KeyError(case_id)
    return CASES_DIR / f"{case_id}.enc"


def _doc_path(token: str, ext: str) -> Path:
    if not valid_id(token) or ext not in ("docx", "pdf"):
        raise KeyError(token)
    return DOCS_DIR / f"{token}.{ext}.enc"


def _seal(key: bytes, data: bytes, aad: bytes) -> bytes:
    nonce = secrets.token_bytes(_NONCE)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def _open(key: bytes, blob: bytes, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(blob[:_NONCE], blob[_NONCE:], aad)


def _write(path: Path, blob: bytes) -> None:
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def create(mode: str) -> tuple[dict, bytes]:
    """새 사건과 그 키를 돌려준다. 키는 호출자가 브라우저에 한 번만 전달한다."""
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
    key = new_key()
    save(case, key)
    return case, key


def load(case_id: str, key: bytes | None) -> dict | None:
    """키가 맞지 않거나 사건이 없으면 None — 두 경우를 구분하지 않는다."""
    if not key:
        return None
    try:
        path = _path(case_id)
    except KeyError:
        return None
    with _lock:
        try:
            blob = path.read_bytes()
        except OSError:
            return None
    try:
        return json.loads(_open(key, blob, case_id.encode()))
    except (InvalidTag, ValueError):
        return None


def save(case: dict, key: bytes) -> None:
    case["updated"] = time.time()
    data = json.dumps(case, ensure_ascii=False).encode()
    path = _path(case["id"])
    with _lock:
        _write(path, _seal(key, data, case["id"].encode()))
        # 문서도 사건과 함께 마지막 활동 시각 기준으로 보존한다
        token = (case.get("files") or {}).get("token")
        for ext in ("docx", "pdf") if token else ():
            try:
                os.utime(_doc_path(token, ext))
            except (KeyError, OSError):
                pass


def write_doc(token: str, ext: str, data: bytes, key: bytes) -> None:
    with _lock:
        _write(_doc_path(token, ext), _seal(key, data, f"{token}.{ext}".encode()))


def read_doc(token: str, ext: str, key: bytes) -> bytes | None:
    try:
        path = _doc_path(token, ext)
        blob = path.read_bytes()
        return _open(key, blob, f"{token}.{ext}".encode())
    except (KeyError, OSError, InvalidTag):
        return None


def delete_docs(token: str | None) -> None:
    if not token:
        return
    for ext in ("docx", "pdf"):
        try:
            _doc_path(token, ext).unlink(missing_ok=True)
        except KeyError:
            pass


def delete(case_id: str, key: bytes | None) -> bool:
    """키가 맞는 사건만 지운다(남의 사건 id만으로는 지울 수 없다)."""
    case = load(case_id, key)
    if not case:
        return False
    with _lock:
        delete_docs((case.get("files") or {}).get("token"))
        _path(case_id).unlink(missing_ok=True)
    return True


@contextmanager
def scratch_dir():
    """평문 파일을 잠깐 다뤄야 할 때 쓰는 임시 폴더. 끝나면 통째로 지운다."""
    with tempfile.TemporaryDirectory(prefix="complaint-", dir=_SCRATCH) as d:
        os.chmod(d, 0o700)
        yield Path(d)


def purge_expired() -> int:
    """마지막 활동 후 보존 시간이 지난 사건·문서(이전 형식의 평문 파일 포함)를 지운다."""
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
