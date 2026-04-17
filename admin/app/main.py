from fastapi import FastAPI
from app.routes import auth_routes, main_routes, log_routes, bug_routes, crawler_routes

app = FastAPI(title="PAILAB Dashboard")

# 라우터 등록
app.include_router(auth_routes.router)
app.include_router(main_routes.router)
app.include_router(log_routes.router)
app.include_router(bug_routes.router)
app.include_router(crawler_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=3004, reload=True)