from fastapi import APIRouter
from .user_routes import router as user_router
from .crawl_routes import router as crawl_router
from .board_routes import router as board_router

api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(crawl_router, prefix="/crawls", tags=["Crawls"])
api_router.include_router(board_router, prefix="/board", tags=["Board"])