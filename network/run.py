# uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8003)),
        workers=1,
        log_level="warning",
        timeout_keep_alive=86400,
        # PM2 stop/restart 때 열린 연결을 기다리느라 종료가 늘어지지 않게 — 그 사이
        # 작업 러너가 분석 프로세스 그룹을 정리한다(system/jobs/runner.py)
        timeout_graceful_shutdown=5,
        access_log=True,
    )
