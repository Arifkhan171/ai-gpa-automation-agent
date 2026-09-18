"""
AcadTrack — Analytics Router
University of Loralai, Pakistan

Module 4: Analytics API

Endpoints:
  GET /api/v1/analytics/kpi                  hod, controller, super_admin
  GET /api/v1/analytics/grade-distribution   hod, controller, super_admin
  GET /api/v1/analytics/cgpa-trend           hod, controller, super_admin
  GET /api/v1/analytics/subject-difficulty   hod, controller, super_admin
  GET /api/v1/analytics/batch-comparison     hod, controller, super_admin
  GET /api/v1/analytics/semester-completion  hod, controller, super_admin
  GET /api/v1/analytics/department-breakdown hod, controller, super_admin
  GET /api/v1/analytics/merit-list           hod, controller, super_admin
  GET /api/v1/analytics/summary-report       hod, controller, super_admin
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.utils.auth_utils import require_role
from backend.utils.grade_utils import get_grade_letter
from backend.schemas.analytics_schemas import (
    BatchComparisonItem,
    CGPATrendItem,
    CGPATrendResponse,
    DepartmentAnalyticsResponse,
    GradeDistributionItem,
    GradeDistributionResponse,
    KPIResponse,
    MeritListItem,
    SemesterCompletionResponse,
    SubjectDifficultyItem,
)
from src.models.database_models import CGPA, Mark, SemesterGPA, Student, Subject

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

# Roles that may access every analytics endpoint
_ANALYTICS_ROLES = ("hod", "controller", "super_admin")

# HEC Pakistan grade-boundary order used for distribution buckets
_GRADE_ORDER = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _grade_distribution_for_marks(marks) -> List[GradeDistributionItem]:
    """
    Given an iterable of Mark ORM objects, return all 10 HEC grade buckets
    with counts and percentages (zero-filled if no marks fall in a bucket).
    """
    counts: Dict[str, int] = {g: 0 for g in _GRADE_ORDER}
    total = 0
    for m in marks:
        if m.grade_point is not None:
            letter = get_grade_letter(float(m.grade_point))
            counts[letter] += 1
            total += 1

    distribution = []
    for grade in _GRADE_ORDER:
        count = counts[grade]
        pct = round((count / total * 100) if total > 0 else 0.0, 2)
        distribution.append(GradeDistributionItem(grade=grade, count=count, percentage=pct))
    return distribution


def _difficulty_level(fail_rate: float) -> str:
    if fail_rate >= 30.0:
        return "high"
    if fail_rate >= 15.0:
        return "medium"
    return "low"


def _extract_enrollment_year(roll_no: str) -> Optional[str]:
    """
    Extract 2-digit enrollment year from patterns like UoL/CS-F-22/001-BS.
    Returns '2022' for '22', None if no match.
    """
    m = re.search(r"[/\-]F[/\-](\d{2})[/\-]", roll_no, re.IGNORECASE)
    if m:
        yy = m.group(1)
        return f"20{yy}"
    return None


# ── Endpoint 1 — KPI ─────────────────────────────────────────────────────────

@router.get("/kpi", response_model=KPIResponse)
def get_kpi(
    department: Optional[str] = Query(None, description="Filter by department"),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Main dashboard KPI numbers for the HoD page."""

    student_q = db.query(Student)
    if department:
        student_q = student_q.filter(Student.department == department)
    student_ids = [s.id for s in student_q.all()]

    total_students = len(student_ids)
    dept_q = db.query(func.count(func.distinct(Student.department)))
    if department:
        dept_q = dept_q.filter(Student.department == department)
    total_departments = dept_q.scalar() or 0

    cgpa_q = db.query(CGPA)
    if student_ids:
        cgpa_q = cgpa_q.filter(CGPA.student_id.in_(student_ids))
    elif department:
        # department filter was given but no matching students
        cgpa_q = cgpa_q.filter(False)

    cgpa_records = cgpa_q.all()
    valid_cgpas = [r.cgpa for r in cgpa_records if r.cgpa is not None]
    average_cgpa = round(sum(valid_cgpas) / len(valid_cgpas), 4) if valid_cgpas else None

    at_risk_count = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa < 2.0)
    excellent_count = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa >= 3.5)

    sem_q = db.query(func.count(func.distinct(SemesterGPA.semester)))
    if department:
        sem_q = (
            sem_q
            .join(Student, SemesterGPA.student_id == Student.id)
            .filter(Student.department == department)
        )
    semesters_active = sem_q.scalar() or 0

    mark_q = db.query(func.count(Mark.id))
    if department:
        mark_q = (
            mark_q
            .join(Student, Mark.student_id == Student.id)
            .filter(Student.department == department)
        )
    total_marks_recorded = mark_q.scalar() or 0

    return KPIResponse(
        total_students=total_students,
        total_departments=total_departments,
        average_cgpa=average_cgpa,
        at_risk_count=at_risk_count,
        excellent_count=excellent_count,
        semesters_active=semesters_active,
        total_marks_recorded=total_marks_recorded,
    )


