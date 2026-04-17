from fastapi import FastAPI
from .routes.views import router

app = FastAPI(title="PAILAB Dashboard")

app.include_router(router)