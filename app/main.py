# main.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db.database import engine, Base
from app.db import models  # noqa: F401 – registers models with Base

from app.api.auth import router as auth_router
from app.api.jd import router as jd_router
from app.api.cv_analysis import router as cv_router
from app.api.job_requests import router as jobs_router
from app.api.notifications import router as notif_router
from app.api.analytics import router as analytics_router
from app.api.keka import router as keka_router
from app.utils.scheduler import start_scheduler, shutdown_scheduler, reschedule_active_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Start background scheduler
    start_scheduler()
    reschedule_active_jobs()
    yield
    # Shutdown scheduler
    shutdown_scheduler()


app = FastAPI(title="Recruitment AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "Backend running"}


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(notif_router)
app.include_router(analytics_router)
app.include_router(jd_router, prefix="/jd", tags=["JD"])
app.include_router(cv_router, prefix="/cv", tags=["CV Analysis"])
app.include_router(keka_router)


# ── Serve React Frontend (production) ──────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    # Serve static assets (JS, CSS, images) under /assets
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIR / "assets"),
        name="frontend-assets",
    )

    # Catch-all: serve index.html for any non-API route (React Router SPA)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If a file exists in dist, serve it (e.g. favicon.ico, manifest.json)
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for React Router
        return FileResponse(FRONTEND_DIR / "index.html")
