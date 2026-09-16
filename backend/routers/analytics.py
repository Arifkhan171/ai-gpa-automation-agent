# ============================================================
# AcadTrack — Analytics Router  (STUB)
# This file will be completed in MODULE 6: Analytics & Reporting.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/")
def analytics_placeholder():
    """Placeholder — analytics endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
