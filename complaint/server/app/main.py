from fastapi import FastAPI
from app.routes import api_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.include_router(api_router, prefix="/api", tags=["api"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
