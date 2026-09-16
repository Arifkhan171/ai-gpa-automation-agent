# ============================================================
# AcadTrack — Payments Router  (STUB)
# This file will be completed in MODULE 8: Fee & Payments.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.get("/")
def payments_placeholder():
    """Placeholder — payment endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
