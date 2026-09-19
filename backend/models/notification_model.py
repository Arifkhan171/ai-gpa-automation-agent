"""
AcadTrack — Notification Model
University of Loralai, Pakistan

Two tables:
  - NotificationQueue  : email/SMS messages waiting to be sent or retried
  - AuditLog           : immutable record of every user action
"""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from backend.database import Base


class NotificationQueue(Base):
    """
    Holds outgoing email and SMS notifications.
    The background queue processor polls this table every 60 seconds.
    """
    __tablename__ = "notification_queue"

    id                = Column(Integer, primary_key=True, autoincrement=True)

    # What kind of event triggered this notification
    notification_type = Column(
        String(30), nullable=False,
        # Values: grade_published, transcript_ready, voucher_created,
        #         voucher_paid, at_risk_alert, password_changed, welcome
    )

    # Delivery channel
    channel           = Column(String(10), nullable=False)   # email | sms

    # Recipient info
    recipient_name    = Column(String(200), nullable=False)
    recipient_email   = Column(String(200), nullable=True)
    recipient_phone   = Column(String(20),  nullable=True)

    # Message content
    subject           = Column(String(300), nullable=True)   # email subject
    body              = Column(Text,        nullable=False)

    # Status lifecycle:  pending → sent | failed | cancelled
    status            = Column(String(20), nullable=False, default="pending")

    # Retry tracking
    retry_count       = Column(Integer, default=0)
    max_retries       = Column(Integer, default=3)

    # Scheduling — defaults to now so the queue picks it up immediately
    scheduled_at      = Column(DateTime, default=func.now())
    sent_at           = Column(DateTime, nullable=True)
    last_error        = Column(Text,     nullable=True)

    # Audit linkage
    created_by        = Column(String(50),  nullable=True)   # username who triggered
    related_roll_no   = Column(String(100), nullable=True)   # student this is about

    created_at        = Column(DateTime, default=func.now())

    def __repr__(self) -> str:
        return (
            f"<NotificationQueue id={self.id} type={self.notification_type!r} "
            f"channel={self.channel!r} status={self.status!r}>"
        )


class AuditLog(Base):
    """
    Immutable record of every significant action performed in the system.
    Never delete rows from this table.
    """
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)

    # Who did it
    user_id     = Column(Integer,    nullable=True)
    username    = Column(String(50), nullable=False)
    user_role   = Column(String(20), nullable=False)

    # What they did
    action      = Column(String(100), nullable=False)
    # Examples: "uploaded_file", "approved_grades", "generated_transcript",
    #           "login", "logout", "changed_password", "marked_voucher_paid",
    #           "revoked_transcript", "viewed_student"

    # What was acted on
    entity_type = Column(String(50),  nullable=True)
    # Examples: "student", "grade", "transcript", "voucher", "upload_job"
    entity_id   = Column(String(100), nullable=True)

    # Request metadata
    ip_address  = Column(String(50), nullable=True)
    details     = Column(Text, nullable=True)   # JSON string with extra context

    # When it happened — indexed for fast date-range queries
    timestamp   = Column(DateTime, default=func.now(), index=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user={self.username!r} "
            f"action={self.action!r} ts={self.timestamp}>"
        )
