import asyncio
import os
import re
import time
from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask
import psutil
from app.services.pm2_service import PM2Service
from app.routes.dependencies import get_current_user
from app.libs.jwt import decode_token
from app.services import settings_service
from app.db import homepage_users_col, user_logs_col
from system.auth.session import revalidate_session
from system.logging.user_log import insert_log

router = APIRouter(prefix="/process", tags=["process"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered

_prev_sample = {"ts": None, "net": None, "disk": None}
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    entries = temps.get("coretemp") or temps.get("k10temp") or []
    if not entries:
        return None
    for e in entries:
        if "package" in e.label.lower():
            return round(e.current, 1)
    return round(sum(e.current for e in entries) / len(entries), 1)


def _rate_per_sec(prev_value, cur_value, dt):
    if prev_value is None or dt <= 0:
        return 0
    return max(0, (cur_value - prev_value) / dt)


@router.get("/")
async def pm2_manager_page(request: Request, user=Depends(get_current_user)):
    processes = await asyncio.to_thread(PM2Service.get_processes)
    return templates.TemplateResponse(
        request=request,
        name="process.html",
        context={"processes": processes, "active_page": "process"},
    )


@router.post("/control/restart-all")
async def restart_all_processes(user=Depends(get_current_user)):

    def _run_and_log():
        # 개별 재시작과 동일하게 --update-env 를 붙인다. 이게 없으면 pm2 가 프로세스를
        # 처음 띄울 때 저장해 둔 환경 변수를 그대로 다시 쓰기 때문에, .env 나
        # ecosystem 의 env 를 고치고 전체 재시작해도 반영되지 않는다.
        success = PM2Service.run_command("restart", "all", ["--update-env"])
        insert_log(
            user_logs_col,
            user["sub"],
            "admin.pm2.restart_all",
            "admin",
            message="pm2 restart all --update-env",
            target={"type": "pm2_process", "id": "all"},
            outcome="success" if success else "failure",
        )

    return JSONResponse(
        {"status": "accepted"},
        background=BackgroundTask(_run_and_log),
    )


@router.post("/control/{action}/{name}")
async def control_process(action: str, name: str, user=Depends(get_current_user)):
    if action not in ["restart", "stop", "start", "delete"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    # URL 로 받은 이름이 실제 PM2 프로세스인지 확인 (옵션 주입 · 임의 대상 차단)
    if not name or name.startswith("-") or len(name) > 200:
        raise HTTPException(status_code=400, detail="Invalid process name")
    names = {p.get("name") for p in await asyncio.to_thread(PM2Service.get_processes)}
    if name not in names:
        raise HTTPException(status_code=404, detail="Process not found")

    # 재시작은 --update-env 로 환경 변수 변경을 반영한다 (UnivDash 와 같은 동작)
    extra = ["--update-env"] if action == "restart" else None
    success = await asyncio.to_thread(PM2Service.run_command, action, name, extra)
    insert_log(
        user_logs_col,
        user["sub"],
        f"admin.pm2.{action}",
        "admin",
        message=f"pm2 {action}: {name}",
        target={"type": "pm2_process", "id": name},
        outcome="success" if success else "failure",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Command failed")

    return {"status": "success"}


@router.get("/status")
async def get_pm2_status_api(user=Depends(get_current_user)):
    return await asyncio.to_thread(PM2Service.get_processes)


@router.get("/server-stats")
async def get_server_stats(user=Depends(get_current_user)):
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    du = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()

    now = time.monotonic()
    prev_ts = _prev_sample["ts"]
    dt = (now - prev_ts) if prev_ts else 0

    net_upload_bps = 0
    net_download_bps = 0
    disk_read_bps = 0
    disk_write_bps = 0
    if _prev_sample["net"] is not None:
        net_upload_bps = _rate_per_sec(
            _prev_sample["net"].bytes_sent, net.bytes_sent, dt
        )
        net_download_bps = _rate_per_sec(
            _prev_sample["net"].bytes_recv, net.bytes_recv, dt
        )
    if _prev_sample["disk"] is not None and disk_io is not None:
        disk_read_bps = _rate_per_sec(
            _prev_sample["disk"].read_bytes, disk_io.read_bytes, dt
        )
        disk_write_bps = _rate_per_sec(
            _prev_sample["disk"].write_bytes, disk_io.write_bytes, dt
        )

    _prev_sample["ts"] = now
    _prev_sample["net"] = net
    _prev_sample["disk"] = disk_io

    load1, load5, load15 = os.getloadavg()

    return {
        "cpu_percent": psutil.cpu_percent(),
        "cpu_cores": psutil.cpu_percent(percpu=True),
        "cpu_count_logical": psutil.cpu_count(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_temp": _get_cpu_temp(),
        "load_avg": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "process_count": len(psutil.pids()),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "memory_total": vm.total,
        "memory_available": vm.available,
        "memory_used": vm.used,
        "memory_percent": vm.percent,
        "swap_total": sw.total,
        "swap_used": sw.used,
        "swap_percent": sw.percent,
        "disk_total": du.total,
        "disk_used": du.used,
        "disk_free": du.free,
        "disk_percent": du.percent,
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
        "net_upload_bps": round(net_upload_bps),
        "net_download_bps": round(net_download_bps),
        "disk_read_bps": round(disk_read_bps),
        "disk_write_bps": round(disk_write_bps),
    }


@router.websocket("/ws/logs/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    token = websocket.cookies.get("session")
    live = await asyncio.to_thread(
        revalidate_session, decode_token(token) if token else None, homepage_users_col
    )
    if not live or live.get("role") != "admin":
        await websocket.close(code=1008)
        return
    processes = await asyncio.to_thread(PM2Service.get_processes)
    if name not in {proc.get("name") for proc in processes}:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    process = await asyncio.create_subprocess_exec(
        "pm2",
        "logs",
        name,
        "--lines",
        "50",
        "--raw",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    disconnect_task = asyncio.create_task(websocket.receive_text())
    try:
        while True:
            line_task = asyncio.create_task(process.stdout.readline())
            done, _ = await asyncio.wait(
                {line_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if disconnect_task in done:
                try:
                    disconnect_task.result()
                except WebSocketDisconnect:
                    pass
                line_task.cancel()
                await asyncio.gather(line_task, return_exceptions=True)
                break
            line = line_task.result()
            if not line:
                break
            clean_line = _ANSI_ESCAPE.sub("", line.decode(errors="replace")).rstrip(
                "\r\n"
            )
            await websocket.send_text(clean_line)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Log Streaming Error: {e}")
    finally:
        disconnect_task.cancel()
        await asyncio.gather(disconnect_task, return_exceptions=True)
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


@router.post("/toggle-watch/{name}")
async def toggle_watch(name: str, user=Depends(get_current_user)):
    processes = PM2Service.get_processes()
    target_proc = next((p for p in processes if p["name"] == name), None)

    if not target_proc:
        raise HTTPException(status_code=404, detail="Process not found")

    current_watch = target_proc.get("pm2_env", {}).get("watch", False)

    new_flag = ["--watch", "false"] if current_watch else ["--watch"]

    new_flag.append("--update-env")

    success = PM2Service.run_command("restart", name, new_flag)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.pm2.toggle_watch",
        "admin",
        message=f"pm2 watch 모드 전환: {name} -> {not current_watch}",
        target={"type": "pm2_process", "id": name},
        outcome="success" if success else "failure",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to toggle watch mode")

    return {"status": "success", "watch": not current_watch}


@router.get("/startup-status")
async def get_startup_status():
    status = PM2Service.get_startup_status()
    return {"is_registered": status}


@router.post("/save")
async def save_pm2_list():
    success = PM2Service.save_processes()
    if not success:
        raise HTTPException(status_code=500, detail="Save failed")
    return {"status": "success"}


# ── ecosystem.config.js: 등록된 앱 목록 · 새 앱 추가 · 시작 (UnivDash 에서 옮겨 옴) ──

from pydantic import BaseModel, Field  # noqa: E402
from fastapi import Query  # noqa: E402

from app.services import ecosystem_service  # noqa: E402
from app.services.ecosystem_service import EcosystemError  # noqa: E402


class EcosystemAppRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    cwd: str = Field(min_length=1, max_length=1024)
    script: str = Field(min_length=1, max_length=500)
    interpreter: str = Field(default="", max_length=500)
    args: str = Field(default="", max_length=500)
    watch: bool = False
    time: bool = True
    env: str = Field(default="", max_length=20000)
    start: bool = True


def _ecosystem_error(error: Exception):
    if isinstance(error, KeyError):
        raise HTTPException(
            status_code=404, detail=str(error.args[0] if error.args else error)
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/api/ecosystem")
async def get_ecosystem(user=Depends(get_current_user)):
    path = ecosystem_service.ecosystem_path()
    try:
        apps = await asyncio.to_thread(ecosystem_service.load_apps, path)
    except EcosystemError as error:
        return {
            "path": str(path),
            "exists": path.exists(),
            "error": str(error),
            "apps": [],
        }
    running = {
        proc.get("name"): (proc.get("pm2_env") or {}).get("status")
        for proc in await asyncio.to_thread(PM2Service.get_processes)
    }
    for app in apps:
        app["status"] = running.get(app.get("name"))
    return {"path": str(path), "exists": path.exists(), "apps": apps}


@router.get("/api/ecosystem/inspect")
async def inspect_ecosystem_directory(
    cwd: str = Query(..., max_length=1024), user=Depends(get_current_user)
):
    return await asyncio.to_thread(ecosystem_service.inspect_directory, cwd)


@router.post("/api/ecosystem/apps")
async def add_ecosystem_app(body: EcosystemAppRequest, user=Depends(get_current_user)):
    try:
        result = await asyncio.to_thread(ecosystem_service.add_app, body.model_dump())
    except (ValueError, KeyError, EcosystemError, OSError) as error:
        _ecosystem_error(error)
    result["started"] = None
    if body.start:
        try:
            ok, output = await asyncio.to_thread(ecosystem_service.start_app, body.name)
        except (ValueError, KeyError, EcosystemError) as error:
            ok, output = False, str(error)
        result.update(started=ok, output=output)
    insert_log(
        user_logs_col,
        user.get("uid") or user.get("sub"),
        "admin.pm2.ecosystem_add",
        "admin",
        message=f"ecosystem 앱 추가: {body.name} ({body.cwd})",
        target={"type": "pm2_process", "id": body.name},
        outcome="success",
    )
    return result


@router.post("/api/ecosystem/apps/{name}/start")
async def start_ecosystem_app(name: str, user=Depends(get_current_user)):
    try:
        ok, output = await asyncio.to_thread(ecosystem_service.start_app, name)
    except (ValueError, KeyError, EcosystemError) as error:
        _ecosystem_error(error)
    insert_log(
        user_logs_col,
        user.get("uid") or user.get("sub"),
        "admin.pm2.ecosystem_start",
        "admin",
        message=f"ecosystem 앱 시작: {name}",
        target={"type": "pm2_process", "id": name},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(
            status_code=500, detail=output or "pm2 start 가 실패했습니다."
        )
    return {"started": True, "output": output}
