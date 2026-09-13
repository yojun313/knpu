from fastapi import APIRouter

from .note_routes import router as note_router

api_router = APIRouter()
api_router.include_router(note_router, tags=["Notes"])
