import os
import uvicorn
import warnings
from requests.exceptions import RequestsDependencyWarning

warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        # nginx 뒤에서만 받는다. 0.0.0.0 이면 nginx 를 건너뛰고 포트로 바로 접속할 수 있다.
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8009)),
        log_level="warning",
        access_log=True,
        timeout_keep_alive=86400,
    )
