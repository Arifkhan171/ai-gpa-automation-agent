
# Agentic GPA Calculation System
**University of Loralai — Final Year Project**
**Tech Lead:** Arif Khan, AI Engineer

---

## 1. Project Overview

The Agentic GPA Calculation System is an AI-powered pipeline that:

1. Reads student mark sheets from Google Drive (Excel format)
2. Parses and extracts the data using openpyxl
3. Validates every data point against 18 defined edge case rules
4. Calculates GPA using the university grading formula
5. Writes results to a database (SQLite in development, PostgreSQL in production)
6. Presents a Human-in-the-Loop (HITL) dashboard via Streamlit for review and approval

The system is built using **LangGraph** for agent orchestration — meaning each major function (parsing, validation, calculation) is a separate AI agent node in a graph pipeline.

---

## 2. Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.11+** | Core programming language |
| **LangGraph** | Agent orchestration and pipeline management |
| **Google Drive API** | Reading Excel mark sheets from Drive |
| **openpyxl** | Parsing and extracting data from Excel files |
| **Pydantic v2** | Data validation and edge case enforcement |
| **SQLAlchemy** | ORM for all database operations |
| **SQLite** | Development database (local) |
| **PostgreSQL** | Production database (deployment) |
| **Streamlit** | Human-in-the-Loop dashboard for final review |

---

## 3. System Architecture — Agent Pipeline

```
Google Drive (Excel Files)
        ↓
[ Parser Agent ]          ← Engineer 1 builds this
Reads Excel → Returns list of Python dicts
        ↓
[ Validation Agent ]      ← Engineer 2 builds this
Checks EC-01 to EC-18 → Returns validation report
        ↓
[ GPA Calculator Agent ]  ← Engineer 3 builds this
Applies GPA formula → Writes results to database
        ↓
[ Streamlit Dashboard ]   ← Human-in-the-Loop review
Tech Lead reviews → Approves or rejects
```

Each block above is a **LangGraph node**. They connect as a directed graph. Data flows from one node to the next only when the previous node completes successfully.

---

## 4. Repository Structure

Every engineer must follow this exact folder structure. Do not create folders outside of this structure without approval from the Tech Lead.

```
gpa-agentic-system/
│
├── agents/
│   ├── parser_agent.py          ← Engineer 1
│   ├── validation_agent.py      ← Engineer 2
│   └── calculator_agent.py      ← Engineer 3
│
├── models/
│   └── database_models.py       ← Engineer 3
│
├── validators/
│   └── edge_cases.py            ← Engineer 2
│
├── utils/
│   └── drive_connector.py       ← Engineer 1
│
├── dashboard/
│   └── app.py                   ← Tech Lead (later)
│
├── tests/
│   ├── test_parser.py           ← Engineer 1
│   ├── test_validation.py       ← Engineer 2
│   └── test_calculator.py       ← Engineer 3
│
├── requirements.txt             ← Engineer 1 creates this
├── .env.example                 ← Engineer 1 creates this
├── README.md                    ← Already exists
└── PROJECT_BRIEF.md             ← This file
```

---

## 5. Engineer Assignments

---

### ENGINEER 1 — Project Setup + Excel Parser Agent
**Branch:** `feature/parser-agent`
**Files to create:**
- `requirements.txt`
- `.env.example`
- `utils/drive_connector.py`
- `agents/parser_agent.py`
- `tests/test_parser.py`

**Deliverable:**
A function called `parse_marksheet(file_path: str) -> list[dict]` that:
- Accepts a path to an Excel (.xlsx) file
- Reads it using openpyxl
- Returns a list of Python dictionaries, one per student row
- Each dictionary must contain these keys:
  - `student_id` (str)
  - `student_name` (str)
  - `subject_code` (str)
  - `marks_obtained` (float)
  - `total_marks` (float)
  - `credit_hours` (int)

**requirements.txt must include:**
```
langchain
langgraph
langsmith
langchain-google-genai
openpyxl
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
pydantic>=2.0
sqlalchemy
psycopg2-binary
streamlit
python-dotenv
```

---

### ENGINEER 2 — Validation Agent
**Branch:** `feature/validation-agent`
**Files to create:**
- `validators/edge_cases.py`
- `agents/validation_agent.py`
- `tests/test_validation.py`

**Deliverable:**
A function called `validate_marksheet(data: list[dict]) -> dict` that:
- Accepts the list of dicts produced by the Parser Agent
- Checks all 18 edge cases (EC-01 to EC-18) listed in Section 6 below
- Returns a validation report dictionary with this structure:
```python
{
    "status": "PASS" or "FAIL",
    "total_records": int,
    "passed_records": int,
    "failed_records": int,
    "errors": [
        {
            "row": int,
            "student_id": str,
            "error_code": str,       # e.g. "EC-03"
            "error_message": str,
            "severity": "CRITICAL" or "WARNING"
        }
    ]
}
```

---

