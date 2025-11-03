"""
AcadTrack — TranscriptRecord Model
University of Loralai, Pakistan

Stores every generated transcript with its QR verification token.
Each row is one issued transcript, allowing revocation and scan tracking.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text
)

from backend.database import Base


class TranscriptRecord(Base):
    """
    One row = one issued transcript PDF.

    verification_token  — short hash embedded in the QR code and URL
    student_id          — FK to Student (informational; no FK constraint
                          because Student lives in the src/ Base)
    is_valid            — False once revoked by admin
    scan_count          — incremented on every public /verify/{token} hit
    """
    __tablename__ = "transcript_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── QR verification ───────────────────────────────────────────────────────
    verification_token = Column(
        String(40), unique=True, nullable=False, index=True
    )

    # ── Student identity (denormalised for fast lookup) ───────────────────────
    student_id    = Column(Integer, nullable=False)
    roll_no       = Column(String(100), nullable=False)
    student_name  = Column(String(200), nullable=False)

    # ── What was issued ───────────────────────────────────────────────────────
    semester_range     = Column(String(50), nullable=False)   # "1-4" | "all"
    cgpa_at_issue      = Column(Float, nullable=True)
    total_credit_hours = Column(Float, nullable=True)
    semesters_count    = Column(Integer, default=0)
    is_unofficial      = Column(Boolean, default=True)

    # ── Who issued it ─────────────────────────────────────────────────────────
    issued_by  = Column(String(50), nullable=False)
    issued_at  = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Scan tracking ─────────────────────────────────────────────────────────
    scan_count      = Column(Integer, default=0)
    last_scanned_at = Column(DateTime, nullable=True)
    last_scanned_ip = Column(String(50), nullable=True)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    is_valid = Column(Boolean, default=True)
    notes    = Column(Text, nullable=True)
