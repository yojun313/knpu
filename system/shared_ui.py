import json
import os

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from system.endpoints import IS_DEV, SERVICES_FILE, _config

SHARED_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")


class NoCacheStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-store, must-revalidate"))
                message = {**message, "headers": headers}
            await send(message)

        await super().__call__(scope, receive, send_wrapper)


def _services_js() -> str:
    cfg = _config()
    login_svc = cfg["services"][cfg["login_service"]]
    payload = {
        "isDev": IS_DEV,
        "cookieDomain": cfg["cookie_domain"],
        # 중앙 로그인은 dev/prod 공통이라 항상 운영 도메인이다.
        "loginOrigin": f"https://{login_svc['prod_domain']}",
        "services": {
            name: {
                "prodDomain": svc["prod_domain"],
                "devDomain": svc["dev_domain"],
                "publicPath": svc.get("public_path", ""),
            }
            for name, svc in cfg["services"].items()
        },
    }
    return (
        "/* knpu/services.json에서 생성됨 — 직접 수정하지 말 것 */\n"
        f"window.KNPU_SERVICES = {json.dumps(payload, ensure_ascii=False)};\n"
    )


def mount_shared_ui(app) -> None:
    @app.get("/shared-ui/services.js", include_in_schema=False)
    def shared_services_js():
        return Response(
            content=_services_js(),
            media_type="application/javascript",
            headers={"cache-control": "no-store, must-revalidate"},
        )

    app.mount(
        "/shared-ui",
        NoCacheStaticFiles(directory=SHARED_UI_DIR),
        name="shared-ui",
    )


__all__ = ["mount_shared_ui", "NoCacheStaticFiles", "SHARED_UI_DIR", "SERVICES_FILE"]
