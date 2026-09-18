"""
AcadTrack — Students Router
University of Loralai, Pakistan

Module 3: Student and Grades Read API  (READ-ONLY)

Endpoints:
  GET  /api/v1/students                          coordinator, hod, controller, super_admin
  GET  /api/v1/students/at-risk                  coordinator, hod, controller, super_admin
  GET  /api/v1/students/deans-list               coordinator, hod, controller, super_admin
  GET  /api/v1/students/search                   coordinator, hod, controller, super_admin
  GET  /api/v1/students/department-summary       hod, controller, super_admin
  GET  /api/v1/students/{roll_no}                any authenticated user *
  GET  /api/v1/students/{roll_no}/semesters/{n}  any authenticated user *
  GET  /api/v1/students/{roll_no}/cgpa-history   any authenticated user *

  * students can only access their own roll_no (HTTP 403 otherwise).
    Convention: a student user's username == their roll_no.

IMPORTANT — route ordering:
  Static paths (/at-risk, /deans-list, /search, /department-summary) are
  declared BEFORE the dynamic /{roll_no} route so FastAPI does not swallow
  them as path parameters.
"""

from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.database import get_db
from backend.utils.auth_utils import get_current_user, require_role
from backend.schemas.student_schemas import (
    PaginatedStudentResponse,
    SemesterDetailResponse,
    StudentDetailResponse,
    StudentSummaryResponse,
    SubjectMarkResponse,
)
from backend.utils.grade_utils import get_grade_letter
from src.models.database_models import CGPA, Mark, SemesterGPA, Student, Subject

router = APIRouter(prefix="/api/v1/students", tags=["Students"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_status(cgpa: Optional[float]) -> str:
    """Derive a student's academic status from their CGPA."""
    if cgpa is None:
        return "no_grades"
    if cgpa >= 3.5:
        return "excellent"
    if cgpa >= 2.5:
        return "good"
    if cgpa >= 2.0:
        return "satisfactory"
    return "at_risk"


def _to_summary(student: Student, cgpa_rec: Optional[CGPA]) -> StudentSummaryResponse:
    """Build a lightweight StudentSummaryResponse from ORM objects."""
    cgpa_val = cgpa_rec.cgpa if cgpa_rec else None
    return StudentSummaryResponse(
        id=student.id,
        roll_no=student.roll_no,
        student_name=student.student_name,
        father_name=student.father_name,
        department=student.department,
        cgpa=cgpa_val,
        total_credit_hours=cgpa_rec.total_credit_hours if cgpa_rec else 0.0,
        semesters_completed=cgpa_rec.semesters_completed if cgpa_rec else 0,
        status=_get_status(cgpa_val),
    )


def _check_own_access(current_user, roll_no: str) -> None:
    """
    Raise HTTP 403 when a student tries to access another student's data.
    Student accounts use their roll_no as their username.
    """
    if current_user.role == "student" and current_user.username != roll_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only access their own academic data",
        )


def _student_or_404(roll_no: str, db: Session) -> Student:
    """Load a Student by roll_no or raise HTTP 404."""
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{roll_no}' not found",
        )
    return student


