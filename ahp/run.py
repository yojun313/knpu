# uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8010,
        workers=1,
        log_level="warning",
        timeout_keep_alive=86400,
        access_log=True,
    )
