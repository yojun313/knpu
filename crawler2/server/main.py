# ┌─────────────────────────────────────────────────────────────────────┐
# │  FastAPI 앱의 진입점(entry point)                                    │
# │                                                                     │
# │  실행 흐름:                                                          │
# │  run.py (gunicorn 설정)                                             │
# │    └── main.py (app 객체 생성 + 미들웨어 + 예외 핸들러 + 라우터 등록) │
# │          └── routes/__init__.py (URL prefix별 라우터 조립)           │
# │                └── routes/*.py (실제 엔드포인트 함수들)              │
# └─────────────────────────────────────────────────────────────────────┘

from fastapi import FastAPI, Request
from app.routes import api_router  # routes/__init__.py에서 조립된 전체 라우터를 가져옴
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import traceback

# Rich: 터미널 출력에 색상/스타일을 입혀주는 라이브러리.
# console.print("[green]OK[/green]") 처럼 마크업 문법을 사용한다.
console = Console()


# ── 백그라운드 태스크 ──────────────────────────────────────────────────
# FastAPI는 내부적으로 asyncio 이벤트 루프 위에서 동작한다.
# asyncio.create_task()로 등록하면 서버가 요청을 처리하는 동안 병렬로 실행된다.
# 여기서는 60초마다 Python 가비지 컬렉터(gc)를 강제 실행해 메모리를 정리한다.
# (분석 작업처럼 큰 데이터를 다루다 보면 메모리가 쌓이기 쉽기 때문)
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)  # await: 이 시간 동안 다른 요청 처리를 양보함
        gc.collect()


# ── 미들웨어(Middleware) ───────────────────────────────────────────────
# 미들웨어 = 모든 HTTP 요청/응답이 실제 라우트 핸들러에 닿기 전후에 반드시 통과하는 관문.
#
# 비유: 공항 보안검색대. 어떤 게이트(라우트)로 가든 보안검색(미들웨어)은 반드시 거침.
#
# BaseHTTPMiddleware:
#   Starlette(FastAPI의 하위 프레임워크)가 제공하는 미들웨어 기반 클래스.
#   이걸 상속하고 dispatch() 메서드만 구현하면 커스텀 미들웨어를 만들 수 있다.
#
# dispatch() 구조:
#   ┌─────────────────────────────────────────┐
#   │  [요청 들어옴]                           │
#   │      ↓                                  │
#   │  dispatch() 시작 (call_next 호출 전)     │ ← 여기서 요청 전처리 가능
#   │      ↓                                  │
#   │  await call_next(request)               │ ← 실제 라우트 핸들러 실행
#   │      ↓                                  │
#   │  dispatch() 계속 (call_next 호출 후)     │ ← 여기서 응답 후처리 가능
#   │      ↓                                  │
#   │  [응답 반환]                             │
#   └─────────────────────────────────────────┘
#
# 이 미들웨어는 요청마다 소요 시간을 측정하고 터미널에 로그를 출력한다.
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()

        response = await call_next(request)  # ← 이 한 줄이 실제 라우트 핸들러 실행 지점

        duration = (datetime.now() - start_time).total_seconds()
        status = response.status_code

        # Rich 마크업: 2xx는 초록, 나머지(4xx, 5xx)는 빨강
        status_str = f"[green]{status}[/green]" if 200 <= status < 300 else f"[red]{status}[/red]"

        # 출력 예시: 14:32:05  200  GET  /api/users  0.03s
        log_message = (
            f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] "
            f"{status_str} "
            f"[cyan]{request.method}[/cyan] "
            f"[green]{request.url.path}[/green] "
            f"[yellow]{duration:.2f}s[/yellow]"
        )
        console.print(log_message)
        return response


# ── FastAPI 앱 인스턴스 생성 ───────────────────────────────────────────
# 이 app 객체가 서버 그 자체다.
# run.py에서 gunicorn이 "app.main:app"으로 이 객체를 가져다 실행한다.
app = FastAPI()


# ── 전역 예외 핸들러 ───────────────────────────────────────────────────
# 라우트 핸들러 안에서 try/except로 잡히지 않은 예외가 터지면 여기로 떨어진다.
#
# @app.exception_handler(Exception):
#   특정 예외 타입을 이 함수에서 처리하겠다고 등록하는 데코레이터.
#   Exception은 모든 예외의 부모 클래스이므로 사실상 전체 예외를 잡는다.
#
# 기본 동작(FastAPI 내장): {"detail": "Internal Server Error"} 500 응답
# 여기서 커스터마이징하는 이유: traceback에서 라이브러리 내부 코드를 걷어내고
# 우리가 작성한 코드의 에러 위치만 클라이언트에 전달하기 위해서.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)  # traceback의 각 스택 프레임 목록을 추출

    # site-packages(설치된 라이브러리), lib/python(표준 라이브러리) 경로의 프레임은 제거.
    # 남은 건 우리 코드(app/ 안의 파일들)에서 발생한 프레임만.
    filtered_frames = []
    for frame in frames:
        if "site-packages" not in frame.filename and "lib/python" not in frame.filename:
            filtered_frames.append(frame)

    # 필터링 후 아무것도 안 남으면(에러가 완전히 라이브러리 내부에서 발생한 경우)
    # 마지막 프레임 하나만 남겨서 최소한의 정보는 전달한다.
    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    # 서버 터미널에는 전체 traceback을 출력 (개발/운영 시 서버 로그 확인용)
    console.print(f"[bold red]Exception at {request.url.path}:[/bold red]\n{traceback.format_exc()}")

    # 클라이언트(API 호출자)에는 필터링된 traceback만 JSON으로 반환
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "detail": custom_traceback, # 이제 필터링된 내용만 클라이언트로 전송됨
            "path": request.url.path
        },
    )

# 미들웨어 등록. app 인스턴스 생성 이후에 붙여야 한다.
app.add_middleware(RichLoggerMiddleware)


# ── 시작 이벤트(startup hook) ─────────────────────────────────────────
# @app.on_event("startup"): 서버가 처음 뜰 때 딱 한 번 실행되는 훅.
# (반대로 @app.on_event("shutdown")은 서버가 종료될 때 실행된다.)
# 여기서 위에서 정의한 periodic_gc를 백그라운드 태스크로 이벤트 루프에 등록한다.
@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_gc(60))


# ── 라우터 등록 ───────────────────────────────────────────────────────
# app.include_router(): 다른 파일에서 조립한 APIRouter를 앱에 붙인다.
# Express의 app.use('/api', router)와 같은 개념.
#
# prefix="/api" → 하위 모든 엔드포인트 앞에 /api가 자동으로 붙는다.
#   예) routes/__init__.py에서 /users로 등록 → 실제 URL: /api/users
#       routes/__init__.py에서 /crawls로 등록 → 실제 URL: /api/crawls
#
# 세부 라우터 구성(어떤 prefix에 무슨 라우터가 붙는지)은 app/routes/__init__.py 참고.
app.include_router(api_router, prefix="/api", tags=["API"])
