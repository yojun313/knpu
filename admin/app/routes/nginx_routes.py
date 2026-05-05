import asyncio
from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from app.services.nginx_service import NginxService
from app.routes.dependencies import get_current_user
import os

router = APIRouter(prefix="/nginx", tags=["nginx"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def nginx_manager_page(request: Request, user=Depends(get_current_user)):
    domains = NginxService.get_domains()
    return templates.TemplateResponse(
        request=request,
        name="nginx.html",
        context={
            "domains": domains,
            "active_page": "nginx"
        }
    )

@router.websocket("/ws/console")
async def nginx_console_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        action = data.get("action")
        
        if action == "add":
            cmd = ["sudo", "bash", os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")), "add_nginx.sh"), data['domain'], data['email'], data['port']]
        elif action == "delete":
            cmd = ["sudo", "certbot", "delete", "--cert-name", data['domain'], "--non-interactive"]
        else:
            await websocket.send_text("Invalid Action")
            await websocket.close()
            return

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode().strip())
        
        await process.wait()
        if action == "delete":
            os.system(f"sudo rm -f /etc/nginx/sites-enabled/{data['domain']}")
            os.system(f"sudo rm -f /etc/nginx/sites-available/{data['domain']}")
            os.system("sudo systemctl reload nginx")
            await websocket.send_text("Nginx configuration removed and reloaded.")

        await websocket.send_text("작업이 완료되었습니다.")
        
    except Exception as e:
        await websocket.send_text(f"에러 발생: {str(e)}")
    finally:
        await websocket.close()