"""
AcadTrack — Health-Check Router
University of Loralai, Pakistan

Endpoints:
    GET /health      → basic app status
    GET /health/db   → live database connectivity test
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from backend.config import settings
from backend.database import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Return basic application status."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "university": settings.UNIVERSITY_NAME,
        "database": "connected",
    }


@router.get("/health/db")
def health_db():
    """
    Test a live round-trip to the database.
    Returns HTTP 503 if the connection fails.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = settings.DATABASE_URL.split("://")[0]
        return {
            "status": "ok",
            "database_url": db_type,
            "message": "Database connection successful",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(exc)}",
        )
