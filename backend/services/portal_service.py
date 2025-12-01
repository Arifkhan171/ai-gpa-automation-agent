"""
AcadTrack — Student Portal Service
University of Loralai, Pakistan

Module 6: Student Portal and Payment Vouchers

Provides:
    get_student_portal_data(roll_no, db) → dict
        Aggregates all data needed for the student portal home screen.
"""

import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.database_models import CGPA, Student
from backend.models.transcript_model import TranscriptRecord
from backend.models.payment_model import PaymentVoucher


# ── CGPA → academic status ────────────────────────────────────────────────────

def _get_status(cgpa: Optional[float]) -> str:
    if cgpa is None:
        return "no_grades"
    if cgpa >= 3.5:
        return "excellent"
    if cgpa >= 2.5:
        return "good"
    if cgpa >= 2.0:
        return "satisfactory"
    return "at_risk"


# ── Session year inference ────────────────────────────────────────────────────

def _infer_session(roll_no: str) -> str:
    """
    Extract the 2-digit year from a UoL roll number and produce a 4-year span.

    Pattern: [/-]F[-/](\\d{2})[/-]
    Example: "UoL/CS-F-22/004-BS" -> year_digit="22" -> "2022-2026"
    Falls back to "Unknown" if the pattern is not found.
    """
    match = re.search(r"[/\-]F[/\-](\d{2})[/\-]", roll_no, re.IGNORECASE)
    if match:
        two_digit = int(match.group(1))
        start_year = 2000 + two_digit
        end_year = start_year + 4
        return f"{start_year}-{end_year}"
    return "Unknown"


# ── Main service function ─────────────────────────────────────────────────────

def get_student_portal_data(roll_no: str, db: Session) -> dict:
    """
    Aggregate portal home data for the given roll_no.

    Returns a dict compatible with StudentPortalResponse.
    Raises HTTP 404 if the student is not found.
    """
    # 1. Find student
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{roll_no}' not found",
        )

    # 2. CGPA record
    cgpa_rec = db.query(CGPA).filter(CGPA.student_id == student.id).first()
    cgpa_val = cgpa_rec.cgpa if cgpa_rec else None
    total_ch = cgpa_rec.total_credit_hours if cgpa_rec else 0.0
    semesters_done = cgpa_rec.semesters_completed if cgpa_rec else 0

    # 3. Academic status
    academic_status = _get_status(cgpa_val)

    # 4. Pending vouchers
    pending_vouchers = (
        db.query(PaymentVoucher)
        .filter(
            PaymentVoucher.roll_no == roll_no,
            PaymentVoucher.status == "pending",
        )
        .count()
    )

    # 5. Valid transcripts issued
    total_transcripts = (
        db.query(TranscriptRecord)
        .filter(
            TranscriptRecord.roll_no == roll_no,
            TranscriptRecord.is_valid.is_(True),
        )
        .count()
    )

    # 6. Infer session year
    session = _infer_session(roll_no)

    return {
        "student_name": student.student_name,
        "roll_no": student.roll_no,
        "father_name": student.father_name,
        "department": student.department,
        "session": session,
        "cgpa": cgpa_val,
        "total_credit_hours": total_ch,
        "semesters_completed": semesters_done,
        "status": academic_status,
        "pending_vouchers": pending_vouchers,
        "total_transcripts_issued": total_transcripts,
    }
