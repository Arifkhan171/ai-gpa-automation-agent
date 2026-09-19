"""
AcadTrack — Audit Service
University of Loralai, Pakistan

Provides log_action() — call it after any significant operation.

IMPORTANT: This function NEVER raises an exception.
Audit logging must never break the main request flow.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.notification_model import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    username: str,
    user_role: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict] = None,
    user_id: Optional[int] = None,
) -> Optional[AuditLog]:
    """
    Create an AuditLog record and commit it to the database.

    Parameters
    ----------
    db          : SQLAlchemy session
    username    : who performed the action
    user_role   : their role at the time of the action
    action      : what they did  (e.g. "login", "approved_grades")
    entity_type : category of the thing acted on  (e.g. "student", "voucher")
    entity_id   : ID or roll_no of the thing acted on
    ip_address  : client IP from request.client.host
    details     : extra context — will be serialised to a JSON string
    user_id     : integer PK from the acadtrack_users table (optional)

    Returns
    -------
    The saved AuditLog instance, or None if logging failed (silently).
    """
    try:
        details_str: Optional[str] = None
        if details is not None:
            try:
                details_str = json.dumps(details, default=str)
            except Exception:
                details_str = str(details)

        entry = AuditLog(
            user_id     = user_id,
            username    = username,
            user_role   = user_role,
            action      = action,
            entity_type = entity_type,
            entity_id   = str(entity_id) if entity_id is not None else None,
            ip_address  = ip_address,
            details     = details_str,
            timestamp   = datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    except Exception as exc:
        # Swallow every error — audit logging MUST NOT break the main request
        logger.warning(f"[audit] log_action failed silently: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return None
