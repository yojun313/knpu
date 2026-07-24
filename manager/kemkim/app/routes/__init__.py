from fastapi import APIRouter
from .auth_routes import router as auth_router
from .project_routes import router as project_router

api_router = APIRouter()
api_router.include_router(auth_router, tags=["Auth"])
api_router.include_router(project_router, tags=["Projects"])
