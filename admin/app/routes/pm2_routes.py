import asyncio
import os
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
import psutil
from app.services.pm2_service import PM2Service
from app.routes.dependencies import get_current_user

router = APIRouter(prefix="/process", tags=["process"])
templates = Jinja2Templates(directory="app/templates")

_prev_sample = {"ts": None, "net": None, "disk": None}


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
    processes = PM2Service.get_processes()
    return templates.TemplateResponse(
        request=request,
        name="process.html",
        context={"processes": processes, "active_page": "pm2"},
    )


@router.post("/control/{action}/{name}")
async def control_process(action: str, name: str):
    if action not in ["restart", "stop", "start", "delete"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    success = PM2Service.run_command(action, name)
    if not success:
        raise HTTPException(status_code=500, detail="Command failed")

    return {"status": "success"}


@router.get("/status")
async def get_pm2_status_api(user=Depends(get_current_user)):
    return PM2Service.get_processes()


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

    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode().strip())
    except WebSocketDisconnect:
        process.terminate()
    except Exception as e:
        print(f"Log Streaming Error: {e}")
    finally:
        if process.returncode is None:
            process.terminate()


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
