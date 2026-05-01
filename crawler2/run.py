# 크롤러 실행 서버
# 실행: cd crawler2 && python run.py
# workers=1 필수: CrawlerRegistry가 in-process 상태를 유지하므로 단일 워커만 가능

import os
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(BASE_DIR, "server")

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=3002,
    )
