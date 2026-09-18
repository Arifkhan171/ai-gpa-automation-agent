"""
AcadTrack — Student Pydantic Schemas
University of Loralai, Pakistan

Module 3: Student and Grades Read API

Schemas:
  SubjectMarkResponse      — one subject's marks inside a semester
  SemesterDetailResponse   — one semester with all its subject marks
  StudentSummaryResponse   — lightweight student card (for list views)
  StudentDetailResponse    — full student record with nested semesters
  PaginatedStudentResponse — paginated wrapper for student lists
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ── Subject-level mark ────────────────────────────────────────────────────────
class SubjectMarkResponse(BaseModel):
    subject_name: str
    credit_hours: int
    obtained_marks: float
    total_marks: float
    percentage: float
    grade_point: float
    grade: str          # letter grade from get_grade_letter()
    quality_points: float
    is_non_credit: bool


# ── Semester detail (includes all subjects) ───────────────────────────────────
class SemesterDetailResponse(BaseModel):
    semester: int
    academic_year: str
    subjects: List[SubjectMarkResponse]
    total_credit_hours: float
    total_quality_points: float
    gpa: Optional[float]    # None when every subject is non-credit


# ── Lightweight student card (list / search views) ────────────────────────────
class StudentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    roll_no: str
    student_name: str
    father_name: Optional[str] = None
    department: Optional[str] = None
    cgpa: Optional[float] = None
    total_credit_hours: float = 0.0
    semesters_completed: int = 0
    status: str
    # Status values:
    #   "excellent"    → cgpa >= 3.5
    #   "good"         → cgpa >= 2.5
    #   "satisfactory" → cgpa >= 2.0
    #   "at_risk"      → cgpa < 2.0
    #   "no_grades"    → cgpa is None


# ── Full student record (detail view) ────────────────────────────────────────
class StudentDetailResponse(BaseModel):
    id: int
    roll_no: str
    student_name: str
    father_name: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime
    cgpa: Optional[float] = None
    total_credit_hours: float = 0.0
    semesters_completed: int = 0
    status: str
    semesters: List[SemesterDetailResponse]


# ── Paginated wrapper for student lists ───────────────────────────────────────
class PaginatedStudentResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    students: List[StudentSummaryResponse]
