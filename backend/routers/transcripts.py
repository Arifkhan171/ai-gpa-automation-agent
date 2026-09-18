"""
AcadTrack — Transcripts Router
University of Loralai, Pakistan

Module 5: Transcript Generation with QR Verification
"""

from __future__ import annotations

import io
import logging
import traceback
import zipfile
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from backend.config import LOGO_PATH, settings
from backend.database import get_db
from backend.models.transcript_model import TranscriptRecord
from backend.schemas.transcript_schemas import (
    BulkTranscriptRequest,
    TranscriptRecordResponse,
    TranscriptRequest,
    VerificationResponse,
)
from backend.services.qr_service import embed_qr_in_pdf, generate_verification_token
from backend.utils.auth_utils import get_current_user, require_role
from src.dashboard.transcript_generator import (
    fetch_student_transcript_data,
    generate_transcript_pdf,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/transcripts", tags=["Transcripts"])

# Absolute path from config — works on Windows + Linux regardless of CWD
_LOGO_PATH = LOGO_PATH
_BASE_URL  = "http://localhost:8000"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filter_and_recalc(data: dict, up_to_semester: Optional[int]) -> tuple[dict, str]:
    if up_to_semester is not None:
        data["semesters"] = [
            s for s in data["semesters"] if s["number"] <= up_to_semester
        ]
        filtered_ch = sum(s.get("total_credit_hours", 0) for s in data["semesters"])
        filtered_qp = sum(s.get("total_quality_points", 0) for s in data["semesters"])
        new_cgpa = (filtered_qp / filtered_ch) if filtered_ch > 0 else None
        data["cgpa"]               = new_cgpa
        data["total_credit_hours"] = filtered_ch
        semester_range = f"1-{up_to_semester}"
    else:
        semester_range = "all"
    return data, semester_range


def _save_record(
    db: Session,
    data: dict,
    semester_range: str,
    unofficial: bool,
    issued_by: str,
    notes: Optional[str],
    issued_at_str: str,
    token: str,
) -> TranscriptRecord:
    record = TranscriptRecord(
        verification_token  = token,
        student_id          = data.get("student_id", 0),
        roll_no             = data.get("roll_no", ""),
        student_name        = data.get("student_name", ""),
        semester_range      = semester_range,
        cgpa_at_issue       = data.get("cgpa"),
        total_credit_hours  = data.get("total_credit_hours"),
        semesters_count     = len(data.get("semesters", [])),
        is_unofficial       = unofficial,
        issued_by           = issued_by,
        issued_at           = datetime.fromisoformat(issued_at_str),
        scan_count          = 0,
        is_valid            = True,
        notes               = notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _generate_one(
    roll_no: str,
    up_to_semester: Optional[int],
    unofficial: bool,
    issued_by: str,
    notes: Optional[str],
    db: Session,
) -> tuple[bytes, str, dict]:
    """Full pipeline: fetch → filter → PDF → token → QR → save → return PDF bytes."""

    # Step 1: fetch student data
    logger.info(f"[generate] fetching data for {roll_no} from {settings.DATABASE_URL}")
    data = fetch_student_transcript_data(roll_no=roll_no, db_url=settings.DATABASE_URL)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Student not found: {roll_no}")

    # Step 2: filter semesters
    data, semester_range = _filter_and_recalc(data, up_to_semester)
    logger.info(f"[generate] semester_range={semester_range}, semesters={len(data['semesters'])}")

    # Step 3: generate PDF
    logger.info(f"[generate] generating PDF, logo={_LOGO_PATH}")
    pdf_bytes = generate_transcript_pdf(
        student_data=data,
        unofficial=unofficial,
        logo_path=_LOGO_PATH,
    )
    logger.info(f"[generate] PDF done, {len(pdf_bytes)} bytes")

    # Step 4: token + QR embed
    issued_at_str = datetime.now(timezone.utc).isoformat()
    token = generate_verification_token(
        roll_no=roll_no,
        semester_range=semester_range,
        issued_at=issued_at_str,
        secret_key=settings.SECRET_KEY,
    )
    logger.info(f"[generate] token={token}")

    final_pdf = embed_qr_in_pdf(pdf_bytes, token, _BASE_URL)
    logger.info(f"[generate] QR embedded, final PDF {len(final_pdf)} bytes")

    # Step 5: save record
    _save_record(db, data, semester_range, unofficial, issued_by, notes, issued_at_str, token)
    logger.info(f"[generate] record saved")

    return final_pdf, token, data


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1 — Generate single transcript
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    summary="Generate a single PDF transcript with QR verification",
    dependencies=[Depends(require_role("coordinator", "controller", "super_admin"))],
)
def generate_transcript(
    request: TranscriptRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        final_pdf, _token, _data = _generate_one(
            roll_no        = request.roll_no,
            up_to_semester = request.up_to_semester,
            unofficial     = request.unofficial,
            issued_by      = current_user.username,
            notes          = request.notes,
            db             = db,
        )
    except HTTPException:
        raise
    except Exception as exc:
        # Print full traceback to uvicorn terminal AND return it in the response
        tb = traceback.format_exc()
        logger.error(f"[generate] CRASH:\n{tb}")
        # Return 500 with the actual error message visible in browser
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": tb},
        )

    safe     = request.roll_no.replace("/", "_").replace("\\", "_")
    filename = f"{safe}_transcript.pdf"

    return Response(
        content=final_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2 — Bulk generate → ZIP
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/generate-bulk",
    summary="Generate multiple transcript PDFs as a ZIP download",
    dependencies=[Depends(require_role("coordinator", "controller", "super_admin"))],
)
def generate_bulk_transcripts(
    request: BulkTranscriptRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not request.roll_nos:
        raise HTTPException(status_code=400, detail="roll_nos list cannot be empty")

    zip_buf = io.BytesIO()
    errors: list[str] = []

    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for roll_no in request.roll_nos:
            try:
                final_pdf, _token, _data = _generate_one(
                    roll_no        = roll_no,
                    up_to_semester = request.up_to_semester,
                    unofficial     = request.unofficial,
                    issued_by      = current_user.username,
                    notes          = None,
                    db             = db,
                )
                safe = roll_no.replace("/", "_").replace("\\", "_")
                zf.writestr(f"{safe}_transcript.pdf", final_pdf)
            except HTTPException as exc:
                errors.append(f"{roll_no}: {exc.detail}")
            except Exception as exc:
                errors.append(f"{roll_no}: {str(exc)}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename  = f"transcripts_{timestamp}.zip"

    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 3 — List records
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/records",
    response_model=List[TranscriptRecordResponse],
    summary="List all generated transcripts",
    dependencies=[Depends(require_role("coordinator", "controller", "super_admin"))],
)
def list_transcript_records(
    roll_no: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(TranscriptRecord)
    if roll_no:
        query = query.filter(TranscriptRecord.roll_no.ilike(f"%{roll_no}%"))
    return query.order_by(TranscriptRecord.issued_at.desc()).limit(limit).all()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 4 — Revoke
# ─────────────────────────────────────────────────────────────────────────────

@router.delete(
    "/records/{token}/revoke",
    summary="Revoke a transcript — QR scan will return INVALID after this",
    dependencies=[Depends(require_role("controller", "super_admin"))],
)
def revoke_transcript(token: str, db: Session = Depends(get_db)):
    record = db.query(TranscriptRecord).filter(
        TranscriptRecord.verification_token == token
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"No transcript found: {token}")
    record.is_valid = False
    db.commit()
    return {"message": "Transcript revoked successfully"}
