"""응답자 접속 코드 · 배포 링크 토큰.

접속 코드는 익명 응답자를 재접속·이어쓰기 가능하게 식별하는 유일한 수단이다
(PLAN.md 7절). 평문은 생성 시 한 번만 반환하고 저장하지 않는다 — respondents_db
에는 해시만 남아서, DB가 유출돼도 코드와 응답자를 다시 연결할 수 없다.
"""

import hashlib
import secrets
import string

# 헷갈리기 쉬운 문자(0/O, 1/I/L)를 뺀 32자 알파벳. "XXX-XXX" 형식 6자리면
# 32^6 ≈ 10억 조합 — 오프라인으로 배부하는 코드로는 충분한 엔트로피다.
_ALPHABET = "".join(
    c for c in (string.ascii_uppercase + string.digits) if c not in "0O1IL"
)


def generate_code() -> str:
    chars = [secrets.choice(_ALPHABET) for _ in range(6)]
    return "".join(chars[:3]) + "-" + "".join(chars[3:])


def hash_code(code: str) -> str:
    normalized = code.strip().upper().replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_access_token() -> str:
    """온라인/실시간 collection의 공개 배포 링크(/r/{token})용 — 추측 불가능해야
    하므로 코드보다 훨씬 긴 URL-safe 토큰(192비트)을 쓴다."""
    return secrets.token_urlsafe(24)
