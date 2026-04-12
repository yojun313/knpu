from fastapi import APIRouter
from app.services.registry import CrawlerRegistry
from app.services.persistence import JobPersistence
from app.services.queue_service import QueueManager
from app.routes.job_routes import router as job_router, set_queue_manager as set_job_qm
from app.routes.ws_routes import router as ws_router, set_queue_manager as set_ws_qm
from app.routes.proxy_routes import router as proxy_router
from config import MAX_CONCURRENT_JOBS

# ── 서비스 초기화 ────────────────────────────────────────────────────
registry = CrawlerRegistry(max_concurrent=MAX_CONCURRENT_JOBS)
persistence = JobPersistence()
queue_manager = QueueManager(registry, persistence)

# 라우터에 queue_manager 주입
set_job_qm(queue_manager)
set_ws_qm(queue_manager)

# ── 라우터 조립 ──────────────────────────────────────────────────────
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

# Job 관리 API
api_router.include_router(job_router, tags=["Jobs"])

# WebSocket (prefix 없이 — /ws/dashboard)
api_router.include_router(ws_router, tags=["WebSocket"])

# 프록시 관리 API
api_router.include_router(proxy_router, tags=["Proxy"])
