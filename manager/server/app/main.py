from fastapi import FastAPI
from app.routes import api_router
import gc
import asyncio

async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()

app = FastAPI()
@app.on_event("startup")
async def start_background_gc():
    asyncio.create_task(periodic_gc(60))

app.include_router(api_router, prefix="/api", tags=["API"])