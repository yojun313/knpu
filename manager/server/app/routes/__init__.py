from fastapi import APIRouter
from .user_routes import router as user_router
from .crawl_routes import router as crawl_router
from .board_routes import router as board_router
from .auth_routes import router as auth_router
from .analysis_routes import router as analysis_router
from .ping_routes import router as ping_router
from .format_routes import router as format_router
from fastapi import Depends
from app.libs.jwt import verify_token


api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["Users"], dependencies=[Depends(verify_token)])
api_router.include_router(crawl_router, prefix="/crawls", tags=["Crawls"], dependencies=[Depends(verify_token)])
api_router.include_router(board_router, prefix="/board", tags=["Board"], dependencies=[Depends(verify_token)])
api_router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"], dependencies=[Depends(verify_token)])
api_router.include_router(format_router, prefix="/format", tags=["Format"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(ping_router, prefix="/ping", tags=["Ping"])