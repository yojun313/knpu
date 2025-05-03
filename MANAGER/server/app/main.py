from fastapi import FastAPI
from app.api import routes_user, routes_crawl, routes_analysis

app = FastAPI()

# API 라우터 등록
app.include_router(routes_user.router, prefix="/users", tags=["Users"])
app.include_router(routes_crawl.router, prefix="/crawl", tags=["Crawling"])
app.include_router(routes_analysis.router, prefix="/analysis", tags=["Analysis"])
