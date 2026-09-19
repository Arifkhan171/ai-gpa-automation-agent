"""
AcadTrack — Payment and Student Portal Pydantic Schemas
University of Loralai, Pakistan

Module 6: Student Portal and Payment Vouchers
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Voucher request / response
# ─────────────────────────────────────────────────────────────────────────────

_VALID_PURPOSES = {"transcript", "attestation", "character_certificate", "migration"}


class VoucherCreateRequest(BaseModel):
    purpose: str
    # Must be one of: transcript, attestation, character_certificate, migration
    semester_range: Optional[str] = None
    # For transcript: "1-4" or "all"
    notes: Optional[str] = None

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if v not in _VALID_PURPOSES:
            raise ValueError(
                f"purpose must be one of: {', '.join(sorted(_VALID_PURPOSES))}"
            )
        return v


class VoucherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    voucher_number: str
    student_name: str
    roll_no: str
    purpose: str
    amount: float
    status: str
    semester_range: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    paid_at: Optional[datetime] = None
    action_taken: bool
    message: str = ""


class MarkPaidRequest(BaseModel):
    payment_notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Admin daily collection report
# ─────────────────────────────────────────────────────────────────────────────

class DailyCollectionResponse(BaseModel):
    date: str
    total_vouchers: int
    total_amount: float
    paid_count: int
    pending_count: int
    cancelled_count: int
    breakdown: List[dict]
    # Each item: {"purpose": str, "count": int, "amount": float}


# ─────────────────────────────────────────────────────────────────────────────
# Student portal home
# ─────────────────────────────────────────────────────────────────────────────

class StudentPortalResponse(BaseModel):
    student_name: str
    roll_no: str
    father_name: Optional[str] = None
    department: Optional[str] = None
    session: str
    cgpa: Optional[float] = None
    total_credit_hours: float
    semesters_completed: int
    status: str
    pending_vouchers: int
    total_transcripts_issued: int
