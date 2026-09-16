# ============================================================
# AcadTrack — Transcripts Router  (STUB)
# This file will be completed in MODULE 5: Transcript Generation.
# Do NOT add business logic here until that module begins.
# ============================================================

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/transcripts", tags=["Transcripts"])


@router.get("/")
def transcripts_placeholder():
    """Placeholder — transcript endpoints are not yet implemented."""
    return {"message": "This module is not yet implemented"}
