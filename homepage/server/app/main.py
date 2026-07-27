import os
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import api_router
from app.routes.frontend_routes import router as frontend_router
from app.routes.files_routes import router as files_router
from app.libs.audit_log import AuditLogMiddleware
from app.libs.discord_notify import notify_discord

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")

app = FastAPI()
app.add_middleware(AuditLogMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)

    filtered_frames = [
        f
        for f in frames
        if "site-packages" not in f.filename and "lib/python" not in f.filename
    ]
    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    print(f"[HOMEPAGE] Exception at {request.url.path}:\n{traceback.format_exc()}")

    notify_discord(
        "system_error",
        f"[HOMEPAGE] {request.method} {request.url.path}\n```py\n{custom_traceback[-1500:]}\n```",
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "path": request.url.path,
        },
    )


app.add_middleware(
    CORSMiddleware,
    # allow_credentials=True와 allow_origins=["*"]는 브라우저가 동시 사용을 거부하므로
    # (쿠키 기반 SSO 로그아웃 등 credentialed 요청을 다른 *.knpu.re.kr 서브도메인에서
    # 받으려면) 정규식으로 knpu.re.kr 서브도메인만 명시적으로 허용한다.
    allow_origin_regex=r"https://([a-z0-9-]+\.)?knpu\.re\.kr",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(frontend_router, tags=["frontend"])
app.include_router(files_router, tags=["manager-files"])

# 위 라우트들과 겹치지 않는 나머지 정적 파일(css/js/assets/manuals 및
# about.html·manager.html처럼 직접 경로로도 접근되던 파일들)은 예전 Express 정적 서빙과
# 동일하게 public/ 디렉토리를 통째로 서빙해 대체한다. 반드시 다른 라우트보다 뒤에 등록해야
# 위의 명시적 라우트(/, /login, /api/* 등)가 우선 매치된다.
app.mount("/", StaticFiles(directory=PUBLIC_DIR), name="public")
