"""
AcadTrack — Grades Router
University of Loralai, Pakistan

Endpoints:
  POST   /api/v1/grades/upload                   — coordinator, super_admin
  GET    /api/v1/grades/jobs                      — coordinator, hod, super_admin
  GET    /api/v1/grades/jobs/{job_id}             — coordinator, hod, super_admin
  GET    /api/v1/grades/jobs/{job_id}/report      — coordinator, hod, super_admin
  POST   /api/v1/grades/jobs/{job_id}/approve     — coordinator, super_admin
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.upload_model import UploadJob
from backend.schemas.upload_schemas import (
    ApproveRequest,
    BatchUploadResponse,
    CalcResultResponse,
    JobStatusResponse,
    ParsedDataResponse,
    ReValidateRequest,
    ReValidateResponse,
    UploadResponse,
    ValidationReportResponse,
)
from backend.services import pipeline_service
from backend.services.audit_service import log_action
from backend.utils.auth_utils import get_current_user, require_role

router = APIRouter(prefix="/api/v1/grades", tags=["Grades"])

# Allowed file extensions
_ALLOWED_EXTENSIONS = {".xlsx", ".csv"}


def _ext(filename: str) -> str:
    """Return the lowercase extension of *filename*, including the dot."""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _job_or_404(job_id: str, db: Session) -> UploadJob:
    """Load an UploadJob by job_id or raise HTTP 404."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return job


def _job_to_status(job: UploadJob) -> JobStatusResponse:
    """Convert an UploadJob ORM row to a JobStatusResponse schema."""
    return JobStatusResponse.model_validate(job)


