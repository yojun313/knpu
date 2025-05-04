from fastapi import FastAPI
from app.routes import api_router

app = FastAPI()

app.include_router(api_router, prefix="/api", tags=["API"])