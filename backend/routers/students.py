# ============================================================
# AcadTrack — Students Router  (STUB)
# This file will be completed in MODULE 3: Student Management.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/students", tags=["Students"])


@router.get("/")
def students_placeholder():
    """Placeholder — student endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
