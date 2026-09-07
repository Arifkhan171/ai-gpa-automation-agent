"""
Automated Test Cases - GPA Calculator Agent
Agentic GPA Calculation System
Tech Lead: Arif Khan
Branch: feature/calculator-db

Run with:
    pip install pytest sqlalchemy --break-system-packages   (if not already installed)
    PYTHONPATH=. pytest tests/test_calculator_agent.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.calculator_agent import (  # noqa: E402
    calculate_grade_point,
    calculate_percentage,
    calculator_agent_node,
)


def make_record(
    subject_name,
    obtained_marks,
    total_marks=100,
    credit_hours=3,
    roll_no="CS-2021-01",
    semester=1,
    academic_year="2023-2024",
    has_issues=False,
):
    return {
        "student_name": "Muhammad Arif Khan",
        "roll_no": roll_no,
        "father_name": "Ghulam Khan",
        "subject_name": subject_name,
        "total_marks": total_marks,
        "obtained_marks": obtained_marks,
        "credit_hours": credit_hours,
        "department": "CS",
        "semester": semester,
        "academic_year": academic_year,
        "has_issues": has_issues,
        "parse_warnings": [],
    }


@pytest.fixture
def db_url(tmp_path):
    """A fresh SQLite file per test so tests never interfere with each other."""
    path = tmp_path / "test_gpa.db"
    return f"sqlite:///{path}"


# --------------------------------------------------------------------------
# 1. Grade-point boundary values (pure function, no DB needed)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "percentage,expected_gp",
    [
        (100, 4.00),
        (85, 4.00),
        (84.99, 3.70),
        (80, 3.70),
        (79.99, 3.30),
        (75, 3.30),
        (74.99, 3.00),
        (70, 3.00),
        (69.99, 2.70),
        (65, 2.70),
        (64.99, 2.30),
        (61, 2.30),
        (60.99, 2.00),
        (58, 2.00),
        (57.99, 1.70),
        (55, 1.70),
        (54.99, 1.00),
        (50, 1.00),
        (49.99, 0.00),
        (0, 0.00),
    ],
)
def test_grade_point_boundaries(percentage, expected_gp):
    assert calculate_grade_point(percentage) == expected_gp


def test_percentage_calculation():
    assert calculate_percentage(72, 100) == 72.0
    assert calculate_percentage(36, 50) == 72.0
    assert calculate_percentage(0, 100) == 0.0
    assert calculate_percentage(50, 0) == 0.0  # no division by zero


# --------------------------------------------------------------------------
# 2. Basic single-subject GPA
# --------------------------------------------------------------------------

def test_basic_single_subject_gpa(db_url):
    state = {
        "validated_records": [make_record("Data Structures", 72, credit_hours=3)],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    assert result["marks_written"] == 1
    sem_gpa = result["semester_gpas"][0]
    assert sem_gpa["total_credit_hours"] == 3
    assert sem_gpa["total_quality_points"] == 9.0   # 3 CH * 3.00 GP
    assert sem_gpa["gpa"] == 3.00


# --------------------------------------------------------------------------
# 3. F grade still counts in the denominator
# --------------------------------------------------------------------------

def test_f_grade_counts_in_denominator(db_url):
    state = {
        "validated_records": [
            make_record("Calculus I", 45, credit_hours=3),   # F -> 0.00 GP
            make_record("Data Structures", 90, credit_hours=3),  # 90% -> 4.00 GP
        ],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    sem_gpa = result["semester_gpas"][0]
    # denominator MUST include the F-grade subject's credit hours
    assert sem_gpa["total_credit_hours"] == 6
    assert sem_gpa["total_quality_points"] == 12.0   # 0 + (3*4.00)
    assert sem_gpa["gpa"] == round(12.0 / 6, 2)


# --------------------------------------------------------------------------
# 4. Non-credit subject excluded entirely
# --------------------------------------------------------------------------

def test_non_credit_subject_excluded(db_url):
    state = {
        "validated_records": [
            make_record("Sports", 95, credit_hours=0),        # excluded
            make_record("Data Structures", 90, credit_hours=3),  # 90% -> 4.00 GP
        ],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    sem_gpa = result["semester_gpas"][0]
    assert sem_gpa["total_credit_hours"] == 3         # Sports CH not counted
    assert sem_gpa["total_quality_points"] == 12.0    # 3 * 4.00
    assert sem_gpa["gpa"] == 4.00


# --------------------------------------------------------------------------
# 5. All subjects non-credit -> GPA is NULL
# --------------------------------------------------------------------------

def test_all_non_credit_gpa_is_null(db_url):
    state = {
        "validated_records": [
            make_record("Sports", 95, credit_hours=0),
            make_record("Co-Curricular", 88, credit_hours=0),
        ],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    sem_gpa = result["semester_gpas"][0]
    assert sem_gpa["total_credit_hours"] == 0
    assert sem_gpa["gpa"] is None


# --------------------------------------------------------------------------
# 6. CGPA pools RAW numbers across semesters - never averages GPAs
# --------------------------------------------------------------------------

def test_cgpa_pools_raw_numbers_not_averaging(db_url):
    state = {
        "validated_records": [
            # Semester 1: 6 credit hours, GPA 3.00
            make_record("Data Structures", 72, credit_hours=3, semester=1),
            make_record("Discrete Math", 72, credit_hours=3, semester=1),
            # Semester 2: 3 credit hours, GPA 4.00 (90% -> 4.00 GP)
            make_record("Databases", 90, credit_hours=3, semester=2),
        ],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    # naive (WRONG) average of GPAs would be (3.00 + 4.00) / 2 = 3.50
    wrong_average = round((3.00 + 4.00) / 2, 2)

    cgpa_row = result["cgpas"][0]
    # correct pooled CGPA: total_qp = (3*3.00)+(3*3.00)+(3*4.00) = 30
    total_ch = 3 + 3 + 3
    total_qp = (3 * 3.00) + (3 * 3.00) + (3 * 4.00)
    expected_cgpa = round(total_qp / total_ch, 2)

    assert cgpa_row["total_credit_hours"] == total_ch
    assert cgpa_row["cgpa"] == expected_cgpa
    assert cgpa_row["cgpa"] != wrong_average
    assert cgpa_row["semesters_completed"] == 2


# --------------------------------------------------------------------------
# 7. has_issues=True records are skipped, not written
# --------------------------------------------------------------------------

def test_has_issues_records_are_skipped(db_url):
    state = {
        "validated_records": [
            make_record("Data Structures", 72, credit_hours=3, has_issues=True),
        ],
        "db_url": db_url,
    }
    result = calculator_agent_node(state)

    assert result["marks_written"] == 0
    assert result["semester_gpas"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0]["roll_no"] == "CS-2021-01"


# --------------------------------------------------------------------------
# 8. Re-submitting the same subject/semester updates in place (no duplicate row,
#    no UNIQUE constraint crash) and the GPA reflects the corrected marks
# --------------------------------------------------------------------------

def test_resubmitting_same_mark_updates_not_duplicates(db_url):
    state = {
        "validated_records": [make_record("Data Structures", 60, credit_hours=3)],
        "db_url": db_url,
    }
    first = calculator_agent_node(state)
    assert first["semester_gpas"][0]["gpa"] == 2.00  # 60% -> 2.00 GP (58-60.99 band)

    # Same student/subject/semester/year, corrected marks
    state2 = {
        "validated_records": [make_record("Data Structures", 90, credit_hours=3)],
        "db_url": db_url,
    }
    second = calculator_agent_node(state2)

    assert second["marks_written"] == 1
    assert second["semester_gpas"][0]["gpa"] == 4.00  # updated, not duplicated (90% -> 4.00 GP)
    assert second["semester_gpas"][0]["total_credit_hours"] == 3  # not 6