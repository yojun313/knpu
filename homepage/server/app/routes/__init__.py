from fastapi import APIRouter
from .paper_routes import router as paper_router
from .edit_routes import router as edit_router
from .member_routes import router as member_router
from .news_routes import router as news_router
from .paper_routes import router as paper_router
from .image_routes import router as image_router
from fastapi import Depends
from app.libs.jwt import verify_token

api_router = APIRouter()
api_router.include_router(paper_router, prefix="/papers", tags=["papers"])
api_router.include_router(member_router, prefix="/members", tags=["members"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(paper_router, prefix="/papers", tags=["papers"])
api_router.include_router(image_router, prefix="/image", tags=["image"], dependencies=[Depends(verify_token)])
api_router.include_router(edit_router, prefix="/edit", tags=["edit"], dependencies=[Depends(verify_token)])
