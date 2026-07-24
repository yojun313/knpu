from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import api_router
from app.routes.frontend_routes import router as frontend_router

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

PUBLIC_DIR = Path(__file__).resolve().parent / "public"
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")
