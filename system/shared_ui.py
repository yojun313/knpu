import asyncio
import json
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
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


def _manifest_json(app_name: str, theme_color: str) -> str:
    # 홈 화면 앱(PWA) 매니페스트. 아이콘은 /shared-ui 정적 자산을 그대로 쓰고
    # 이름만 사이트별로 다르다. iOS는 apple-* 메타를, 안드로이드는 이 파일을 읽는다.
    payload = {
        "name": app_name,
        "short_name": app_name,
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": theme_color,
        "theme_color": theme_color,
        "lang": "ko",
        "icons": [
            {
                "src": "/shared-ui/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/shared-ui/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/shared-ui/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def mount_shared_ui(
    app,
    *,
    app_name: str | None = None,
    theme_color: str = "#0B1226",
    chatbot: str | None = "member",
) -> None:
    """chatbot: "member"(구성원용만) · "public"(홈페이지: 외부인용 + 로그인하면 구성원용) · None(끔)."""

    @app.get("/shared-ui/services.js", include_in_schema=False)
    def shared_services_js():
        return Response(
            content=_services_js(),
            media_type="application/javascript",
            headers={"cache-control": "no-store, must-revalidate"},
        )

    if app_name:
        manifest = _manifest_json(app_name, theme_color)

        @app.get("/shared-ui/manifest.webmanifest", include_in_schema=False)
        def shared_manifest():
            return Response(
                content=manifest,
                media_type="application/manifest+json",
                headers={"cache-control": "no-store, must-revalidate"},
            )

    # 사용자별 LLM 설정(로컬/내 GPT API·월 한도·사용량) — 네비바 설정 창에서 쓴다.
    # AuthMiddleware 가 붙은 서비스에서만 로그인 사용자가 잡히고, 아니면 401을 돌려
    # 설정 창이 이 영역을 숨긴다.
    def _llm_uid(request: Request) -> str:
        user = request.scope.get("state", {}).get("user")
        if not user:
            raise HTTPException(401, "인증이 필요합니다")
        return user["uid"]

    @app.get("/api/llm-settings", include_in_schema=False)
    def llm_settings_get(request: Request):
        from system.llm import user_llm

        return JSONResponse(
            user_llm.public_settings(_llm_uid(request)),
            headers={"cache-control": "no-store"},
        )

    @app.put("/api/llm-settings", include_in_schema=False)
    async def llm_settings_put(request: Request):
        from system.llm import user_llm

        uid = _llm_uid(request)
        body = await request.json()
        try:
            return JSONResponse(
                await asyncio.to_thread(user_llm.save_settings, uid, body)
            )
        except user_llm.SettingsError as e:
            raise HTTPException(400, str(e))

    # 설정 창의 '내 계정' · '로컬 AI API' 섹션 API
    from system.account import register as register_account

    register_account(app)

    # 연구실 챗봇 API (오른쪽 아래 동그라미 버튼) — 정적 마운트보다 먼저 등록해야 한다
    if chatbot:
        from system.chatbot.routes import register as register_chatbot

        register_chatbot(app, public=(chatbot == "public"))

    app.mount(
        "/shared-ui",
        NoCacheStaticFiles(directory=SHARED_UI_DIR),
        name="shared-ui",
    )


__all__ = ["mount_shared_ui", "NoCacheStaticFiles", "SHARED_UI_DIR", "SERVICES_FILE"]
