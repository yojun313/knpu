import asyncio
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import settings_service
from app.db import user_logs_col
from system.llm import LLMError, achat, global_model
from system.logging.user_log import insert_log

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/settings")
async def settings_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request, name="settings.html", context={"active_page": "settings"}
    )


@router.get("/api/nav-order")
async def api_get_nav_order(user=Depends(get_current_user)):
    return {"items": settings_service.get_nav_items_ordered()}


@router.post("/api/nav-order")
async def api_save_nav_order(
    order: list[str] = Body(..., embed=True), user=Depends(get_current_user)
):
    items = settings_service.save_nav_order(order)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.settings.nav_order_update",
        "admin",
        message="네비게이션 순서 변경",
        metadata={"order": order},
    )
    return {"items": items}


# ── 전역 AI 모델 ─────────────────────────────────────────────────────────────
# 모든 서비스의 system.llm 호출이 따르는 '서버 기본 모델'. 사용자가 설정에서 '내 GPT API'를
# 직접 고른 호출은 이 설정과 무관하다.


@router.get("/api/llm-global")
async def api_get_llm_global(user=Depends(get_current_user)):
    return await asyncio.to_thread(global_model.status)


@router.post("/api/llm-global")
async def api_save_llm_global(
    provider: str = Body(...),
    openai_model: str | None = Body(None),
    user=Depends(get_current_user),
):
    try:
        await asyncio.to_thread(
            global_model.save, provider, openai_model, user.get("name") or user["sub"]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    status = await asyncio.to_thread(global_model.status)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.settings.llm_global_update",
        "admin",
        message=f"전역 AI 모델 변경: {status['active']}",
        metadata={
            "provider": status["provider"],
            "openai_model": status["openai_model"],
        },
    )
    return status


@router.post("/api/llm-global/test")
async def api_test_llm_global(user=Depends(get_current_user)):
    """현재 전역 설정으로 짧은 요청을 보내 실제로 어느 모델이 응답하는지 확인한다."""
    started = time.monotonic()
    try:
        res = await achat(
            prompt="연결 확인입니다. '정상'이라고만 답해 주시기 바랍니다.",
            max_tokens=256,
        )
    except LLMError as e:
        return {
            "ok": False,
            "error": str(e)[:300],
            "elapsed_s": round(time.monotonic() - started, 1),
        }
    return {
        "ok": True,
        "model": res.display_model,
        "used_fallback": res.used_fallback,
        "reply": (res.text or "").strip()[:80],
        "elapsed_s": round(time.monotonic() - started, 1),
    }
