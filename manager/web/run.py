import uvicorn

if __name__ == "__main__":
    # 모듈 경로: app/main.py 에서 'app' 객체를 export 한 경우
    uvicorn.run(
        "app.main:app",           # "<패키지>.<파일이름>:<FastAPI 인스턴스 변수>"
        host="0.0.0.0",
        port=8080,
        workers=1,
        reload=True,              # 코드 수정 시 자동 재시작
        timeout_keep_alive=86400  # WebSocket 장시간 연결 유지
    )
