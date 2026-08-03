from fastapi import APIRouter
from .project_routes import router as project_router
from .analysis_routes import router as analysis_router

api_router = APIRouter()
api_router.include_router(project_router, tags=["Projects"])
api_router.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])
