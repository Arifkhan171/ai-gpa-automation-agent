"""
AcadTrack — FastAPI Application Entry Point
University of Loralai, Pakistan

Run from the project root:
    uvicorn backend.main:app --reload --port 8000

The Streamlit app continues to run independently:
    streamlit run src/dashboard/app.py
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db, init_db
# Import models so SQLAlchemy registers their tables against Base before
# init_db() / Base.metadata.create_all() is called.
from backend.models.user_model import User                      # noqa: F401
from backend.models.upload_model import UploadJob               # noqa: F401
from backend.models.transcript_model import TranscriptRecord    # noqa: F401
from backend.models.payment_model import PaymentVoucher         # noqa: F401
from backend.schemas.transcript_schemas import VerificationResponse

# Show INFO logs in terminal so we can trace the generate endpoint step by step
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

from backend.routers import (
    analytics,
    auth,
    grades,
    health,
    notifications,
    payments,
    students,
    transcripts,
)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run initialisation tasks before the server starts accepting requests."""
    init_db()           # ensure backend tables exist (safe no-op if already present)
    yield
    # nothing to clean up on shutdown


# ── Application factory ───────────────────────────────────────────────────────
app = FastAPI(
    title="AcadTrack API",
    description="University of Loralai Academic Records System",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (open in dev — restrict origins before deploying to production) ──────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Health checks are mounted directly (no /api/v1 prefix) so they're easy to hit
app.include_router(health.router)

# All feature routers carry their own /api/v1/... prefix
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(grades.router)
app.include_router(transcripts.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(payments.router)


# ── Public QR verification endpoint ──────────────────────────────────────────
# Registered here (root level) so it lives at /verify/{token},
# not under /api/v1/.  NO authentication required — anyone with the QR code
# can scan and verify.

@app.get(
    "/verify/{token}",
    response_model=VerificationResponse,
    tags=["Public Verification"],
    summary="Verify a transcript by its QR token (public, no auth)",
)
def verify_transcript(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    record: TranscriptRecord | None = (
        db.query(TranscriptRecord)
        .filter(TranscriptRecord.verification_token == token)
        .first()
    )

    # ── Not found ─────────────────────────────────────────────────────────────
    if record is None:
        return VerificationResponse(
            is_valid            = False,
            verification_token  = token,
            student_name        = None,
            roll_no             = None,
            semester_range      = None,
            cgpa_at_issue       = None,
            is_unofficial       = True,
            issued_by           = None,
            issued_at           = None,
            scan_count          = 0,
            message=(
                "INVALID — This transcript could not be verified. "
                "It may be fraudulent or tampered with."
            ),
        )

    # ── Revoked ───────────────────────────────────────────────────────────────
    if not record.is_valid:
        return VerificationResponse(
            is_valid            = False,
            verification_token  = record.verification_token,
            student_name        = record.student_name,
            roll_no             = record.roll_no,
            semester_range      = record.semester_range,
            cgpa_at_issue       = record.cgpa_at_issue,
            is_unofficial       = record.is_unofficial,
            issued_by           = record.issued_by,
            issued_at           = record.issued_at,
            scan_count          = record.scan_count,
            message="INVALID — This transcript has been revoked by the university.",
        )

    # ── Valid — update scan tracking ──────────────────────────────────────────
    record.scan_count      += 1
    record.last_scanned_at  = datetime.now(timezone.utc)
    record.last_scanned_ip  = request.client.host if request.client else None
    db.commit()
    db.refresh(record)

    return VerificationResponse(
        is_valid            = True,
        verification_token  = record.verification_token,
        student_name        = record.student_name,
        roll_no             = record.roll_no,
        semester_range      = record.semester_range,
        cgpa_at_issue       = record.cgpa_at_issue,
        is_unofficial       = record.is_unofficial,
        issued_by           = record.issued_by,
        issued_at           = record.issued_at,
        scan_count          = record.scan_count,
        message=(
            "VERIFIED — This transcript is authentic. "
            "Issued by the Office of Controller of Examinations, "
            "University of Loralai."
        ),
    )


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    """Landing endpoint — confirms the API is running."""
    return {
        "message": "AcadTrack API is running",
        "docs": "/docs",
        "health": "/health",
    }
