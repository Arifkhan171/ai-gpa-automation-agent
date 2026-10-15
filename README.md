<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1a0533,25:3d0a52,50:6a0572,75:c62a88,100:ff6b35&height=220&section=header&text=AcadTrack&fontSize=72&fontColor=FFD700&animation=fadeIn&fontAlignY=44&desc=Agentic%20GPA%20Automation%20System%20%7C%20University%20of%20Loralai&descAlignY=66&descSize=20&descColor=FFB347&stroke=c62a88&strokeWidth=2" width="100%"/>

<br/>

[![YouTube Demo](https://img.shields.io/badge/▶️_Watch_Full_Demo-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/Z2Cbma3yKYY)
&nbsp;
[![LangGraph](https://img.shields.io/badge/LangGraph-FF6B6B?style=for-the-badge&logo=python&logoColor=white)](https://github.com/langchain-ai/langgraph)
&nbsp;
[![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
&nbsp;
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)

<br/>

![Status](https://img.shields.io/badge/Status-Production_Ready-2ea44f?style=flat-square)
&nbsp;
![Team](https://img.shields.io/badge/Team-3_Engineers-c62a88?style=flat-square)
&nbsp;
![Formula](https://img.shields.io/badge/Formula-HEC_Pakistan_Standard-6a0572?style=flat-square)
&nbsp;
![Access](https://img.shields.io/badge/Access-Request_Required-ff6b35?style=flat-square)

</div>

<img src="https://capsule-render.vercel.app/api?type=soft&color=0:ff6b35,50:c62a88,100:6a0572&height=6" width="100%"/>

---

## 📌 Overview

> "Zero manual calculation. Zero human error. Full automation."

*AcadTrack* is a production-grade agentic AI system that fully automates GPA management for universities. It reads student mark sheets from Google Drive, validates every data point through 22 edge-case rules, calculates GPA and CGPA using the official HEC Pakistan formula, generates verified transcripts, and delivers results through a role-based dashboard — all without a single manual step.

Built with a *3-engineer LangGraph pipeline* under tech lead supervision with full Human-in-the-Loop review before any data is committed.

---

## 🎬 Demo

<div align="center">

[![Watch Demo](https://img.shields.io/badge/▶️_Watch_Full_System_Demo_on_YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white&labelColor=1a0533)](https://youtu.be/Z2Cbma3yKYY)

</div>

---

## 📸 Screenshotss

<details open>
<summary><b>🔐 Login — Role-Based Access Control</b></summary>
<br/>

> Each user role (Student, Coordinator, Controller of Examinations) sees a completely different dashboard and permissions.

<!-- DRAG AND DROP YOUR LOGIN SCREENSHOT HERE IN GITHUB EDITOR -->
<img width="1600" height="669" alt="WhatsApp Image 2026-10-02 at 12 34 02 PM" src="https://github.com/user-attachments/assets/d037ee2c-e053-40bd-8b35-b66430179eb9" />


</details>

---

<details open>
<summary><b>📂 Coordinator Dashboard — Upload & GPA Calculation</b></summary>
<br/>

> Coordinator uploads semester mark sheets. All 8 semesters are validated and approved before GPA calculation is triggered.

<!-- DRAG AND DROP YOUR COORDINATOR DASHBOARD SCREENSHOT HERE IN GITHUB EDITOR -->
<img width="1600" height="671" alt="WhatsApp Image 2026-10-02 at 12 34 02 PM (2)" src="https://github.com/user-attachments/assets/74c6016e-5495-460e-a592-9bcd286dca03" />


</details>

---

<details open>
<summary><b>📊 Student Portal — My Grades View</b></summary>
<br/>

> Students see their Cumulative GPA, per-semester breakdown, credit hours, marks, grade points, and letter grades — all auto-calculated by the AI pipeline.

<!-- DRAG AND DROP YOUR STUDENT GRADES SCREENSHOT HERE IN GITHUB EDITOR -->
<img width="1600" height="713" alt="WhatsApp Image 2026-10-02 at 12 34 02 PM (1)" src="https://github.com/user-attachments/assets/0259205b-e8b7-4036-ab16-9e83d1ce9dc1" />

</details>

---

<details open>
<summary><b>📜 Transcripts — Controller of Examinations Panel</b></summary>
<br/>

> Controller of Examinations can generate, download, and revoke official transcripts with CGPA, semester range, issue date, and validation status.

<!-- DRAG AND DROP YOUR TRANSCRIPTS SCREENSHOT HERE IN GITHUB EDITOR -->

<img width="1600" height="664" alt="WhatsApp Image 2026-10-02 at 12 34 02 PM (3)" src="https://github.com/user-attachments/assets/3f1da782-b25c-4da5-b197-41922736a89f" />

</details>

---

## 👥 User Roles

| Role | Access Level | Key Actions |
|---|---|---|
| 🎓 *Student* | Read Only | View grades, GPA, transcript, payment status |
| 📋 *GPA Coordinator* | Upload + Approve | Upload mark sheets, approve semesters, trigger GPA calculation |
| 🏛️ *Controller of Examinations* | Full Control | Generate transcripts, revoke access, audit log, analytics |

---

## ⚙️ Core Features

<table>
<tr>
<td width="50%" valign="top">

### 🤖 Agentic Pipeline
- ✅ Fully automated end-to-end GPA workflow
- ✅ LangGraph stateful multi-agent execution
- ✅ Human-in-the-Loop review before DB commit
- ✅ 22 edge-case validation rules via Pydantic v2
- ✅ Automatic error detection and flagging

</td>
<td width="50%" valign="top">

### 📊 Academic Features
- ✅ HEC Pakistan official GPA formula
- ✅ Per-semester and cumulative CGPA
- ✅ Letter grade and grade point calculation
- ✅ Multi-semester support (1–8 semesters)
- ✅ QR-verified official transcript generation

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔐 Security & Roles
- ✅ Role-based access control (RBAC)
- ✅ Audit log for all critical actions
- ✅ Transcript revocation system
- ✅ Scan tracking per transcript

</td>
<td width="50%" valign="top">

### 📈 Dashboard & Analytics
- ✅ Real-time GPA analytics dashboard
- ✅ Semester-wise performance charts
- ✅ Min-required GPA threshold line
- ✅ Credit hours tracking per student

</td>
</tr>
</table>

---

## 🏗️ Agent Pipeline Architecture

mermaid
%%{init: {'theme': 'dark'}}%%
flowchart TD
    A[📁 Google Drive\nExcel Mark Sheets] --> B

    B[🤖 Parser Agent\nEngineer 1\nfeature/parser-agent] --> C
    B --> |Parse Error| E1[❌ Flag & Notify]

    C[✅ Validation Agent\nEngineer 2\nfeature/validation-agent\n22 Edge-Case Rules] --> D
    C --> |Validation Failed| E2[❌ Reject & Report]

    D[🧮 GPA Calculator Agent\nEngineer 3\nfeature/calculator-db\nHEC Pakistan Formula] --> F

    F[🗄️ Database Writer\nSQLAlchemy ORM\nSQLite / PostgreSQL] --> G

    G[🖥️ Streamlit Dashboard\nHuman-in-the-Loop Review\nTech Lead Approval] --> H

    H{✅ Approved?}
    H --> |Yes| I[📜 Transcript Generation\nQR-Verified PDF]
    H --> |No| J[🔁 Return for Correction]

    style A fill:#1a0533,color:#FFD700
    style B fill:#3d0a52,color:#fff
    style C fill:#6a0572,color:#fff
    style D fill:#c62a88,color:#fff
    style F fill:#3d0a52,color:#fff
    style G fill:#ff6b35,color:#fff
    style H fill:#1a0533,color:#FFD700
    style I fill:#2ea44f,color:#fff
    style J fill:#d71f00,color:#fff


---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| 🤖 *Agent Orchestration* | LangGraph | Stateful multi-agent pipeline execution |
| 🔗 *Agent Framework* | LangChain | LLM integration and tool binding |
| 📊 *Excel Parsing* | openpyxl | Reading student mark sheet files |
| ✅ *Data Validation* | Pydantic v2 | 22 edge-case validation rules |
| 🧮 *GPA Formula* | HEC Pakistan Standard | Official CGPA and grade calculation |
| 🗄️ *ORM* | SQLAlchemy + Alembic | Database models and migrations |
| 💾 *Dev Database* | SQLite | Local development and testing |
| 🏭 *Prod Database* | PostgreSQL | Production deployment |
| ☁️ *File Source* | Google Drive API | Mark sheet ingestion |
| 🖥️ *Dashboard* | Streamlit | HITL review and coordinator interface |
| 🐍 *Language* | Python 3.11 | Core system language |

---

## 🚀 Setup Instructions

<details>
<summary><b>Click to expand setup guide</b></summary>

<br/>

### Prerequisites
- Python 3.11+
- PostgreSQL (for production)
- Google Drive API credentials
- Git

### Installation

bash
# 1. Clone the repository
git clone https://github.com/Arifkhan171/ai-gpa-automation-agent.git
cd ai-gpa-automation-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Open .env and fill in your Google Drive credentials and DB config

# 5. Run database migrations
alembic upgrade head

# 6. Launch the dashboard
streamlit run app.py


### Environment Variables Required
env
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
DATABASE_URL=postgresql://user:password@localhost/acadtrack
OPENAI_API_KEY=your_openai_key
SECRET_KEY=your_secret_key


</details>

---

## 🌿 Branch Strategy

| Branch | Owner | Purpose |
|---|---|---|
| main | ⭐ Tech Lead Only | Protected — no direct commits |
| feature/parser-agent | Engineer 1 | Excel parsing and Drive ingestion |
| feature/validation-agent | Engineer 2 | Pydantic validation rules |
| feature/calculator-db | Engineer 3 | GPA calculation and DB writing |

> ⚠️ Read PROJECT_BRIEF.md before writing any code.

---

## 📅 Project Timeline


Phase 1  ✦  Parser Agent        →  Google Drive ingestion + Excel parsing
Phase 2  ✦  Validation Agent    →  22 edge-case rules + error reporting
Phase 3  ✦  Calculator Agent    →  HEC formula + CGPA + letter grades
Phase 4  ✦  Database Layer      →  SQLAlchemy ORM + Alembic migrations
Phase 5  ✦  Streamlit Dashboard →  HITL review + role-based UI
Phase 6  ✦  Transcript System   →  QR-verified PDF generation
Phase 7  ✦  Production Deploy   →  PostgreSQL + full testing


---

## 🔒 Repository Access

This is a *private repository*.

To request access for review or collaboration:

[![Email](https://img.shields.io/badge/Request_Access-arif.cs.bs%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:arif.cs.bs@gmail.com)
&nbsp;
[![LinkedIn](https://img.shields.io/badge/Connect-Arif_Khan-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/arif-khan-71a711376)

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=soft&color=0:1a0533,50:6a0572,100:c62a88&height=8" width="100%"/>

<br/>

*Built by Arif Khan — AI Engineer | University of Loralai, Pakistan*

If this project helped you — a ⭐ on the repo means the world!

<br/>

</div>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff6b35,40:c62a88,70:6a0572,100:1a0533&height=130&section=footer" width="100%"/>
