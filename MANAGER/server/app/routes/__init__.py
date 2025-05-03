from fastapi import APIRouter
from .user_routes import router as user_router
from .crawl_routes import router as crawl_router
from .board_routes import router as board_router
from .auth_routes import router as auth_router
from .ping_routes import router as ping_router

api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(crawl_router, prefix="/crawls", tags=["Crawls"])
api_router.include_router(board_router, prefix="/board", tags=["Board"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(ping_router, prefix="/ping", tags=["Ping"])