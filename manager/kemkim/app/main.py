# app/main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.routes import api_router
from app.auth.middleware import AuthMiddleware

app = FastAPI(title="KNPU KemKim Analyzer")

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCacheStaticFiles(StaticFiles):
    """개발 중 자산(js/css)이 자주 바뀌므로 브라우저가 캐시된 옛 버전을 계속 쓰는 일이
    없도록 캐시를 끈다. 정적 파일이 몇 개 안 되는 내부 도구라 성능 영향은 무시할 만하다."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-store, must-revalidate"))
                message = {**message, "headers": headers}
            await send(message)

        await super().__call__(scope, receive, send_wrapper)


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/js", NoCacheStaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js")
app.mount("/css", NoCacheStaticFiles(directory=os.path.join(STATIC_DIR, "css")), name="css")

app.include_router(api_router)

print("KemKim viewer server is running...")
