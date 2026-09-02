from fastapi import APIRouter, Depends
from .paper_routes import router as paper_router
from .member_routes import router as member_router
from .news_routes import router as news_router
from .image_routes import router as image_router
from .photo_routes import router as photo_router
from .popup_routes import router as popup_router
from .faq_routes import router as faq_router
from .auth_routes import router as auth_router
from app.auth.dependencies import require_admin

api_router = APIRouter()

api_router.include_router(paper_router, prefix="/papers", tags=["papers"])
api_router.include_router(member_router, prefix="/members", tags=["members"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(photo_router, prefix="/gallery", tags=["gallery"])
api_router.include_router(popup_router, prefix="/popups", tags=["popups"])
api_router.include_router(faq_router, prefix="/faq", tags=["faq"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# 이미지 업로드/삭제는 콘텐츠 편집(논문/멤버/뉴스/갤러리/팝업) 전용이라 관리자만 허용한다.
api_router.include_router(
    image_router,
    prefix="/image",
    tags=["image"],
    dependencies=[Depends(require_admin)],
)