# ── Endpoint 2 — Grade Distribution ──────────────────────────────────────────

@router.get("/grade-distribution", response_model=GradeDistributionResponse)
def get_grade_distribution(
    semester: Optional[int] = Query(None),
    department: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Grade-bucket distribution across all marks (bar-chart data)."""

    q = db.query(Mark)
    if semester:
        q = q.filter(Mark.semester == semester)
    if academic_year:
        q = q.filter(Mark.academic_year == academic_year)
    if department:
        q = q.join(Student, Mark.student_id == Student.id).filter(
            Student.department == department
        )

    marks = q.all()
    distribution = _grade_distribution_for_marks(marks)
    total_students = sum(item.count for item in distribution)

    return GradeDistributionResponse(
        semester=semester,
        department=department,
        academic_year=academic_year,
        total_students=total_students,
        distribution=distribution,
    )


# ── Endpoint 3 — CGPA Trend ───────────────────────────────────────────────────

@router.get("/cgpa-trend", response_model=CGPATrendResponse)
def get_cgpa_trend(
    department: Optional[str] = Query(None),
    enrollment_year: Optional[str] = Query(None, description="e.g. '2022'"),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Average GPA per semester (line chart data for HoD dashboard)."""

    q = db.query(SemesterGPA)
    if department:
        q = q.join(Student, SemesterGPA.student_id == Student.id).filter(
            Student.department == department
        )

    records = q.order_by(SemesterGPA.semester.asc()).all()

    # Optional: filter by enrollment year extracted from roll_no
    if enrollment_year:
        student_ids_in_year: set[int] = set()
        students = db.query(Student).all()
        for s in students:
            yr = _extract_enrollment_year(s.roll_no)
            if yr == enrollment_year:
                student_ids_in_year.add(s.id)
        records = [r for r in records if r.student_id in student_ids_in_year]

    # Group by (semester, academic_year)
    grouped: Dict[tuple, list] = {}
    for r in records:
        key = (r.semester, r.academic_year or "")
        grouped.setdefault(key, []).append(r.gpa)

    trend = []
    for (sem, yr), gpas in sorted(grouped.items(), key=lambda x: x[0][0]):
        valid = [g for g in gpas if g is not None]
        avg_gpa = round(sum(valid) / len(valid), 4) if valid else None
        trend.append(
            CGPATrendItem(
                semester=sem,
                academic_year=yr,
                average_gpa=avg_gpa,
                student_count=len(gpas),
            )
        )

    return CGPATrendResponse(
        department=department,
        enrollment_year=enrollment_year,
        trend=trend,
    )


# ── Endpoint 4 — Subject Difficulty ──────────────────────────────────────────

@router.get("/subject-difficulty", response_model=List[SubjectDifficultyItem])
def get_subject_difficulty(
    department: Optional[str] = Query(None),
    semester: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Which subjects students struggle with most (ordered by fail rate desc)."""

    q = db.query(Mark, Subject).join(Subject, Mark.subject_id == Subject.id)
    if department:
        q = q.filter(Subject.department == department)
    if semester:
        q = q.filter(Mark.semester == semester)

    rows = q.all()

    # Group by subject
    by_subject: Dict[int, Dict] = {}
    for mark, subject in rows:
        sid = subject.id
        if sid not in by_subject:
            by_subject[sid] = {
                "subject_name": subject.subject_name,
                "department": subject.department,
                "credit_hours": subject.credit_hours,
                "grade_points": [],
                "percentages": [],
                "fail_count": 0,
                "total": 0,
            }
        entry = by_subject[sid]
        entry["total"] += 1
        if mark.grade_point is not None:
            entry["grade_points"].append(float(mark.grade_point))
            if float(mark.grade_point) < 1.0:
                entry["fail_count"] += 1
        if mark.percentage is not None:
            entry["percentages"].append(float(mark.percentage))

    results = []
    for data in by_subject.values():
        total = data["total"]
        fail_count = data["fail_count"]
        fail_rate = round((fail_count / total * 100) if total > 0 else 0.0, 2)
        gps = data["grade_points"]
        pcts = data["percentages"]
        results.append(
            SubjectDifficultyItem(
                subject_name=data["subject_name"],
                department=data["department"],
                credit_hours=data["credit_hours"],
                average_grade_point=round(sum(gps) / len(gps), 4) if gps else 0.0,
                average_percentage=round(sum(pcts) / len(pcts), 2) if pcts else 0.0,
                fail_count=fail_count,
                total_students=total,
                fail_rate=fail_rate,
                difficulty_level=_difficulty_level(fail_rate),
            )
        )

    results.sort(key=lambda x: x.fail_rate, reverse=True)
    return results


# ── Endpoint 5 — Batch Comparison ────────────────────────────────────────────

@router.get("/batch-comparison", response_model=List[BatchComparisonItem])
def get_batch_comparison(
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Compare performance across enrollment-year batches."""

    students = db.query(Student).all()
    cgpa_map: Dict[int, CGPA] = {
        r.student_id: r for r in db.query(CGPA).all()
    }

    # Group by extracted enrollment year
    batches: Dict[str, List[Student]] = {}
    for s in students:
        yr = _extract_enrollment_year(s.roll_no) or "unknown"
        batches.setdefault(yr, []).append(s)

    results = []
    for yr, batch_students in batches.items():
        cgpa_records = [cgpa_map[s.id] for s in batch_students if s.id in cgpa_map]
        valid_cgpas = [r.cgpa for r in cgpa_records if r.cgpa is not None]
        avg_cgpa = round(sum(valid_cgpas) / len(valid_cgpas), 4) if valid_cgpas else None
        at_risk = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa < 2.0)
        excellent = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa >= 3.5)
        sems = max((r.semesters_completed for r in cgpa_records), default=0)

        results.append(
            BatchComparisonItem(
                enrollment_year=yr,
                total_students=len(batch_students),
                average_cgpa=avg_cgpa,
                at_risk_count=at_risk,
                excellent_count=excellent,
                semesters_completed=sems,
            )
        )

    # Newest batch first; push 'unknown' to the end
    results.sort(
        key=lambda x: x.enrollment_year if x.enrollment_year != "unknown" else "0000",
        reverse=True,
    )
    return results


