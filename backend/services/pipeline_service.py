"""
AcadTrack — Pipeline Service
University of Loralai, Pakistan

Orchestrates the three-agent pipeline and persists every state transition to
the UploadJob row.  The router delegates all agent calls to this module.

Agent call signatures (never modify the agents themselves):
  parse_file_to_records(file_bytes, filename, subject_hint, department) → dict
  validate_records(records, semester)                                  → ValidationReport
  calculator_agent_node(state)                                         → dict
"""

import json
import logging
from datetime import datetime, timezone

from src.agents.parser_agent import parse_file_to_records
from src.agents.validation_agent import validate_records
from src.agents.calculator_agent import calculator_agent_node

from backend.config import settings
from backend.models.upload_model import UploadJob

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> datetime:
    """Current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _set(job: UploadJob, **fields) -> None:
    """Apply keyword updates to a job object (no commit — caller does that)."""
    for key, value in fields.items():
        setattr(job, key, value)
    job.updated_at = _now()


def _safe_json(obj) -> str:
    """Serialise to JSON, coercing types that the default encoder rejects."""
    return json.dumps(obj, default=str)


# ── Public service functions ──────────────────────────────────────────────────

def run_parse_and_validate(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    subject_hint: str | None,
    department: str,
    semester_label: str | None,
    db_session,
) -> dict:
    """
    Agent 1 (parser) → Agent 2 (validator).

    Drives the job through:
      pending → parsing → validating → awaiting_approval   (CLEAN / FLAGGED)
      pending → parsing → validating → failed               (BLOCKED)
      pending → parsing → failed                            (parser ERROR)

    Returns:
      {"success": True,  "report": <report dict>}   on success
      {"success": False, "error":  <message>}        on failure
    """
    job: UploadJob | None = (
        db_session.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    )
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' not found in database"}

    # ── Step 1: Parse ─────────────────────────────────────────────────────────
    try:
        _set(job, status="parsing")
        db_session.commit()

        parse_result = parse_file_to_records(
            file_bytes=file_bytes,
            filename=filename,
            subject_hint=subject_hint,
            department=department,
        )
        job.parse_result = _safe_json(parse_result)

    except Exception as exc:
        logger.exception("Parser agent raised an exception for job %s", job_id)
        _set(job, status="failed", error_message=f"Parser exception: {exc}")
        db_session.commit()
        return {"success": False, "error": str(exc)}

    if parse_result.get("status") == "ERROR":
        warnings = parse_result.get("warnings", ["Unknown parser error"])
        error_msg = f"Parser error: {'; '.join(str(w) for w in warnings)}"
        _set(job, status="failed", error_message=error_msg)
        db_session.commit()
        return {"success": False, "error": error_msg}

    # ── Step 2: Validate ──────────────────────────────────────────────────────
    try:
        _set(job, status="validating")
        db_session.commit()

        records = parse_result.get("records", [])
        report = validate_records(records=records, semester=semester_label)

    except Exception as exc:
        logger.exception("Validation agent raised an exception for job %s", job_id)
        _set(job, status="failed", error_message=f"Validation exception: {exc}")
        db_session.commit()
        return {"success": False, "error": str(exc)}

    # Persist validation output
    job.validation_result = _safe_json(report.model_dump())
    job.validation_status = report.status
    job.total_rows        = report.summary.total_rows
    job.clean_rows        = report.summary.clean
    job.flagged_rows      = report.summary.flagged
    job.blocked_rows      = report.summary.blocked
    job.updated_at        = _now()

    if report.status == "BLOCKED":
        job.status = "failed"
        job.error_message = (
            f"Validation BLOCKED: {report.summary.blocked} critical error(s) found. "
            "Correct the source file and re-upload."
        )
    else:
        # CLEAN or FLAGGED — coordinator decides whether to approve
        job.status = "awaiting_approval"

    db_session.commit()
    return {"success": True, "report": report.model_dump()}


def run_calculator(
    job_id: str,
    semester: int,
    academic_year: str,
    approved_by: str,
    db_session,
) -> dict:
    """
    Agent 3 (calculator).

    Drives the job through:
      approved → calculating → completed

    The job MUST be in "approved" status before this is called.

    Returns:
      {"success": True,  "result": <calc result dict>}
      {"success": False, "error":  <message>}
    """
    # ── Step 1: Load and guard ─────────────────────────────────────────────────
    job: UploadJob | None = (
        db_session.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    )
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' not found in database"}

    if job.status != "approved":
        return {
            "success": False,
            "error": f"Job is not approved (current status: '{job.status}')",
        }

    # ── Step 2: Extract clean rows from stored validation report ──────────────
    if not job.validation_result:
        return {"success": False, "error": "No validation result stored for this job"}

    try:
        validation_data = json.loads(job.validation_result)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Could not parse stored validation result: {exc}"}

    clean_rows = validation_data.get("clean_rows", [])

    # ── Step 3: Mark as calculating ───────────────────────────────────────────
    _set(job, status="calculating")
    db_session.commit()

    # ── Step 4: Run the calculator agent ──────────────────────────────────────
    state = {
        "validated_records": clean_rows,
        "semester":          semester,
        "academic_year":     academic_year,
        "db_url":            settings.DATABASE_URL,
        "approved_by":       approved_by,
        "source_file":       job.file_name,
        "errors":            [],
    }

    try:
        result = calculator_agent_node(state)
    except Exception as exc:
        logger.exception("Calculator agent raised an exception for job %s", job_id)
        _set(job, status="failed", error_message=f"Calculator exception: {exc}")
        db_session.commit()
        return {"success": False, "error": str(exc)}

    # ── Step 5: Persist results ────────────────────────────────────────────────
    job.calc_result    = _safe_json(result)
    job.status         = "completed"
    job.marks_written  = result.get("marks_written", 0)
    job.updated_at     = _now()
    db_session.commit()

    return {"success": True, "result": result}
