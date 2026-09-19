"""
AcadTrack — Payments Router
University of Loralai, Pakistan

Module 6: Student Portal and Payment Vouchers

Endpoints:
  POST   /api/v1/payments/request-voucher                    student
  GET    /api/v1/payments/vouchers                           coordinator, controller, super_admin
  PATCH  /api/v1/payments/vouchers/{voucher_number}/mark-paid coordinator, controller, super_admin
  GET    /api/v1/payments/vouchers/{voucher_number}          any authenticated user
  PATCH  /api/v1/payments/vouchers/{voucher_number}/cancel   coordinator|controller|super_admin OR owning student
  GET    /api/v1/payments/daily-report                       coordinator, controller, super_admin
  GET    /api/v1/payments/download-transcript/{voucher_number} student (own) or staff
"""

from __future__ import annotations

import logging
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from backend.config import LOGO_PATH, settings
from backend.database import get_db
from backend.models.payment_model import PaymentVoucher, generate_voucher_number
from backend.models.transcript_model import TranscriptRecord
from backend.schemas.payment_schemas import (
    DailyCollectionResponse,
    MarkPaidRequest,
    VoucherCreateRequest,
    VoucherResponse,
)
from backend.services.qr_service import embed_qr_in_pdf, generate_verification_token
from backend.utils.auth_utils import get_current_user, require_role
from src.models.database_models import Student
from src.dashboard.transcript_generator import (
    fetch_student_transcript_data,
    generate_transcript_pdf,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])

_BASE_URL = "http://localhost:8000"

# ── Fee schedule ──────────────────────────────────────────────────────────────
_FEE_SCHEDULE: dict[str, float] = {
    "transcript":            200.0,
    "attestation":           100.0,
    "character_certificate": 150.0,
    "migration":             500.0,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _voucher_to_response(v: PaymentVoucher, message: str = "") -> VoucherResponse:
    return VoucherResponse(
        id=v.id,
        voucher_number=v.voucher_number,
        student_name=v.student_name,
        roll_no=v.roll_no,
        purpose=v.purpose,
        amount=v.amount,
        status=v.status,
        semester_range=v.semester_range,
        created_at=v.created_at,
        expires_at=v.expires_at,
        paid_at=v.paid_at,
        action_taken=v.action_taken,
        message=message,
    )


def _find_voucher_or_404(voucher_number: str, db: Session) -> PaymentVoucher:
    v = (
        db.query(PaymentVoucher)
        .filter(PaymentVoucher.voucher_number == voucher_number)
        .first()
    )
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voucher '{voucher_number}' not found",
        )
    return v