# ── Endpoint 6 — Semester Completion ─────────────────────────────────────────

@router.get("/semester-completion", response_model=List[SemesterCompletionResponse])
def get_semester_completion(
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """
    Per-semester grading completion status.
    (total_expected == total_graded until enrollment data is added.)
    """

    q = db.query(SemesterGPA)
    if department:
        q = q.join(Student, SemesterGPA.student_id == Student.id).filter(
            Student.department == department
        )

    records = q.all()

    # Group by (semester, academic_year)
    grouped: Dict[tuple, set] = {}
    for r in records:
        key = (r.semester, r.academic_year or "")
        grouped.setdefault(key, set()).add(r.student_id)

    results = []
    for (sem, yr), student_ids in sorted(grouped.items(), key=lambda x: x[0][0]):
        graded = len(student_ids)
        results.append(
            SemesterCompletionResponse(
                semester=sem,
                academic_year=yr,
                total_expected=graded,
                total_graded=graded,
                completion_percentage=100.0,
            )
        )

    return results


# ── Endpoint 7 — Department Breakdown ────────────────────────────────────────

@router.get("/department-breakdown", response_model=List[DepartmentAnalyticsResponse])
def get_department_breakdown(
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Full analytics broken down per department."""

    dept_rows = db.query(func.distinct(Student.department)).all()
    departments = [row[0] for row in dept_rows if row[0]]

    results = []
    for dept in departments:
        dept_students = db.query(Student).filter(Student.department == dept).all()
        total_students = len(dept_students)
        student_ids = [s.id for s in dept_students]

        cgpa_records = (
            db.query(CGPA).filter(CGPA.student_id.in_(student_ids)).all()
            if student_ids else []
        )
        valid_cgpas = [r.cgpa for r in cgpa_records if r.cgpa is not None]

        avg_cgpa = round(sum(valid_cgpas) / len(valid_cgpas), 4) if valid_cgpas else None
        highest_cgpa = round(max(valid_cgpas), 4) if valid_cgpas else None
        lowest_cgpa = round(min(valid_cgpas), 4) if valid_cgpas else None
        at_risk = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa < 2.0)
        excellent = sum(1 for r in cgpa_records if r.cgpa is not None and r.cgpa >= 3.5)

        marks = (
            db.query(Mark).filter(Mark.student_id.in_(student_ids)).all()
            if student_ids else []
        )
        grade_dist = _grade_distribution_for_marks(marks)

        results.append(
            DepartmentAnalyticsResponse(
                department=dept,
                total_students=total_students,
                average_cgpa=avg_cgpa,
                highest_cgpa=highest_cgpa,
                lowest_cgpa=lowest_cgpa,
                at_risk_count=at_risk,
                excellent_count=excellent,
                grade_distribution=grade_dist,
            )
        )

    return results


# ── Endpoint 8 — Merit List ───────────────────────────────────────────────────

@router.get("/merit-list", response_model=List[MeritListItem])
def get_merit_list(
    department: Optional[str] = Query(None),
    semester: Optional[int] = Query(None, description="Use semester GPA instead of CGPA"),
    top_n: int = Query(10, ge=1, le=50, description="Return top N students (max 50)"),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """Top-N students by CGPA (or semester GPA) for merit/scholarship decisions."""

    student_q = db.query(Student)
    if department:
        student_q = student_q.filter(Student.department == department)
    students = {s.id: s for s in student_q.all()}

    if not students:
        return []

    if semester:
        # Use semester-specific GPA
        sgpa_q = (
            db.query(SemesterGPA)
            .filter(
                SemesterGPA.student_id.in_(students.keys()),
                SemesterGPA.semester == semester,
            )
        )
        candidates = []
        for r in sgpa_q.all():
            if r.gpa is not None and r.student_id in students:
                s = students[r.student_id]
                # semesters_completed from CGPA or fall back to 0
                cgpa_r = db.query(CGPA).filter(CGPA.student_id == s.id).first()
                candidates.append(
                    {
                        "roll_no": s.roll_no,
                        "student_name": s.student_name,
                        "department": s.department,
                        "cgpa": round(float(r.gpa), 4),
                        "semesters_completed": cgpa_r.semesters_completed if cgpa_r else 0,
                    }
                )
        candidates.sort(key=lambda x: x["cgpa"], reverse=True)
    else:
        # Use overall CGPA
        cgpa_q = db.query(CGPA).filter(CGPA.student_id.in_(students.keys()))
        candidates = []
        for r in cgpa_q.all():
            if r.cgpa is not None and r.student_id in students:
                s = students[r.student_id]
                candidates.append(
                    {
                        "roll_no": s.roll_no,
                        "student_name": s.student_name,
                        "department": s.department,
                        "cgpa": round(float(r.cgpa), 4),
                        "semesters_completed": r.semesters_completed,
                    }
                )
        candidates.sort(key=lambda x: x["cgpa"], reverse=True)

    top = candidates[:top_n]
    return [
        MeritListItem(rank=i + 1, **item)
        for i, item in enumerate(top)
    ]


# ── Endpoint 9 — Summary Report ───────────────────────────────────────────────

@router.get("/summary-report")
def get_summary_report(
    department: Optional[str] = Query(None),
    semester: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role(*_ANALYTICS_ROLES)),
):
    """
    Combined summary suitable for PDF report generation.
    Merges KPI + grade distribution + CGPA trend +
    top-5 at-risk + top-5 Dean's List + top-5 hardest subjects.
    """

    # ── KPI ───────────────────────────────────────────────────────────────────
    kpi = get_kpi(department=department, db=db, _=None)  # role already checked

    # ── Grade Distribution ────────────────────────────────────────────────────
    grade_dist = get_grade_distribution(
        semester=semester, department=department, academic_year=academic_year, db=db, _=None
    )

    # ── CGPA Trend ────────────────────────────────────────────────────────────
    cgpa_trend_resp = get_cgpa_trend(department=department, enrollment_year=None, db=db, _=None)

    # ── Top-5 at-risk ─────────────────────────────────────────────────────────
    student_q = db.query(Student)
    if department:
        student_q = student_q.filter(Student.department == department)
    student_map = {s.id: s for s in student_q.all()}

    cgpa_q = db.query(CGPA)
    if student_map:
        cgpa_q = cgpa_q.filter(CGPA.student_id.in_(student_map.keys()))

    all_cgpa = cgpa_q.all()

    at_risk_rows = sorted(
        [r for r in all_cgpa if r.cgpa is not None and r.cgpa < 2.0],
        key=lambda x: x.cgpa,
    )[:5]
    top_at_risk = [
        {
            "roll_no": student_map[r.student_id].roll_no,
            "student_name": student_map[r.student_id].student_name,
            "department": student_map[r.student_id].department,
            "cgpa": round(float(r.cgpa), 4),
            "semesters_completed": r.semesters_completed,
        }
        for r in at_risk_rows
        if r.student_id in student_map
    ]

    # ── Top-5 Dean's List ─────────────────────────────────────────────────────
    excellent_rows = sorted(
        [r for r in all_cgpa if r.cgpa is not None and r.cgpa >= 3.5],
        key=lambda x: x.cgpa,
        reverse=True,
    )[:5]
    deans_list = [
        {
            "roll_no": student_map[r.student_id].roll_no,
            "student_name": student_map[r.student_id].student_name,
            "department": student_map[r.student_id].department,
            "cgpa": round(float(r.cgpa), 4),
            "semesters_completed": r.semesters_completed,
        }
        for r in excellent_rows
        if r.student_id in student_map
    ]

    # ── Top-5 hardest subjects ────────────────────────────────────────────────
    difficulty = get_subject_difficulty(
        department=department, semester=semester, db=db, _=None
    )
    hardest_subjects = [
        {
            "subject_name": s.subject_name,
            "department": s.department,
            "fail_rate": s.fail_rate,
            "difficulty_level": s.difficulty_level,
            "total_students": s.total_students,
            "average_grade_point": s.average_grade_point,
        }
        for s in difficulty[:5]
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {
            "department": department,
            "semester": semester,
            "academic_year": academic_year,
        },
        "kpi": kpi.model_dump(),
        "grade_distribution": [item.model_dump() for item in grade_dist.distribution],
        "cgpa_trend": [item.model_dump() for item in cgpa_trend_resp.trend],
        "top_at_risk": top_at_risk,
        "deans_list": deans_list,
        "hardest_subjects": hardest_subjects,
    }