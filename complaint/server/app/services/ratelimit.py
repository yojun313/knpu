"""IP별 간단한 요청 제한 — 공개 서비스라 LLM 호출 남용을 막는다."""

import ipaddress
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# IP는 메모리에만 두고 디스크·로그에 남기지 않는다
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _trusted_proxy(host: str | None) -> bool:
    try:
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else None
    # 전달 헤더는 앞단 프록시(nginx 등)를 거친 요청에서만 믿는다 — 직접 접속이면 위조할 수 있다
    if _trusted_proxy(peer):
        for header in ("cf-connecting-ip", "x-real-ip"):
            v = request.headers.get(header)
            if v:
                return v.strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[-1].strip()
    return peer or "unknown"


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
            detail=f"요청이 너무 많습니다. {retry}초 후에 다시 시도해 주시기 바랍니다.",
            headers={"Retry-After": str(retry)},
        )
    q.append(now)
    if len(_hits) > 20000:  # 메모리 보호
        for k in list(_hits)[:5000]:
            if not _hits[k]:
                del _hits[k]
