"""
AcadTrack — Upload Pipeline Pydantic Schemas
University of Loralai, Pakistan

Pydantic v2 models for request/response validation on grades upload endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Response: POST /upload ────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    """Returned immediately after a file is accepted and the pipeline starts."""
    job_id:    str
    file_name: str
    status:    str
    message:   str
    already_saved: Optional[bool] = None


# ── Response: GET /jobs/{job_id} and GET /jobs ───────────────────────────────
class JobStatusResponse(BaseModel):
    """Current state of an upload job — row counts, status, timestamps."""
    job_id:            str
    file_name:         str
    status:            str
    validation_status: Optional[str] = None
    total_rows:        int
    clean_rows:        int
    flagged_rows:      int
    blocked_rows:      int
    marks_written:     int
    error_message:     Optional[str] = None
    created_at:        datetime
    updated_at:        datetime

    model_config = ConfigDict(from_attributes=True)


# ── Response: GET /jobs/{job_id}/report ──────────────────────────────────────
class ValidationReportResponse(BaseModel):
    """Full validation report with per-row flag details."""
    job_id:            str
    status:            str          # pipeline status (e.g. "awaiting_approval")
    validation_status: str          # CLEAN | FLAGGED | BLOCKED
    summary:           dict         # {total_rows, clean, flagged, blocked}
    flagged_rows:      list[dict]   # one dict per flagged row (error_code, message, …)
    clean_rows_count:  int


# ── Request: POST /jobs/{job_id}/approve ─────────────────────────────────────
class ApproveRequest(BaseModel):
    """Coordinator provides semester context before the calculator runs."""
    semester:      int
    academic_year: str
    notes:         Optional[str] = None


# ── Response: POST /jobs/{job_id}/approve ────────────────────────────────────
class CalcResultResponse(BaseModel):
    """Summary of what the calculator agent wrote to the database."""
    job_id:        str
    marks_written: int
    semester_gpas: list[dict]
    cgpas:         list[dict]
    errors:        list[dict]


# ── Response: POST /upload/batch ──────────────────────────────────────────────
class BatchUploadResponse(BaseModel):
    """Summary returned after uploading multiple files in one request."""
    total_files: int                # how many files were sent
    succeeded:   int                # how many reached awaiting_approval
    failed:      int                # how many failed or were rejected
    jobs:        list[UploadResponse]  # one entry per file, in order


# ── Response: GET /jobs/{job_id}/parsed-data ─────────────────────────────────
class ParsedDataResponse(BaseModel):
    """Full parsed records for one job — used by the HITL editable table."""
    job_id:            str
    file_name:         str
    detected_semester: Optional[int]   = None
    detected_subject:  Optional[str]   = None
    records:           list[dict]      = []   # list of student record dicts
    total_records:     int             = 0


# ── Request: POST /jobs/{job_id}/re-validate ─────────────────────────────────
class ReValidateRequest(BaseModel):
    """Coordinator submits manually-edited records for re-validation."""
    records: list[dict]   # edited student record dicts (same shape as parser output)


# ── Response: POST /jobs/{job_id}/re-validate ────────────────────────────────
class ReValidateResponse(BaseModel):
    """Result of re-running the validation agent on edited records."""
    job_id:            str
    validation_status: str          # CLEAN | FLAGGED | BLOCKED
    total_rows:        int
    clean_rows:        int
    flagged_rows:      int
    blocked_rows:      int
    errors:            list[dict]   = []
    warnings:          list[dict]   = []