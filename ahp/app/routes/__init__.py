from fastapi import APIRouter

from .page_routes import router as page_router
from .project_routes import router as project_router
from .survey_routes import router as survey_router
from .collection_routes import router as collection_router
from .entry_routes import router as entry_router
from .respond_routes import router as respond_router
from .ws_routes import router as ws_router
from .result_routes import router as result_router
from .export_routes import router as export_router

api_router = APIRouter()
api_router.include_router(page_router, tags=["Pages"])
api_router.include_router(project_router, tags=["Projects"])
api_router.include_router(survey_router, tags=["Surveys"])
api_router.include_router(collection_router, tags=["Collections"])
api_router.include_router(entry_router, tags=["Entry"])
api_router.include_router(respond_router, tags=["Respond"])
api_router.include_router(ws_router, tags=["WebSocket"])
api_router.include_router(result_router, tags=["Results"])
api_router.include_router(export_router, tags=["Export"])
