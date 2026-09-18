"""
AcadTrack — Transcript Pydantic Schemas
University of Loralai, Pakistan

Request and response models for the transcript generation and verification
endpoints (Module 5).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────

class TranscriptRequest(BaseModel):
    """Body for POST /api/v1/transcripts/generate — single student."""
    roll_no: str
    up_to_semester: Optional[int] = None   # None → include all semesters
    unofficial: bool = True
    notes: Optional[str] = None


class BulkTranscriptRequest(BaseModel):
    """Body for POST /api/v1/transcripts/generate-bulk — multiple students."""
    roll_nos: list[str]
    up_to_semester: Optional[int] = None
    unofficial: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────

class TranscriptRecordResponse(BaseModel):
    """Returned by GET /api/v1/transcripts/records — list of issued transcripts."""
    id: int
    verification_token: str
    roll_no: str
    student_name: str
    semester_range: str
    cgpa_at_issue: Optional[float]
    is_unofficial: bool
    issued_by: str
    issued_at: datetime
    scan_count: int
    is_valid: bool

    model_config = ConfigDict(from_attributes=True)


class VerificationResponse(BaseModel):
    """
    Returned by the public GET /verify/{token} endpoint.

    is_valid=True  → message starts with "VERIFIED"
    is_valid=False → message starts with "INVALID"
    """
    is_valid: bool
    verification_token: str
    student_name: Optional[str]
    roll_no: Optional[str]
    semester_range: Optional[str]
    cgpa_at_issue: Optional[float]
    is_unofficial: bool
    issued_by: Optional[str]
    issued_at: Optional[datetime]
    scan_count: int
    message: str
