from fastapi import APIRouter
from app.services.registry import CrawlerRegistry
from app.services.persistence import JobPersistence
from app.services.queue_service import QueueManager
from app.routes.job_routes import router as job_router, set_queue_manager as set_job_qm
from app.routes.ws_routes import router as ws_router, set_queue_manager as set_ws_qm
from app.routes.proxy_routes import router as proxy_router
from app.routes.db_routes import router as db_router
from config import MAX_CONCURRENT_JOBS

registry = CrawlerRegistry(max_concurrent=MAX_CONCURRENT_JOBS)
persistence = JobPersistence()
queue_manager = QueueManager(registry, persistence)

set_job_qm(queue_manager)
set_ws_qm(queue_manager)

api_router = APIRouter()


# Health check
@api_router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "crawler-execution-server",
        "active_jobs": registry.active_count(),
        "queued_jobs": len(queue_manager.queue),
        "max_concurrent": registry.max_concurrent,
    }


api_router.include_router(job_router, tags=["Jobs"])
api_router.include_router(ws_router, tags=["WebSocket"])
api_router.include_router(proxy_router, tags=["Proxy"])
api_router.include_router(db_router, tags=["Database"])
