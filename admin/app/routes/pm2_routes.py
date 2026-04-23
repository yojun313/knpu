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
async def control_process(action: str, name: str, user=Depends(get_current_user)):
    if action not in ["restart", "stop", "start"]:
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