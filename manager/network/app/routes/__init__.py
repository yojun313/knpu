from fastapi import APIRouter
from .viewer_routes import router as viewer_router

api_router = APIRouter()
api_router.include_router(viewer_router, tags=["Viewer"])