def _build_semester_detail(
    student_id: int,
    sem_gpa: SemesterGPA,
    db: Session,
) -> SemesterDetailResponse:
    """Build a SemesterDetailResponse for a single SemesterGPA record."""
    rows = (
        db.query(Mark, Subject)
        .join(Subject, Mark.subject_id == Subject.id)
        .filter(
            Mark.student_id == student_id,
            Mark.semester == sem_gpa.semester,
            Mark.academic_year == sem_gpa.academic_year,
        )
        .order_by(Subject.subject_name.asc())
        .all()
    )

    subjects = [
        SubjectMarkResponse(
            subject_name=subj.subject_name,
            credit_hours=subj.credit_hours,
            obtained_marks=mark.obtained_marks,
            total_marks=mark.total_marks,
            percentage=mark.percentage,
            grade_point=mark.grade_point,
            grade=get_grade_letter(mark.grade_point),
            quality_points=mark.quality_points,
            is_non_credit=mark.is_non_credit,
        )
        for mark, subj in rows
    ]

    return SemesterDetailResponse(
        semester=sem_gpa.semester,
        academic_year=sem_gpa.academic_year,
        subjects=subjects,
        total_credit_hours=sem_gpa.total_credit_hours,
        total_quality_points=sem_gpa.total_quality_points,
        gpa=sem_gpa.gpa,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STATIC ROUTES — must be declared BEFORE /{roll_no}
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. GET /api/v1/students ───────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedStudentResponse,
    summary="Paginated list of all students with optional filters",
)
def list_students(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    search: Optional[str] = Query(None, description="Partial match on student_name or roll_no"),
    department: Optional[str] = Query(None, description="Exact department code, e.g. 'CS'"),
    status: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: excellent | good | satisfactory | at_risk | no_grades",
    ),
    semester: Optional[int] = Query(None, description="Only students who have grades in this semester"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "hod", "controller", "super_admin")),
):
    """
    Returns a paginated list of students joined with their CGPA record.
    Each student includes a computed *status* field based on their CGPA.
    """
    query = (
        db.query(Student, CGPA)
        .outerjoin(CGPA, Student.id == CGPA.student_id)
    )

    # Search: case-insensitive partial match on name or roll_no
    if search:
        pat = f"%{search}%"
        query = query.filter(
            or_(
                Student.student_name.ilike(pat),
                Student.roll_no.ilike(pat),
            )
        )

    # Department: exact match
    if department:
        query = query.filter(Student.department == department)

    # Status: translate to CGPA range filter
    if status:
        if status == "excellent":
            query = query.filter(CGPA.cgpa >= 3.5)
        elif status == "good":
            query = query.filter(CGPA.cgpa >= 2.5, CGPA.cgpa < 3.5)
        elif status == "satisfactory":
            query = query.filter(CGPA.cgpa >= 2.0, CGPA.cgpa < 2.5)
        elif status == "at_risk":
            query = query.filter(CGPA.cgpa < 2.0)
        elif status == "no_grades":
            query = query.filter(CGPA.cgpa.is_(None))

    # Semester: students who have a SemesterGPA row for that semester
    if semester is not None:
        subq = db.query(SemesterGPA.student_id).filter(
            SemesterGPA.semester == semester
        )
        query = query.filter(Student.id.in_(subq))

    total = query.count()
    offset = (page - 1) * page_size
    rows = query.order_by(Student.student_name.asc()).offset(offset).limit(page_size).all()

    return PaginatedStudentResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
        students=[_to_summary(s, c) for s, c in rows],
    )


# ── 2. GET /api/v1/students/at-risk ──────────────────────────────────────────
@router.get(
    "/at-risk",
    response_model=List[StudentSummaryResponse],
    summary="Students with CGPA below 2.0, ordered lowest first",
)
def at_risk_students(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "hod", "controller", "super_admin")),
):
    rows = (
        db.query(Student, CGPA)
        .join(CGPA, Student.id == CGPA.student_id)   # inner join — must have a CGPA record
        .filter(CGPA.cgpa < 2.0)
        .order_by(CGPA.cgpa.asc())
        .all()
    )
    return [_to_summary(s, c) for s, c in rows]


# ── 3. GET /api/v1/students/deans-list ───────────────────────────────────────
@router.get(
    "/deans-list",
    response_model=List[StudentSummaryResponse],
    summary="Students with CGPA >= 3.5, ordered highest first",
)
def deans_list(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "hod", "controller", "super_admin")),
):
    rows = (
        db.query(Student, CGPA)
        .join(CGPA, Student.id == CGPA.student_id)
        .filter(CGPA.cgpa >= 3.5)
        .order_by(CGPA.cgpa.desc())
        .all()
    )
    return [_to_summary(s, c) for s, c in rows]


# ── 4. GET /api/v1/students/search ───────────────────────────────────────────
@router.get(
    "/search",
    response_model=List[StudentSummaryResponse],
    summary="Fast autocomplete search — min 2 chars, max 10 results",
)
def search_students(
    q: str = Query(..., min_length=2, description="Search string (minimum 2 characters)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("coordinator", "hod", "controller", "super_admin")),
):
    pat = f"%{q}%"
    rows = (
        db.query(Student, CGPA)
        .outerjoin(CGPA, Student.id == CGPA.student_id)
        .filter(
            or_(
                Student.student_name.ilike(pat),
                Student.roll_no.ilike(pat),
            )
        )
        .order_by(Student.student_name.asc())
        .limit(10)
        .all()
    )
    return [_to_summary(s, c) for s, c in rows]


# ── 5. GET /api/v1/students/department-summary ────────────────────────────────
@router.get(
    "/department-summary",
    summary="GPA statistics aggregated by department",
)
def department_summary(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("hod", "controller", "super_admin")),
):
    """
    Returns a list of per-department statistics:
      department, total_students, average_cgpa,
      at_risk_count, excellent_count, good_count, satisfactory_count
    """
    rows = (
        db.query(Student, CGPA)
        .outerjoin(CGPA, Student.id == CGPA.student_id)
        .all()
    )

    # Aggregate in Python — straightforward and database-agnostic
    buckets: dict = {}
    for student, cgpa_rec in rows:
        dept = student.department or "Unknown"
        if dept not in buckets:
            buckets[dept] = {
                "department": dept,
                "total_students": 0,
                "_cgpa_sum": 0.0,
                "_cgpa_count": 0,
                "at_risk_count": 0,
                "excellent_count": 0,
                "good_count": 0,
                "satisfactory_count": 0,
            }
        b = buckets[dept]
        b["total_students"] += 1

        cgpa_val = cgpa_rec.cgpa if cgpa_rec else None
        if cgpa_val is not None:
            b["_cgpa_sum"] += cgpa_val
            b["_cgpa_count"] += 1
            st = _get_status(cgpa_val)
            b[f"{st}_count"] = b.get(f"{st}_count", 0) + 1

    result = []
    for b in sorted(buckets.values(), key=lambda x: x["department"]):
        n = b["_cgpa_count"]
        result.append({
            "department": b["department"],
            "total_students": b["total_students"],
            "average_cgpa": round(b["_cgpa_sum"] / n, 2) if n > 0 else None,
            "at_risk_count": b["at_risk_count"],
            "excellent_count": b["excellent_count"],
            "good_count": b["good_count"],
            "satisfactory_count": b["satisfactory_count"],
        })
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC ROUTES — /{roll_no} and sub-paths
# ═══════════════════════════════════════════════════════════════════════════════


