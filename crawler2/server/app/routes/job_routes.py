from fastapi import APIRouter, HTTPException
from app.models.job_model import JobSubmitRequest, QueueConfigUpdate

router = APIRouter()

# queue_manager는 main.py에서 주입됨
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
            raise HTTPException(status_code=409, detail=f"Job {job_id} is running; stop first")
    return {"status": "ok", "message": f"Job {job_id} removed ({removed_from})"}


@router.get("/queue/config")
def get_queue_config():
    return {"max_concurrent": queue_manager.registry.max_concurrent}


@router.put("/queue/config")
def update_queue_config(config: QueueConfigUpdate):
    queue_manager.registry.max_concurrent = config.max_concurrent
    queue_manager.registry.executor._max_workers = config.max_concurrent
    return {"status": "ok", "max_concurrent": config.max_concurrent}