# ── POST /upload ──────────────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a mark-sheet and run parse + validate",
)
async def upload_grades(
    file:           UploadFile = File(..., description="Excel (.xlsx) or CSV file"),
    subject_hint:   Optional[str] = Form(None, description="Hint for the parser, e.g. 'Mathematics'"),
    department:     str          = Form("CS", description="Department code, e.g. 'CS'"),
    semester_label: Optional[str] = Form(None, description="Label like 'Semester 3'"),
    db:             Session       = Depends(get_db),
    current_user                  = Depends(require_role("coordinator", "super_admin")),
):
    """
    Accept an Excel or CSV mark-sheet, persist an UploadJob, then run
    Agent 1 (parser) and Agent 2 (validator) synchronously.

    The job transitions to **awaiting_approval** (CLEAN/FLAGGED) or **failed**
    (BLOCKED / parser error).  Check the returned *job_id* with GET /jobs/{job_id}.
    """
    # 1. Validate file extension
    if _ext(file.filename or "") not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx and .csv files are allowed",
        )

    # 2. Read file bytes
    file_bytes = await file.read()

    # 3. Generate a UUID4 job_id
    job_id = str(uuid.uuid4())

    # 4. Create UploadJob record
    job = UploadJob(
        job_id      = job_id,
        uploaded_by = current_user.username,
        file_name   = file.filename or "unknown",
        subject_hint= subject_hint,
        department  = department,
        status      = "pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 5. Run Agent 1 + Agent 2 via the pipeline service
    pipeline_service.run_parse_and_validate(
        job_id        = job_id,
        file_bytes    = file_bytes,
        filename      = file.filename or "unknown",
        subject_hint  = subject_hint,
        department    = department,
        semester_label= semester_label,
        db_session    = db,
    )

    # Reload to get the latest status after the pipeline ran
    db.refresh(job)

    log_action(
        db,
        username=current_user.username,
        user_role=current_user.role,
        action="uploaded_file",
        entity_type="upload_job",
        entity_id=job_id,
        details={"file_name": file.filename},
        user_id=current_user.id,
    )

    # Check if a completed job with the same file name already exists
    is_already_saved = db.query(UploadJob).filter(
        UploadJob.file_name == file.filename,
        UploadJob.status == "completed"
    ).first() is not None

    return UploadResponse(
        job_id    = job_id,
        file_name = job.file_name,
        status    = job.status,
        message   = (
            "File parsed and validated — awaiting coordinator approval"
            if job.status == "awaiting_approval"
            else f"Pipeline finished with status: {job.status}"
        ),
        already_saved = is_already_saved,
    )


# ── POST /upload/batch ───────────────────────────────────────────────────────
@router.post(
    "/upload/batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload multiple mark-sheet files at once",
)
async def upload_grades_batch(
    files:          list[UploadFile] = File(..., description="Select multiple .xlsx or .csv files"),
    subject_hint:   Optional[str]   = Form(None, description="Hint for the parser, e.g. 'Mathematics'"),
    department:     str             = Form("CS", description="Department code, e.g. 'CS'"),
    semester_label: Optional[str]   = Form(None, description="Label like 'Semester 3'"),
    db:             Session         = Depends(get_db),
    current_user                    = Depends(require_role("coordinator", "super_admin")),
):
    """
    Upload **many** Excel or CSV mark-sheets in a single request.

    Each file is processed independently through the full parse → validate
    pipeline and gets its own `job_id`.  This means:

    - One bad file does not stop the others from being processed.
    - You can approve each file separately using its own `job_id`.
    - The response tells you exactly which files succeeded and which failed.

    After this call, use `GET /api/v1/grades/jobs` to see all jobs at once.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided. Please select at least one file.",
        )

    job_responses: list[UploadResponse] = []
    succeeded = 0
    failed    = 0

    for file in files:

        # ── 1. Extension check for this file ──────────────────────────────────
        if _ext(file.filename or "") not in _ALLOWED_EXTENSIONS:
            job_responses.append(UploadResponse(
                job_id    = "N/A",
                file_name = file.filename or "unknown",
                status    = "rejected",
                message   = "Skipped — only .xlsx and .csv files are allowed",
            ))
            failed += 1
            continue

        # ── 2. Read bytes ──────────────────────────────────────────────────────
        file_bytes = await file.read()

        # ── 3. Create job record ───────────────────────────────────────────────
        job_id = str(uuid.uuid4())
        job = UploadJob(
            job_id      = job_id,
            uploaded_by = current_user.username,
            file_name   = file.filename or "unknown",
            subject_hint= subject_hint,
            department  = department,
            status      = "pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # ── 4. Run pipeline for this file ──────────────────────────────────────
        pipeline_service.run_parse_and_validate(
            job_id        = job_id,
            file_bytes    = file_bytes,
            filename      = file.filename or "unknown",
            subject_hint  = subject_hint,
            department    = department,
            semester_label= semester_label,
            db_session    = db,
        )

        db.refresh(job)

        # ── 5. Count result ────────────────────────────────────────────────────
        if job.status == "failed":
            failed += 1
        else:
            succeeded += 1

        is_already_saved = db.query(UploadJob).filter(
            UploadJob.file_name == file.filename,
            UploadJob.status == "completed",
            UploadJob.job_id != job_id
        ).first() is not None

        job_responses.append(UploadResponse(
            job_id    = job_id,
            file_name = job.file_name,
            status    = job.status,
            message   = (
                "Parsed and validated — awaiting coordinator approval"
                if job.status == "awaiting_approval"
                else f"Pipeline finished with status: {job.status}"
            ),
            already_saved = is_already_saved,
        ))

    # ── Run content-based duplicate detection across all jobs ─────────────────
    # Build fingerprints from each job's parse_result (already stored in DB)
    import json as _json
    from backend.services.content_analysis import detect_duplicates_in_batch

    fingerprints = []
    for resp in job_responses:
        if resp.job_id == "N/A":
            continue
        try:
            _job = db.query(UploadJob).filter(UploadJob.job_id == resp.job_id).first()
            if _job and _job.parse_result:
                _pd = _json.loads(_job.parse_result)
                _fp = _pd.get("content_fingerprint", {})
                if _fp:
                    fingerprints.append({
                        **_fp,
                        "job_id":        resp.job_id,
                        "job_filename":  resp.file_name,
                    })
        except Exception:
            pass

    dup_warnings: dict[str, dict] = {}   # job_id → warning dict
    if len(fingerprints) > 1:
        dups = detect_duplicates_in_batch(fingerprints)
        for d in dups:
            dup_warnings[d["job_id"]] = d

    # Rebuild responses with duplicate_warning injected
    final_responses = []
    for resp in job_responses:
        dw = dup_warnings.get(resp.job_id)
        if dw:
            final_responses.append(UploadResponse(
                job_id    = resp.job_id,
                file_name = resp.file_name,
                status    = resp.status,
                message   = (
                    f"[DUPLICATE WARNING] {dw['message']} "
                    f"— {resp.message}"
                ),
                already_saved = resp.already_saved,
            ))
        else:
            final_responses.append(resp)

    return BatchUploadResponse(
        total_files = len(files),
        succeeded   = succeeded,
        failed      = failed,
        jobs        = final_responses,
    )


# ── GET /jobs ─────────────────────────────────────────────────────────────────
@router.get(
    "/jobs",
    response_model=list[JobStatusResponse],
    summary="List all upload jobs (newest first)",
)
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by pipeline status"),
    db:            Session       = Depends(get_db),
    current_user                 = Depends(require_role("coordinator", "hod", "super_admin")),
):
    """
    Return all UploadJob rows ordered by creation time (descending).
    Use the optional *status* query parameter to filter by pipeline status,
    e.g. ``?status=awaiting_approval``.
    """
    query = db.query(UploadJob).order_by(UploadJob.created_at.desc())
    if status_filter:
        query = query.filter(UploadJob.status == status_filter)

    jobs = query.all()
    return [_job_to_status(j) for j in jobs]


# ── GET /jobs/{job_id} ────────────────────────────────────────────────────────
@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get the current status of a single upload job",
)
def get_job_status(
    job_id: str,
    db:     Session = Depends(get_db),
    current_user    = Depends(require_role("coordinator", "hod", "super_admin")),
):
    """
    Return the current pipeline status, row counts, and timestamps for the
    given *job_id*.  Raises 404 if the job does not exist.
    """
    job = _job_or_404(job_id, db)
    return _job_to_status(job)


# ── GET /jobs/{job_id}/report ─────────────────────────────────────────────────
@router.get(
    "/jobs/{job_id}/report",
    response_model=ValidationReportResponse,
    summary="View the full validation report for a job",
)
def get_validation_report(
    job_id: str,
    db:     Session = Depends(get_db),
    current_user    = Depends(require_role("coordinator", "hod", "super_admin")),
):
    """
    Return the full validation report — summary counts, every flagged row
    with its error code and severity, and the total count of clean rows.

    Raises 404 if the job does not exist.
    Raises 400 if validation has not yet completed for this job.
    """
    import json

    job = _job_or_404(job_id, db)

    if not job.validation_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Validation has not completed for job '{job_id}' "
                f"(current status: '{job.status}')"
            ),
        )

    try:
        validation_data = json.loads(job.validation_result)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored validation result is corrupt — please re-upload the file",
        )

    flagged_rows = validation_data.get("flagged_rows", [])
    # FlaggedRow objects were serialised with model_dump(); normalise to plain dicts.
    flagged_dicts: list[dict] = []
    for row in flagged_rows:
        if isinstance(row, dict):
            flagged_dicts.append(row)

    return ValidationReportResponse(
        job_id            = job_id,
        status            = job.status,
        validation_status = job.validation_status or "UNKNOWN",
        summary           = validation_data.get("summary", {}),
        flagged_rows      = flagged_dicts,
        clean_rows_count  = job.clean_rows,
    )


# ── POST /jobs/{job_id}/approve ───────────────────────────────────────────────
@router.post(
    "/jobs/{job_id}/approve",
    response_model=CalcResultResponse,
    summary="Approve a validated job and trigger GPA calculation",
)
def approve_job(
    job_id: str,
    body:   ApproveRequest,
    db:     Session = Depends(get_db),
    current_user    = Depends(require_role("coordinator", "super_admin")),
):
    """
    Approve a job that is **awaiting_approval** and immediately run
    Agent 3 (calculator) to write marks and (re)compute GPA / CGPA.

    Business rules enforced here:
    - The job must be in ``awaiting_approval`` status.
    - The job's validation_status must not be ``BLOCKED``.

    On success the job transitions to ``completed`` and the response
    contains the counts of marks written plus updated GPA rows.
    """
    # 1. Load job
    job = _job_or_404(job_id, db)

    # 2. Guard: must be awaiting approval
    if job.status != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Job is not awaiting approval "
                f"(current status: '{job.status}')"
            ),
        )

    # 3. Guard: cannot approve a BLOCKED job
    if job.validation_status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve a BLOCKED job — fix the source file and re-upload",
        )

    # 4. Stamp approval metadata
    job.status          = "approved"
    job.semester        = body.semester
    job.academic_year   = body.academic_year
    job.approved_by_user= current_user.username
    job.approved_at     = datetime.now(timezone.utc)
    job.updated_at      = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    # 5. Run Agent 3 (calculator)
    calc_outcome = pipeline_service.run_calculator(
        job_id       = job_id,
        semester     = body.semester,
        academic_year= body.academic_year,
        approved_by  = current_user.username,
        db_session   = db,
    )

    if not calc_outcome.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calculator failed: {calc_outcome.get('error', 'Unknown error')}",
        )

    result = calc_outcome["result"]

    log_action(
        db,
        username=current_user.username,
        user_role=current_user.role,
        action="approved_grades",
        entity_type="upload_job",
        entity_id=job_id,
        details={
            "semester": body.semester,
            "marks_written": result.get("marks_written", 0),
        },
        user_id=current_user.id,
    )

    # 6. Return summary
    return CalcResultResponse(
        job_id        = job_id,
        marks_written = result.get("marks_written", 0),
        semester_gpas = result.get("semester_gpas", []),
        cgpas         = result.get("cgpas", []),
        errors        = result.get("errors", []),
    )


# ── GET /jobs/{job_id}/parsed-data ────────────────────────────────────────────
@router.get(
    "/jobs/{job_id}/parsed-data",
    response_model=ParsedDataResponse,
    summary="Return the parsed student records for HITL inline editing",
)
def get_parsed_data(
    job_id: str,
    db:     Session = Depends(get_db),
    current_user    = Depends(require_role("coordinator", "super_admin")),
):
    """
    Return the raw parsed records stored in the UploadJob so the coordinator
    can review and inline-edit them in the HITL review tab.

    Semester detection priority:
      1. Filename pattern  (S2-Pakistan.xlsx → 2,  Semester_6.xlsx → 6)
      2. Content scan of parse_result records (subject_name metadata row)
    """
    import json, re as _re

    job = _job_or_404(job_id, db)

    if not job.parse_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No parsed data available for job '{job_id}'",
        )

    try:
        parse_data = json.loads(job.parse_result)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored parse result is corrupt — please re-upload the file",
        )

    records = parse_data.get("records", [])

    # ── Semester ──────────────────────────────────────────────────────────────
    # 1. Content-based (stored at upload time by pipeline_service — preferred)
    detected_semester: int | None = None
    detected_subject:  str | None = None

    sem_stored = parse_data.get("detected_semester")
    if sem_stored is not None:
        try:
            detected_semester = int(sem_stored)
        except (ValueError, TypeError):
            pass

    # 2. Legacy filename fallback (old jobs uploaded before content detection)
    if detected_semester is None:
        import re as _re2
        _stem2 = _re2.sub(r"\.[^.]+$", "", job.file_name or "")
        for _p in [
            _re2.compile(r"^[Ss](\d)\b"),
            _re2.compile(r"\bSem(?:ester)?[_\s-]?(\d)\b", _re2.I),
            _re2.compile(r"[-_\s](\d)[-_\s.]"),
        ]:
            _m2 = _p.search(_stem2)
            if _m2:
                _n2 = int(_m2.group(1))
                if 1 <= _n2 <= 8:
                    detected_semester = _n2
                    break

    # 3. Subject from first record
    if records:
        subj = records[0].get("subject_name")
        if subj:
            detected_subject = str(subj)

    return ParsedDataResponse(
        job_id            = job_id,
        file_name         = job.file_name,
        detected_semester = detected_semester,
        detected_subject  = detected_subject,
        records           = records,
        total_records     = len(records),
    )



# ── POST /jobs/{job_id}/re-validate ──────────────────────────────────────────
@router.post(
    "/jobs/{job_id}/re-validate",
    response_model=ReValidateResponse,
    summary="Re-run validation on coordinator-edited records",
)
def re_validate_job(
    job_id: str,
    body:   ReValidateRequest,
    db:     Session = Depends(get_db),
    current_user    = Depends(require_role("coordinator", "super_admin")),
):
    """
    Accept a list of manually-edited student records (same shape as parser output)
    and re-run the validation agent on them.

    The updated validation result is persisted to the job so a subsequent
    approve call will use the corrected records.
    """
    outcome = pipeline_service.run_revalidate(
        job_id         = job_id,
        edited_records = body.records,
        db_session     = db,
    )

    if not outcome.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=outcome.get("error", "Re-validation failed"),
        )

    report = outcome["report"]
    summary = report.get("summary", {})

    # Collect errors (BLOCKED) and warnings (FLAGGED) for the response
    all_flagged: list[dict] = report.get("flagged_rows", [])
    errors   = [f for f in all_flagged if f.get("severity") == "BLOCKED"]
    warnings = [f for f in all_flagged if f.get("severity") in ("FLAGGED", "INFO")]

    log_action(
        db,
        username=current_user.username,
        user_role=current_user.role,
        action="re_validated_job",
        entity_type="upload_job",
        entity_id=job_id,
        details={"validation_status": report.get("status")},
        user_id=current_user.id,
    )

    return ReValidateResponse(
        job_id            = job_id,
        validation_status = report.get("status", "BLOCKED"),
        total_rows        = summary.get("total_rows", 0),
        clean_rows        = summary.get("clean", 0),
        flagged_rows      = summary.get("flagged", 0),
        blocked_rows      = summary.get("blocked", 0),
        errors            = [{"row": e.get("row_index"), "message": e.get("error_message"), "field": e.get("error_code")} for e in errors],
        warnings          = [{"row": w.get("row_index"), "message": w.get("error_message"), "field": w.get("error_code")} for w in warnings],
    )