# ============================================================
# AcadTrack — Notifications Router  (STUB)
# This file will be completed in MODULE 7: Notifications.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("/")
def notifications_placeholder():
    """Placeholder — notification endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
