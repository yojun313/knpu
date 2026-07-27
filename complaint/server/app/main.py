import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import api_router
from app.routes.frontend_routes import router as frontend_router
from app.libs.discord_notify import notify_discord

app = FastAPI()
app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(frontend_router, tags=["frontend"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[COMPLAINT] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[COMPLAINT] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "path": request.url.path},
    )


PUBLIC_DIR = Path(__file__).resolve().parent / "public"
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")
