import asyncio
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import settings_service
from app.db import user_logs_col
from system.llm import LLMError, achat, get_client, global_model
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
# 모든 서비스의 system.llm 호출이 따르는 '서버 기본 모델'. 사용자(관리자 포함)는 개인 API를
# 따로 설정할 수 없다.


@router.get("/api/llm-global")
async def api_get_llm_global(user=Depends(get_current_user)):
    return await asyncio.to_thread(global_model.status)


@router.post("/api/llm-global")
async def api_save_llm_global(
    entries: list[dict] = Body(..., embed=True),
    user=Depends(get_current_user),
):
    """우선순위 목록 저장(목록 순서 = 우선순위)."""
    try:
        await asyncio.to_thread(
            global_model.save, entries, user.get("name") or user["sub"]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    status = await asyncio.to_thread(global_model.status)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.settings.llm_global_update",
        "admin",
        message=f"전역 AI 모델 우선순위 변경: {status['active']}",
        metadata={
            "entries": [
                {k: e.get(k) for k in ("name", "kind", "base_url", "model", "enabled")}
                for e in status["entries"]
            ]
        },
    )
    return status


def _elapsed(started: float) -> float:
    return round(time.monotonic() - started, 1)


@router.post("/api/llm-global/test")
async def api_test_llm_global(
    entry: dict | None = Body(None, embed=True), user=Depends(get_current_user)
):
    """entry 를 주면 그 대상 하나만, 없으면 저장된 우선순위대로 짧은 요청을 보내 응답을 확인한다."""
    started = time.monotonic()
    kwargs = {}
    label = None
    if entry:
        try:
            conn = await asyncio.to_thread(global_model.draft_connection, entry)
        except ValueError as e:
            return {"ok": False, "error": str(e), "elapsed_s": 0}
        label = conn["label"]
        kwargs = {
            "base_url": conn["base_url"],
            "api_key": conn["api_key"],
            "model": conn["model"],
        }
    try:
        res = await achat(
            prompt="연결 확인입니다. '정상'이라고만 답해 주시기 바랍니다.",
            max_tokens=256,
            **kwargs,
        )
    except LLMError as e:
        return {"ok": False, "error": str(e)[:400], "elapsed_s": _elapsed(started)}
    return {
        "ok": True,
        "target": label or res.target_label,
        "model": res.display_model,
        "used_fallback": res.used_fallback,
        "reply": (res.text or "").strip()[:80],
        "elapsed_s": _elapsed(started),
    }


@router.post("/api/llm-global/models")
async def api_llm_global_models(
    entry: dict = Body(..., embed=True), user=Depends(get_current_user)
):
    """추가하려는 API 주소에서 모델 목록(/models)을 불러온다."""
    try:
        conn = await asyncio.to_thread(global_model.draft_connection, entry)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    def _list():
        client = get_client(conn["base_url"], conn["api_key"])
        data = client.with_options(timeout=15.0, max_retries=0).models.list()
        return [m.id for m in getattr(data, "data", []) if getattr(m, "id", None)]

    try:
        models = await asyncio.to_thread(_list)
    except Exception as e:
        return {
            "ok": False,
            "error": f"모델 목록을 불러오지 못했습니다: {str(e)[:300]}",
        }
    return {"ok": True, "models": sorted(models)[:300]}
