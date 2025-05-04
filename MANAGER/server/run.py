# run.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "run:app",               # or your app path
        host="0.0.0.0",
        port=8000,
        timeout_keep_alive=86400,
        http_timeout=86400,
        reload=True              # 개발환경이라면
    )
