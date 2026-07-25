from fastapi import APIRouter
from .project_routes import router as project_router

api_router = APIRouter()
api_router.include_router(project_router, tags=["Projects"])
