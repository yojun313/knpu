# app/main.py
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import api_router
from app.services.graph_store import cleanup_expired_sessions, SESSION_TTL_SECONDS

app = FastAPI(title="KNPU Network Viewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/js", StaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js")
app.mount("/css", StaticFiles(directory=os.path.join(STATIC_DIR, "css")), name="css")

app.include_router(api_router)


async def periodic_cleanup(interval_seconds: int = 3600):
    while True:
        await asyncio.sleep(interval_seconds)
        cleanup_expired_sessions(SESSION_TTL_SECONDS)


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_cleanup())


print("Network viewer server is running...")
