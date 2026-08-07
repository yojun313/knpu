from fastapi import APIRouter
from .user_routes import router as user_router
from .board_routes import router as board_router
from .analysis_routes import router as analysis_router
from .ping_routes import router as ping_router
from .format_routes import router as format_router
from .llm_routes import router as llm_router
from .download_routes import router as download_router


api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(board_router, prefix="/board", tags=["Board"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(llm_router, prefix="/llm", tags=["LLM"])
api_router.include_router(format_router, prefix="/format", tags=["Format"])
api_router.include_router(ping_router, prefix="/ping", tags=["Ping"])
api_router.include_router(download_router, prefix="/download", tags=["Download"])
