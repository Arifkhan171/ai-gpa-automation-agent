# ============================================================
# AcadTrack — Grades Router  (STUB)
# This file will be completed in MODULE 4: Grades & GPA.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/grades", tags=["Grades"])


@router.get("/")
def grades_placeholder():
    """Placeholder — grade endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
