"""
calculator_agent.py
-------------------
LangGraph Node 5 — GPA Calculator Agent.
Applies the HEC Pakistan GPA formula to clean
validated student records.

ASSIGNED TO : Engineer 3 (feature/calculator-db)
STATUS      : NOT STARTED

Formula:
  percentage  = (obtained_marks / total_marks) * 100
  grade_point = lookup from HEC grading table
  quality_pts = credit_hours * grade_point
  GPA         = sum(quality_pts) / sum(credit_hours)
  CGPA        = sum(ALL quality_pts) / sum(ALL credit_hours)
"""

# Your code goes here
"""
GPA Calculator Agent - Node 5 in LangGraph Pipeline
Agentic GPA Calculation System
Tech Lead: Arif Khan
Branch: feature/calculator-db

Consumes clean validated records from the Validation Agent, computes
percentage / grade_point / quality_points per the HEC Pakistan standard,
persists Student / Subject / Mark rows, and recalculates SemesterGPA + CGPA.

CGPA always pools RAW quality_points and credit_hours across every semester
for a student - it never averages per-semester GPA values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.models.database_models import CGPA, Base, Mark, SemesterGPA, Student, Subject

DEFAULT_DB_URL = "sqlite:///gpa_system.db"


# --------------------------------------------------------------------------
# Engine / session helpers
# --------------------------------------------------------------------------

def get_engine(db_url: str = DEFAULT_DB_URL):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(db_url: str = DEFAULT_DB_URL):
    engine = get_engine(db_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


# --------------------------------------------------------------------------
# HEC Pakistan grade point lookup
# --------------------------------------------------------------------------

GRADE_TABLE: List[Tuple[float, float]] = [
    (85, 4.00),
    (80, 3.70),
    (75, 3.30),
    (70, 3.00),
    (65, 2.70),
    (61, 2.30),
    (58, 2.00),
    (55, 1.70),
    (50, 1.00),
]


def calculate_grade_point(percentage: float) -> float:
    for threshold, gp in GRADE_TABLE:
        if percentage >= threshold:
            return gp
    return 0.00


def calculate_percentage(obtained_marks: float, total_marks: float) -> float:
    if not total_marks:
        return 0.0
    return (obtained_marks / total_marks) * 100


# --------------------------------------------------------------------------
# Get-or-create helpers
# --------------------------------------------------------------------------

def get_or_create_student(session: Session, record: Dict[str, Any]) -> Student:
    roll_no = record["roll_no"]
    student = session.execute(
        select(Student).where(Student.roll_no == roll_no)
    ).scalar_one_or_none()

    if student is None:
        student = Student(
            roll_no=roll_no,
            student_name=record.get("student_name", ""),
            father_name=record.get("father_name"),
            department=record.get("department"),
        )
        session.add(student)
        session.flush()
    else:
        student.student_name = record.get("student_name", student.student_name)
        student.father_name = record.get("father_name", student.father_name)
        student.department = record.get("department", student.department)

    return student


def get_or_create_subject(session: Session, record: Dict[str, Any]) -> Subject:
    subject_name = record["subject_name"]
    subject = session.execute(
        select(Subject).where(Subject.subject_name == subject_name)
    ).scalar_one_or_none()

    if subject is None:
        subject = Subject(
            subject_name=subject_name,
            credit_hours=record.get("credit_hours", 0),
            department=record.get("department"),
        )
        session.add(subject)
        session.flush()
    else:
        subject.credit_hours = record.get("credit_hours", subject.credit_hours)

    return subject


# --------------------------------------------------------------------------
# Mark upsert
# --------------------------------------------------------------------------

def upsert_mark(
    session: Session,
    student: Student,
    subject: Subject,
    record: Dict[str, Any],
    semester: int,
    academic_year: str,
    approved_by: Optional[str] = None,
    source_file: Optional[str] = None,
) -> Mark:
    total_marks = float(record["total_marks"])
    obtained_marks = float(record["obtained_marks"])
    credit_hours = record.get("credit_hours", subject.credit_hours) or 0

    # Grade lookup uses the RAW percentage (not pre-rounded) so boundary
    # cases (e.g. 84.996%) land on the correct grade band.
    raw_percentage = calculate_percentage(obtained_marks, total_marks)
    grade_point = calculate_grade_point(raw_percentage)

    is_non_credit = credit_hours == 0
    # Non-credit subjects earn no quality points and are excluded from GPA
    # math entirely, but percentage / grade_point are still recorded for
    # the transcript.
    quality_points = 0.0 if is_non_credit else round(credit_hours * grade_point, 2)

    mark = session.execute(
        select(Mark).where(
            Mark.student_id == student.id,
            Mark.subject_id == subject.id,
            Mark.semester == semester,
            Mark.academic_year == academic_year,
        )
    ).scalar_one_or_none()

    if mark is None:
        mark = Mark(
            student_id=student.id,
            subject_id=subject.id,
            semester=semester,
            academic_year=academic_year,
        )
        session.add(mark)

    mark.total_marks = total_marks
    mark.obtained_marks = obtained_marks
    mark.percentage = round(raw_percentage, 2)
    mark.grade_point = grade_point
    mark.quality_points = quality_points
    mark.is_non_credit = is_non_credit
    mark.approved_by = approved_by
    mark.approved_at = datetime.utcnow() if approved_by else mark.approved_at
    mark.source_file = source_file

    session.flush()
    return mark


# --------------------------------------------------------------------------
# Semester GPA + CGPA recalculation
# --------------------------------------------------------------------------

def recompute_semester_gpa(
    session: Session, student_id: int, semester: int, academic_year: str
) -> SemesterGPA:
    marks = session.execute(
        select(Mark).where(
            Mark.student_id == student_id,
            Mark.semester == semester,
            Mark.academic_year == academic_year,
        )
    ).scalars().all()

    # credit_hours = 0 subjects are excluded entirely, even from the
    # denominator. F grades (grade_point 0.00) with real credit hours DO
    # count in the denominator - they are simply not filtered out here.
    credit_marks = [m for m in marks if not m.is_non_credit]

    total_credit_hours = 0.0
    total_quality_points = 0.0
    for m in credit_marks:
        subject = session.get(Subject, m.subject_id)
        ch = subject.credit_hours if subject else 0
        total_credit_hours += ch
        total_quality_points += m.quality_points

    gpa: Optional[float] = None
    if total_credit_hours > 0:
        gpa = round(total_quality_points / total_credit_hours, 2)
    # else: every subject this semester was non-credit -> GPA stays NULL

    sem_gpa = session.execute(
        select(SemesterGPA).where(
            SemesterGPA.student_id == student_id,
            SemesterGPA.semester == semester,
            SemesterGPA.academic_year == academic_year,
        )
    ).scalar_one_or_none()

    if sem_gpa is None:
        sem_gpa = SemesterGPA(
            student_id=student_id,
            semester=semester,
            academic_year=academic_year,
        )
        session.add(sem_gpa)

    sem_gpa.total_credit_hours = total_credit_hours
    sem_gpa.total_quality_points = round(total_quality_points, 2)
    sem_gpa.gpa = gpa
    sem_gpa.calculated_at = datetime.utcnow()

    session.flush()
    return sem_gpa


def recompute_cgpa(session: Session, student_id: int) -> CGPA:
    # CGPA pools RAW quality_points / credit_hours across every semester -
    # NEVER averages the per-semester GPA values.
    sem_gpas = session.execute(
        select(SemesterGPA).where(SemesterGPA.student_id == student_id)
    ).scalars().all()

    total_credit_hours = sum(s.total_credit_hours for s in sem_gpas)
    total_quality_points = sum(s.total_quality_points for s in sem_gpas)
    semesters_completed = sum(1 for s in sem_gpas if s.gpa is not None)

    cgpa_value: Optional[float] = None
    if total_credit_hours > 0:
        cgpa_value = round(total_quality_points / total_credit_hours, 2)

    cgpa_row = session.execute(
        select(CGPA).where(CGPA.student_id == student_id)
    ).scalar_one_or_none()

    if cgpa_row is None:
        cgpa_row = CGPA(student_id=student_id)
        session.add(cgpa_row)

    cgpa_row.total_credit_hours = total_credit_hours
    cgpa_row.total_quality_points = round(total_quality_points, 2)
    cgpa_row.cgpa = cgpa_value
    cgpa_row.semesters_completed = semesters_completed
    cgpa_row.last_updated = datetime.utcnow()

    session.flush()
    return cgpa_row


# --------------------------------------------------------------------------
# LangGraph Node 5 - GPA Calculator Agent
# --------------------------------------------------------------------------

def calculator_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph pipeline node.

    Expected incoming state keys:
      - validated_records: List[dict]   (clean records from the Validation Agent)
      - semester: int                   (fallback if a record has no "semester" key)
      - academic_year: str               (fallback if a record has no "academic_year" key)
      - db_url: str                     (optional, defaults to local SQLite file)
      - approved_by: str                (optional, audit trail)
      - source_file: str                (optional, audit trail)

    Adds to outgoing state:
      - marks_written: int
      - semester_gpas: List[dict]
      - cgpas: List[dict]
      - errors: List[dict]              (appended to, never overwritten)
    """
    records: List[Dict[str, Any]] = state.get("validated_records", [])
    default_semester = state.get("semester", 1)
    default_academic_year = state.get("academic_year", "2024-2025")
    db_url = state.get("db_url", DEFAULT_DB_URL)
    approved_by = state.get("approved_by")
    source_file = state.get("source_file")

    session_factory = get_session_factory(db_url)
    session = session_factory()

    marks_written = 0
    errors: List[Dict[str, Any]] = []
    touched: Set[Tuple[int, int, str]] = set()  # (student_id, semester, academic_year)
    semester_gpa_results: List[Dict[str, Any]] = []
    cgpa_results: List[Dict[str, Any]] = []

    try:
        for record in records:
            if record.get("has_issues"):
                errors.append({
                    "roll_no": record.get("roll_no"),
                    "reason": "has_issues=True, skipped by calculator agent",
                    "parse_warnings": record.get("parse_warnings", []),
                })
                continue

            try:
                semester = record.get("semester", default_semester)
                academic_year = record.get("academic_year", default_academic_year)

                student = get_or_create_student(session, record)
                subject = get_or_create_subject(session, record)

                upsert_mark(
                    session,
                    student,
                    subject,
                    record,
                    semester=semester,
                    academic_year=academic_year,
                    approved_by=approved_by,
                    source_file=source_file,
                )

                marks_written += 1
                touched.add((student.id, semester, academic_year))

            except Exception as exc:  # per-record isolation, don't kill the batch
                errors.append({
                    "roll_no": record.get("roll_no"),
                    "reason": str(exc),
                })

        for student_id, semester, academic_year in touched:
            sem_gpa = recompute_semester_gpa(session, student_id, semester, academic_year)
            semester_gpa_results.append({
                "student_id": sem_gpa.student_id,
                "semester": sem_gpa.semester,
                "academic_year": sem_gpa.academic_year,
                "total_credit_hours": sem_gpa.total_credit_hours,
                "total_quality_points": sem_gpa.total_quality_points,
                "gpa": sem_gpa.gpa,
            })

        cgpa_students = {student_id for student_id, _, _ in touched}
        for student_id in cgpa_students:
            cgpa_row = recompute_cgpa(session, student_id)
            cgpa_results.append({
                "student_id": cgpa_row.student_id,
                "total_credit_hours": cgpa_row.total_credit_hours,
                "total_quality_points": cgpa_row.total_quality_points,
                "cgpa": cgpa_row.cgpa,
                "semesters_completed": cgpa_row.semesters_completed,
            })

        session.commit()

    except Exception as exc:
        session.rollback()
        errors.append({"roll_no": None, "reason": f"batch failure: {exc}"})
        semester_gpa_results = []
        cgpa_results = []
    finally:
        session.close()

    state["marks_written"] = marks_written
    state["semester_gpas"] = semester_gpa_results
    state["cgpas"] = cgpa_results
    state["errors"] = state.get("errors", []) + errors
    return state


# --------------------------------------------------------------------------
# Manual smoke test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sample_state = {
        "validated_records": [
            {
                "student_name": "Muhammad Arif Khan",
                "roll_no": "CS-2021-01",
                "father_name": "Ghulam Khan",
                "subject_name": "Data Structures",
                "total_marks": 100,
                "obtained_marks": 72,
                "credit_hours": 3,
                "department": "CS",
                "has_issues": False,
                "parse_warnings": [],
            }
        ],
        "semester": 3,
        "academic_year": "2023-2024",
        "db_url": "sqlite:///gpa_smoke_test.db",
    }

    result_state = calculator_agent_node(sample_state)
    print("marks_written:", result_state["marks_written"])
    print("semester_gpas:", result_state["semester_gpas"])
    print("cgpas:", result_state["cgpas"])
    print("errors:", result_state["errors"])