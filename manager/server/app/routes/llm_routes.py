"""MANAGER 데스크톱 앱용 LLM 프록시.

- /v1/openai/chat/completions : OpenAI 공식 API로 전달(서버 키 사용)
- /v1/{path}/stream           : 로컬 vLLM으로 스트리밍 전달
- /v1/{path}                  : 로컬 vLLM으로 그대로 전달

로컬 vLLM(기본 localhost:9001)은 GPU 서버로 가는 SSH 포트 포워딩이다. GPU 서버의
모델이 내려가 있으면 터널은 연결을 받자마자 끊어 httpx가 ReadError를 낸다. 이때
예전에는 500 트레이스백만 남았는데, 이제는 폴백 엔드포인트(기본 localhost:9000)로
한 번 더 시도하고, 그래도 안 되면 원인을 적은 502 JSON을 돌려준다.
"""

import json
import logging
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_PROXY_UPSTREAM", "http://localhost:9001").rstrip("/")
# 주 엔드포인트에 연결조차 안 될 때만 쓰는 폴백(빈 값이면 폴백 없음)
LLM_FALLBACK_URL = os.getenv("LLM_PROXY_FALLBACK", "http://localhost:9000").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# 요청/응답에서 그대로 넘기면 안 되는 홉 단위 헤더. httpx가 본문을 이미 풀어서
# 주므로 content-encoding/length 를 그대로 돌려주면 클라이언트가 본문을 깨뜨린다.
_HOP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-authenticate",
    "accept-encoding",
    "content-encoding",
}
_CONN_ERRORS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.ConnectTimeout,
)
_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)


def _req_headers(request: Request) -> dict:
    return {k: v for k, v in request.headers.items() if k.lower() not in _HOP}


def _resp_headers(resp: httpx.Response) -> dict:
    return {k: v for k, v in resp.headers.items() if k.lower() not in _HOP}


def _bad_gateway(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": {"message": detail, "type": "upstream_unavailable"}},
    )


async def _served_model(
    client: httpx.AsyncClient, base: str, headers: dict
) -> str | None:
    """폴백 서버가 실제로 올리고 있는 모델 이름(요청의 model을 바꿔 끼우기 위해)."""
    try:
        r = await client.get(f"{base}/v1/models", headers=headers, timeout=10.0)
        data = r.json().get("data") or []
        return data[0].get("id") if data else None
    except Exception:
        return None


async def _fallback_body(client, headers, body: bytes) -> bytes:
    """폴백 서버는 다른 모델을 올리고 있으므로 요청 본문의 model을 바꿔 준다."""
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        return body
    if isinstance(payload, dict) and "model" in payload:
        model = await _served_model(client, LLM_FALLBACK_URL, headers)
        if model:
            payload["model"] = model
            return json.dumps(payload).encode()
    return body


@router.post("/v1/openai/chat/completions")
async def proxy_openai_chat(request: Request):
    body = await request.json()
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0)
        ) as client:
            resp = await client.post(OPENAI_CHAT_URL, headers=headers, json=body)
    except httpx.HTTPError as e:
        logger.warning("OpenAI 프록시 실패: %r", e)
        return _bad_gateway(f"OpenAI API에 연결하지 못했습니다: {type(e).__name__}")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_resp_headers(resp),
        media_type=resp.headers.get("content-type"),
    )


# 스트리밍 경로는 아래의 일반 /v1/{path} 보다 먼저 등록해야 한다(예전에는 순서가
# 반대라 /stream 요청이 일반 경로로 빠져 스트리밍이 동작하지 않았다).
@router.post("/v1/{path:path}/stream")
async def proxy_llm_stream(path: str, request: Request):
    headers = _req_headers(request)
    body = await request.body()
    client = httpx.AsyncClient(timeout=_TIMEOUT)

    async def open_stream():
        last = None
        for base in [LLM_BASE_URL] + ([LLM_FALLBACK_URL] if LLM_FALLBACK_URL else []):
            content = (
                body
                if base == LLM_BASE_URL
                else await _fallback_body(client, headers, body)
            )
            req = client.build_request(
                "POST",
                f"{base}/v1/{path}",
                headers=headers,
                content=content,
                params=request.query_params,
            )
            try:
                return await client.send(req, stream=True)
            except _CONN_ERRORS as e:
                logger.warning("LLM 스트림 연결 실패(%s): %r", base, e)
                last = e
        raise last

    try:
        resp = await open_stream()
    except _CONN_ERRORS as e:
        await client.aclose()
        return _bad_gateway(
            f"로컬 LLM 서버에 연결하지 못했습니다({type(e).__name__}). GPU 서버의 모델이 실행 중인지 확인하세요."
        )

    async def event_stream():
        try:
            async for chunk in resp.aiter_raw():
                yield chunk
        except httpx.HTTPError as e:
            logger.warning("LLM 스트림 중단: %r", e)
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        event_stream(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/event-stream"),
    )


@router.api_route(
    "/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
async def proxy_llm(path: str, request: Request):
    headers = _req_headers(request)
    body = await request.body()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        last = None
        for base in [LLM_BASE_URL] + ([LLM_FALLBACK_URL] if LLM_FALLBACK_URL else []):
            content = (
                body
                if base == LLM_BASE_URL
                else await _fallback_body(client, headers, body)
            )
            try:
                resp = await client.request(
                    method=request.method,
                    url=f"{base}/v1/{path}",
                    headers=headers,
                    content=content,
                    params=request.query_params,
                )
            except _CONN_ERRORS as e:
                logger.warning("LLM 프록시 연결 실패(%s): %r", base, e)
                last = e
                continue
            except httpx.TimeoutException as e:
                return _bad_gateway(
                    f"로컬 LLM 응답 시간이 초과되었습니다({type(e).__name__})."
                )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=_resp_headers(resp),
                media_type=resp.headers.get("content-type"),
            )
    return _bad_gateway(
        f"로컬 LLM 서버에 연결하지 못했습니다({type(last).__name__}). GPU 서버의 모델이 실행 중인지 확인하세요."
    )
