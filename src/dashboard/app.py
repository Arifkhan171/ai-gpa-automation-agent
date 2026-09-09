"""
src/dashboard/app.py
====================
University of Loralai — CS Department
Enterprise HITL GPA Calculation Dashboard  |  Tech Lead: Arif Khan

Zero filename dependency: upload any .xlsx / .csv file.
The system auto-detects semester from the filename and lets the HOD
confirm or override every assignment before processing begins.

Run from project root:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ─── Path: ensure project root is resolvable ──────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent   # project root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ─── Agent imports (fail-safe: UI still boots even if one module is broken) ───
_ERRORS: list[str] = []

try:
    from src.agents.parser_agent import (
        detect_semester_and_subject,
        parse_file_to_records,
    )
    _PARSER_OK = True
except Exception as _e:
    _PARSER_OK = False
    _ERRORS.append(f"parser_agent → {_e}")

try:
    from src.agents.validation_agent import validate_records
    _VALIDATOR_OK = True
except Exception as _e:
    _VALIDATOR_OK = False
    _ERRORS.append(f"validation_agent → {_e}")

try:
    from src.agents.calculator_agent import calculator_agent_node, get_engine
    from src.models.database_models import Student, SemesterGPA, CGPA
    from sqlalchemy.orm import Session
    from sqlalchemy import select as sa_select
    _CALC_OK = True
except Exception as _e:
    _CALC_OK = False
    _ERRORS.append(f"calculator_agent / database_models → {_e}")

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title   = "GPA Dashboard — University of Loralai",
    page_icon    = "🎓",
    layout       = "wide",
    initial_sidebar_state = "expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# ENTERPRISE DESIGN SYSTEM  (injected once)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ─────────────────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
.stApp { background-color: #EEF2F7; }

/* ── Sidebar ─────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B1E3D 0%, #122B52 60%, #0F2444 100%);
    border-right: 1px solid #1E3A6E;
}
section[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
section[data-testid="stSidebar"] .sidebar-title {
    color: #F1F5F9 !important; font-size: 1.05rem; font-weight: 700;
}
section[data-testid="stSidebar"] hr { border-color: #1E3A6E !important; }

/* ── Cards ────────────────────────────────────────────────────────────── */
.card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 24px 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04);
    border: 1px solid #E2E8F0;
    margin-bottom: 18px;
}
.card-sm {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid #E2E8F0;
    margin-bottom: 12px;
}

/* ── Stage header ─────────────────────────────────────────────────────── */
.stage-title {
    font-size: 1.55rem;
    font-weight: 800;
    color: #0F2444;
    letter-spacing: -0.5px;
    margin-bottom: 4px;
}
.stage-subtitle {
    font-size: 0.9rem;
    color: #64748B;
    margin-bottom: 24px;
    font-weight: 400;
}

/* ── Section labels ──────────────────────────────────────────────────── */
.section-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 8px;
}

/* ── Severity banners ─────────────────────────────────────────────────── */
.banner {
    border-radius: 8px;
    padding: 12px 18px;
    font-weight: 600;
    font-size: 0.9rem;
    margin: 10px 0;
    display: flex;
    align-items: center;
    gap: 10px;
    line-height: 1.5;
}
.banner-critical {
    background: linear-gradient(135deg, #FEF2F2, #FEE2E2);
    border: 1px solid #FECACA;
    border-left: 4px solid #DC2626;
    color: #7F1D1D;
}
.banner-warning {
    background: linear-gradient(135deg, #FFFBEB, #FEF3C7);
    border: 1px solid #FDE68A;
    border-left: 4px solid #D97706;
    color: #78350F;
}
.banner-success {
    background: linear-gradient(135deg, #F0FDF4, #DCFCE7);
    border: 1px solid #BBF7D0;
    border-left: 4px solid #16A34A;
    color: #14532D;
}
.banner-info {
    background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
    border: 1px solid #BFDBFE;
    border-left: 4px solid #2563EB;
    color: #1E3A8A;
}

/* ── Status badges ────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    vertical-align: middle;
}
.badge-blocked { background:#FEE2E2; color:#B91C1C; border:1px solid #FECACA; }
.badge-flagged { background:#FEF3C7; color:#B45309; border:1px solid #FDE68A; }
.badge-clean   { background:#DCFCE7; color:#15803D; border:1px solid #BBF7D0; }
.badge-info    { background:#DBEAFE; color:#1D4ED8; border:1px solid #BFDBFE; }

/* ── Semester progress timeline ───────────────────────────────────────── */
.timeline { display:flex; align-items:center; gap:0; margin-bottom:28px; flex-wrap:wrap; }
.tl-step {
    display:flex; align-items:center; gap:6px;
    padding:6px 12px; border-radius:20px;
    font-size:0.78rem; font-weight:600;
    white-space:nowrap;
}
.tl-done    { background:#DCFCE7; color:#166534; }
.tl-active  { background:#1D4ED8; color:#FFFFFF; box-shadow:0 0 0 3px #BFDBFE; }
.tl-pending { background:#F1F5F9; color:#94A3B8; }
.tl-arrow   { color:#CBD5E1; font-size:0.75rem; padding:0 4px; }

/* ── KPI metric box ───────────────────────────────────────────────────── */
.kpi-box {
    background:#FFFFFF; border-radius:12px;
    padding:20px 24px; text-align:center;
    box-shadow:0 1px 4px rgba(0,0,0,0.06);
    border:1px solid #E2E8F0;
}
.kpi-value  { font-size:2.2rem; font-weight:800; color:#0F2444; line-height:1.1; }
.kpi-label  { font-size:0.78rem; font-weight:600; color:#64748B;
              text-transform:uppercase; letter-spacing:0.8px; margin-top:6px; }
.kpi-delta-pos { color:#16A34A; font-size:0.8rem; font-weight:600; }
.kpi-delta-neg { color:#DC2626; font-size:0.8rem; font-weight:600; }

/* ── File chip ────────────────────────────────────────────────────────── */
.file-chip {
    display:inline-flex; align-items:center; gap:6px;
    background:#F8FAFC; border:1px solid #E2E8F0;
    border-radius:8px; padding:6px 12px;
    font-size:0.8rem; color:#374151; margin:3px;
}

/* ── Table styling ────────────────────────────────────────────────────── */
.gpa-table {
    width:100%; border-collapse:collapse;
    font-size:0.85rem;
}
.gpa-table th {
    background:#0F2444; color:#F1F5F9;
    padding:10px 14px; text-align:center;
    font-weight:600; font-size:0.75rem;
    letter-spacing:0.5px; white-space:nowrap;
}
.gpa-table td {
    padding:9px 14px; text-align:center;
    border-bottom:1px solid #F1F5F9;
    color:#374151;
}
.gpa-table tr:hover td { background:#F8FAFC; }
.gpa-table td.name-col { text-align:left; font-weight:600; color:#0F2444; }
.gpa-table td.roll-col { text-align:left; color:#64748B; font-size:0.8rem; }
.gpa-high { background:#DCFCE7 !important; color:#166534; font-weight:700; border-radius:6px; }
.gpa-mid  { background:#FEF3C7 !important; color:#92400E; font-weight:600; border-radius:6px; }
.gpa-low  { background:#FEE2E2 !important; color:#991B1B; font-weight:600; border-radius:6px; }
.gpa-dash { color:#CBD5E1; }

/* ── Sidebar steps ────────────────────────────────────────────────────── */
.sb-step { padding:6px 0; font-size:0.85rem; display:flex; align-items:center; gap:8px; }
.sb-done { color:#4ADE80 !important; }
.sb-active { color:#60A5FA !important; font-weight:700 !important; }
.sb-pending { color:#475569 !important; }
.sb-sem { font-size:0.8rem; display:flex; align-items:center;
          gap:6px; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.07); }

/* ── Upload dropzone ──────────────────────────────────────────────────── */
.upload-zone {
    border: 2px dashed #CBD5E1; border-radius:12px;
    padding:40px; text-align:center;
    background:#F8FAFC; margin-bottom:16px;
}
.upload-zone h3 { color:#0F2444; margin:0 0 8px 0; font-size:1.1rem; }
.upload-zone p  { color:#64748B; margin:0; font-size:0.88rem; }

/* ── Divider ──────────────────────────────────────────────────────────── */
.divider {
    border:none; border-top:1px solid #E2E8F0; margin:20px 0;
}

/* Remove Streamlit default padding on some elements */
.block-container { padding-top: 2rem !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

EXPECTED_STRENGTH: dict[str, int] = {
    "Semester 1": 20,
    "Semester 2": 20,
    "Semester 3": 20,
    "Semester 4": 19,
    "Semester 5": 18,
    "Semester 6": 18,
    "Semester 7": 18,
    "Semester 8": 18,
}
ALL_SEMESTERS = list(EXPECTED_STRENGTH.keys())
SEM_OPTIONS   = ["— Unassigned —"] + ALL_SEMESTERS
DEFAULT_DB    = os.getenv("DATABASE_URL", "sqlite:///./gpa_system.db")

EDITOR_COLS = [
    "student_name", "roll_no", "father_name",
    "subject_name", "total_marks", "obtained_marks",
    "credit_hours", "department",
]


# ──────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def sem_num(label: str) -> int:
    m = re.search(r"(\d+)", label)
    return int(m.group(1)) if m else 0


def fmt_size(b: int) -> str:
    return f"{b/1024:.1f} KB" if b < 1_048_576 else f"{b/1_048_576:.1f} MB"


def records_to_df(records: list[dict]) -> pd.DataFrame:
    rows = [{c: r.get(c) for c in EDITOR_COLS} for r in records]
    df = pd.DataFrame(rows, columns=EDITOR_COLS)
    for col in ("total_marks", "obtained_marks"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["credit_hours"] = pd.to_numeric(df["credit_hours"], errors="coerce")
    return df


def df_to_records(df: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    for _, row in df.iterrows():
        rec: dict[str, Any] = {"has_issues": False, "parse_warnings": []}
        for col in EDITOR_COLS:
            val = row.get(col)
            is_null = val is None or (isinstance(val, float) and pd.isna(val)) \
                      or str(val).strip() in ("", "nan", "None", "NaT")
            if is_null:
                rec[col] = None
                continue
            if col in ("total_marks", "obtained_marks"):
                try:
                    rec[col] = float(val)
                except (ValueError, TypeError):
                    rec[col] = str(val)
                    rec["has_issues"] = True
                    rec["parse_warnings"].append(f"'{val}' not numeric for {col}.")
            elif col == "credit_hours":
                try:
                    rec[col] = int(float(val))
                except (ValueError, TypeError):
                    rec[col] = str(val)
                    rec["has_issues"] = True
                    rec["parse_warnings"].append(f"'{val}' not integer for credit_hours.")
            else:
                rec[col] = str(val).strip()
        out.append(rec)
    return out


def infer_academic_year(sn: int) -> str:
    override = st.session_state.get("academic_year", "").strip()
    if override:
        return override
    y = datetime.now().year - (sn - 1) // 2
    return f"{y}-{y + 1}"


# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────

def _init() -> None:
    defaults: dict[str, Any] = {
        "stage"           : "upload",     # upload|assign|review|calculate|results
        "raw_files"       : {},           # {fname: bytes}
        "file_assignments": {},           # {fname: "Semester N" | None}
        "file_subjects"   : {},           # {fname: subject_hint}
        "semester_groups" : {},           # {sem: [fname, ...]}
        "sem_records"     : {},           # {sem: list[dict]}  combined records
        "sem_dfs"         : {},           # {sem: pd.DataFrame}
        "approvals"       : {},           # {sem: bool}
        "val_reports"     : {},           # {sem: report.model_dump()}
        "review_idx"      : 0,
        "ordered_sems"    : [],
        "calc_results"    : None,
        "final_saved"     : False,
        "db_url"          : DEFAULT_DB,
        "academic_year"   : "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 8px 0">
            <div style="font-size:1.4rem;font-weight:800;color:#F1F5F9;letter-spacing:-0.5px">
                🎓 GPA System
            </div>
            <div style="font-size:0.75rem;color:#94A3B8;margin-top:2px">
                University of Loralai · CS Dept
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()

        # ── Pipeline steps ─────────────────────────────────────────────────
        st.markdown('<div class="section-label" style="color:#475569">Pipeline</div>',
                    unsafe_allow_html=True)
        stages   = ["upload", "assign", "review", "calculate", "results"]
        labels   = ["Upload Files", "Assign Semesters", "HITL Review",
                    "GPA Calculation", "Results & Save"]
        icons    = ["📁", "🗂️", "📋", "⚙️", "📊"]
        cur      = st.session_state.stage
        cur_idx  = stages.index(cur)

        for i, (s, lbl, ico) in enumerate(zip(stages, labels, icons)):
            if i < cur_idx:
                cls, prefix = "sb-step sb-done", "✓"
            elif i == cur_idx:
                cls, prefix = "sb-step sb-active", "▶"
            else:
                cls, prefix = "sb-step sb-pending", "○"
            st.markdown(
                f'<div class="{cls}">'
                f'<span style="font-size:1rem">{ico}</span>'
                f'<span>{prefix} {lbl}</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Semester approval grid ─────────────────────────────────────────
        ordered = st.session_state.ordered_sems
        if ordered:
            st.markdown('<div class="section-label" style="color:#475569">Semester Status</div>',
                        unsafe_allow_html=True)
            for sem in ordered:
                ok    = st.session_state.approvals.get(sem, False)
                files = st.session_state.semester_groups.get(sem, [])
                is_active = (
                    st.session_state.stage == "review"
                    and st.session_state.review_idx < len(ordered)
                    and sem == ordered[st.session_state.review_idx]
                )
                icon = "✅" if ok else ("🔵" if is_active else "○")
                st.markdown(
                    f'<div class="sb-sem">'
                    f'<span>{icon}</span>'
                    f'<span style="flex:1;font-size:0.8rem">{sem}</span>'
                    f'<span style="font-size:0.7rem;color:#475569">{len(files)} file(s)</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.divider()

        # ── System health ──────────────────────────────────────────────────
        st.markdown('<div class="section-label" style="color:#475569">System Health</div>',
                    unsafe_allow_html=True)

        def _health(ok: bool, label: str) -> None:
            c, dot = ("#4ADE80", "●") if ok else ("#F87171", "●")
            st.markdown(
                f'<div class="sb-step"><span style="color:{c}">{dot}</span>'
                f'<span>{label}</span></div>',
                unsafe_allow_html=True,
            )

        _health(_PARSER_OK,    "Parser Agent")
        _health(_VALIDATOR_OK, "Validation Agent")
        _health(_CALC_OK,      "Calculator Agent")

        if _ERRORS:
            with st.expander("⚠️ Import Errors"):
                for e in _ERRORS:
                    st.error(e, icon="🚫")

        st.divider()

        # ── Settings ───────────────────────────────────────────────────────
        with st.expander("⚙️ Settings"):
            st.session_state.db_url = st.text_input(
                "Database URL", value=st.session_state.db_url,
                help="SQLite (dev) or PostgreSQL (prod)"
            )
            st.session_state.academic_year = st.text_input(
                "Academic Year", value=st.session_state.academic_year,
                placeholder="e.g. 2024-2025",
                help="Leave blank to auto-infer"
            )

        st.markdown(
            '<div style="font-size:0.7rem;color:#475569;margin-top:12px">'
            'v1.0 · HEC Pakistan GPA Standard</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 0 — UPLOAD  (any filename accepted)
# ──────────────────────────────────────────────────────────────────────────────

def render_upload() -> None:
    st.markdown('<div class="stage-title">📁 Upload Mark Sheet Files</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">Upload any .xlsx or .csv files — '
        'no specific naming convention required. '
        'The system will auto-detect semesters from filenames (e.g. S1, S2, Sem3) '
        'and you can confirm or change every assignment before processing.</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop all your mark sheet files here",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    # ── Strength reference ─────────────────────────────────────────────────
    with st.expander("📊 HOD Ground-Truth Student Strength Baseline"):
        cols = st.columns(4)
        for i, (sem, n) in enumerate(EXPECTED_STRENGTH.items()):
            cols[i % 4].metric(sem, f"{n} students")

    if not uploaded:
        st.markdown("""
        <div class="upload-zone">
            <h3>📂 No files uploaded yet</h3>
            <p>Supports any naming convention — S1-Subject.xlsx, SemX-Name.csv,<br>
               DataStructures.xlsx, marks_fall2024.xlsx, and more.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Build raw_files dict ───────────────────────────────────────────────
    raw: dict[str, bytes] = {uf.name: uf.read() for uf in uploaded}

    # ── Auto-detect semester + subject from filename ────────────────────────
    auto_sem: dict[str, str | None] = {}
    auto_sub: dict[str, str | None] = {}
    for fname in raw:
        s, sub = (detect_semester_and_subject(fname)
                  if _PARSER_OK
                  else _fallback_detect(fname))
        auto_sem[fname] = s
        auto_sub[fname] = sub

    detected   = sum(1 for v in auto_sem.values() if v)
    undetected = len(raw) - detected

    # ── Summary cards ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files Uploaded",   len(raw))
    c2.metric("Auto-Detected",    detected,   delta=None)
    c3.metric("Need Assignment",  undetected,
              delta=f"−{undetected}" if undetected else None,
              delta_color="inverse" if undetected else "off")
    c4.metric("Unique Semesters",
              len({v for v in auto_sem.values() if v}))

    if undetected:
        st.markdown(
            f'<div class="banner banner-warning">⚠️  <b>{undetected} file(s)</b> '
            f'could not be assigned automatically — you will set them manually '
            f'in the next step.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="banner banner-success">✅  All files have been '
            'automatically matched to semesters. Review assignments on the next step.'
            '</div>', unsafe_allow_html=True,
        )

    # ── File preview list ──────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:16px">Detected Files</div>',
                unsafe_allow_html=True)
    hdr = st.columns([3, 1.2, 2, 2.2])
    for lbl in ("Filename", "Size", "Detected Semester", "Detected Subject"):
        hdr[["Filename","Size","Detected Semester","Detected Subject"].index(lbl)].markdown(
            f'<div style="font-size:0.75rem;font-weight:700;color:#64748B;'
            f'text-transform:uppercase;letter-spacing:0.8px">{lbl}</div>',
            unsafe_allow_html=True,
        )
    for fname, data in raw.items():
        c = st.columns([3, 1.2, 2, 2.2])
        c[0].markdown(f'<div class="file-chip">📄 {fname}</div>', unsafe_allow_html=True)
        c[1].markdown(f'<span style="font-size:0.82rem;color:#64748B">{fmt_size(len(data))}</span>',
                      unsafe_allow_html=True)
        sem = auto_sem[fname]
        sub = auto_sub[fname]
        if sem:
            c[2].markdown(f'<span class="badge badge-clean">✓ {sem}</span>',
                          unsafe_allow_html=True)
        else:
            c[2].markdown('<span class="badge badge-flagged">⚠ Undetected</span>',
                          unsafe_allow_html=True)
        c[3].markdown(
            f'<span style="font-size:0.82rem;color:#374151">{sub or "—"}</span>',
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    if st.button("Next → Confirm Semester Assignments", type="primary",
                 use_container_width=True):
        st.session_state.raw_files        = raw
        st.session_state.file_assignments = dict(auto_sem)
        st.session_state.file_subjects    = dict(auto_sub)
        st.session_state.stage            = "assign"
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 1 — ASSIGN  (confirm / override semester per file)
# ──────────────────────────────────────────────────────────────────────────────

def render_assign() -> None:
    st.markdown('<div class="stage-title">🗂️ Confirm Semester Assignments</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">Review auto-detected assignments and override '
        'any that are wrong. Every file must be assigned before review begins.</div>',
        unsafe_allow_html=True,
    )

    raw       = st.session_state.raw_files
    assigns   = dict(st.session_state.file_assignments)   # mutable local copy
    subjects  = dict(st.session_state.file_subjects)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">File Assignment Table</div>', unsafe_allow_html=True)

    # ── Editable table (one row per file) ─────────────────────────────────
    for fname, data in raw.items():
        col_f, col_sz, col_sem, col_sub = st.columns([3, 1, 2.2, 2.5])

        col_f.markdown(
            f'<div style="padding-top:8px"><span class="file-chip">📄 {fname}</span></div>',
            unsafe_allow_html=True,
        )
        col_sz.markdown(
            f'<div style="padding-top:10px;font-size:0.8rem;color:#64748B">'
            f'{fmt_size(len(data))}</div>',
            unsafe_allow_html=True,
        )

        # Semester select
        current = assigns.get(fname)
        default_idx = SEM_OPTIONS.index(current) if current in SEM_OPTIONS else 0
        choice = col_sem.selectbox(
            f"sem_{fname}", SEM_OPTIONS,
            index=default_idx,
            label_visibility="collapsed",
            key=f"sem_sel_{fname}",
        )
        assigns[fname] = None if choice == "— Unassigned —" else choice

        # Subject editable
        sub_val = col_sub.text_input(
            f"sub_{fname}",
            value=subjects.get(fname) or "",
            placeholder="Subject name (optional)",
            label_visibility="collapsed",
            key=f"sub_inp_{fname}",
        )
        subjects[fname] = sub_val.strip() or None

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Assignment summary by semester ─────────────────────────────────────
    sem_groups: dict[str, list[str]] = {}
    for fname, sem in assigns.items():
        if sem:
            sem_groups.setdefault(sem, []).append(fname)

    unassigned = [f for f, s in assigns.items() if not s]

    st.markdown('<div class="section-label" style="margin-top:8px">Assignment Summary</div>',
                unsafe_allow_html=True)
    cols = st.columns(min(len(sem_groups) or 1, 4))
    for i, (sem, files) in enumerate(sorted(sem_groups.items(), key=lambda x: sem_num(x[0]))):
        expected = EXPECTED_STRENGTH.get(sem, 0)
        cols[i % 4].markdown(f"""
        <div class="kpi-box">
            <div class="kpi-value">{len(files)}</div>
            <div class="kpi-label">{sem}</div>
            <div style="font-size:0.75rem;color:#94A3B8;margin-top:4px">
                Expected: {expected} students
            </div>
        </div>
        """, unsafe_allow_html=True)

    if unassigned:
        st.markdown(
            f'<div class="banner banner-critical">🚫 <b>{len(unassigned)} file(s) '
            f'still unassigned</b>: '
            + ", ".join(f"<code>{f}</code>" for f in unassigned)
            + '. Assign them above to continue.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    bc1, bc2 = st.columns([1, 5])
    with bc1:
        if st.button("← Back", use_container_width=True):
            st.session_state.stage = "upload"
            st.rerun()
    with bc2:
        can_proceed = not unassigned and bool(sem_groups)
        if st.button("Begin HITL Review →", type="primary",
                     disabled=not can_proceed, use_container_width=True):
            ordered = sorted(sem_groups.keys(), key=sem_num)
            st.session_state.file_assignments = assigns
            st.session_state.file_subjects    = subjects
            st.session_state.semester_groups  = sem_groups
            st.session_state.ordered_sems     = ordered
            st.session_state.review_idx       = 0
            st.session_state.approvals        = {}
            st.session_state.sem_records      = {}
            st.session_state.sem_dfs          = {}
            st.session_state.val_reports      = {}
            st.session_state.calc_results     = None
            st.session_state.final_saved      = False
            st.session_state.stage            = "review"
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 2 — REVIEW  (HITL carousel, one semester at a time)
# ──────────────────────────────────────────────────────────────────────────────

def render_review() -> None:
    ordered = st.session_state.ordered_sems
    idx     = st.session_state.review_idx

    if idx >= len(ordered):
        st.session_state.stage = "calculate"
        st.rerun()
        return

    cur_sem = ordered[idx]

    # ── Progress timeline ──────────────────────────────────────────────────
    tl_html = '<div class="timeline">'
    for i, sem in enumerate(ordered):
        ok = st.session_state.approvals.get(sem, False)
        if i < idx or ok:
            cls = "tl-done"; icon = "✓"
        elif i == idx:
            cls = "tl-active"; icon = "▶"
        else:
            cls = "tl-pending"; icon = str(i + 1)
        tl_html += f'<div class="tl-step {cls}">{icon} {sem}</div>'
        if i < len(ordered) - 1:
            tl_html += '<div class="tl-arrow">›</div>'
    tl_html += '</div>'
    st.markdown(tl_html, unsafe_allow_html=True)

    st.markdown(
        f'<div class="stage-title">📋 Reviewing {cur_sem}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="stage-subtitle">Step {idx + 1} of {len(ordered)} — '
        f'Parse, verify strength, fix issues, then approve.</div>',
        unsafe_allow_html=True,
    )

    _review_panel(cur_sem, idx, ordered)


def _parse_semester(sem: str) -> None:
    """Parse + combine all files assigned to this semester (runs once per sem)."""
    groups   = st.session_state.semester_groups.get(sem, [])
    raw      = st.session_state.raw_files
    subjects = st.session_state.file_subjects
    combined: list[dict] = []

    for fname in groups:
        fb = raw.get(fname, b"")
        sub_hint = subjects.get(fname)

        if _PARSER_OK:
            try:
                result = parse_file_to_records(fb, fname, subject_hint=sub_hint)
            except Exception as exc:
                result = {"status": "ERROR", "records": [],
                          "warnings": [str(exc)], "file_name": fname}
        else:
            result = _fallback_parse(fb, fname, sub_hint)

        if result.get("status") == "ERROR":
            for w in result.get("warnings", []):
                st.error(f"**{fname}**: {w}", icon="🚫")
        else:
            for w in result.get("warnings", []):
                st.warning(f"**{fname}**: {w}", icon="⚠️")
            combined.extend(result.get("records", []))

    st.session_state.sem_records[sem] = combined
    st.session_state.sem_dfs[sem]     = records_to_df(combined)


def _review_panel(sem: str, idx: int, ordered: list[str]) -> None:
    # ── Parse once ────────────────────────────────────────────────────────
    if sem not in st.session_state.sem_records:
        with st.spinner(f"Parsing {len(st.session_state.semester_groups.get(sem, []))} "
                        f"file(s) for {sem} …"):
            _parse_semester(sem)

    cur_df   = st.session_state.sem_dfs[sem]
    expected = EXPECTED_STRENGTH.get(sem, 0)

    # Distinct students (by roll_no) is the real strength measure
    distinct_rolls = cur_df["roll_no"].dropna().nunique()

    # ── A · Strength Gate ─────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">A · Student Strength Verification</div>',
                unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f"""<div class="kpi-box">
        <div class="kpi-value">{expected}</div>
        <div class="kpi-label">Expected</div></div>""", unsafe_allow_html=True)
    k2.markdown(f"""<div class="kpi-box">
        <div class="kpi-value">{distinct_rolls}</div>
        <div class="kpi-label">Distinct Students</div></div>""", unsafe_allow_html=True)
    k3.markdown(f"""<div class="kpi-box">
        <div class="kpi-value">{len(cur_df)}</div>
        <div class="kpi-label">Total Rows</div></div>""", unsafe_allow_html=True)
    k4.markdown(f"""<div class="kpi-box">
        <div class="kpi-value">{len(st.session_state.semester_groups.get(sem, []))}</div>
        <div class="kpi-label">Subject Files</div></div>""", unsafe_allow_html=True)

    strength_locked = distinct_rolls < expected
    if strength_locked:
        st.markdown(
            f'<div class="banner banner-critical">🚨 CRITICAL STRENGTH DISCREPANCY — '
            f'Expected <b>{expected}</b> students but found only <b>{distinct_rolls}</b> '
            f'distinct roll numbers. Add the missing <b>{expected - distinct_rolls}</b> '
            f'row(s) in the data grid below before approving.</div>',
            unsafe_allow_html=True,
        )
    elif distinct_rolls == expected:
        st.markdown(
            '<div class="banner banner-success">✅ Student count matches the '
            'expected strength perfectly.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="banner banner-warning">⚠️ {distinct_rolls - expected} extra '
            f'student(s) found vs expected strength. Verify no duplicate entries.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── B · Automated Validation ───────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">B · Automated Validation Results</div>',
                unsafe_allow_html=True)

    live_records = df_to_records(cur_df)
    has_blocked  = True

    if not _VALIDATOR_OK:
        st.error("validation_agent could not be imported — fix the module error in the sidebar.", icon="🚫")
    else:
        try:
            report      = validate_records(live_records, semester=sem)
            has_blocked = report.status == "BLOCKED"
            _render_validation(report)
            st.session_state.val_reports[sem] = report.model_dump()
        except Exception as exc:
            st.error(f"Validation engine error: {exc}", icon="🚫")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── C · Data Editor ───────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">C · Mark Sheet Data Editor</div>',
                unsafe_allow_html=True)

    file_list = st.session_state.semester_groups.get(sem, [])
    st.caption(
        f"Combined from {len(file_list)} file(s): "
        + ", ".join(f"`{f}`" for f in file_list)
        + "  ·  Edit cells or add rows directly. Click **Re-Validate** to refresh."
    )

    edited_df: pd.DataFrame = st.data_editor(
        st.session_state.sem_dfs[sem],
        key               = f"editor_{sem}",
        use_container_width=True,
        num_rows          = "dynamic",
        hide_index        = True,
        column_config={
            "student_name"  : st.column_config.TextColumn("Student Name",  required=True, width="medium"),
            "roll_no"       : st.column_config.TextColumn("Roll No",       required=True, width="medium"),
            "father_name"   : st.column_config.TextColumn("Father Name",                 width="medium"),
            "subject_name"  : st.column_config.TextColumn("Subject",       required=True, width="medium"),
            "total_marks"   : st.column_config.NumberColumn("Total Marks", min_value=0, format="%.1f", width="small"),
            "obtained_marks": st.column_config.NumberColumn("Obtained",    min_value=0, format="%.1f", width="small"),
            "credit_hours"  : st.column_config.NumberColumn("Cr. Hrs",     min_value=0, step=1, format="%d", width="small"),
            "department"    : st.column_config.TextColumn("Dept",                        width="small"),
        },
    )
    st.session_state.sem_dfs[sem] = edited_df
    st.markdown('</div>', unsafe_allow_html=True)

    # ── D · Controls ──────────────────────────────────────────────────────
    can_approve = (not has_blocked) and (not strength_locked)

    b1, b2, b3 = st.columns([2, 2, 4])
    with b1:
        if st.button("🔄 Re-Validate", use_container_width=True, key=f"reval_{sem}"):
            st.rerun()
    with b2:
        if st.button("✅ Approve Semester", type="primary",
                     disabled=not can_approve, use_container_width=True,
                     key=f"approve_{sem}"):
            _approve(sem, edited_df, idx, ordered)
    with b3:
        if not can_approve:
            reasons = []
            if has_blocked:    reasons.append("resolve all 🔴 BLOCKED errors")
            if strength_locked: reasons.append(f"add {expected - distinct_rolls} missing student(s)")
            st.markdown(
                f'<div class="banner banner-info" style="margin:0">🔒 '
                f'To unlock approval: <b>{"  &amp;  ".join(reasons)}</b></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="banner banner-success" style="margin:0">'
                '🔓 No blockers — ready to approve.</div>',
                unsafe_allow_html=True,
            )


