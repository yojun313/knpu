# uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8008)),
        workers=1,
        log_level="warning",
        timeout_keep_alive=86400,
        access_log=True,
    )
