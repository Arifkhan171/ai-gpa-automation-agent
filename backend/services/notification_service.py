"""
AcadTrack — Notification Service
University of Loralai, Pakistan

Responsibilities:
  1. queue_notification()          — add a message to the queue (no immediate send)
  2. send_email()                  — actually deliver via SMTP (or pretend if disabled)
  3. send_sms()                    — actually deliver via Twilio (or pretend if disabled)
  4. process_notification_queue()  — called by the background task every 60 s
  5. Template helpers              — build (subject, body) for each event type
"""

import logging
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.notification_model import NotificationQueue

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Queue a notification (does NOT send immediately)
# ─────────────────────────────────────────────────────────────────────────────

def queue_notification(
    db: Session,
    notification_type: str,
    channel: str,
    recipient_name: str,
    body: str,
    recipient_email: Optional[str] = None,
    recipient_phone: Optional[str] = None,
    subject: Optional[str] = None,
    created_by: Optional[str] = None,
    related_roll_no: Optional[str] = None,
) -> NotificationQueue:
    """
    Create a NotificationQueue record with status='pending'.
    The background processor will pick it up and send it.
    """
    notification = NotificationQueue(
        notification_type=notification_type,
        channel=channel,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        subject=subject,
        body=body,
        status="pending",
        retry_count=0,
        max_retries=settings.NOTIFICATION_RETRY_MAX,
        scheduled_at=datetime.now(timezone.utc),
        created_by=created_by,
        related_roll_no=related_roll_no,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# ─────────────────────────────────────────────────────────────────────────────
# 2. Send email
# ─────────────────────────────────────────────────────────────────────────────

def send_email(notification: NotificationQueue) -> bool:
    """
    Send an email for the given notification record.

    If EMAIL_ENABLED is False (default), logs a skip message and returns True
    so the queue processor marks it as 'sent' — useful for demo / dev mode.

    If EMAIL_ENABLED is True, connects to Gmail SMTP with STARTTLS.
    Returns True on success, False on any exception.
    """
    if not settings.EMAIL_ENABLED:
        logger.info(
            f"[notification] Email disabled — skipping id={notification.id} "
            f"to {notification.recipient_email!r}"
        )
        return True  # pretend success in demo mode

    try:
        msg = MIMEMultipart()
        msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"]      = notification.recipient_email
        msg["Subject"] = notification.subject or "(no subject)"
        msg.attach(MIMEText(notification.body, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(
                settings.SMTP_FROM_EMAIL,
                notification.recipient_email,
                msg.as_string(),
            )

        logger.info(
            f"[notification] Email sent id={notification.id} "
            f"to {notification.recipient_email!r}"
        )
        return True

    except Exception as exc:
        logger.error(
            f"[notification] Email failed id={notification.id} "
            f"to {notification.recipient_email!r}: {exc}"
        )
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Send SMS
# ─────────────────────────────────────────────────────────────────────────────

def send_sms(notification: NotificationQueue) -> bool:
    """
    Send an SMS via Twilio for the given notification record.

    If SMS_ENABLED is False (default), logs a skip message and returns True.
    If SMS_ENABLED is True, uses the Twilio REST client.
    Returns True on success, False on any exception.
    """
    if not settings.SMS_ENABLED:
        logger.info(
            f"[notification] SMS disabled — skipping id={notification.id} "
            f"to {notification.recipient_phone!r}"
        )
        return True  # pretend success in demo mode

    try:
        from twilio.rest import Client  # imported lazily — only when enabled
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=notification.body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=notification.recipient_phone,
        )
        logger.info(
            f"[notification] SMS sent id={notification.id} "
            f"to {notification.recipient_phone!r}"
        )
        return True

    except Exception as exc:
        logger.error(
            f"[notification] SMS failed id={notification.id} "
            f"to {notification.recipient_phone!r}: {exc}"
        )
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Process the queue (called by the 60-second background task)
# ─────────────────────────────────────────────────────────────────────────────

def process_notification_queue(db: Session) -> dict:
    """
    Fetch up to 50 pending / retryable notifications and attempt to deliver them.

    Pending    → ready to send immediately
    Failed     → retry if retry_count < max_retries AND scheduled_at has passed

    Returns a summary dict: {"processed": n, "sent": m, "failed": k}
    """
    now = datetime.now(timezone.utc)

    notifications = (
        db.query(NotificationQueue)
        .filter(
            (NotificationQueue.status == "pending")
            | (
                (NotificationQueue.status == "failed")
                & (NotificationQueue.retry_count < NotificationQueue.max_retries)
                & (NotificationQueue.scheduled_at <= now)
            )
        )
        .order_by(NotificationQueue.scheduled_at.asc())
        .limit(50)
        .all()
    )

    processed = 0
    sent      = 0
    failed    = 0

    for notif in notifications:
        processed += 1
        success = False
        error_msg = ""

        try:
            if notif.channel == "email":
                success = send_email(notif)
            elif notif.channel == "sms":
                success = send_sms(notif)
            else:
                logger.warning(f"[notification] Unknown channel {notif.channel!r} — skipping")
                success = False
                error_msg = f"Unknown channel: {notif.channel}"
        except Exception as exc:
            success = False
            error_msg = str(exc)

        if success:
            notif.status  = "sent"
            notif.sent_at = datetime.now(timezone.utc)
            sent += 1
        else:
            notif.retry_count += 1
            notif.last_error   = error_msg or "Send failed"

            if notif.retry_count >= notif.max_retries:
                notif.status = "failed"
                failed += 1
            else:
                notif.status       = "pending"
                notif.scheduled_at = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.NOTIFICATION_RETRY_DELAY_MINUTES
                )

    try:
        db.commit()
    except Exception as exc:
        logger.error(f"[notification] Queue commit failed: {exc}")

    return {"processed": processed, "sent": sent, "failed": failed}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Message template helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_grade_published_message(
    student_name: str,
    semester: int,
    gpa: float,
    cgpa: float,
) -> tuple:
    """Return (subject, body) for the grade_published event."""
    subject = f"Semester {semester} Results — University of Loralai"
    body = (
        f"Dear {student_name},\n\n"
        f"Your Semester {semester} results have been published.\n\n"
        f"Semester GPA:     {gpa:.2f}\n"
        f"Cumulative CGPA:  {cgpa:.2f}\n\n"
        f"Login to view details: http://localhost:3000/portal\n\n"
        f"— AcadTrack, University of Loralai"
    )
    return subject, body


def build_transcript_ready_message(
    student_name: str,
    voucher_number: str,
) -> tuple:
    """Return (subject, body) for the transcript_ready event."""
    subject = "Your Transcript is Ready — University of Loralai"
    body = (
        f"Dear {student_name},\n\n"
        f"Your transcript request has been processed.\n\n"
        f"Voucher: {voucher_number}\n\n"
        f"Login to download: http://localhost:3000/portal\n\n"
        f"— AcadTrack, University of Loralai"
    )
    return subject, body


def build_voucher_created_message(
    student_name: str,
    voucher_number: str,
    amount: float,
    purpose: str,
) -> tuple:
    """Return (subject, body) for the voucher_created event."""
    subject = "Payment Voucher Created — University of Loralai"
    body = (
        f"Dear {student_name},\n\n"
        f"Your payment voucher has been created.\n\n"
        f"Voucher Number: {voucher_number}\n"
        f"Purpose:        {purpose}\n"
        f"Amount:         Rs. {amount:.0f}\n\n"
        f"Please visit the cashier window with this number.\n"
        f"Voucher expires in 7 days.\n\n"
        f"— AcadTrack, University of Loralai"
    )
    return subject, body
