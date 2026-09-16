# AcadTrack — FastAPI Backend

University of Loralai Academic Records System  
**Backend: Module 0 — Foundation**

---

## Overview

The FastAPI backend runs **alongside** the existing Streamlit app.  
Both systems share the same `gpa_system.db` SQLite database but are
completely independent: they run on different ports and do not call
each other.

```
gpa-agentic-system/
├── src/                        ← Streamlit app (DO NOT MODIFY)
│   ├── agents/
│   ├── dashboard/              → streamlit run src/dashboard/app.py  (port 8501)
│   ├── models/
│   ├── validators/
│   └── utils/
├── backend/                    ← FastAPI backend (this module)
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── requirements_backend.txt
│   └── routers/
│       ├── health.py           → live (GET /health, GET /health/db)
│       ├── auth.py             → stub (Module 2)
│       ├── students.py         → stub (Module 3)
│       ├── grades.py           → stub (Module 4)
│       ├── transcripts.py      → stub (Module 5)
│       ├── analytics.py        → stub (Module 6)
│       ├── notifications.py    → stub (Module 7)
│       └── payments.py         → stub (Module 8)
└── gpa_system.db               ← shared database
```

---

## Quick Start

### 1 — Install backend dependencies

```bash
cd backend
pip install -r requirements_backend.txt
```

### 2 — Run the FastAPI server

Run from the **project root** (the directory that contains `backend/` and `src/`):

```bash
uvicorn backend.main:app --reload --port 8000
```

### 3 — Run the Streamlit app (unchanged)

In a separate terminal, also from the project root:

```bash
streamlit run src/dashboard/app.py
```

Both services run simultaneously on different ports:

| Service   | URL                          |
|-----------|------------------------------|
| FastAPI   | http://localhost:8000         |
| Swagger   | http://localhost:8000/docs    |
| ReDoc     | http://localhost:8000/redoc   |
| Streamlit | http://localhost:8501         |

---

## Health Checks

```bash
# Basic status
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/db
```

---

## Environment Variables

Create a `.env` file in the project root to override defaults:

```dotenv
DATABASE_URL=sqlite:///../gpa_system.db
SECRET_KEY=your-production-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

All variables are optional — the server works with its built-in defaults.

---

## Module Roadmap

| Module | Description              | Router(s)                    | Status      |
|--------|--------------------------|------------------------------|-------------|
| 0      | Foundation               | health                       | ✅ Complete  |
| 1      | Pydantic Schemas         | —                            | Pending     |
| 2      | Authentication           | auth                         | Stub        |
| 3      | Student Management       | students                     | Stub        |
| 4      | Grades & GPA             | grades                       | Stub        |
| 5      | Transcript Generation    | transcripts                  | Stub        |
| 6      | Analytics & Reporting    | analytics                    | Stub        |
| 7      | Notifications            | notifications                | Stub        |
| 8      | Fee & Payments           | payments                     | Stub        |
