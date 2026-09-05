# Agentic GPA Calculation System

**University of Loralai — CS Department**
**Tech Lead:** Arif Khan, AI Engineer

---

## What This System Does

An AI-powered pipeline that reads student mark sheets from Google Drive,
validates every data point, calculates GPA using the HEC Pakistan formula,
and stores results in a database with a Human-in-the-Loop review dashboard.

## Agent Pipeline

```
Google Drive (Excel Files)
        ↓
[ Parser Agent ]         → feature/parser-agent     (Engineer 1)
        ↓
[ Validation Agent ]     → feature/validation-agent  (Engineer 2)
        ↓
[ GPA Calculator Agent ] → feature/calculator-db     (Engineer 3)
        ↓
[ Database Writer ]      → feature/calculator-db     (Engineer 3)
        ↓
[ Streamlit Dashboard ]  → Tech Lead Review (HITL)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Orchestration | LangGraph |
| Excel Parsing | openpyxl |
| Data Validation | Pydantic v2 |
| GPA Formula | HEC Pakistan Standard |
| Database ORM | SQLAlchemy + Alembic |
| Dev Database | SQLite |
| Prod Database | PostgreSQL |
| Dashboard | Streamlit |

## Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/gpa-agentic-system.git
cd gpa-agentic-system

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and fill in your values

# 5. Run database migrations
alembic upgrade head
```

## Branch Rules

- **main** — protected. No direct commits. Tech Lead only.
- **feature/parser-agent** — Engineer 1 only
- **feature/validation-agent** — Engineer 2 only
- **feature/calculator-db** — Engineer 3 only

Read PROJECT_BRIEF.md before writing any code.
