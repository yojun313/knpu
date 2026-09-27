"""IP별 간단한 요청 제한 — 공개 서비스라 LLM 호출 남용을 막는다."""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-real-ip"):
        v = request.headers.get(header)
        if v:
            return v.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request: Request, bucket: str, limit: int, window_sec: float) -> None:
    key = (bucket, client_ip(request))
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_sec:
        q.popleft()
    if len(q) >= limit:
        retry = int(window_sec - (now - q[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"요청이 너무 많습니다. {retry}초 후에 다시 시도해 주세요.",
            headers={"Retry-After": str(retry)},
        )
    q.append(now)
    if len(_hits) > 20000:  # 메모리 보호
        for k in list(_hits)[:5000]:
            if not _hits[k]:
                del _hits[k]
