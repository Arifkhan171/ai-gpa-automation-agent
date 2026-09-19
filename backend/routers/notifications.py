"""
AcadTrack — Notifications & Audit Router
University of Loralai, Pakistan

Module 7: Notifications (Part A) + Audit Trail (Part B)

Endpoints:
  POST  /api/v1/notifications/send-grades-published   coordinator|controller|super_admin
  POST  /api/v1/notifications/send-custom             coordinator|controller|super_admin
  GET   /api/v1/notifications/queue                   coordinator|controller|super_admin
  POST  /api/v1/notifications/process-queue           super_admin
  GET   /api/v1/notifications/stats                   coordinator|controller|super_admin

  GET   /api/v1/notifications/audit-log               controller|super_admin
  GET   /api/v1/notifications/audit-log/export        controller|super_admin
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.notification_model import AuditLog, NotificationQueue
from backend.models.user_model import User
from backend.services.audit_service import log_action
from backend.services.notification_service import (
    build_grade_published_message,
    process_notification_queue,
    queue_notification,
)
from backend.utils.auth_utils import get_current_user, require_role
from src.models.database_models import CGPA, SemesterGPA, Student

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ═══════════════════════════════════════════════════════════════════════════════
# PART A — NOTIFICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── POST /send-grades-published ───────────────────────────────────────────────

@router.post("/send-grades-published")
def send_grades_published(
    semester: int,
    academic_year: str,
    department: str = "CS",
    channel: str = "email",
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role("coordinator", "controller", "super_admin")
    ),
):
    """
    Queue grade-published notifications for all students who have a
    SemesterGPA record matching (semester, academic_year, department).
    """
    # 1. Find all SemesterGPA rows for this semester/year
    semester_gpas = (
        db.query(SemesterGPA)
        .join(Student, SemesterGPA.student_id == Student.id)
        .filter(
            SemesterGPA.semester == semester,
            SemesterGPA.academic_year == academic_year,
            Student.department.ilike(f"%{department}%"),
        )
        .all()
    )

    if not semester_gpas:
        return {
            "queued": 0,
            "message": f"No SemesterGPA records found for semester={semester} "
                       f"year={academic_year} dept={department}",
        }

    queued = 0
    for sg in semester_gpas:
        student: Student = sg.student

        # Get CGPA
        cgpa_row: Optional[CGPA] = student.cgpa
        cgpa_val = cgpa_row.cgpa if cgpa_row else 0.0
        gpa_val  = sg.gpa if sg.gpa is not None else 0.0

        # Try to find email/phone from User table (username = roll_no)
        user_record: Optional[User] = (
            db.query(User)
            .filter(User.username == student.roll_no)
            .first()
        )
        recipient_email = user_record.email if user_record else None
        recipient_phone = user_record.phone if user_record else None

        subject, body = build_grade_published_message(
            student_name=student.student_name,
            semester=semester,
            gpa=gpa_val,
            cgpa=cgpa_val,
        )

        queue_notification(
            db=db,
            notification_type="grade_published",
            channel=channel,
            recipient_name=student.student_name,
            body=body,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            subject=subject,
            created_by=current_user.username,
            related_roll_no=student.roll_no,
        )
        queued += 1

    return {
        "queued": queued,
        "message": f"Notifications queued for {queued} students",
    }


# ── POST /send-custom ─────────────────────────────────────────────────────────

@router.post("/send-custom")
def send_custom(
    roll_nos: List[str],
    subject: str,
    message: str,
    channel: str = "email",
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role("coordinator", "controller", "super_admin")
    ),
):
    """
    Queue a custom notification for a specific list of students.
    """
    if not roll_nos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="roll_nos list cannot be empty",
        )

    queued = 0
    not_found = []

    for roll_no in roll_nos:
        student: Optional[Student] = (
            db.query(Student).filter(Student.roll_no == roll_no).first()
        )
        if not student:
            not_found.append(roll_no)
            continue

        user_record: Optional[User] = (
            db.query(User).filter(User.username == roll_no).first()
        )
        recipient_email = user_record.email if user_record else None
        recipient_phone = user_record.phone if user_record else None

        queue_notification(
            db=db,
            notification_type="custom",
            channel=channel,
            recipient_name=student.student_name,
            body=message,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            subject=subject,
            created_by=current_user.username,
            related_roll_no=roll_no,
        )
        queued += 1

    result: dict = {
        "queued": queued,
        "message": f"Notifications queued for {queued} students",
    }
    if not_found:
        result["not_found"] = not_found
    return result


# ── GET /queue ────────────────────────────────────────────────────────────────

@router.get("/queue")
def get_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    channel: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("coordinator", "controller", "super_admin")),
):
    """
    List notification queue records, optionally filtered by status and/or channel.
    """
    query = db.query(NotificationQueue).order_by(
        NotificationQueue.created_at.desc()
    )
    if status_filter:
        query = query.filter(NotificationQueue.status == status_filter)
    if channel:
        query = query.filter(NotificationQueue.channel == channel)
    rows = query.limit(limit).all()

    return [
        {
            "id":                row.id,
            "notification_type": row.notification_type,
            "channel":           row.channel,
            "recipient_name":    row.recipient_name,
            "recipient_email":   row.recipient_email,
            "recipient_phone":   row.recipient_phone,
            "subject":           row.subject,
            "status":            row.status,
            "retry_count":       row.retry_count,
            "max_retries":       row.max_retries,
            "scheduled_at":      row.scheduled_at,
            "sent_at":           row.sent_at,
            "last_error":        row.last_error,
            "created_by":        row.created_by,
            "related_roll_no":   row.related_roll_no,
            "created_at":        row.created_at,
        }
        for row in rows
    ]


# ── POST /process-queue ───────────────────────────────────────────────────────

@router.post("/process-queue")
def trigger_process_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("super_admin")),
):
    """
    Manually trigger the notification queue processor right now.
    Useful for testing without waiting 60 seconds.
    """
    result = process_notification_queue(db)
    return result


# ── GET /stats ────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_notification_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("coordinator", "controller", "super_admin")),
):
    """
    Return aggregate counts of notifications by status and channel.
    """
    total   = db.query(func.count(NotificationQueue.id)).scalar() or 0
    pending = db.query(func.count(NotificationQueue.id)).filter(
        NotificationQueue.status == "pending"
    ).scalar() or 0
    sent = db.query(func.count(NotificationQueue.id)).filter(
        NotificationQueue.status == "sent"
    ).scalar() or 0
    failed = db.query(func.count(NotificationQueue.id)).filter(
        NotificationQueue.status == "failed"
    ).scalar() or 0

    # Per-channel breakdown
    def _channel_counts(ch: str) -> dict:
        s = db.query(func.count(NotificationQueue.id)).filter(
            NotificationQueue.channel == ch,
            NotificationQueue.status == "sent",
        ).scalar() or 0
        f = db.query(func.count(NotificationQueue.id)).filter(
            NotificationQueue.channel == ch,
            NotificationQueue.status == "failed",
        ).scalar() or 0
        return {"sent": s, "failed": f}

    return {
        "total_queued": total,
        "pending":      pending,
        "sent":         sent,
        "failed":       failed,
        "by_channel": {
            "email": _channel_counts("email"),
            "sms":   _channel_counts("sms"),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PART B — AUDIT TRAIL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /audit-log ────────────────────────────────────────────────────────────

@router.get("/audit-log")
def get_audit_log(
    username:    Optional[str] = Query(None),
    action:      Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:     Optional[str] = Query(None, description="YYYY-MM-DD"),
    page:        int           = Query(1, ge=1),
    page_size:   int           = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("controller", "super_admin")),
):
    """
    Return a paginated, filterable list of AuditLog records.
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

    if username:
        query = query.filter(AuditLog.username.ilike(f"%{username}%"))
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            query = query.filter(AuditLog.timestamp >= dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from must be YYYY-MM-DD",
            )
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.filter(AuditLog.timestamp <= dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_to must be YYYY-MM-DD",
            )

    offset = (page - 1) * page_size
    rows   = query.offset(offset).limit(page_size).all()

    return [_audit_to_dict(r) for r in rows]


