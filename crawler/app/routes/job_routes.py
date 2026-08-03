from fastapi import APIRouter, HTTPException, Depends
from app.models.job_model import (
    JobSubmitRequest,
    QueueConfigUpdate,
    RecrawlRequest,
    ResumeRequest,
)
from app.routes.dependencies import get_current_user, check_owner_or_admin
from app.db import crawler_db, user_logs_db
from system.logging.user_log import insert_log

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
    insert_log(
        user_logs_db,
        user["uid"],
        "crawler.crawl.resume",
        "crawler",
        target={"type": "crawl_db", "id": db_uid, "name": doc.get("name")},
    )
    return {"status": "ok", "job_id": job_id}


@router.post("/jobs/recrawl/{db_uid}")
def recrawl_job(
    db_uid: str,
    req: RecrawlRequest = RecrawlRequest(),
    user=Depends(get_current_user),
):
    doc = crawler_db["db-list"].find_one({"uid": db_uid})
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"크롤링 작업을 찾을 수 없습니다: {db_uid}"
        )
    if doc.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail="진행 중인 작업은 먼저 중단한 뒤 재크롤링해주세요",
        )
    check_owner_or_admin(user, doc)

    try:
        job_id = queue_manager.enqueue_recrawl(db_uid, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    insert_log(
        user_logs_db,
        user["uid"],
        "crawler.crawl.recrawl",
        "crawler",
        message=f"크롤링 재실행(기존 데이터 삭제): {doc.get('name')}",
        target={"type": "crawl_db", "id": db_uid, "name": doc.get("name")},
        metadata={
            "start_date": req.start_date or doc.get("startDate"),
            "end_date": req.end_date or doc.get("endDate"),
        },
    )
    return {"status": "ok", "job_id": job_id}


@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    logs = queue_manager.persistence.get_logs(job_id)
    return {"job_id": job_id, "logs": logs}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str, user=Depends(get_current_user)):
    success = queue_manager.stop_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not running")
    insert_log(
        user_logs_db,
        user["uid"],
        "crawler.crawl.stop",
        "crawler",
        target={"type": "crawl_job", "id": job_id},
    )
    return {"status": "ok", "message": f"Job {job_id} stop signal sent"}


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str, user=Depends(get_current_user)):
    success, removed_from = queue_manager.remove_job(job_id)
    if not success:
        if removed_from == "running":
            raise HTTPException(
                status_code=409, detail=f"Job {job_id} is running; stop first"
            )
    insert_log(
        user_logs_db,
        user["uid"],
        "crawler.crawl.cancel",
        "crawler",
        target={"type": "crawl_job", "id": job_id},
        outcome="success" if success else "failure",
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
