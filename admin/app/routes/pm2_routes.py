from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from app.services.pm2_service import PM2Service
from app.routes.dependencies import get_current_user
import asyncio

router = APIRouter(prefix="/process", tags=["process"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def pm2_manager_page(request: Request, user=Depends(get_current_user)):
    processes = PM2Service.get_processes()
    return templates.TemplateResponse("process.html", {
        "request": request,
        "processes": processes,
        "active_page": "pm2"
    })

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

@router.websocket("/ws/logs/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    await websocket.accept()
    
    process = await asyncio.create_subprocess_exec(
        "pm2", "logs", name, "--lines", "50", "--raw",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
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
    target_proc = next((p for p in processes if p['name'] == name), None)
    
    if not target_proc:
        raise HTTPException(status_code=404, detail="Process not found")

    current_watch = target_proc.get('pm2_env', {}).get('watch', False)
    
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