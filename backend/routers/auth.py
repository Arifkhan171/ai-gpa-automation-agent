# ============================================================
# AcadTrack — Auth Router  (STUB)
# This file will be completed in MODULE 2: Authentication.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.get("/")
def auth_placeholder():
    """Placeholder — authentication endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
