from fastapi import APIRouter
from .analysis_routes import router as analysis_router
from .whisper_routes import router as whisper_router

api_router = APIRouter()
api_router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(whisper_router, prefix="/whisper", tags=["Whisper"])