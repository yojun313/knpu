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


def dedupe_label(base: str, existing_labels: set[str]) -> str:
    """같은 수집 회차 안에서 응답자 이름이 겹치면 "이름 (2)"처럼 구분자를 붙여
    유일하게 만든다 — 이름이 같으면 결과 화면·CSV 내보내기에서 서로 다른
    응답자를 구별할 수 없어진다. entry_routes(오프라인)·collection_routes(코드 발급)가 공유."""
    if base not in existing_labels:
        return base
    n = 2
    while f"{base} ({n})" in existing_labels:
        n += 1
    return f"{base} ({n})"


def seq_letters(index: int) -> str:
    """0→A, 1→B, … 25→Z, 26→AA … 스프레드시트식 열 문자. 수집(collection) 순번 표시용."""
    s = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        s = chr(65 + rem) + s
    return s
