from fastapi import FastAPI
from app.routes import api_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.include_router(api_router, prefix="/api", tags=["api"])
app.add_middleware(
    CORSMiddleware,
    # allow_credentials=True와 allow_origins=["*"]는 브라우저가 동시 사용을 거부하므로
    # (쿠키 기반 SSO 로그아웃 등 credentialed 요청을 다른 *.knpu.re.kr 서브도메인에서
    # 받으려면) 정규식으로 knpu.re.kr 서브도메인만 명시적으로 허용한다.
    allow_origin_regex=r"https://([a-z0-9-]+\.)?knpu\.re\.kr",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
