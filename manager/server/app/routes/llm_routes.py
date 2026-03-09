from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
import httpx
from app.libs.jwt import verify_token 
import os

router = APIRouter()

LLM_BASE_URL = "http://localhost:9001"  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

@router.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
async def proxy_llm(
    path: str,
    request: Request,
    userUid=Depends(verify_token),
):
    url = f"{LLM_BASE_URL}/v1/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client: # 타임아웃을 명시적으로 설정
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type"),
            )
    except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError) as e:
        # 업스트림 서버(vLLM) 에러 발생 시 로그 출력 및 예외 처리
        print(f"Upstream Error (vLLM): {e}")
        raise HTTPException(status_code=502, detail="Upstream server connection failed.")

@router.post("/v1/openai/chat/completions")
async def proxy_openai_chat(
    request: Request,
    userUid=Depends(verify_token),
):
    body = await request.json()
    # 스트리밍 여부 확인
    is_stream = body.get("stream", False)

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    if is_stream:
        async def event_stream():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", OPENAI_CHAT_URL, headers=headers, json=body) as resp:
                    async for chunk in resp.aiter_raw():
                        yield chunk
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.post(OPENAI_CHAT_URL, headers=headers, json=body)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )