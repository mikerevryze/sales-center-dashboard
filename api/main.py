"""Revryze OS — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from api.scorecard import router as scorecard_router
from api.analytics import router as analytics_router
from api.calls import router as calls_router
from api.pipeline import router as pipeline_router
from api.clients import router as clients_router

app = FastAPI(title="Revryze OS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scorecard_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(calls_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(clients_router, prefix="/api")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.get("/")
async def serve_app():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "revryze-os"}
