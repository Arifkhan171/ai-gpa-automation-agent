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
import pandas as pd
from backend.config import settings
from backend.models.upload_model import UploadJob
from backend.models.user_model import User  # for roll_no enrichment
from backend.services.content_analysis import (
    extract_semester_from_content,
    compute_content_fingerprint,
)

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

    # ── Step 1: Parse ──────────────────────────────────────────────────────
    try:
        _set(job, status="parsing")
        db_session.commit()

        parse_result = parse_file_to_records(
            file_bytes=file_bytes,
            filename=filename,
            subject_hint=subject_hint,
            department=department,
        )

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

    # ── Step 1a: Merge extra Excel columns into records ───────────────────
    #
    # The parser agent only stores the 8 known mapped fields.
    # Any extra columns in the Excel (Semester, Program, Section, CNIC, etc.)
    # are dropped by the parser.  We re-read the raw sheet here and attach
    # those extra columns back to each record so the HITL table can show them.
    # We match by row position (index) since the parser preserves row order.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        import io as _io, re as _re
        from pathlib import Path as _Path
        _KNOWN = {
            "student_name", "roll_no", "father_name", "subject_name",
            "total_marks", "obtained_marks", "credit_hours", "department",
            "has_issues", "parse_warnings",
        }
        _ext = _Path(filename).suffix.lower()
        _buf = _io.BytesIO(file_bytes)

        # Read raw to find header row (same 25-row scan as parser)
        _df_raw = (
            pd.read_csv(_buf, header=None, dtype=str)
            if _ext == ".csv"
            else pd.read_excel(_buf, header=None, dtype=str, engine="openpyxl")
        )
        # Find best header row by word overlap with known column names
        _col_words = {
            "student", "name", "roll", "marks", "obtained", "total",
            "credit", "semester", "subject", "father", "department",
        }
        _best, _best_score = 0, -1
        for _i in range(min(25, len(_df_raw))):
            _words = {
                w for v in _df_raw.iloc[_i].values
                if pd.notna(v)
                for w in _re.sub(r"\s+", " ", str(v).strip().lower()).split()
            }
            _s = len(_words & _col_words)
            if _s > _best_score:
                _best_score, _best = _s, _i

        if _best_score >= 1:
            _buf2 = _io.BytesIO(file_bytes)
            _df = (
                pd.read_csv(_buf2, header=_best, dtype=str)
                if _ext == ".csv"
                else pd.read_excel(_buf2, header=_best, dtype=str, engine="openpyxl")
            )
            _df.dropna(how="all", inplace=True)
            _df.dropna(axis=1, how="all", inplace=True)
            _df.reset_index(drop=True, inplace=True)

            # Normalise column names
            _col_norm = {
                _re.sub(r"\s+", " ", str(c).strip().lower()): str(c)
                for c in _df.columns
            }

            # Known aliases (same as parser) so we can skip them
            # NOTE: we intentionally do NOT include 'program'/'programme' here
            # even though the parser maps them to 'department'.  We want users
            # to still see their original 'Program' column in the HITL table.
            _KNOWN_ALIASES = {
                "student name", "name", "student", "roll no", "roll number",
                "rollno", "reg no", "registration no", "father name",
                "father's name", "fathers name", "subject name", "subject",
                "course name", "total marks", "total", "max marks",
                "obtained marks", "obtained", "marks", "credit hours",
                "credits", "ch", "credit hour", "department", "dept",
                "faculty",
            }


            # Extra columns = all columns whose normalised name is not a known alias
            _extra_cols = [
                raw_col for norm, raw_col in _col_norm.items()
                if norm not in _KNOWN_ALIASES
            ]

            if _extra_cols:
                parsed_records = parse_result.get("records", [])
                for _row_idx, _rec in enumerate(parsed_records):
                    if _row_idx >= len(_df):
                        break
                    for _ec in _extra_cols:
                        _val = _df.iloc[_row_idx].get(_ec)
                        if pd.isna(_val) or str(_val).strip() in ("", "nan", "NaN", "None"):
                            _rec[_ec] = None
                        else:
                            _rec[_ec] = str(_val).strip()
                parse_result["records"] = parsed_records
                logger.info(
                    "Job %s: merged %d extra columns into records: %s",
                    job_id, len(_extra_cols),
                    [str(c) for c in _extra_cols],
                )

    except Exception as _exc:
        logger.warning(
            "Job %s: extra-column merge failed (non-fatal): %s", job_id, _exc
        )
        # Non-fatal — records still have the 8 parser fields, just no extras

    # ── Step 1b: Enrich parse_result with content-based semester detection ───
    #
    # Priority order:
    #   1. Content scan of the Excel metadata rows (most reliable)
    #   2. Filename pattern (fallback)
    #   3. None (coordinator assigns manually in HITL stage)
    # ─────────────────────────────────────────────────────────────────────────
    content_semester: int | None = None
    try:
        content_semester = extract_semester_from_content(file_bytes, filename)
        if content_semester:
            logger.info(
                "Job %s: semester %d detected from Excel content",
                job_id, content_semester,
            )
    except Exception as exc:
        logger.warning("Job %s: content semester detection failed: %s", job_id, exc)

    # If content didn't find it, try the filename (mirror of parser_agent logic)
    if content_semester is None:
        import re as _re
        _fname_patterns = [
            _re.compile(r"^[Ss](\d)\b"),
            _re.compile(r"\bSem(?:ester)?[_\s-]?(\d)\b", _re.I),
            _re.compile(r"[-_\s](\d)[-_\s.]"),
        ]
        _stem = _re.sub(r"\.[^.]+$", "", filename)
        for _pat in _fname_patterns:
            _m = _pat.search(_stem)
            if _m:
                _n = int(_m.group(1))
                if 1 <= _n <= 8:
                    content_semester = _n
                    logger.info(
                        "Job %s: semester %d detected from filename '%s'",
                        job_id, content_semester, filename,
                    )
                    break

    # Build content fingerprint for duplicate detection
    records_for_fp = parse_result.get("records", [])
    content_fp = compute_content_fingerprint(records_for_fp)

    # Inject both into parse_result before storing
    parse_result["detected_semester"] = content_semester
    parse_result["content_fingerprint"] = content_fp

    job.parse_result = _safe_json(parse_result)

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

    # ── Step 2: Build validated_records for the calculator ───────────────────
    #
    # Strategy (in priority order):
    #   A) parse_result records — all rows the parser produced, minus any where
    #      has_issues=True (parse-level failures). FLAGGED rows (validation
    #      warnings) are intentionally INCLUDED — they have real marks that
    #      should count toward the GPA. Only hard parser failures are excluded.
    #   B) clean_rows from validation_result — fallback if parse_result is missing.
    #
    # Why not use validation clean_rows directly?
    #   The validator's clean_rows list excludes FLAGGED rows (rows with warnings).
    #   If a student has a minor warning (e.g. roll_no format) their entire
    #   semester mark would be lost from the GPA — which is wrong.
    # ─────────────────────────────────────────────────────────────────────────
    validated_records: list[dict] = []

    if job.parse_result:
        try:
            parse_data = json.loads(job.parse_result)
            all_parsed = parse_data.get("records", [])
            # Include all rows that don't have hard parser-level failures
            validated_records = [
                r for r in all_parsed
                if not r.get("has_issues", False)
            ]
            logger.info(
                "Job %s: using %d/%d parse_result records for calculator",
                job_id, len(validated_records), len(all_parsed),
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Job %s: could not parse parse_result: %s", job_id, exc)

    if not validated_records and job.validation_result:
        # Fallback: use clean_rows from validation report
        try:
            validation_data = json.loads(job.validation_result)
            validated_records = validation_data.get("clean_rows", [])
            logger.info(
                "Job %s: fallback — using %d clean_rows from validation_result",
                job_id, len(validated_records),
            )
        except (json.JSONDecodeError, Exception) as exc:
            return {"success": False, "error": f"Could not parse stored validation result: {exc}"}

    if not validated_records:
        return {"success": False, "error": "No records available for GPA calculation"}

    # ── Step 3: Mark as calculating ───────────────────────────────────────────
    _set(job, status="calculating")
    db_session.commit()

    # ── Step 3b: Purge old marks for the same subject + semester ─────────────
    #
    # Problem this solves:
    #   If the same subject (e.g. "Calculus", Semester 1) was uploaded before,
    #   those old Mark rows are still in the DB. Re-uploading a CORRECTED sheet
    #   with 19 students would upsert the overlapping 18 but the student who
    #   was removed is still counted in the semester GPA — giving a wrong result.
    #
    # Fix: delete ALL Mark rows for (subject_name, semester, academic_year)
    #      BEFORE inserting the new ones.  The calculator then recalculates from
    #      a clean slate.  This makes the new file the authoritative source.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        from src.models.database_models import Mark, Subject, Student
        from sqlalchemy import create_engine as _ce, select as _sel, or_ as _or
        from sqlalchemy.orm import Session as _OrmSession

        _engine = _ce(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False}
            if settings.DATABASE_URL.startswith("sqlite") else {},
        )
        _purge_session = _OrmSession(_engine)

        # Determine subject name from first valid record
        subject_name_for_purge: str | None = None
        for _rec in validated_records:
            _sn = _rec.get("subject_name")
            if _sn and str(_sn).strip():
                subject_name_for_purge = str(_sn).strip()
                break

        if subject_name_for_purge:
            # Find subject row
            _subj_row = _purge_session.execute(
                _sel(Subject).where(Subject.subject_name == subject_name_for_purge)
            ).scalar_one_or_none()

            # Extract batch prefixes from the uploaded records to scope the purge
            # e.g., 'UoL/CS-F-22/001-BS' -> 'UoL/CS-F-22/'
            batch_prefixes = set()
            for _rec in validated_records:
                rn = str(_rec.get("roll_no") or "")
                if "/" in rn:
                    parts = rn.split("/")
                    if len(parts) >= 2:
                        batch_prefixes.add(f"{parts[0]}/{parts[1]}/")

            if _subj_row and batch_prefixes:
                # Find all marks for this subject + semester + academic_year
                _marks_query = _sel(Mark).join(Student).where(
                    Mark.subject_id    == _subj_row.id,
                    Mark.semester      == semester,
                    Mark.academic_year == academic_year,
                )
                
                # Filter by the batches present in this file
                batch_filters = [Student.roll_no.startswith(p) for p in batch_prefixes]
                _marks_query = _marks_query.where(_or(*batch_filters))
                
                _marks_to_del = _purge_session.execute(_marks_query).scalars().all()

                if _marks_to_del:
                    logger.info(
                        "Job %s: purging %d old marks for subject '%s' "
                        "semester=%d year=%s before re-insert",
                        job_id, len(_marks_to_del),
                        subject_name_for_purge, semester, academic_year,
                    )
                    for _m in _marks_to_del:
                        _purge_session.delete(_m)
                    _purge_session.commit()

        _purge_session.close()

    except Exception as purge_exc:
        logger.warning(
            "Job %s: mark purge step failed (non-fatal, proceeding): %s",
            job_id, purge_exc,
        )
        # Non-fatal — calculator upsert will still handle individual rows correctly

    # ── Step 4: Run the calculator agent ──────────────────────────────────────

    state = {
        "validated_records": validated_records,
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

    # ── Step 5: Enrich GPA results with roll_no + student_name ───────────────
    #
    # The calculator agent only stores student_id in its output dicts.
    # The API response needs roll_no so the frontend can display a readable table.
    # We build a lookup from student_id → {roll_no, student_name} using the
    # Student table (same DB session, already open).
    # ─────────────────────────────────────────────────────────────────────────
    try:
        from src.models.database_models import Student
        from sqlalchemy.orm import Session as _Session
        from sqlalchemy import create_engine as _ce, select as _sel

        # Use the calculator's own DB URL (may differ from FastAPI session DB)
        _engine  = _ce(settings.DATABASE_URL, connect_args={"check_same_thread": False}
                       if settings.DATABASE_URL.startswith("sqlite") else {})
        _session: _Session = _Session(_engine)

        student_ids = set(
            g.get("student_id") for g in result.get("semester_gpas", [])
            if g.get("student_id")
        ) | set(
            c.get("student_id") for c in result.get("cgpas", [])
            if c.get("student_id")
        )

        id_to_info: dict[int, dict] = {}
        if student_ids:
            students = _session.execute(
                _sel(Student).where(Student.id.in_(student_ids))
            ).scalars().all()
            id_to_info = {
                s.id: {"roll_no": s.roll_no, "student_name": s.student_name}
                for s in students
            }
        _session.close()

        # Patch roll_no into semester_gpas
        enriched_sem_gpas = []
        for g in result.get("semester_gpas", []):
            info = id_to_info.get(g.get("student_id"), {})
            enriched_sem_gpas.append({
                **g,
                "roll_no":      info.get("roll_no", ""),
                "student_name": info.get("student_name", ""),
            })

        # Patch roll_no into cgpas
        enriched_cgpas = []
        for c in result.get("cgpas", []):
            info = id_to_info.get(c.get("student_id"), {})
            enriched_cgpas.append({
                **c,
                "roll_no":      info.get("roll_no", ""),
                "student_name": info.get("student_name", ""),
            })

        result["semester_gpas"] = enriched_sem_gpas
        result["cgpas"]         = enriched_cgpas

    except Exception as enrich_exc:
        logger.warning("Could not enrich GPA results with roll_no: %s", enrich_exc)
        # Non-fatal — return results without roll_no enrichment

    # ── Step 6: Persist results ────────────────────────────────────────────────
    job.calc_result    = _safe_json(result)
    job.status         = "completed"
    job.marks_written  = result.get("marks_written", 0)
    job.updated_at     = _now()
    db_session.commit()

    return {"success": True, "result": result}


# ── New: re-validate with edited records ──────────────────────────────────────

def run_revalidate(
    job_id: str,
    edited_records: list[dict],
    db_session,
) -> dict:
    """
    Re-run Agent 2 (validator) on coordinator-edited records.

    The job must exist and must NOT be in 'completed' state.
    Persists the updated validation result, row counts and status back to the job.

    Returns:
      {"success": True,  "report": <report dict>}   on success
      {"success": False, "error":  <message>}        on failure
    """
    job: UploadJob | None = (
        db_session.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    )
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' not found"}

    if job.status == "completed":
        return {"success": False, "error": "Job already completed — cannot re-validate"}

    try:
        report = validate_records(records=edited_records, semester=None)
    except Exception as exc:
        logger.exception("Re-validation raised an exception for job %s", job_id)
        return {"success": False, "error": str(exc)}

    # Persist updated validation result
    job.validation_result = _safe_json(report.model_dump())
    job.validation_status = report.status
    job.total_rows        = report.summary.total_rows
    job.clean_rows        = report.summary.clean
    job.flagged_rows      = report.summary.flagged
    job.blocked_rows      = report.summary.blocked
    job.updated_at        = _now()

    # Also update parse_result to store the edited records so approve still works
    try:
        import json as _json
        existing = _json.loads(job.parse_result or "{}")
    except Exception:
        existing = {}

    existing["records"] = edited_records
    job.parse_result = _safe_json(existing)

    if report.status == "BLOCKED":
        job.status = "awaiting_approval"   # keep it reviewable
        job.error_message = (
            f"Re-validation BLOCKED: {report.summary.blocked} critical error(s) remain."
        )
    else:
        job.status = "awaiting_approval"
        job.error_message = None

    db_session.commit()
    return {"success": True, "report": report.model_dump()}