# ── 7. GET /api/v1/students/{roll_no}/semesters/{semester} ───────────────────
@router.get(
    "/{roll_no:path}/semesters/{semester_no}",
    response_model=SemesterDetailResponse,
    summary="Grades and GPA for one specific semester",
)
def get_student_semester(
    roll_no: str,
    semester_no: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _check_own_access(current_user, roll_no)

    student = _student_or_404(roll_no, db)

    sem_gpa = (
        db.query(SemesterGPA)
        .filter(
            SemesterGPA.student_id == student.id,
            SemesterGPA.semester == semester_no,
        )
        .first()
    )
    if not sem_gpa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for semester {semester_no} for student '{roll_no}'",
        )

    return _build_semester_detail(student.id, sem_gpa, db)


# ── 8. GET /api/v1/students/{roll_no}/cgpa-history ───────────────────────────
@router.get(
    "/{roll_no:path}/cgpa-history",
    summary="Running CGPA progression after each semester (HEC standard)",
)
def get_cgpa_history(
    roll_no: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns a list of objects — one per semester — showing:
      semester, academic_year, semester_gpa,
      cgpa_after_semester (cumulative), total_credit_hours_so_far

    The cumulative CGPA is computed as:
      sum(quality_points for semesters 1..N) / sum(credit_hours for semesters 1..N)
    which is the HEC Pakistan standard.
    """
    _check_own_access(current_user, roll_no)

    student = _student_or_404(roll_no, db)

    semester_gpas = (
        db.query(SemesterGPA)
        .filter(SemesterGPA.student_id == student.id)
        .order_by(SemesterGPA.semester.asc())
        .all()
    )

    history = []
    running_qp = 0.0
    running_ch = 0.0

    for sg in semester_gpas:
        running_qp += sg.total_quality_points
        running_ch += sg.total_credit_hours

        cgpa_so_far = round(running_qp / running_ch, 2) if running_ch > 0 else None

        history.append({
            "semester": sg.semester,
            "academic_year": sg.academic_year,
            "semester_gpa": sg.gpa,
            "cgpa_after_semester": cgpa_so_far,
            "total_credit_hours_so_far": running_ch,
        })

    return history
# ── 6. GET /api/v1/students/{roll_no} ────────────────────────────────────────
@router.get(
    "/{roll_no:path}",
    response_model=StudentDetailResponse,
    summary="Full student record with all semesters and subject marks",
)
def get_student(
    roll_no: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns the complete academic record for a student.
    Students can only fetch their own record (username == roll_no).
    Coordinators, HoD, controller, and super_admin can fetch any student.
    """
    _check_own_access(current_user, roll_no)

    student = _student_or_404(roll_no, db)
    cgpa_rec = db.query(CGPA).filter(CGPA.student_id == student.id).first()

    semester_gpas = (
        db.query(SemesterGPA)
        .filter(SemesterGPA.student_id == student.id)
        .order_by(SemesterGPA.semester.asc())
        .all()
    )

    semesters_out = [
        _build_semester_detail(student.id, sg, db)
        for sg in semester_gpas
    ]

    cgpa_val = cgpa_rec.cgpa if cgpa_rec else None

    return StudentDetailResponse(
        id=student.id,
        roll_no=student.roll_no,
        student_name=student.student_name,
        father_name=student.father_name,
        department=student.department,
        created_at=student.created_at,
        cgpa=cgpa_val,
        total_credit_hours=cgpa_rec.total_credit_hours if cgpa_rec else 0.0,
        semesters_completed=cgpa_rec.semesters_completed if cgpa_rec else 0,
        status=_get_status(cgpa_val),
        semesters=semesters_out,
    )

