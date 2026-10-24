# uvicorn app.main:app --host 0.0.0.0 --port 8003

import os
import uvicorn
import warnings
from requests.exceptions import RequestsDependencyWarning

warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8010)),
        workers=1,
        log_level="warning",
        # 접속 기록(IP·경로)을 남기지 않는다 — 사용자 정보를 최소한으로 보관한다
        access_log=False,
        server_header=False,
        # 운영은 pm2 watch가 재시작을 맡으므로 개발 모드에서만 자동 재시작한다
        reload=os.getenv("MODE", "1") == "0",
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        timeout_keep_alive=75,
        limit_concurrency=200,
        h11_max_incomplete_event_size=64 * 1024,
    )
