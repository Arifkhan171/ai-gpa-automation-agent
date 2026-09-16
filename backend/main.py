"""
AcadTrack — FastAPI Application Entry Point
University of Loralai, Pakistan

Run from the project root:
    uvicorn backend.main:app --reload --port 8000

The Streamlit app continues to run independently:
    streamlit run src/dashboard/app.py
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.routers import (
    analytics,
    auth,
    grades,
    health,
    notifications,
    payments,
    students,
    transcripts,
)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run initialisation tasks before the server starts accepting requests."""
    init_db()           # ensure backend tables exist (safe no-op if already present)
    yield
    # nothing to clean up on shutdown


# ── Application factory ───────────────────────────────────────────────────────
app = FastAPI(
    title="AcadTrack API",
    description="University of Loralai Academic Records System",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (open in dev — restrict origins before deploying to production) ──────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Health checks are mounted directly (no /api/v1 prefix) so they're easy to hit
app.include_router(health.router)

# All feature routers carry their own /api/v1/... prefix
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(grades.router)
app.include_router(transcripts.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(payments.router)


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    """Landing endpoint — confirms the API is running."""
    return {
        "message": "AcadTrack API is running",
        "docs": "/docs",
        "health": "/health",
    }
