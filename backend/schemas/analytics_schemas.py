"""
AcadTrack — Analytics Schemas
University of Loralai, Pakistan

Pydantic models for the Analytics API (Module 4).
"""

from typing import List, Optional
from pydantic import BaseModel


# ── KPI ───────────────────────────────────────────────────────────────────────

class KPIResponse(BaseModel):
    total_students: int
    total_departments: int
    average_cgpa: Optional[float]
    at_risk_count: int
    excellent_count: int
    semesters_active: int
    total_marks_recorded: int


# ── Grade Distribution ────────────────────────────────────────────────────────

class GradeDistributionItem(BaseModel):
    grade: str          # A, A-, B+, B, B-, C+, C, C-, D, F
    count: int
    percentage: float


class GradeDistributionResponse(BaseModel):
    semester: Optional[int]
    department: Optional[str]
    academic_year: Optional[str]
    total_students: int
    distribution: List[GradeDistributionItem]


# ── CGPA Trend ────────────────────────────────────────────────────────────────

class CGPATrendItem(BaseModel):
    semester: int
    academic_year: str
    average_gpa: Optional[float]
    student_count: int


class CGPATrendResponse(BaseModel):
    department: Optional[str]
    enrollment_year: Optional[str]
    trend: List[CGPATrendItem]


# ── Subject Difficulty ────────────────────────────────────────────────────────

class SubjectDifficultyItem(BaseModel):
    subject_name: str
    department: Optional[str]
    credit_hours: int
    average_grade_point: float
    average_percentage: float
    fail_count: int
    total_students: int
    fail_rate: float
    difficulty_level: str   # "high" | "medium" | "low"


# ── Batch Comparison ──────────────────────────────────────────────────────────

class BatchComparisonItem(BaseModel):
    enrollment_year: str
    total_students: int
    average_cgpa: Optional[float]
    at_risk_count: int
    excellent_count: int
    semesters_completed: int


# ── Semester Completion ───────────────────────────────────────────────────────

class SemesterCompletionResponse(BaseModel):
    semester: int
    academic_year: str
    total_expected: int
    total_graded: int
    completion_percentage: float


# ── Department Analytics ──────────────────────────────────────────────────────

class DepartmentAnalyticsResponse(BaseModel):
    department: str
    total_students: int
    average_cgpa: Optional[float]
    highest_cgpa: Optional[float]
    lowest_cgpa: Optional[float]
    at_risk_count: int
    excellent_count: int
    grade_distribution: List[GradeDistributionItem]


# ── Merit List ────────────────────────────────────────────────────────────────

class MeritListItem(BaseModel):
    rank: int
    roll_no: str
    student_name: str
    department: str
    cgpa: float
    semesters_completed: int