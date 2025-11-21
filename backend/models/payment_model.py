"""
AcadTrack — Payment Voucher Model
University of Loralai, Pakistan

Stores payment vouchers that students request and cashiers mark as paid.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from backend.database import Base


class PaymentVoucher(Base):
    """
    One row = one payment voucher.

    Lifecycle: pending → paid (or cancelled / expired)
    When purpose == "transcript" and status becomes "paid",
    a transcript PDF is auto-generated and action_taken is set True.
    """
    __tablename__ = "payment_vouchers"

    id               = Column(Integer, primary_key=True, autoincrement=True)

    # ── Voucher identity ──────────────────────────────────────────────────────
    voucher_number   = Column(String(20), unique=True, nullable=False, index=True)
    # Format: VCHR-{YEAR}-{5-digit-seq}  e.g. VCHR-2026-00001

    # ── Student identity (denormalised) ───────────────────────────────────────
    student_id       = Column(Integer, nullable=False)
    roll_no          = Column(String(100), nullable=False)
    student_name     = Column(String(200), nullable=False)

    # ── Purpose and amount ────────────────────────────────────────────────────
    purpose          = Column(String(50), nullable=False)
    # Values: transcript | attestation | character_certificate | migration
    amount           = Column(Float, nullable=False)

    # ── Status ────────────────────────────────────────────────────────────────
    status           = Column(String(20), nullable=False, default="pending")
    # Values: pending | paid | cancelled | expired

    # ── Transcript-specific ───────────────────────────────────────────────────
    semester_range   = Column(String(20), nullable=True)
    # For transcript requests: "1-4" or "all"

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at       = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at       = Column(DateTime, nullable=False)
    # Set to 7 days after created_at

    paid_at          = Column(DateTime, nullable=True)
    paid_by_staff    = Column(String(50), nullable=True)
    # Username of the cashier who marked the voucher as paid
    payment_notes    = Column(Text, nullable=True)

    # ── Post-payment action ───────────────────────────────────────────────────
    action_taken     = Column(Boolean, default=False)
    # True when transcript was auto-released after payment
    action_taken_at  = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PaymentVoucher {self.voucher_number!r} status={self.status!r}>"


# ── Helper ────────────────────────────────────────────────────────────────────

def generate_voucher_number(db_session) -> str:
    """
    Generate the next sequential voucher number for the current year.

    Format: VCHR-{YEAR}-{5-digit-seq}
    Example: VCHR-2026-00001

    Counts all existing vouchers whose voucher_number starts with
    'VCHR-{year}-', then uses count+1 as the sequence.
    Thread-safety relies on the DB's unique constraint on voucher_number:
    if two requests race and produce the same number, only one will commit.
    """
    year = datetime.now().year
    prefix = f"VCHR-{year}-"
    count = (
        db_session.query(PaymentVoucher)
        .filter(PaymentVoucher.voucher_number.like(f"{prefix}%"))
        .count()
    )
    seq = count + 1
    return f"{prefix}{seq:05d}"