### ENGINEER 3 — GPA Calculator + Database Writer
**Branch:** `feature/calculator-db`
**Files to create:**
- `models/database_models.py`
- `agents/calculator_agent.py`
- `tests/test_calculator.py`

**Deliverable Part A — GPA Calculator:**
A function called `calculate_gpa(validated_data: list[dict]) -> list[dict]` that:
- Accepts validated student records
- Applies the GPA formula (see Section 7 below)
- Returns each record with these additional keys added:
  - `grade_points` (float)
  - `letter_grade` (str)
  - `gpa` (float)

**Deliverable Part B — Database Models:**
Using SQLAlchemy, create 5 database table models:
1. `Student` — student_id, name, department, semester
2. `Subject` — subject_code, subject_name, credit_hours
3. `Marksheet` — marksheet_id, student_id, subject_code, marks_obtained, total_marks
4. `GPA_Result` — result_id, student_id, semester, gpa, total_credit_hours
5. `Validation_Log` — log_id, marksheet_id, status, errors_json, created_at

---

## 6. Validation Edge Cases (EC-01 to EC-18)

Engineer 2 must implement checks for all of the following:

| Code | Rule | Severity |
|---|---|---|
| EC-01 | student_id is missing or empty | CRITICAL |
| EC-02 | student_name is missing or empty | CRITICAL |
| EC-03 | marks_obtained is not a number | CRITICAL |
| EC-04 | total_marks is not a number | CRITICAL |
| EC-05 | credit_hours is not a positive integer | CRITICAL |
| EC-06 | marks_obtained is negative | CRITICAL |
| EC-07 | marks_obtained exceeds total_marks | CRITICAL |
| EC-08 | total_marks is zero or negative | CRITICAL |
| EC-09 | subject_code is missing or empty | CRITICAL |
| EC-10 | Duplicate student_id + subject_code combination | CRITICAL |
| EC-11 | credit_hours is zero | CRITICAL |
| EC-12 | marks_obtained is exactly 0 (possible missing entry) | WARNING |
| EC-13 | student_name contains numbers or special characters | WARNING |
| EC-14 | total_marks is not a standard value (not 50, 100, or 200) | WARNING |
| EC-15 | credit_hours exceeds 6 (unusual but not impossible) | WARNING |
| EC-16 | marks_obtained has more than 2 decimal places | WARNING |
| EC-17 | student_id format does not match expected pattern | WARNING |
| EC-18 | Excel row is completely empty | CRITICAL |

---

## 7. GPA Formula

Engineer 3 must implement the following grading scale exactly:

| Marks % | Letter Grade | Grade Points |
|---|---|---|
| 90 – 100 | A+ | 4.0 |
| 85 – 89 | A | 4.0 |
| 80 – 84 | A- | 3.7 |
| 75 – 79 | B+ | 3.3 |
| 70 – 74 | B | 3.0 |
| 65 – 69 | B- | 2.7 |
| 60 – 64 | C+ | 2.3 |
| 55 – 59 | C | 2.0 |
| 50 – 54 | C- | 1.7 |
| 45 – 49 | D | 1.0 |
| Below 45 | F | 0.0 |

**GPA Calculation Formula:**
```
marks_percentage = (marks_obtained / total_marks) * 100
grade_points = lookup from table above
weighted_points = grade_points * credit_hours

GPA = sum(weighted_points for all subjects) / sum(credit_hours for all subjects)
```

---

## 8. Branch and Submission Rules

**Every engineer must follow these rules without exception:**

1. **Never push code to `main` directly.** Your branch is your workspace.
2. **Only push to your assigned branch:**
   - Engineer 1 → `feature/parser-agent`
   - Engineer 2 → `feature/validation-agent`
   - Engineer 3 → `feature/calculator-db`
3. When your work is ready, **open a Pull Request** on GitHub targeting `main`
4. Write a clear PR description explaining what you built
5. **Notify the Tech Lead** (Arif Khan) after opening the PR
6. Do not merge your own PR — the Tech Lead reviews and merges all code
7. If changes are requested, fix them on your branch and push again — the PR updates automatically

---

## 9. Environment Variables

Never hardcode secrets in your code. Use a `.env` file locally.
Engineer 1 will create a `.env.example` file showing which variables are needed:

```
GOOGLE_DRIVE_CREDENTIALS_PATH=
GOOGLE_DRIVE_FOLDER_ID=
DATABASE_URL=sqlite:///./gpa_system.db
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=gpa-agentic-system
```

Every engineer must create their own `.env` file locally by copying `.env.example`.
The `.env` file is already blocked by `.gitignore` — it will never be pushed to GitHub.

---

## 10. Contact and Communication

**Tech Lead:** Arif Khan
**Repository:** `gpa-agentic-system` (private)
**All questions and code reviews go through the Tech Lead.**

When in doubt — ask before writing code.

---
*This document is the single source of truth for the project. All engineers must read it fully before writing any code.*
