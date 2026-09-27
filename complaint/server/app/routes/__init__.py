from fastapi import APIRouter

from .api import router as core_router
from .police_routes import router as police_router

api_router = APIRouter()
api_router.include_router(core_router)
api_router.include_router(police_router, prefix="/police", tags=["police"])
