from fastapi import APIRouter
from fastapi import Depends
from .crawl_routes import router as crawl_router
from app.libs.jwt import verify_token

api_router = APIRouter()
api_router.include_router(crawl_router, prefix="/crawls", tags=["Crawls"], dependencies=[Depends(verify_token)])
