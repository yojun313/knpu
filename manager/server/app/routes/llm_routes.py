from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
import httpx
from app.libs.jwt import verify_token 

router = APIRouter()

LLM_BASE_URL = "http://localhost:9000"  

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

    async with httpx.AsyncClient(timeout=None) as client:
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

@router.post("/v1/{path:path}/stream")
async def proxy_llm_stream(
    path: str,
    request: Request,
    userUid=Depends(verify_token),
):
    url = f"{LLM_BASE_URL}/v1/{path}"

    headers = dict(request.headers)
    headers.pop("host", None)
    body = await request.body()

    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                content=body,
                params=request.query_params,
            ) as resp:
                async for chunk in resp.aiter_raw():
                    yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
