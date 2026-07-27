from fastapi import APIRouter, HTTPException, Depends
from app.models.job_model import JobSubmitRequest, QueueConfigUpdate, ResumeRequest
from app.routes.dependencies import get_current_user, check_owner_or_admin
from app.db import crawler_db

router = APIRouter()

queue_manager = None


def set_queue_manager(qm):
    global queue_manager
    queue_manager = qm


@router.post("/jobs/submit")
def submit_job(req: JobSubmitRequest):
    job_id = queue_manager.enqueue(req)
    return {"status": "ok", "job_id": job_id}


@router.get("/jobs/list")
def list_jobs():
    return queue_manager.get_all_statuses()


@router.get("/jobs/{job_id}/status")
def get_job_status(job_id: str):
    status = queue_manager.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status


@router.post("/jobs/resume/{db_uid}")
def resume_job(
    db_uid: str,
    req: ResumeRequest = ResumeRequest(),
    user=Depends(get_current_user),
):
    """중단·에러·완료된 크롤링을 같은 파일에 이어서 진행한다.
    완료된 작업은 req.end_date(새 종료일)를 반드시 지정해야 확장해서 이어받을 수 있다.
    관리자 또는 그 크롤링의 요청자만 이어받을 수 있다."""
    doc = crawler_db["db-list"].find_one({"uid": db_uid})
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"크롤링 작업을 찾을 수 없습니다: {db_uid}"
        )
    check_owner_or_admin(user, doc)

    try:
        job_id = queue_manager.enqueue_resume(db_uid, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "job_id": job_id}


@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    logs = queue_manager.persistence.get_logs(job_id)
    return {"job_id": job_id, "logs": logs}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str):
    success = queue_manager.stop_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not running")
    return {"status": "ok", "message": f"Job {job_id} stop signal sent"}


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    success, removed_from = queue_manager.remove_job(job_id)
    if not success:
        if removed_from == "running":
            raise HTTPException(
                status_code=409, detail=f"Job {job_id} is running; stop first"
            )
    return {"status": "ok", "message": f"Job {job_id} removed ({removed_from})"}


@router.get("/queue/config")
def get_queue_config():
    return {"max_concurrent": queue_manager.registry.max_concurrent}


@router.put("/queue/config")
def update_queue_config(config: QueueConfigUpdate):
    queue_manager.registry.max_concurrent = config.max_concurrent
    queue_manager.registry.executor._max_workers = config.max_concurrent
    return {"status": "ok", "max_concurrent": config.max_concurrent}
