"""
AcadTrack — Upload Job Model
University of Loralai, Pakistan

Tracks every file upload through the parse → validate → approve → calculate
pipeline.  One row per upload attempt.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from backend.database import Base


class UploadJob(Base):
    """
    Represents a single file-upload attempt and its progression through the
    three-agent pipeline.

    Status flow (happy path):
        pending → parsing → validating → awaiting_approval → approved
               → calculating → completed

    Error exits:
        parsing     → failed   (parser returned ERROR)
        validating  → failed   (validation_status == BLOCKED)
        calculating → failed   (calculator raised an unhandled exception)
    """

    __tablename__ = "upload_jobs"

    # ── Identity ───────────────────────────────────────────────────────────
    id               = Column(Integer, primary_key=True, autoincrement=True)
    job_id           = Column(String(36), unique=True, nullable=False, index=True)
    #                  UUID4 string, e.g. "a1b2c3d4-1234-5678-abcd-ef0123456789"

    # ── Who / What ─────────────────────────────────────────────────────────
    uploaded_by      = Column(String(50),  nullable=False)
    file_name        = Column(String(255), nullable=False)
    subject_hint     = Column(String(200), nullable=True)
    department       = Column(String(100), nullable=True)
    semester         = Column(Integer,     nullable=True)
    academic_year    = Column(String(20),  nullable=True)

    # ── Pipeline status ────────────────────────────────────────────────────
    # Values: pending | parsing | validating | awaiting_approval |
    #         approved | calculating | completed | failed
    status           = Column(String(20), nullable=False, default="pending")

    # Values: CLEAN | FLAGGED | BLOCKED  (null until validation finishes)
    validation_status = Column(String(20), nullable=True)

    # ── Row counters ───────────────────────────────────────────────────────
    total_rows       = Column(Integer, default=0)
    clean_rows       = Column(Integer, default=0)
    flagged_rows     = Column(Integer, default=0)
    blocked_rows     = Column(Integer, default=0)
    marks_written    = Column(Integer, default=0)

    # ── Human-readable error ───────────────────────────────────────────────
    error_message    = Column(Text, nullable=True)

    # ── Agent output blobs (JSON strings) ─────────────────────────────────
    parse_result      = Column(Text, nullable=True)
    validation_result = Column(Text, nullable=True)
    calc_result       = Column(Text, nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at       = Column(DateTime, default=func.now())
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())
    approved_at      = Column(DateTime, nullable=True)
    approved_by_user = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<UploadJob {self.job_id!r} status={self.status!r}>"