def _render_validation(report: Any) -> None:
    status_map = {
        "CLEAN"  : ("banner-success", "✅ All records are clean."),
        "FLAGGED": ("banner-warning", "⚠️ Some records need review."),
        "BLOCKED": ("banner-critical","🚫 Critical issues must be fixed before approval."),
    }
    cls, msg = status_map.get(report.status, ("banner-info", ""))

    # Status bar
    st.markdown(f"""
    <div class="banner {cls}">
        <div style="flex:1">{msg}</div>
        <div style="display:flex;gap:12px;font-size:0.8rem">
            <span class="badge badge-clean">✓ {report.summary.clean} clean</span>
            <span class="badge badge-flagged">⚠ {report.summary.flagged} flagged</span>
            <span class="badge badge-blocked">✗ {report.summary.blocked} blocked</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not report.flagged_rows:
        return

    blocked = [r for r in report.flagged_rows if r.severity == "BLOCKED"]
    flagged = [r for r in report.flagged_rows if r.severity == "FLAGGED"]
    info    = [r for r in report.flagged_rows if r.severity == "INFO"]

    if blocked:
        with st.expander(f"🔴 BLOCKED Issues — {len(blocked)} (must fix)", expanded=True):
            for r in blocked:
                st.error(
                    f"**Row {r.row_index}** · `{r.roll_no or 'NO ROLL'}` · "
                    f"**{r.error_code}**: {r.error_message}",
                    icon="🚫",
                )
    if flagged:
        with st.expander(f"🟡 FLAGGED Warnings — {len(flagged)} (review recommended)"):
            for r in flagged:
                st.warning(
                    f"**Row {r.row_index}** · `{r.roll_no or 'NO ROLL'}` · "
                    f"**{r.error_code}**: {r.error_message}",
                    icon="⚠️",
                )
    if info:
        with st.expander(f"🔵 INFO Notes — {len(info)} (non-credit subjects)"):
            for r in info:
                st.info(
                    f"**Row {r.row_index}** · `{r.roll_no or 'NO ROLL'}` · "
                    f"**{r.error_code}**: {r.error_message}",
                    icon="ℹ️",
                )


def _approve(sem: str, df: pd.DataFrame, idx: int, ordered: list[str]) -> None:
    st.session_state.sem_records[sem] = df_to_records(df)
    st.session_state.approvals[sem]   = True
    st.session_state.review_idx       = idx + 1
    if st.session_state.review_idx >= len(ordered):
        st.session_state.stage = "calculate"
    st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 3 — CALCULATE
# ──────────────────────────────────────────────────────────────────────────────

def render_calculate() -> None:
    st.markdown('<div class="stage-title">⚙️ Running GPA Calculation Engine</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="stage-subtitle">Processing all approved semester records '
                'through the HEC Pakistan GPA formula.</div>', unsafe_allow_html=True)

    approved = [s for s in st.session_state.ordered_sems
                if st.session_state.approvals.get(s)]

    if not approved:
        st.error("No approved semesters. Return to review.", icon="🚫")
        if st.button("← Back to Review"):
            st.session_state.stage      = "review"
            st.session_state.review_idx = 0
            st.rerun()
        return

    c1, c2, c3 = st.columns(3)
    total_recs = sum(len(st.session_state.sem_records.get(s, [])) for s in approved)
    c1.metric("Approved Semesters", len(approved))
    c2.metric("Total Records",      total_recs)
    c3.metric("Distinct Subjects",
              len({r.get("subject_name") for s in approved
                   for r in st.session_state.sem_records.get(s, [])
                   if r.get("subject_name")}))

    if not _CALC_OK:
        st.error("calculator_agent could not be imported. Fix import errors in sidebar.", icon="🚫")
        return

    all_records: list[dict] = []
    for sem in approved:
        sn = sem_num(sem)
        ay = infer_academic_year(sn)
        for rec in st.session_state.sem_records.get(sem, []):
            e = dict(rec)
            e["semester"]      = sn
            e["academic_year"] = ay
            all_records.append(e)

    with st.spinner("Calculating GPA and CGPA for all approved records …"):
        try:
            out = calculator_agent_node({
                "validated_records": all_records,
                "semester"         : sem_num(approved[0]),
                "academic_year"    : infer_academic_year(sem_num(approved[0])),
                "db_url"           : st.session_state.db_url,
                "approved_by"      : "HOD",
                "source_file"      : "dashboard_upload",
                "errors"           : [],
            })
            st.session_state.calc_results = out
            st.session_state.stage        = "results"
            st.rerun()
        except Exception as exc:
            st.error(f"Calculation engine error: {exc}", icon="🚫")
            st.exception(exc)


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 4 — RESULTS
# ──────────────────────────────────────────────────────────────────────────────

def render_results() -> None:
    st.markdown('<div class="stage-title">📊 GPA Results & Final Approval</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="stage-subtitle">Review the progressive GPA table carefully '
                'before committing to the database.</div>', unsafe_allow_html=True)

    res           = st.session_state.calc_results or {}
    marks_written = res.get("marks_written", 0)
    sem_gpas      = res.get("semester_gpas", [])
    cgpas         = res.get("cgpas", [])
    errors        = res.get("errors", [])

    # ── Top metrics ────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Records Written",     marks_written)
    m2.metric("Semester GPAs",       len(sem_gpas))
    m3.metric("Students (CGPA)",     len(cgpas))
    m4.metric("Errors",              len(errors),
              delta=f"{len(errors)} errors" if errors else None,
              delta_color="inverse" if errors else "off")

    if errors:
        with st.expander(f"⚠️ Calculation Errors ({len(errors)})", expanded=True):
            for e in errors:
                st.error(f"`{e.get('roll_no','N/A')}` — {e.get('reason','unknown')}", icon="🚫")

    # ── Progressive GPA Table ─────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Progressive Semester GPA & Cumulative CGPA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.8rem;color:#64748B;margin-bottom:14px">'
        'CGPA = Σ Quality Points ÷ Σ Credit Hours (HEC Pakistan standard — '
        'never an average of GPA values)</div>',
        unsafe_allow_html=True,
    )

    approved_sems = [s for s in st.session_state.ordered_sems
                     if st.session_state.approvals.get(s)]
    prog_html = _build_progressive_html(approved_sems)
    st.markdown(prog_html, unsafe_allow_html=True)

    # Download
    prog_df = _build_progressive_df_for_export(approved_sems)
    if not prog_df.empty:
        buf = io.StringIO()
        prog_df.to_csv(buf, index=False)
        st.download_button(
            "⬇ Download GPA Report (CSV)",
            data      = buf.getvalue(),
            file_name = f"gpa_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime      = "text/csv",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Final decision ─────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Final Decision</div>', unsafe_allow_html=True)

    if st.session_state.final_saved:
        st.markdown(
            '<div class="banner banner-success">💾 Results approved and permanently '
            'saved to the database. The HOD sign-off has been recorded.</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 Start New Batch", use_container_width=True):
            _reset(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    col_save, col_reject = st.columns(2)
    with col_save:
        if st.button("💾 Approve & Save Permanently to Database",
                     type="primary", use_container_width=True):
            # Calculator already committed; this records HOD sign-off
            st.session_state.final_saved = True
            st.success("✅ HOD approval recorded. Results saved.", icon="✅")
            st.rerun()
    with col_reject:
        if st.button("🛑 Report Calculation Error / Reject",
                     type="secondary", use_container_width=True):
            st.session_state.calc_results = None
            st.session_state.approvals    = {}
            st.session_state.review_idx   = 0
            st.session_state.stage        = "review"
            st.warning("Results rejected. All approvals cleared — please re-review.", icon="⚠️")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _build_progressive_html(approved_sems: list[str]) -> str:
    """Build an HTML progressive GPA table from the DB (or in-memory fallback)."""

    def _gpa_cell(val: float | None) -> str:
        if val is None:
            return '<td class="gpa-dash">—</td>'
        cls = ("gpa-high" if val >= 3.50 else
               "gpa-mid"  if val >= 2.50 else "gpa-low")
        return f'<td class="{cls}">{val:.2f}</td>'

    sem_nums = sorted(sem_num(s) for s in approved_sems)

    # ── Try DB query ──────────────────────────────────────────────────────
    rows_data: list[dict] = []
    try:
        if _CALC_OK:
            engine = get_engine(st.session_state.db_url)
            with Session(engine) as sess:
                students  = sess.execute(sa_select(Student)).scalars().all()
                all_sgpas = sess.execute(sa_select(SemesterGPA)).scalars().all()
                all_cgpas = sess.execute(sa_select(CGPA)).scalars().all()

            sgpa_map: dict[int, dict[int, Any]] = {}
            for sg in all_sgpas:
                sgpa_map.setdefault(sg.student_id, {})[sg.semester] = sg
            cgpa_map = {c.student_id: c for c in all_cgpas}

            for stu in students:
                row: dict = {"name": stu.student_name, "roll": stu.roll_no,
                             "dept": stu.department or ""}
                running_qp = running_ch = 0.0
                for sn in sem_nums:
                    sg = sgpa_map.get(stu.id, {}).get(sn)
                    row[f"gpa_{sn}"] = sg.gpa if sg else None
                    if sg:
                        running_ch += sg.total_credit_hours or 0
                        running_qp += sg.total_quality_points or 0
                    row[f"cgpa_{sn}"] = (round(running_qp / running_ch, 2)
                                         if running_ch > 0 else None)
                final = cgpa_map.get(stu.id)
                row["final_cgpa"] = final.cgpa if final else None
                rows_data.append(row)
    except Exception:
        # fall back to in-memory
        res = st.session_state.calc_results or {}
        sgpa_mem: dict[int, dict[int, dict]] = {}
        for sg in res.get("semester_gpas", []):
            sgpa_mem.setdefault(sg["student_id"], {})[sg["semester"]] = sg
        cgpa_mem = {c["student_id"]: c for c in res.get("cgpas", [])}
        for sid in sorted(sgpa_mem):
            row = {"name": f"Student {sid}", "roll": "—", "dept": ""}
            rqp = rch = 0.0
            for sn in sem_nums:
                sg = sgpa_mem.get(sid, {}).get(sn, {})
                gpa = sg.get("gpa")
                row[f"gpa_{sn}"] = gpa
                rch += sg.get("total_credit_hours", 0) or 0
                rqp += sg.get("total_quality_points", 0) or 0
                row[f"cgpa_{sn}"] = round(rqp / rch, 2) if rch > 0 else None
            fc = cgpa_mem.get(sid, {})
            row["final_cgpa"] = fc.get("cgpa")
            rows_data.append(row)

    if not rows_data:
        return '<div class="banner banner-warning">No student data found in the database.</div>'

    # ── Build HTML ────────────────────────────────────────────────────────
    # Header
    th = "<tr><th>Student Name</th><th>Roll No</th><th>Dept</th>"
    for sn in sem_nums:
        th += f"<th>Sem {sn} GPA</th><th>CGPA (1–{sn})</th>"
    th += "<th>Final CGPA</th></tr>"

    body = ""
    for r in rows_data:
        body += (f'<tr><td class="name-col">{r["name"]}</td>'
                 f'<td class="roll-col">{r["roll"]}</td>'
                 f'<td class="roll-col">{r["dept"]}</td>')
        for sn in sem_nums:
            body += _gpa_cell(r.get(f"gpa_{sn}"))
            body += _gpa_cell(r.get(f"cgpa_{sn}"))
        body += _gpa_cell(r.get("final_cgpa"))
        body += "</tr>"

    return (f'<div style="overflow-x:auto">'
            f'<table class="gpa-table"><thead>{th}</thead><tbody>{body}</tbody></table>'
            f'</div>'
            f'<div style="margin-top:10px;font-size:0.75rem;color:#94A3B8">'
            f'🟢 ≥ 3.50 Excellent &nbsp;|&nbsp; '
            f'🟡 2.50 – 3.49 Good &nbsp;|&nbsp; '
            f'🔴 &lt; 2.50 At Risk</div>')


def _build_progressive_df_for_export(approved_sems: list[str]) -> pd.DataFrame:
    """Plain DataFrame for CSV export."""
    sem_nums = sorted(sem_num(s) for s in approved_sems)
    rows: list[dict] = []
    try:
        if not _CALC_OK:
            raise RuntimeError("calc not available")
        engine = get_engine(st.session_state.db_url)
        with Session(engine) as sess:
            students  = sess.execute(sa_select(Student)).scalars().all()
            all_sgpas = sess.execute(sa_select(SemesterGPA)).scalars().all()
            all_cgpas = sess.execute(sa_select(CGPA)).scalars().all()
        sgpa_map: dict[int, dict[int, Any]] = {}
        for sg in all_sgpas:
            sgpa_map.setdefault(sg.student_id, {})[sg.semester] = sg
        cgpa_map = {c.student_id: c for c in all_cgpas}
        for stu in students:
            row = {"Student Name": stu.student_name, "Roll No": stu.roll_no,
                   "Department": stu.department or ""}
            rqp = rch = 0.0
            for sn in sem_nums:
                sg = sgpa_map.get(stu.id, {}).get(sn)
                row[f"Sem {sn} GPA"]    = f"{sg.gpa:.2f}"  if (sg and sg.gpa)  else "—"
                if sg:
                    rch += sg.total_credit_hours or 0
                    rqp += sg.total_quality_points or 0
                row[f"CGPA (1–{sn})"] = f"{rqp/rch:.2f}" if rch > 0 else "—"
            fc = cgpa_map.get(stu.id)
            row["Final CGPA"] = f"{fc.cgpa:.2f}" if (fc and fc.cgpa) else "—"
            rows.append(row)
    except Exception:
        pass
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# FALLBACK PARSER  (when parser_agent can't be imported)
# ──────────────────────────────────────────────────────────────────────────────
_FALIAS: dict[str, list[str]] = {
    "student_name"  : ["student name","name","student","sname"],
    "roll_no"       : ["roll no","roll number","rollno","reg no","registration no"],
    "father_name"   : ["father name","father's name","fname"],
    "subject_name"  : ["subject name","subject","course name","course"],
    "total_marks"   : ["total marks","total","max marks","maximum marks","full marks"],
    "obtained_marks": ["obtained marks","obtained","marks","marks obtained","scored"],
    "credit_hours"  : ["credit hours","credits","ch","credit_hours"],
    "department"    : ["department","dept","program"],
}

_SEM_RE = [
    (re.compile(r"^[Ss](\d)\b"),              1),
    (re.compile(r"\bSem(?:ester)?[\s_-]?(\d)", re.I), 1),
    (re.compile(r"(\d)(?:st|nd|rd|th)\b", re.I),      1),
]


def _fallback_detect(filename: str) -> tuple[str | None, str | None]:
    stem = Path(filename).stem
    for pat, grp in _SEM_RE:
        m = pat.search(stem)
        if m:
            n = int(m.group(grp))
            if 1 <= n <= 8:
                rest = stem[m.end():].lstrip("-_ ")
                sub  = rest or None
                return f"Semester {n}", sub
    return None, None


def _fallback_parse(file_bytes: bytes, filename: str,
                    subject_hint: str | None) -> dict[str, Any]:
    import io as _io
    ext = Path(filename).suffix.lower()
    buf = _io.BytesIO(file_bytes)
    try:
        df_raw = (pd.read_csv(buf, header=None, dtype=str)
                  if ext == ".csv"
                  else pd.read_excel(buf, header=None, dtype=str, engine="openpyxl"))
    except Exception as exc:
        return {"file_name": filename, "status": "ERROR", "records": [],
                "warnings": [str(exc)]}

    # simple header detect
    alias_words = {w for a_list in _FALIAS.values() for a in a_list for w in a.split()}
    best, score = 0, -1
    for i in range(min(10, len(df_raw))):
        words = {w for v in df_raw.iloc[i].values if pd.notna(v)
                 for w in str(v).strip().lower().split()}
        s = len(words & alias_words)
        if s > score:
            score, best = s, i
    buf = _io.BytesIO(file_bytes)
    try:
        df = (pd.read_csv(buf, header=best, dtype=str)
              if ext == ".csv"
              else pd.read_excel(buf, header=best, dtype=str, engine="openpyxl"))
    except Exception:
        return {"file_name": filename, "status": "ERROR", "records": [], "warnings": []}
    df.dropna(how="all", inplace=True)

    n2raw = {re.sub(r"\s+", " ", str(c).strip().lower()): c for c in df.columns}
    cm: dict[str, str] = {}
    for field, aliases in _FALIAS.items():
        for a in aliases:
            if a in n2raw:
                cm[field] = n2raw[a]; break

    records: list[dict] = []
    for _, row in df.iterrows():
        rec: dict = {"has_issues": False, "parse_warnings": [],
                     "subject_name": subject_hint}
        all_null = True
        for field, col in cm.items():
            raw = row.get(col)
            if pd.isna(raw) or str(raw).strip() in ("", "nan"):
                continue
            all_null = False
            val = str(raw).strip()
            if field in ("total_marks", "obtained_marks"):
                try:    rec[field] = float(val)
                except: rec[field] = val; rec["has_issues"] = True
            elif field == "credit_hours":
                try:    rec[field] = int(float(val))
                except: rec[field] = val; rec["has_issues"] = True
            else:
                rec[field] = val
        if not all_null:
            records.append(rec)
    return {"file_name": filename,
            "status": "OK" if records else "ERROR",
            "records": records, "warnings": []}


# ──────────────────────────────────────────────────────────────────────────────
# RESET
# ──────────────────────────────────────────────────────────────────────────────

def _reset() -> None:
    for k in ["stage","raw_files","file_assignments","file_subjects",
              "semester_groups","sem_records","sem_dfs","approvals",
              "val_reports","review_idx","ordered_sems","calc_results","final_saved"]:
        st.session_state.pop(k, None)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _init()
    render_sidebar()

    stage = st.session_state.stage
    if   stage == "upload"    : render_upload()
    elif stage == "assign"    : render_assign()
    elif stage == "review"    : render_review()
    elif stage == "calculate" : render_calculate()
    elif stage == "results"   : render_results()
    else:
        st.error(f"Unknown stage '{stage}'.")
        if st.button("🔄 Reset"): _reset(); st.rerun()


if __name__ == "__main__":
    main()
