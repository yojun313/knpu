from fastapi import APIRouter
from .complaint_routes import router as complaint_router
from .download_routes import router as download_router
from .preview_routes import router as preview_router
from .police_routes import router as police_router

api_router = APIRouter()

api_router.include_router(complaint_router, prefix="/complaint", tags=["complaints"])
api_router.include_router(download_router, prefix="/download", tags=["downloads"])
api_router.include_router(preview_router, prefix="/preview", tags=["previews"])
api_router.include_router(police_router, prefix="/police", tags=["police"])