# ── GET /audit-log/export ─────────────────────────────────────────────────────

@router.get("/audit-log/export")
def export_audit_log(
    username:    Optional[str] = Query(None),
    action:      Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:     Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("controller", "super_admin")),
):
    """
    Download the audit log as a CSV file.  Same filters as GET /audit-log.
    Suitable for compliance records and external review.
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.asc())

    if username:
        query = query.filter(AuditLog.username.ilike(f"%{username}%"))
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            query = query.filter(AuditLog.timestamp >= dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from must be YYYY-MM-DD",
            )
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.filter(AuditLog.timestamp <= dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_to must be YYYY-MM-DD",
            )

    rows = query.all()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "username", "user_role", "action",
        "entity_type", "entity_id", "ip_address", "details", "timestamp",
    ])
    for r in rows:
        writer.writerow([
            r.id,
            r.username,
            r.user_role,
            r.action,
            r.entity_type or "",
            r.entity_id   or "",
            r.ip_address  or "",
            r.details     or "",
            r.timestamp.isoformat() if r.timestamp else "",
        ])

    output.seek(0)
    filename = f"audit_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Internal helper ───────────────────────────────────────────────────────────

def _audit_to_dict(r: AuditLog) -> dict:
    details_parsed = None
    if r.details:
        try:
            details_parsed = json.loads(r.details)
        except Exception:
            details_parsed = r.details  # return raw string if not valid JSON

    return {
        "id":          r.id,
        "username":    r.username,
        "user_role":   r.user_role,
        "action":      r.action,
        "entity_type": r.entity_type,
        "entity_id":   r.entity_id,
        "ip_address":  r.ip_address,
        "details":     details_parsed,
        "timestamp":   r.timestamp,
    }