def _auto_generate_transcript(
    voucher: PaymentVoucher,
    db: Session,
    issued_by: str,
) -> None:
    """
    Auto-generate a transcript PDF and save a TranscriptRecord after payment.
    Marks action_taken on the voucher. Errors are logged but do NOT fail the
    mark-paid response — the cashier should still get a success response.
    """
    try:
        data = fetch_student_transcript_data(
            roll_no=voucher.roll_no,
            db_url=settings.DATABASE_URL,
        )
        if data is None:
            logger.error(f"[payments] transcript auto-gen: student not found {voucher.roll_no}")
            return

        # Filter semesters if a range is specified
        semester_range = voucher.semester_range or "all"
        if semester_range != "all":
            # Parse "1-4" style range
            parts = semester_range.split("-")
            if len(parts) == 2:
                try:
                    up_to = int(parts[1])
                    data["semesters"] = [
                        s for s in data["semesters"] if s["number"] <= up_to
                    ]
                    filtered_ch = sum(s.get("total_credit_hours", 0) for s in data["semesters"])
                    filtered_qp = sum(s.get("total_quality_points", 0) for s in data["semesters"])
                    data["cgpa"] = (filtered_qp / filtered_ch) if filtered_ch > 0 else None
                    data["total_credit_hours"] = filtered_ch
                except ValueError:
                    pass  # fallback to "all"

        # Generate PDF
        pdf_bytes = generate_transcript_pdf(
            student_data=data,
            unofficial=True,
            logo_path=LOGO_PATH,
        )

        # Token + QR embed
        issued_at_str = datetime.now(timezone.utc).isoformat()
        token = generate_verification_token(
            roll_no=voucher.roll_no,
            semester_range=semester_range,
            issued_at=issued_at_str,
            secret_key=settings.SECRET_KEY,
        )
        final_pdf = embed_qr_in_pdf(pdf_bytes, token, _BASE_URL)

        # Save TranscriptRecord
        record = TranscriptRecord(
            verification_token  = token,
            student_id          = data.get("student_id", 0),
            roll_no             = data.get("roll_no", voucher.roll_no),
            student_name        = data.get("student_name", voucher.student_name),
            semester_range      = semester_range,
            cgpa_at_issue       = data.get("cgpa"),
            total_credit_hours  = data.get("total_credit_hours"),
            semesters_count     = len(data.get("semesters", [])),
            is_unofficial       = True,
            issued_by           = issued_by,
            issued_at           = datetime.fromisoformat(issued_at_str),
            scan_count          = 0,
            is_valid            = True,
            notes               = f"Auto-generated after payment of voucher {voucher.voucher_number}",
        )
        db.add(record)

        # Mark action taken on voucher
        voucher.action_taken = True
        voucher.action_taken_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"[payments] transcript auto-generated for {voucher.roll_no} "
            f"token={token} after voucher {voucher.voucher_number}"
        )
    except Exception as exc:
        logger.error(
            f"[payments] transcript auto-gen failed for {voucher.voucher_number}: {exc}\n"
            + traceback.format_exc()
        )
        # Do not re-raise — mark-paid still succeeded


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 1 — POST /request-voucher
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/request-voucher",
    response_model=VoucherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Student requests a payment voucher",
)
def request_voucher(
    body: VoucherCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("student")),
):
    """
    Student submits a request — e.g. for a transcript or attestation.
    Returns a voucher the student can take to the cashier window.
    """
    # 1. Find student by roll_no (username for students)
    student = (
        db.query(Student)
        .filter(Student.roll_no == current_user.username)
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found for your account",
        )

    # 2. Amount from fee schedule
    amount = _FEE_SCHEDULE.get(body.purpose, 0.0)

    # 3. Voucher number
    voucher_number = generate_voucher_number(db)

    # 4. Dates
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    # 5. Create and save
    voucher = PaymentVoucher(
        voucher_number = voucher_number,
        student_id     = student.id,
        roll_no        = student.roll_no,
        student_name   = student.student_name,
        purpose        = body.purpose,
        amount         = amount,
        status         = "pending",
        semester_range = body.semester_range,
        created_at     = now,
        expires_at     = expires_at,
        payment_notes  = body.notes,
        action_taken   = False,
    )
    db.add(voucher)
    db.commit()
    db.refresh(voucher)

    # 6. Response message
    message = (
        f"Take voucher number {voucher_number} to the university cashier window "
        f"and pay Rs. {amount:.0f}. "
        f"Your request will be processed within 24 hours of payment confirmation. "
        f"Voucher expires in 7 days."
    )

    return _voucher_to_response(voucher, message)


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 2 — GET /vouchers  (admin list)
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/vouchers",
    response_model=List[VoucherResponse],
    summary="Admin: list all payment vouchers",
)
def list_vouchers(
    voucher_status: Optional[str] = Query(None, alias="status"),
    roll_no: Optional[str] = Query(None),
    date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "controller", "super_admin")),
):
    """Returns all vouchers. Filterable by status, roll_no, and date."""
    query = db.query(PaymentVoucher)

    if voucher_status:
        query = query.filter(PaymentVoucher.status == voucher_status)
    if roll_no:
        query = query.filter(PaymentVoucher.roll_no.ilike(f"%{roll_no}%"))
    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(
                PaymentVoucher.created_at >= datetime(target.year, target.month, target.day, 0, 0, 0),
                PaymentVoucher.created_at < datetime(target.year, target.month, target.day, 23, 59, 59),
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date must be in YYYY-MM-DD format",
            )

    vouchers = query.order_by(PaymentVoucher.created_at.desc()).all()
    return [_voucher_to_response(v) for v in vouchers]


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 3 — PATCH /vouchers/{voucher_number}/mark-paid
# ═════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/vouchers/{voucher_number}/mark-paid",
    response_model=VoucherResponse,
    summary="Admin: mark a voucher as paid",
)
def mark_paid(
    voucher_number: str,
    body: MarkPaidRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "controller", "super_admin")),
):
    """
    Marks a pending voucher as paid. If the purpose is 'transcript',
    a transcript PDF is auto-generated.
    """
    # 1. Find voucher
    voucher = _find_voucher_or_404(voucher_number, db)

    # 2. Status guard
    if voucher.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already paid",
        )
    if voucher.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voucher is cancelled",
        )
    now = datetime.now(timezone.utc)
    if voucher.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expired",
        )

    # 3. Update voucher
    voucher.status        = "paid"
    voucher.paid_at       = now
    voucher.paid_by_staff = current_user.username
    voucher.payment_notes = body.payment_notes
    db.commit()
    db.refresh(voucher)

    # 4. Auto-generate transcript if applicable
    if voucher.purpose == "transcript":
        _auto_generate_transcript(voucher, db, issued_by=current_user.username)
        db.refresh(voucher)

    message = (
        "Payment confirmed. Transcript has been generated and is ready for download."
        if voucher.purpose == "transcript"
        else "Payment confirmed. Your request is being processed."
    )

    return _voucher_to_response(voucher, message)


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 4 — GET /vouchers/{voucher_number}  (any auth user)
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/vouchers/{voucher_number}",
    response_model=VoucherResponse,
    summary="Get a single voucher by number",
)
def get_voucher(
    voucher_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Any authenticated user can call this endpoint.
    Students can only see their own vouchers.
    Staff can see any voucher.
    """
    voucher = _find_voucher_or_404(voucher_number, db)

    # Students can only see their own voucher
    if current_user.role == "student" and voucher.roll_no != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own vouchers",
        )

    return _voucher_to_response(voucher)


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 5 — PATCH /vouchers/{voucher_number}/cancel
# ═════════════════════════════════════════════════════════════════════════════

@router.patch(
    "/vouchers/{voucher_number}/cancel",
    summary="Cancel a voucher",
)
def cancel_voucher(
    voucher_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Staff (coordinator / controller / super_admin) can cancel any voucher.
    A student can cancel their own pending voucher.
    """
    voucher = _find_voucher_or_404(voucher_number, db)

    # Permission check
    is_staff = current_user.role in {"coordinator", "controller", "super_admin"}
    is_owner = (current_user.role == "student" and voucher.roll_no == current_user.username)

    if not is_staff and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to cancel this voucher",
        )

    if voucher.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a voucher with status '{voucher.status}'",
        )

    voucher.status = "cancelled"
    db.commit()
    return {"message": "Voucher cancelled"}


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 6 — GET /daily-report
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/daily-report",
    response_model=DailyCollectionResponse,
    summary="Admin: daily payment collection report",
)
def daily_report(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "controller", "super_admin")),
):
    """Returns a breakdown of payments collected on a given date."""
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date must be in YYYY-MM-DD format",
            )
    else:
        target_date = datetime.now(timezone.utc).date()

    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    day_end   = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)

    all_vouchers = (
        db.query(PaymentVoucher)
        .filter(
            PaymentVoucher.created_at >= day_start,
            PaymentVoucher.created_at <= day_end,
        )
        .all()
    )

    # Paid sub-set (filter by paid_at on the same day)
    paid_on_day = [
        v for v in all_vouchers
        if v.paid_at and day_start <= v.paid_at.replace(tzinfo=None) <= day_end
    ]

    total_amount  = sum(v.amount for v in paid_on_day)
    paid_count    = len(paid_on_day)
    pending_count    = sum(1 for v in all_vouchers if v.status == "pending")
    cancelled_count  = sum(1 for v in all_vouchers if v.status == "cancelled")

    # Breakdown by purpose (paid only)
    by_purpose: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for v in paid_on_day:
        by_purpose[v.purpose]["count"]  += 1
        by_purpose[v.purpose]["amount"] += v.amount

    breakdown = [
        {"purpose": purpose, "count": info["count"], "amount": info["amount"]}
        for purpose, info in sorted(by_purpose.items())
    ]

    return DailyCollectionResponse(
        date=str(target_date),
        total_vouchers=len(all_vouchers),
        total_amount=total_amount,
        paid_count=paid_count,
        pending_count=pending_count,
        cancelled_count=cancelled_count,
        breakdown=breakdown,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 7 — GET /download-transcript/{voucher_number}
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/download-transcript/{voucher_number}",
    summary="Download transcript PDF after payment",
)
def download_transcript(
    voucher_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns the transcript PDF for a paid transcript voucher.
    Only the owning student or staff can download.
    """
    # 1. Find voucher
    voucher = _find_voucher_or_404(voucher_number, db)

    # 2. Permission check
    is_staff = current_user.role in {"coordinator", "controller", "super_admin"}
    is_owner = (current_user.role == "student" and voucher.roll_no == current_user.username)
    if not is_staff and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to download this transcript",
        )

    # 3. Payment guard
    if voucher.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment required before transcript can be downloaded",
        )

    # 4. Purpose guard
    if voucher.purpose != "transcript":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a transcript voucher",
        )

    # 5. Find the TranscriptRecord created after payment
    transcript_record: Optional[TranscriptRecord] = None
    if voucher.paid_at:
        transcript_record = (
            db.query(TranscriptRecord)
            .filter(
                TranscriptRecord.roll_no == voucher.roll_no,
                TranscriptRecord.is_valid.is_(True),
                TranscriptRecord.issued_at >= voucher.paid_at,
            )
            .order_by(TranscriptRecord.issued_at.desc())
            .first()
        )

    # 6. Regenerate if not found
    if transcript_record is None:
        logger.info(
            f"[payments] No transcript record found for {voucher.roll_no} "
            f"after payment; regenerating."
        )
        _auto_generate_transcript(voucher, db, issued_by=current_user.username)
        db.refresh(voucher)
        if voucher.paid_at:
            transcript_record = (
                db.query(TranscriptRecord)
                .filter(
                    TranscriptRecord.roll_no == voucher.roll_no,
                    TranscriptRecord.is_valid.is_(True),
                    TranscriptRecord.issued_at >= voucher.paid_at,
                )
                .order_by(TranscriptRecord.issued_at.desc())
                .first()
            )
        if transcript_record is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate transcript. Please contact admin.",
            )

    # 7. Re-generate the PDF bytes from stored data using the token
    try:
        data = fetch_student_transcript_data(
            roll_no=voucher.roll_no,
            db_url=settings.DATABASE_URL,
        )
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student data not found",
            )

        # Apply semester filter
        semester_range = transcript_record.semester_range or "all"
        if semester_range != "all":
            parts = semester_range.split("-")
            if len(parts) == 2:
                try:
                    up_to = int(parts[1])
                    data["semesters"] = [
                        s for s in data["semesters"] if s["number"] <= up_to
                    ]
                except ValueError:
                    pass

        pdf_bytes = generate_transcript_pdf(
            student_data=data,
            unofficial=transcript_record.is_unofficial,
            logo_path=LOGO_PATH,
        )
        final_pdf = embed_qr_in_pdf(
            pdf_bytes,
            transcript_record.verification_token,
            _BASE_URL,
        )
    except HTTPException:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"[payments] PDF re-gen failed: {exc}\n{tb}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {exc}",
        )

    safe_roll = voucher.roll_no.replace("/", "_").replace("\\", "_")
    filename = f"{safe_roll}_transcript.pdf"

    return Response(
        content=final_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
