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
from app.services.pm2_service import PM2Service, process_flags
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
        context={
            "processes": processes,
            "flags": process_flags(processes),
            "active_page": "process",
        },
    )


@router.post("/control/restart-all")
async def restart_all_processes(user=Depends(get_current_user)):

    def _run_and_log():
        # 한 번에 'pm2 restart all' 을 돌리지 않는다. 대시보드 자신도 대상이라, 차례가 오면
        # pm2 가 대시보드의 프로세스 트리(실행 중인 pm2 명령 포함)를 죽여 뒤 순서 앱들이
        # 재시작되지 않는다. 다른 앱을 하나씩 재시작한 뒤 대시보드는 마지막에 떼어 내 재시작한다.
        me = PM2Service.self_name()
        names = [p.get("name") for p in PM2Service.get_processes() if p.get("name")]
        names = list(dict.fromkeys(names))  # 클러스터 모드 중복 제거, 순서 유지
        failed = []
        for name in names:
            if name == me:
                continue
            ok, _ = PM2Service.restart(name)
            if not ok:
                failed.append(name)
        insert_log(
            user_logs_col,
            user["sub"],
            "admin.pm2.restart_all",
            "admin",
            message="pm2 전체 재시작"
            + (f" — 실패: {', '.join(failed)}" if failed else ""),
            target={"type": "pm2_process", "id": "all"},
            outcome="failure" if failed else "success",
        )
        if me and me in names:
            PM2Service.restart_detached(me)

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

    if action == "restart" and name == PM2Service.self_name():
        # 대시보드 자신: 응답을 먼저 보내고 떼어 낸 프로세스로 재시작한다.
        success = await asyncio.to_thread(PM2Service.restart_detached, name)
    elif action == "restart":
        # ecosystem 파일의 env 를 다시 적용해 재시작한다(대시보드 환경은 섞지 않는다).
        success, _ = await asyncio.to_thread(PM2Service.restart, name)
    else:
        success = await asyncio.to_thread(PM2Service.run_command, action, name)
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


def _check_name(name: str) -> None:
    if not name or name.startswith("-") or len(name) > 200:
        raise HTTPException(status_code=400, detail="잘못된 앱 이름입니다.")


@router.post("/uv-sync/{name}")
async def uv_sync_process(name: str, user=Depends(get_current_user)):
    """uv 로 구성된 pm2 앱의 프로젝트 폴더에서 `uv sync`. 재시작은 하지 않는다."""
    _check_name(name)
    try:
        ok, output = await asyncio.to_thread(PM2Service.uv_sync, name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error.args[0]) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.pm2.uv_sync",
        "admin",
        message=f"uv sync: {name}",
        target={"type": "pm2_process", "id": name},
        outcome="success" if ok else "failure",
    )
    return {"ok": ok, "output": output}


@router.post("/git-pull/{name}")
async def git_pull_process(name: str, user=Depends(get_current_user)):
    """pm2 앱이 들어 있는 저장소에서 `git pull --ff-only`. 재시작은 하지 않는다."""
    _check_name(name)
    try:
        result = await asyncio.to_thread(PM2Service.git_pull, name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error.args[0]) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.pm2.git_pull",
        "admin",
        message=f"git pull: {name} ({result.get('repo', '-')})"
        + (f" — {len(result['changed'])}개 파일 변경" if result.get("updated") else ""),
        target={"type": "pm2_process", "id": name},
        outcome="success" if result["ok"] else "failure",
    )
    return result


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

    # --update-env 는 붙이지 않는다: 대시보드의 환경(PORT 등)이 대상 앱에 덮어써진다.
    new_flag = ["--watch", "false"] if current_watch else ["--watch"]

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
    self_name = PM2Service.self_name()
    for app in apps:
        app["status"] = running.get(app.get("name"))
        app["self"] = self_name is not None and app.get("name") == self_name
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


class EcosystemUpdateRequest(EcosystemAppRequest):
    start: bool = False
    apply: bool = True


def _log_eco(user, action: str, name: str, message: str, ok: bool = True) -> None:
    insert_log(
        user_logs_col,
        user.get("uid") or user.get("sub"),
        f"admin.pm2.ecosystem_{action}",
        "admin",
        message=message,
        target={"type": "pm2_process", "id": name},
        outcome="success" if ok else "failure",
    )


@router.get("/api/ecosystem/apps/{name}")
async def get_ecosystem_app(name: str, user=Depends(get_current_user)):
    _check_name(name)
    try:
        app = await asyncio.to_thread(ecosystem_service.get_app, name)
    except (KeyError, EcosystemError) as error:
        _ecosystem_error(error)
    app["self"] = name == PM2Service.self_name()
    return app


@router.put("/api/ecosystem/apps/{name}")
async def update_ecosystem_app(
    name: str, body: EcosystemUpdateRequest, user=Depends(get_current_user)
):
    """항목을 고친다. apply 면 돌고 있는 프로세스를 지우고 새 설정으로 다시 시작한다 (대시보드 자신은 제외)."""
    _check_name(name)
    self_name = PM2Service.self_name()
    if body.name != name and name == self_name:
        raise HTTPException(
            status_code=400,
            detail="이 대시보드 자신의 앱 이름은 여기서 바꿀 수 없습니다.",
        )
    try:
        result = await asyncio.to_thread(
            ecosystem_service.update_app, name, body.model_dump()
        )
    except (ValueError, KeyError, EcosystemError, OSError) as error:
        _ecosystem_error(error)
    result["applied"] = None
    running = name in {
        p.get("name") for p in await asyncio.to_thread(PM2Service.get_processes)
    }
    if body.apply and result["changed"] and running:
        if name == self_name:
            result["applied"] = "self"
        else:
            # script · cwd · 인터프리터 변경은 restart 로는 반영되지 않아 지우고 새로 시작한다
            await asyncio.to_thread(PM2Service.run_command, "delete", name)
            try:
                ok, output = await asyncio.to_thread(
                    ecosystem_service.start_app, body.name
                )
            except (ValueError, KeyError, EcosystemError) as error:
                ok, output = False, str(error)
            result.update(applied=ok, output=output)
    _log_eco(
        user,
        "update",
        name,
        f"ecosystem 앱 수정: {name}"
        + (f" → {body.name}" if body.name != name else "")
        + f" ({', '.join(result['changed']) or '변경 없음'})",
        result["applied"] is not False,
    )
    return result


@router.delete("/api/ecosystem/apps/{name}")
async def delete_ecosystem_app(
    name: str, pm2: bool = False, user=Depends(get_current_user)
):
    """ecosystem 에서 항목을 지운다. pm2 면 돌고 있는 프로세스도 지운다. 대시보드 자신은 지울 수 없다."""
    _check_name(name)
    if name == PM2Service.self_name():
        raise HTTPException(
            status_code=400, detail="이 대시보드 자신은 여기서 지울 수 없습니다."
        )
    try:
        result = await asyncio.to_thread(ecosystem_service.delete_app, name)
    except (ValueError, KeyError, EcosystemError, OSError) as error:
        _ecosystem_error(error)
    result["pm2_deleted"] = None
    if pm2 and name in {
        p.get("name") for p in await asyncio.to_thread(PM2Service.get_processes)
    }:
        result["pm2_deleted"] = await asyncio.to_thread(
            PM2Service.run_command, "delete", name
        )
    _log_eco(
        user,
        "delete",
        name,
        f"ecosystem 앱 삭제: {name}"
        + (" (pm2 프로세스도 삭제)" if result["pm2_deleted"] else ""),
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
