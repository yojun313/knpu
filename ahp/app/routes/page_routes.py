"""관리자 화면(Jinja) + 응답자 화면(테마 없는 별도 정적 HTML) 페이지 라우트.

network/kemkim/statistics와 마찬가지로 서버는 껍데기 HTML만 내려주고, 실제 데이터는
전부 클라이언트 JS가 /api/*를 호출해 채운다 — URL의 id는 location.pathname에서
JS가 직접 파싱한다. 그래서 이 라우트들은 별도 서버측 데이터 조회 없이 템플릿만
고른다(같은 project_id로 여러 스테이지를 오가도 항상 같은 방식으로 동작).
"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
_NO_CACHE = {"Cache-Control": "no-store, must-revalidate"}


def _respond_page(filename: str) -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, filename), headers=_NO_CACHE)


# ── 관리자 화면 ──────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_stage": None})


@router.get("/design/{project_id}", response_class=HTMLResponse)
async def design_page(request: Request, project_id: str):
    return templates.TemplateResponse(
        request, "design.html", {"active_stage": "design", "project_id": project_id}
    )


@router.get("/survey/{project_id}", response_class=HTMLResponse)
async def survey_page(request: Request, project_id: str):
    # survey_id가 아니라 project_id로 연다 — 설문지는 프로젝트마다 계속 새 버전으로
    # 갱신되는 "현재 버전"이라 프로젝트가 안정적인 탐색 기준이다(design/collect/result와 동일).
    return templates.TemplateResponse(
        request, "survey.html", {"active_stage": "survey", "project_id": project_id}
    )


@router.get("/collect/{project_id}", response_class=HTMLResponse)
async def collect_page(request: Request, project_id: str):
    # 한 프로젝트에 오프라인/온라인/실시간 collection이 동시에 여러 개 있을 수 있어서
    # (PLAN.md 1절) 이 화면은 project 기준으로 그 전체 목록을 관리한다.
    return templates.TemplateResponse(
        request, "collect.html", {"active_stage": "collect", "project_id": project_id}
    )


@router.get("/entry/{collection_id}", response_class=HTMLResponse)
async def entry_page(request: Request, collection_id: str):
    return templates.TemplateResponse(
        request,
        "entry.html",
        {"active_stage": "collect", "collection_id": collection_id},
    )


@router.get("/console/{collection_id}", response_class=HTMLResponse)
async def console_page(request: Request, collection_id: str):
    return templates.TemplateResponse(
        request,
        "console.html",
        {"active_stage": "collect", "collection_id": collection_id},
    )


@router.get("/result/{project_id}", response_class=HTMLResponse)
async def result_page(request: Request, project_id: str):
    # 같은 설문지로 받은 오프라인+온라인 응답을 한 분석에 합쳐야 하므로(PLAN.md 1절)
    # 결과 화면의 기본 단위는 project다. 특정 collection만 보고 싶으면 화면 안에서
    # 클라이언트 사이드로 필터링한다(쿼리스트링 ?collection_id=... 지원, JS에서 처리).
    return templates.TemplateResponse(
        request, "result.html", {"active_stage": "result", "project_id": project_id}
    )


@router.get("/print/{survey_id}", response_class=HTMLResponse)
async def print_page(request: Request, survey_id: str):
    # 인쇄 미리보기는 상단바·레일 없는 독립 화면 — base.html을 상속하지 않는다.
    return templates.TemplateResponse(request, "print.html", {"survey_id": survey_id})


# ── 응답자 화면 (테마 없음, 상단바 없음, 모바일 퍼스트) ────────────────────────
@router.get("/r/{access_token}", response_class=HTMLResponse)
async def respond_page(access_token: str):
    return _respond_page("respond.html")
