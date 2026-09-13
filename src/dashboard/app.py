
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
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ─── Agent imports (fail-safe: UI still boots even if one module is broken) ───
_ERRORS: list[str] = []

try:
    from src.agents.parser_agent import (
        detect_semester_and_subject,
        parse_file_to_records,
        _prettify_subject,          # reused for subject name formatting
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
    from src.models.database_models import Student, Subject, Mark, SemesterGPA, CGPA
    from sqlalchemy.orm import Session
    from sqlalchemy import select as sa_select
    _CALC_OK = True
except Exception as _e:
    _CALC_OK = False
    _ERRORS.append(f"calculator_agent / database_models → {_e}")

# ──────────────────────────────────────────────────────────────────────────────

try:
    from src.dashboard.transcript_generator import (
        fetch_multiple_transcripts,
        generate_transcript_pdf,
        generate_bulk_zip,
    )
    _TRANSCRIPT_OK = True
except Exception as _te:
    _TRANSCRIPT_OK = False
    _ERRORS.append(f"transcript_generator -> {_te}")

# ── University logo — resolved once at startup ────────────────────────────────
_UOL_LOGO: str | None = None
for _lp in [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "uol_logo.png"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "uol_logo.png"),
    "src/dashboard/assets/uol_logo.png",
    "uol_logo.png",
]:
    if os.path.isfile(_lp):
        _UOL_LOGO = _lp
        break

try:
    from src.dashboard.analytics import render_analytics
    _ANALYTICS_OK = True
except Exception as _ana_e:
    _ANALYTICS_OK = False
    _ERRORS.append(f"analytics → {_ana_e}")

try:
    from src.dashboard.auth import (
        render_login, render_logout,
        get_role, is_coordinator, require_coordinator,
    )
    _AUTH_OK = True
except Exception as _auth_e:
    _AUTH_OK = False
    _ERRORS.append(f"auth → {_auth_e}")

# PAGE CONFIG  (must be the first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title   = "GPA Dashboard — University of Loralai",
    page_icon    = "🎓",
    layout       = "wide",
    initial_sidebar_state = "expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# ENTERPRISE DESIGN SYSTEM
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
.stApp { background-color: #EEF2F7; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B1E3D 0%, #122B52 60%, #0F2444 100%);
    border-right: 1px solid #1E3A6E;
}
section[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
section[data-testid="stSidebar"] .sidebar-title { color:#F1F5F9!important;font-size:1.05rem;font-weight:700; }
section[data-testid="stSidebar"] hr { border-color: #1E3A6E !important; }
.card { background:#FFFFFF;border-radius:12px;padding:24px 28px;
        box-shadow:0 1px 4px rgba(0,0,0,.07),0 4px 16px rgba(0,0,0,.04);
        border:1px solid #E2E8F0;margin-bottom:18px; }
.card-sm { background:#FFFFFF;border-radius:10px;padding:16px 20px;
           box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid #E2E8F0;margin-bottom:12px; }
.stage-title  { font-size:1.55rem;font-weight:800;color:#0F2444;letter-spacing:-.5px;margin-bottom:4px; }
.stage-subtitle { font-size:.9rem;color:#64748B;margin-bottom:24px;font-weight:400; }
.section-label { font-size:.7rem;font-weight:700;letter-spacing:1.2px;
                 text-transform:uppercase;color:#94A3B8;margin-bottom:8px; }
.banner { border-radius:8px;padding:12px 18px;font-weight:600;font-size:.9rem;
          margin:10px 0;display:flex;align-items:center;gap:10px;line-height:1.5; }
.banner-critical { background:linear-gradient(135deg,#FEF2F2,#FEE2E2);border:1px solid #FECACA;
                   border-left:4px solid #DC2626;color:#7F1D1D; }
.banner-warning  { background:linear-gradient(135deg,#FFFBEB,#FEF3C7);border:1px solid #FDE68A;
                   border-left:4px solid #D97706;color:#78350F; }
.banner-success  { background:linear-gradient(135deg,#F0FDF4,#DCFCE7);border:1px solid #BBF7D0;
                   border-left:4px solid #16A34A;color:#14532D; }
.banner-info     { background:linear-gradient(135deg,#EFF6FF,#DBEAFE);border:1px solid #BFDBFE;
                   border-left:4px solid #2563EB;color:#1E3A8A; }
.badge { display:inline-block;border-radius:20px;padding:2px 10px;
         font-size:.72rem;font-weight:700;letter-spacing:.3px;vertical-align:middle; }
.badge-blocked { background:#FEE2E2;color:#B91C1C;border:1px solid #FECACA; }
.badge-flagged { background:#FEF3C7;color:#B45309;border:1px solid #FDE68A; }
.badge-clean   { background:#DCFCE7;color:#15803D;border:1px solid #BBF7D0; }
.badge-info    { background:#DBEAFE;color:#1D4ED8;border:1px solid #BFDBFE; }
.kpi-box { background:#FFFFFF;border-radius:12px;padding:20px 24px;text-align:center;
           box-shadow:0 1px 4px rgba(0,0,0,.06);border:1px solid #E2E8F0; }
.kpi-value { font-size:2.2rem;font-weight:800;color:#0F2444;line-height:1.1; }
.kpi-label { font-size:.78rem;font-weight:600;color:#64748B;
             text-transform:uppercase;letter-spacing:.8px;margin-top:6px; }
.file-chip { display:inline-flex;align-items:center;gap:6px;background:#F8FAFC;
             border:1px solid #E2E8F0;border-radius:8px;padding:6px 12px;
             font-size:.8rem;color:#374151;margin:3px; }
.gpa-table { width:100%;border-collapse:collapse;font-size:.85rem; }
.gpa-table th { background:#0F2444;color:#F1F5F9;padding:10px 14px;text-align:center;
                font-weight:600;font-size:.75rem;letter-spacing:.5px;white-space:nowrap; }
.gpa-table td { padding:9px 14px;text-align:center;border-bottom:1px solid #F1F5F9;color:#374151; }
.gpa-table tr:hover td { background:#F8FAFC; }
.gpa-table td.name-col { text-align:left;font-weight:600;color:#0F2444; }
.gpa-table td.roll-col { text-align:left;color:#64748B;font-size:.8rem; }
.gpa-high { background:#DCFCE7!important;color:#166534;font-weight:700;border-radius:6px; }
.gpa-mid  { background:#FEF3C7!important;color:#92400E;font-weight:600;border-radius:6px; }
.gpa-low  { background:#FEE2E2!important;color:#991B1B;font-weight:600;border-radius:6px; }
.gpa-dash { color:#CBD5E1; }
.sb-step   { padding:6px 0;font-size:.85rem;display:flex;align-items:center;gap:8px; }
.sb-done   { color:#4ADE80!important; }
.sb-active { color:#60A5FA!important;font-weight:700!important; }
.sb-pending{ color:#475569!important; }
.sb-sem    { font-size:.8rem;display:flex;align-items:center;gap:6px;padding:4px 0;
             border-bottom:1px solid rgba(255,255,255,.07); }
.upload-zone { border:2px dashed #CBD5E1;border-radius:12px;padding:40px;
               text-align:center;background:#F8FAFC;margin-bottom:16px; }
.upload-zone h3 { color:#0F2444;margin:0 0 8px 0;font-size:1.1rem; }
.upload-zone p  { color:#64748B;margin:0;font-size:.88rem; }
.divider { border:none;border-top:1px solid #E2E8F0;margin:20px 0; }
.block-container { padding-top:2rem!important; }
/* Per-file section separator */
.file-section { border:1px solid #E2E8F0;border-radius:10px;padding:16px 20px;
                margin-bottom:14px;background:#FAFBFC; }
.file-section-header { font-size:.82rem;font-weight:700;color:#0F2444;
                       display:flex;align-items:center;gap:8px;margin-bottom:10px; }
/* Historical banner */
.hist-banner { background:linear-gradient(135deg,#F0F9FF,#E0F2FE);border:1px solid #BAE6FD;
               border-left:4px solid #0284C7;border-radius:8px;padding:12px 18px;
               margin:10px 0;color:#0C4A6E; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

EXPECTED_STRENGTH: dict[str, int] = {
    "Semester 1": 20, "Semester 2": 20, "Semester 3": 20, "Semester 4": 19,
    "Semester 5": 18, "Semester 6": 18, "Semester 7": 18, "Semester 8": 18,
}
ALL_SEMESTERS = list(EXPECTED_STRENGTH.keys())
DEFAULT_DB    = os.getenv("DATABASE_URL", "sqlite:///./gpa_system.db")

EDITOR_COLS = [
    "student_name", "roll_no", "father_name",
    "subject_name", "total_marks", "obtained_marks",
    "credit_hours", "department",
]

# Semester dropdown options used in the Assign stage
_SEM_OPTIONS: list[str] = ["(Select Semester…)"] + [f"Semester {n}" for n in range(1, 9)]


# ──────────────────────────────────────────────────────────────────────────────
# CONTENT-BASED SEMESTER & SUBJECT DETECTION
# Works regardless of filename.  Scans the first 15 rows of any .xlsx/.csv
# for university metadata (rows 1-6 typically contain institution, dept,
# subject, semester, session, date — before the actual data header row).
# ──────────────────────────────────────────────────────────────────────────────

def _prettify_subject_local(raw: str) -> str:
    """
    Local fallback for subject prettification when parser_agent is not importable.
    'SoftEng' → 'Soft Eng'  |  'DataStructures' → 'Data Structures'
    """
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() if len(s) > 2 else s.upper()


def _do_prettify(raw: str) -> str:
    """Use parser_agent._prettify_subject if available, else local fallback."""
    if _PARSER_OK:
        try:
            return _prettify_subject(raw)
        except Exception:
            pass
    return _prettify_subject_local(raw)


# Semester regex patterns applied to individual cell values (three layouts)
_CONTENT_SEM_PATTERNS: list[re.Pattern] = [
    # "Semester: 3"  "Sem: 3"  "Semester No. 3"  "Sem-3"
    re.compile(r'(?:semester|sem)(?:ester)?\s*(?:no\.?|number|#)?\s*[:\-–]?\s*(\d)', re.I),
    # "3rd Semester"  "3 Semester"
    re.compile(r'(\d)\s*(?:st|nd|rd|th)?\s+semester', re.I),
    # "Semester 3"  (space-separated, number after)
    re.compile(r'(?:semester|sem)(?:ester)?\s+(\d)\b', re.I),
]

# Keywords treated as semester-key cells (for two-cell "Semester | 3" format)
_SEM_KEY_CELLS: frozenset[str] = frozenset({
    'semester', 'sem', 'semester no', 'sem no',
    'semester number', 'sem number', 'semester#', 'sem.',
    'semester no.', 'semester no:', 'sem no.',
})

# Keywords treated as subject-key cells
_SUBJ_KEY_CELLS: frozenset[str] = frozenset({
    'subject', 'subject name', 'course', 'course name',
    'paper', 'paper name', 'paper title', 'course title', 'subject title',
})

# Data-column indicators — stop metadata scan when we hit this row
# (prevents false positives from "Subject Name" in the actual column header row)
_DATA_COL_INDICATORS: frozenset[str] = frozenset({
    'roll', 'marks', 'obtained', 'credit', 'grade', 'percentage', 'scored',
})


def extract_meta_from_content(
    file_bytes: bytes,
    filename: str,
) -> tuple[str | None, str | None]:
    """
    Scan the first 15 rows of an Excel/CSV file to detect:
      • semester_label  — "Semester N" (N = 1–8)
      • subject_name    — prettified subject string

    Three cell layouts handled:
      A) Single-cell colon  : "Semester: 3"  /  "Subject: Operating Systems"
      B) Two-cell key–value : | Semester | 3 |  /  | Subject | OS |
      C) Free text in cell  : "3rd Semester" appearing anywhere

    Stops scanning as soon as both values are found, OR when it encounters
    a row that looks like the student-data column header (≥3 cells with ≥2
    data-column keywords such as 'roll', 'marks', 'obtained', 'credit').
    This prevents picking up "Subject Name" from the header row as a subject.

    Returns (semester_label, subject_name); either may be None.
    """
    ext = Path(filename).suffix.lower()
    buf = io.BytesIO(file_bytes)
    try:
        df_raw = (
            pd.read_csv(buf, header=None, dtype=str, nrows=15)
            if ext == ".csv"
            else pd.read_excel(buf, header=None, dtype=str, nrows=15, engine="openpyxl")
        )
    except Exception:
        return None, None

    semester_label: str | None = None
    subject_name:   str | None = None

    def _try_sem(text: str) -> str | None:
        """Return 'Semester N' if text matches any semester pattern, else None."""
        for pat in _CONTENT_SEM_PATTERNS:
            m = pat.search(text)
            if m:
                try:
                    n = int(m.group(1))
                    if 1 <= n <= 8:
                        return f"Semester {n}"
                except (ValueError, IndexError):
                    pass
        return None

    def _is_data_header(cells: list[str]) -> bool:
        """Return True when this row looks like the student-data column header."""
        if len(cells) < 3:
            return False
        joined = " ".join(c.lower() for c in cells)
        hits = sum(1 for kw in _DATA_COL_INDICATORS if kw in joined)
        return hits >= 2

    for row_i in range(min(15, len(df_raw))):
        # Collect non-null, non-empty cell strings for this row
        cells = [
            str(v).strip()
            for v in df_raw.iloc[row_i].values
            if pd.notna(v) and str(v).strip().lower() not in ("", "nan", "none")
        ]
        if not cells:
            continue

        # Stop scanning once we hit the actual student-data header row
        if _is_data_header(cells):
            break

        for col_j, cell in enumerate(cells):
            cell_lower = cell.lower().strip()

            # ── Semester detection ─────────────────────────────────────────────
            if semester_label is None:
                # Layout C / A  — value embedded in the cell itself
                found = _try_sem(cell)
                if found:
                    semester_label = found
                else:
                    # Layout B — key cell ("Semester") + next-cell value ("3")
                    key_norm = cell_lower.rstrip(":").strip()
                    if key_norm in _SEM_KEY_CELLS and col_j + 1 < len(cells):
                        val = cells[col_j + 1].strip()
                        # Value might be a bare digit or "S3" style
                        try:
                            n = int(float(val))
                            if 1 <= n <= 8:
                                semester_label = f"Semester {n}"
                        except (ValueError, TypeError):
                            m = re.match(r"^S(\d)$", val, re.I)
                            if m:
                                n = int(m.group(1))
                                if 1 <= n <= 8:
                                    semester_label = f"Semester {n}"

            # ── Subject detection ──────────────────────────────────────────────
            if subject_name is None:
                if ":" in cell:
                    # Layout A — "Subject: Operating Systems"
                    key_part = cell.split(":", 1)[0].strip().lower()
                    val_part = cell.split(":", 1)[1].strip()
                    if key_part in _SUBJ_KEY_CELLS and val_part and len(val_part) > 1:
                        subject_name = _do_prettify(val_part)
                else:
                    # Layout B — | Subject | Operating Systems |
                    key_norm = cell_lower.rstrip(":").strip()
                    if key_norm in _SUBJ_KEY_CELLS and col_j + 1 < len(cells):
                        val = cells[col_j + 1].strip()
                        # Guard: skip if the next cell looks like a semester value
                        if val and len(val) > 1 and not _try_sem(val):
                            subject_name = _do_prettify(val)

        if semester_label and subject_name:
            break   # both found — no need to scan further rows

    return semester_label, subject_name


def _safe_key(s: str) -> str:
    """Convert any string to a safe Streamlit widget key (no spaces/special chars)."""
    return re.sub(r"[^a-zA-Z0-9]", "_", s)


def _apply_editor_edits(df: pd.DataFrame, editor_key: str) -> pd.DataFrame:
    """
    Read the CURRENT st.data_editor widget state from session_state and apply
    it to *df*, returning an updated copy.

    WHY THIS EXISTS
    ───────────────
    Streamlit stores a data_editor's pending edits in
    st.session_state[editor_key] as:
        {
            "edited_rows" : { "row_idx": {"col": new_val, …}, … },
            "added_rows"  : [ {"col": val, …}, … ],
            "deleted_rows": [ row_idx, … ]
        }
    This dict is written by Streamlit *before* the script re-runs, so reading
    it here (before the widget call) gives the CURRENT edit state — not the
    previous render's state.  Without this, there is a one-render lag where
    a user fills in a credit_hours cell but the validation still reads the old
    None value and keeps showing EC-09 BLOCKED.

    USAGE
    ─────
    Call this just before running validate_records(), passing the same key
    that will be used for st.data_editor() later in the same render cycle.
    """
    if editor_key not in st.session_state:
        return df

    edits = st.session_state[editor_key]
    if not isinstance(edits, dict):
        return df

    df = df.copy()

    # ── Apply cell-level edits ─────────────────────────────────────────────────
    for row_idx_str, changes in edits.get("edited_rows", {}).items():
        try:
            row_idx = int(row_idx_str)
        except (ValueError, TypeError):
            continue
        if row_idx >= len(df):
            continue
        for col, val in changes.items():
            if col in df.columns:
                df.at[row_idx, col] = val

    # ── Apply added rows ───────────────────────────────────────────────────────
    added = edits.get("added_rows", [])
    if added:
        df = pd.concat(
            [df, pd.DataFrame(added, columns=df.columns)],
            ignore_index=True,
        )

    # ── Apply deleted rows ─────────────────────────────────────────────────────
    deleted = [int(i) for i in edits.get("deleted_rows", [])
               if int(i) < len(df)]
    if deleted:
        df = df.drop(index=deleted).reset_index(drop=True)

    return df


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
            is_null = (val is None
                       or (isinstance(val, float) and pd.isna(val))
                       or str(val).strip() in ("", "nan", "None", "NaT"))
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
        "stage"            : "upload",
        "raw_files"        : {},   # {fname: bytes}
        "file_assignments" : {},   # {fname: "Semester N" | None}
        "file_subjects"    : {},   # {fname: subject_hint_str}
        "detection_source" : {},   # {fname: "content" | "filename" | "none"}
        "semester_groups"  : {},   # {sem: [fname, …]}
        "sem_file_records" : {},   # {sem: {fname: list[dict]}}
        "sem_file_dfs"     : {},   # {sem: {fname: pd.DataFrame}}
        "sem_records"      : {},   # {sem: list[dict]}  — combined for calculator
        "approvals"        : {},   # {sem: bool}
        "val_reports"      : {},   # {sem: report_dict}  (legacy compat)
        "ordered_sems"     : [],
        "calc_results"     : None,
        "final_saved"      : False,
        "db_url"           : DEFAULT_DB,
        "academic_year"    : "",
        "invalid_files"    : [],   # kept for legacy compat; always empty now
        "transcript_rolls_raw"   : "",
        "transcript_fetched"     : {},
        "transcript_approvals"   : {},
        "transcript_mode"        : "hitl",
        "transcript_print_idx"   : 0,
        "transcript_print_active": False,
        "transcript_sem_upto"    : 0,    # 0 = all semesters; N = include 1..N
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
            <div style="font-size:1.4rem;font-weight:800;color:#F1F5F9;letter-spacing:-.5px">
                🎓 GPA System
            </div>
            <div style="font-size:.75rem;color:#94A3B8;margin-top:2px">
                University of Loralai · CS Dept
            </div>
        </div>""", unsafe_allow_html=True)
        st.divider()

        st.markdown('<div class="section-label" style="color:#475569">Pipeline</div>',
                    unsafe_allow_html=True)
        stages  = ["upload", "assign", "review", "calculate", "results"]
        labels  = ["Upload Files", "Review Assignments", "HITL Review (Tabs)",
                   "GPA Calculation", "Results & Save"]
        icons   = ["📁", "🗂️", "📋", "⚙️", "📊"]
        cur     = st.session_state.stage
        cur_idx = stages.index(cur)

        for i, (s, lbl, ico) in enumerate(zip(stages, labels, icons)):
            cls    = ("sb-step sb-done" if i < cur_idx
                      else "sb-step sb-active" if i == cur_idx
                      else "sb-step sb-pending")
            prefix = "✓" if i < cur_idx else "▶" if i == cur_idx else "○"
            st.markdown(
                f'<div class="{cls}"><span style="font-size:1rem">{ico}</span>'
                f'<span>{prefix} {lbl}</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        ordered = st.session_state.ordered_sems
        if ordered:
            st.markdown('<div class="section-label" style="color:#475569">Semester Status</div>',
                        unsafe_allow_html=True)
            for sem in ordered:
                ok    = st.session_state.approvals.get(sem, False)
                files = st.session_state.semester_groups.get(sem, [])
                icon  = "✅" if ok else "🔵"
                st.markdown(
                    f'<div class="sb-sem"><span>{icon}</span>'
                    f'<span style="flex:1;font-size:.8rem">{sem}</span>'
                    f'<span style="font-size:.7rem;color:#475569">{len(files)} file(s)</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.divider()

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
        _health(_ANALYTICS_OK, "Analytics Module")
        _health(_AUTH_OK,      "Auth Module")

        if _ERRORS:
            with st.expander("⚠️ Import Errors"):
                for e in _ERRORS:
                    st.error(e, icon="🚫")

        st.divider()

        with st.expander("⚙️ Settings"):
            st.session_state.db_url = st.text_input(
                "Database URL", value=st.session_state.db_url,
                help="SQLite (dev) or PostgreSQL (prod)"
            )
            st.session_state.academic_year = st.text_input(
                "Academic Year", value=st.session_state.academic_year,
                placeholder="e.g. 2024-2025", help="Leave blank to auto-infer"
            )

        st.markdown(
            '<div style="font-size:.7rem;color:#475569;margin-top:12px">'
            'v2.1 · HEC Pakistan GPA Standard</div>',
            unsafe_allow_html=True,
        )

        # ── Auth: signed-in user strip + logout button ─────────────────────
        if _AUTH_OK:
            render_logout()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 0 — UPLOAD  (file-name independent — content-based detection)
# ──────────────────────────────────────────────────────────────────────────────

def render_upload() -> None:
    st.markdown('<div class="stage-title">📁 Upload Mark Sheet Files</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">'
        'Upload any <code>.xlsx</code> or <code>.csv</code> mark sheet — '
        '<b>any filename is accepted</b>. '
        'Semester and subject are auto-detected from the file\'s own content '
        '(the university metadata rows at the top of each sheet). '
        'If detection fails you can assign them manually on the next step.'
        '</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop mark sheet files here",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    with st.expander("📊 HOD Ground-Truth Student Strength Baseline"):
        cols = st.columns(4)
        for i, (sem, n) in enumerate(EXPECTED_STRENGTH.items()):
            cols[i % 4].metric(sem, f"{n} students")

    if not uploaded:
        st.markdown("""
        <div class="upload-zone">
            <h3>📂 No files uploaded yet</h3>
            <p>Upload one <code>.xlsx</code> or <code>.csv</code> file per subject per semester.<br>
               <b>Any filename is accepted</b> — semester and subject are read from file content.<br>
               If auto-detection cannot find them, you assign manually on the next step.</p>
        </div>""", unsafe_allow_html=True)
        return

    # ── Accept all uploaded files regardless of filename ──────────────────────
    valid_files: dict[str, bytes] = {}
    for uf in uploaded:
        valid_files[uf.name] = uf.read()

    # ── Content-based detection for every file ────────────────────────────────
    auto_sem: dict[str, str | None] = {}
    auto_sub: dict[str, str]        = {}
    detection_source: dict[str, str] = {}   # "content" | "filename" | "none"

    for fname, data in valid_files.items():
        sem_label, subject = extract_meta_from_content(data, fname)

        if sem_label:
            auto_sem[fname]          = sem_label
            detection_source[fname]  = "content"
        else:
            # Secondary: try filename-based detection (handles legacy S{N}-... names)
            fl_sem: str | None = None
            fl_sub: str | None = None
            if _PARSER_OK:
                try:
                    fl_sem, fl_sub = detect_semester_and_subject(fname)
                except Exception:
                    pass
            if fl_sem:
                auto_sem[fname]         = fl_sem
                detection_source[fname] = "filename"
                if not subject and fl_sub:
                    subject = fl_sub
            else:
                auto_sem[fname]         = None     # user must assign manually
                detection_source[fname] = "none"

        auto_sub[fname] = subject or ""

    # ── Summary metrics ────────────────────────────────────────────────────────
    n_detected   = sum(1 for v in auto_sem.values() if v is not None)
    n_undetected = len(valid_files) - n_detected
    sem_groups_preview: dict[str, list[str]] = {}
    for fname, sem in auto_sem.items():
        if sem:
            sem_groups_preview.setdefault(sem, []).append(fname)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files Uploaded",         len(valid_files))
    c2.metric("Semester Auto-Detected", n_detected)
    c3.metric("Needs Manual Assignment", n_undetected,
              delta=f"!{n_undetected}" if n_undetected else None,
              delta_color="inverse" if n_undetected else "off")
    c4.metric("Semesters Found",         len(sem_groups_preview))

    if n_undetected == 0:
        st.markdown(
            '<div class="banner banner-success">✅ Semester detected from content for all '
            'files. Review assignments on the next step.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="banner banner-warning">⚠️ Semester could not be detected in '
            f'<b>{n_undetected}</b> file(s). '
            f'You can assign semesters manually on the next step — the pipeline will not '
            f'proceed until every file has a semester.</div>',
            unsafe_allow_html=True,
        )

    # ── File list ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:16px">Detected Files</div>',
                unsafe_allow_html=True)
    hdr = st.columns([3, 1.1, 2.3, 2.1, 1.3])
    for lbl in ("Filename", "Size", "Semester Detected", "Subject Detected", "Source"):
        hdr[("Filename", "Size", "Semester Detected", "Subject Detected", "Source").index(lbl)]\
            .markdown(
                f'<div style="font-size:.75rem;font-weight:700;color:#64748B;'
                f'text-transform:uppercase;letter-spacing:.8px">{lbl}</div>',
                unsafe_allow_html=True,
            )

    _src_badge = {
        "content" : '<span class="badge badge-clean"  title="Detected from file content">📄 Content</span>',
        "filename": '<span class="badge badge-info"   title="Detected from filename">📁 Filename</span>',
        "none"    : '<span class="badge badge-flagged" title="Manual assignment needed">✏️ Manual</span>',
    }

    for fname, data in valid_files.items():
        c = st.columns([3, 1.1, 2.3, 2.1, 1.3])
        sem = auto_sem.get(fname)
        sub = auto_sub.get(fname) or "—"
        src = detection_source.get(fname, "none")

        c[0].markdown(f'<div class="file-chip">📄 {fname}</div>', unsafe_allow_html=True)
        c[1].markdown(
            f'<span style="font-size:.82rem;color:#64748B">{fmt_size(len(data))}</span>',
            unsafe_allow_html=True,
        )
        if sem:
            c[2].markdown(f'<span class="badge badge-clean">✓ {sem}</span>',
                          unsafe_allow_html=True)
        else:
            c[2].markdown('<span class="badge badge-blocked">⚠ Not Detected</span>',
                          unsafe_allow_html=True)
        c[3].markdown(
            f'<span style="font-size:.82rem;color:#374151">{sub}</span>',
            unsafe_allow_html=True,
        )
        c[4].markdown(_src_badge.get(src, ""), unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    if st.button("Next → Review Assignments", type="primary", use_container_width=True):
        st.session_state.raw_files        = valid_files
        st.session_state.file_assignments = dict(auto_sem)
        st.session_state.file_subjects    = dict(auto_sub)
        st.session_state.detection_source = detection_source
        st.session_state.invalid_files    = []
        st.session_state.stage            = "assign"
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 1 — ASSIGN  (semester is now an editable dropdown, not read-only)
# ──────────────────────────────────────────────────────────────────────────────

def render_assign() -> None:
    st.markdown('<div class="stage-title">🗂️ Review & Confirm Assignments</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">'
        'Review auto-detected semester and subject assignments. '
        'Use the <b>Semester</b> dropdown to correct any wrong detection or to assign '
        'files where detection failed. '
        'Every file must have a semester before you can proceed to HITL review.'
        '</div>',
        unsafe_allow_html=True,
    )

    raw              = st.session_state.raw_files
    # Read stored assignments as the starting values; widgets may override them below
    stored_assigns   = st.session_state.file_assignments   # {fname: sem | None}
    subjects         = dict(st.session_state.file_subjects)
    detection_source = st.session_state.get("detection_source", {})

    # ── Assignment table (one row per file) ───────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-label">File Assignments — Semester (Editable) · Subject (Editable)</div>',
        unsafe_allow_html=True,
    )

    # Collect current widget values into a fresh assigns dict
    assigns: dict[str, str | None] = {}

    for i, (fname, data) in enumerate(raw.items()):
        col_f, col_sz, col_sem, col_sub, col_src = st.columns([2.5, 0.9, 2, 2.5, 1.1])

        col_f.markdown(
            f'<div style="padding-top:8px"><span class="file-chip">📄 {fname}</span></div>',
            unsafe_allow_html=True,
        )
        col_sz.markdown(
            f'<div style="padding-top:10px;font-size:.8rem;color:#64748B">'
            f'{fmt_size(len(data))}</div>',
            unsafe_allow_html=True,
        )

        # Semester selectbox — pre-fill from stored detection, editable by user
        stored_sem = stored_assigns.get(fname)
        sem_idx    = (
            _SEM_OPTIONS.index(stored_sem)
            if stored_sem and stored_sem in _SEM_OPTIONS
            else 0
        )
        selected_sem = col_sem.selectbox(
            label             = f"sem_{fname}",
            options           = _SEM_OPTIONS,
            index             = sem_idx,
            key               = f"sem_sel_{i}_{_safe_key(fname)}",
            label_visibility  = "collapsed",
        )
        assigns[fname] = selected_sem if selected_sem != _SEM_OPTIONS[0] else None

        # Subject text input — editable
        sub_val = col_sub.text_input(
            label            = f"sub_{fname}",
            value            = subjects.get(fname) or "",
            placeholder      = "Subject name",
            label_visibility = "collapsed",
            key              = f"sub_inp_{i}_{_safe_key(fname)}",
        )
        subjects[fname] = sub_val.strip()

        # Detection-source badge (informational)
        src = detection_source.get(fname, "none")
        _src_html = {
            "content" : '<span class="badge badge-clean"  title="Detected from file content">📄 Auto</span>',
            "filename": '<span class="badge badge-info"   title="Detected from filename">📁 Name</span>',
            "none"    : '<span class="badge badge-flagged" title="Manually assigned">✏️ Manual</span>',
        }
        col_src.markdown(
            f'<div style="padding-top:10px">{_src_html.get(src, "")}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Unassigned-file warning ────────────────────────────────────────────────
    unassigned = [f for f, s in assigns.items() if not s]
    if unassigned:
        st.markdown(
            f'<div class="banner banner-warning">⚠️ '
            f'<b>{len(unassigned)}</b> file(s) still need a semester assigned: '
            + ", ".join(f"<code>{f}</code>" for f in unassigned) +
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Assignment summary by semester ─────────────────────────────────────────
    sem_groups: dict[str, list[str]] = {}
    for fname, sem in assigns.items():
        if sem:
            sem_groups.setdefault(sem, []).append(fname)

    if sem_groups:
        st.markdown('<div class="section-label" style="margin-top:8px">Assignment Summary</div>',
                    unsafe_allow_html=True)
        sem_cols = st.columns(min(len(sem_groups), 4))
        for i, (sem, files) in enumerate(
            sorted(sem_groups.items(), key=lambda x: sem_num(x[0]))
        ):
            expected = EXPECTED_STRENGTH.get(sem, 0)
            sem_cols[i % 4].markdown(f"""<div class="kpi-box">
                <div class="kpi-value">{len(files)}</div>
                <div class="kpi-label">{sem}</div>
                <div style="font-size:.75rem;color:#94A3B8;margin-top:4px">
                    {len(files)} subject file(s) · Expected {expected} students
                </div></div>""", unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    bc1, bc2 = st.columns([1, 5])
    with bc1:
        if st.button("← Back", use_container_width=True):
            st.session_state.stage = "upload"
            st.rerun()
    with bc2:
        can_proceed = len(unassigned) == 0 and bool(sem_groups)
        if st.button(
            "Begin HITL Review →",
            type                = "primary",
            use_container_width = True,
            disabled            = not can_proceed,
        ):
            ordered = sorted(sem_groups.keys(), key=sem_num)
            # Persist the user-edited assignments back to session state
            st.session_state.file_assignments = assigns
            st.session_state.file_subjects    = subjects
            st.session_state.semester_groups  = sem_groups
            st.session_state.ordered_sems     = ordered
            st.session_state.approvals        = {}
            st.session_state.sem_file_records = {}
            st.session_state.sem_file_dfs     = {}
            st.session_state.sem_records      = {}
            st.session_state.val_reports      = {}
            st.session_state.calc_results     = None
            st.session_state.final_saved      = False
            st.session_state.stage            = "review"
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 2 — REVIEW  (tab-based — one tab per semester, all visible at once)
# ──────────────────────────────────────────────────────────────────────────────

def render_review() -> None:
    ordered = st.session_state.ordered_sems
    if not ordered:
        st.session_state.stage = "calculate"
        st.rerun()
        return

    approved_count = sum(1 for s in ordered if st.session_state.approvals.get(s, False))
    total          = len(ordered)

    st.markdown('<div class="stage-title">📋 HITL Review — Semester Tabs</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="stage-subtitle">Each tab is one semester. '
        f'Validate each file independently, fix any BLOCKED errors, then approve. '
        f'<b>{approved_count} / {total}</b> semesters approved.</div>',
        unsafe_allow_html=True,
    )

    # Overall progress banner
    if approved_count == total:
        st.markdown(
            '<div class="banner banner-success">✅ All semesters approved! '
            'Click below to run GPA calculation.</div>',
            unsafe_allow_html=True,
        )

    # ── Semester tabs ──────────────────────────────────────────────────────────
    tab_labels = [
        f"✅ {s}" if st.session_state.approvals.get(s, False) else s
        for s in ordered
    ]
    tabs = st.tabs(tab_labels)
    for tab, sem in zip(tabs, ordered):
        with tab:
            _review_tab_panel(sem)

    # ── Bottom navigation ──────────────────────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    bc1, bc2 = st.columns([1, 4])
    with bc1:
        if st.button("← Back", use_container_width=True):
            st.session_state.stage = "assign"
            st.rerun()
    with bc2:
        btn_label = (
            f"Proceed to GPA Calculation ({approved_count}/{total} approved) →"
        )
        if st.button(btn_label, type="primary",
                     disabled=(approved_count < total), use_container_width=True):
            st.session_state.stage = "calculate"
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# REVIEW TAB HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _parse_semester_files(sem: str) -> None:
    """
    Parse every file assigned to *sem* SEPARATELY (not combined).
    Stores results in:
      st.session_state.sem_file_records[sem] = {fname: list[dict]}
      st.session_state.sem_file_dfs[sem]     = {fname: pd.DataFrame}
    """
    groups     = st.session_state.semester_groups.get(sem, [])
    raw        = st.session_state.raw_files
    subj_hints = st.session_state.file_subjects

    file_records: dict[str, list[dict]]    = {}
    file_dfs    : dict[str, pd.DataFrame] = {}

    # Warnings that are purely internal parser diagnostics — never shown to user.
    # "Header row detected at row X; N title row(s) skipped." is operational
    # noise: the parser skips university metadata rows automatically, but
    # showing this message confuses users who think data has been lost.
    _SUPPRESS_PATTERNS = (
        "header row detected",
        "title row(s) skipped",
    )

    def _is_user_facing(warning: str) -> bool:
        wl = warning.lower()
        return not any(pat in wl for pat in _SUPPRESS_PATTERNS)

    for fname in groups:
        fb       = raw.get(fname, b"")
        sub_hint = subj_hints.get(fname)

        if _PARSER_OK:
            try:
                result = parse_file_to_records(fb, fname, subject_hint=sub_hint)
            except Exception as exc:
                result = {
                    "status": "ERROR", "records": [],
                    "warnings": [str(exc)], "file_name": fname,
                }
        else:
            result = _fallback_parse(fb, fname, sub_hint)

        # ── Retry with fallback when primary parser produced no records ────────
        # This fixes files that share the same physical structure as sibling
        # files in the same batch but whose specific column header text scores
        # below the alias threshold (e.g. a subject file with a slightly
        # different heading row layout).
        if not result.get("records") and _PARSER_OK:
            fb_result = _fallback_parse(fb, fname, sub_hint)
            if fb_result.get("records"):
                result = fb_result   # fallback found student rows — use them

        # ── Only surface warnings that are meaningful to the user ─────────────
        user_warnings = [w for w in result.get("warnings", []) if _is_user_facing(w)]

        if result.get("status") == "ERROR" and not result.get("records"):
            for w in user_warnings:
                st.error(f"**{fname}**: {w}", icon="🚫")
            file_records[fname] = []
            file_dfs[fname]     = pd.DataFrame(columns=EDITOR_COLS)
        else:
            for w in user_warnings:
                st.warning(f"**{fname}**: {w}", icon="⚠️")
            recs = result.get("records", [])
            file_records[fname] = recs
            file_dfs[fname]     = records_to_df(recs)

    if "sem_file_records" not in st.session_state:
        st.session_state.sem_file_records = {}
    if "sem_file_dfs" not in st.session_state:
        st.session_state.sem_file_dfs = {}

    st.session_state.sem_file_records[sem] = file_records
    st.session_state.sem_file_dfs[sem]     = file_dfs


def _show_historical_context(sn: int) -> None:
    """
    For Semester 2+, query the DB for existing SemesterGPA rows from
    previous semesters and display them as read-only historical context.
    CGPA calculation will automatically include these via recompute_cgpa().
    """
    if not _CALC_OK:
        return
    try:
        engine = get_engine(st.session_state.db_url)
        with Session(engine) as sess:
            prev_sgpas = sess.execute(
                sa_select(SemesterGPA).where(SemesterGPA.semester < sn)
            ).scalars().all()

        if not prev_sgpas:
            st.markdown(
                f'<div class="hist-banner">ℹ️ <b>Historical Data:</b> No Semester 1–{sn-1} '
                f'data found in the database yet. CGPA for this semester will only include '
                f'the records you are uploading now.</div>',
                unsafe_allow_html=True,
            )
            return

        by_sem: dict[int, list] = {}
        for sg in prev_sgpas:
            by_sem.setdefault(sg.semester, []).append(sg)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-label">📚 Historical DB Data — '
            f'Semesters 1–{sn-1} (read-only · auto-included in CGPA)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:.82rem;color:#0C4A6E;margin-bottom:12px">'
            'These GPA values are already stored in the database from a previous session. '
            'When GPA is calculated for this semester, '
            '<b>recompute_cgpa()</b> will automatically pool them to produce the '
            'cumulative CGPA — no re-upload of earlier semesters needed.</div>',
            unsafe_allow_html=True,
        )

        hist_cols = st.columns(min(len(by_sem), 4))
        for i, (prev_sn, sgpa_list) in enumerate(sorted(by_sem.items())):
            valid_gpas = [sg.gpa for sg in sgpa_list if sg.gpa is not None]
            avg_gpa    = sum(valid_gpas) / len(valid_gpas) if valid_gpas else None
            hist_cols[i % 4].markdown(f"""<div class="kpi-box">
                <div class="kpi-value" style="font-size:1.6rem">
                    {f"{avg_gpa:.2f}" if avg_gpa else "—"}
                </div>
                <div class="kpi-label">Sem {prev_sn} Avg GPA</div>
                <div style="font-size:.72rem;color:#94A3B8;margin-top:4px">
                    {len(sgpa_list)} student record(s) in DB
                </div></div>""", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    except Exception:
        pass


def _review_tab_panel(sem: str) -> None:
    """
    Full review panel for one semester, shown inside its st.tab().

    Layout:
      A · Student Strength Verification
      B · Historical Context  (Semester 2+ only)
      C · Per-File Validation + Editor
      D · Approve button
    """
    is_approved = st.session_state.approvals.get(sem, False)
    sn          = sem_num(sem)

    if is_approved:
        st.markdown(
            f'<div class="banner banner-success">✅ {sem} is approved and ready '
            f'for GPA calculation.</div>',
            unsafe_allow_html=True,
        )
        if st.button(f"🔓 Re-open {sem} for editing", key=f"reopen_{sem}"):
            st.session_state.approvals[sem] = False
            st.rerun()
        return

    files_for_sem = st.session_state.semester_groups.get(sem, [])

    # ── Parse files once (per session) ────────────────────────────────────────
    if sem not in st.session_state.get("sem_file_records", {}):
        with st.spinner(f"Parsing {len(files_for_sem)} file(s) for {sem}…"):
            _parse_semester_files(sem)

    file_records = st.session_state.sem_file_records.get(sem, {})
    file_dfs     = st.session_state.sem_file_dfs.get(sem, {})

    # ── A · Student Strength ───────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">A · Student Strength Verification</div>',
                unsafe_allow_html=True)

    all_rolls: set[str] = set()
    for recs in file_records.values():
        for r in recs:
            roll = str(r.get("roll_no") or "").strip()
            if roll:
                all_rolls.add(roll)

    expected       = EXPECTED_STRENGTH.get(sem, 0)
    distinct_rolls = len(all_rolls)
    total_rows     = sum(len(recs) for recs in file_records.values())

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f"""<div class="kpi-box"><div class="kpi-value">{expected}</div>
        <div class="kpi-label">Expected</div></div>""", unsafe_allow_html=True)
    k2.markdown(f"""<div class="kpi-box"><div class="kpi-value">{distinct_rolls}</div>
        <div class="kpi-label">Distinct Students</div></div>""", unsafe_allow_html=True)
    k3.markdown(f"""<div class="kpi-box"><div class="kpi-value">{len(files_for_sem)}</div>
        <div class="kpi-label">Subject Files</div></div>""", unsafe_allow_html=True)
    k4.markdown(f"""<div class="kpi-box"><div class="kpi-value">{total_rows}</div>
        <div class="kpi-label">Total Mark Rows</div></div>""", unsafe_allow_html=True)

    strength_locked = distinct_rolls < expected
    if strength_locked:
        st.markdown(
            f'<div class="banner banner-critical">🚨 Expected <b>{expected}</b> students '
            f'but found <b>{distinct_rolls}</b> distinct roll numbers. '
            f'Add the missing <b>{expected - distinct_rolls}</b> student(s) in the '
            f'file editors below before approving.</div>',
            unsafe_allow_html=True,
        )
    elif distinct_rolls == expected:
        st.markdown(
            '<div class="banner banner-success">✅ Student count matches expected '
            'strength perfectly.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="banner banner-warning">⚠️ {distinct_rolls - expected} extra '
            f'student(s) vs expected — verify no duplicates.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── B · Historical Context (Semester 2+) ──────────────────────────────────
    if sn > 1:
        _show_historical_context(sn)

    # ── C · Per-File Validation + Editor ──────────────────────────────────────
    # KEY DESIGN: the editor key is computed FIRST so we can call
    # _apply_editor_edits() BEFORE rendering the widget.  Streamlit writes the
    # user's latest edits into st.session_state[key] before re-running the
    # script, so reading it here gives the CURRENT state — not the previous
    # render's state.  This eliminates the one-render lag where filling in a
    # credit_hours cell still shows EC-09 BLOCKED on the same interaction.
    any_blocked = False

    for fname in files_for_sem:
        recs = file_records.get(fname, [])
        df   = file_dfs.get(fname, pd.DataFrame(columns=EDITOR_COLS))

        editor_key = f"editor_{_safe_key(sem)}_{_safe_key(fname)}"

        st.markdown(
            f'<div class="file-section">'
            f'<div class="file-section-header">📄 {fname}</div>',
            unsafe_allow_html=True,
        )

        # Apply any pending editor edits to df BEFORE validation
        current_df = _apply_editor_edits(df, editor_key) if not df.empty else df
        live_recs  = df_to_records(current_df) if not current_df.empty else recs

        if not live_recs:
            st.warning(
                f"No valid student rows found in **{fname}**. "
                f"The file may use column names not yet in the alias list — "
                f"check that subject, roll no, total marks and obtained marks "
                f"columns are present.",
                icon="⚠️",
            )
            any_blocked = True
        elif _VALIDATOR_OK:
            try:
                report = validate_records(live_recs, semester=sem)
                if report.status == "BLOCKED":
                    any_blocked = True
                _render_validation(report)
            except Exception as exc:
                st.error(f"Validation engine error for {fname}: {exc}", icon="🚫")
                any_blocked = True
        else:
            st.error(
                "validation_agent could not be imported — fix the module error in the sidebar.",
                icon="🚫",
            )
            any_blocked = True

        if not df.empty:
            edited_df = st.data_editor(
                df,
                key                = editor_key,
                use_container_width= True,
                num_rows           = "dynamic",
                hide_index         = True,
                column_config={
                    "student_name"  : st.column_config.TextColumn("Student Name", width="medium"),
                    "roll_no"       : st.column_config.TextColumn("Roll No",      width="medium"),
                    "father_name"   : st.column_config.TextColumn("Father Name",  width="medium"),
                    "subject_name"  : st.column_config.TextColumn("Subject",      width="medium"),
                    "total_marks"   : st.column_config.NumberColumn("Total",   min_value=0, format="%.1f", width="small"),
                    "obtained_marks": st.column_config.NumberColumn("Obtained",min_value=0, format="%.1f", width="small"),
                    "credit_hours"  : st.column_config.NumberColumn("Cr. Hrs", min_value=0, step=1, format="%d", width="small"),
                    "department"    : st.column_config.TextColumn("Dept",         width="small"),
                },
            )
            st.session_state.sem_file_dfs[sem][fname] = edited_df
        else:
            st.info("Editor unavailable — file produced no parseable records.", icon="ℹ️")

        st.markdown('</div>', unsafe_allow_html=True)

    # ── D · Approve Button ─────────────────────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    can_approve = not any_blocked and not strength_locked

    b1, b2 = st.columns([3, 1])
    with b1:
        if not can_approve:
            reasons = []
            if any_blocked:     reasons.append("resolve all 🔴 BLOCKED errors")
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
    with b2:
        if st.button(
            f"✅ Approve {sem}",
            type             = "primary",
            disabled         = not can_approve,
            use_container_width= True,
            key              = f"approve_{sem}",
        ):
            _approve_semester(sem)


def _approve_semester(sem: str) -> None:
    """
    Combine all per-file edited records for *sem* into sem_records[sem]
    (used by the calculator), then mark the semester as approved.
    """
    file_dfs = st.session_state.sem_file_dfs.get(sem, {})
    combined: list[dict] = []
    for df in file_dfs.values():
        combined.extend(df_to_records(df))
    st.session_state.sem_records[sem] = combined
    st.session_state.approvals[sem]   = True
    st.rerun()


def _render_validation(report: Any) -> None:
    status_map = {
        "CLEAN"  : ("banner-success", "✅ All records are clean."),
        "FLAGGED": ("banner-warning", "⚠️ Some records need review."),
        "BLOCKED": ("banner-critical","🚫 Critical issues must be fixed before approval."),
    }
    cls, msg = status_map.get(report.status, ("banner-info", ""))
    st.markdown(f"""
    <div class="banner {cls}">
        <div style="flex:1">{msg}</div>
        <div style="display:flex;gap:12px;font-size:.8rem">
            <span class="badge badge-clean">✓ {report.summary.clean} clean</span>
            <span class="badge badge-flagged">⚠ {report.summary.flagged} flagged</span>
            <span class="badge badge-blocked">✗ {report.summary.blocked} blocked</span>
        </div>
    </div>""", unsafe_allow_html=True)

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
                    f"**{r.error_code}**: {r.error_message}", icon="🚫")
    if flagged:
        with st.expander(f"🟡 FLAGGED Warnings — {len(flagged)} (review recommended)"):
            for r in flagged:
                st.warning(
                    f"**Row {r.row_index}** · `{r.roll_no or 'NO ROLL'}` · "
                    f"**{r.error_code}**: {r.error_message}", icon="⚠️")
    if info:
        with st.expander(f"🔵 INFO Notes — {len(info)} (non-credit subjects)"):
            for r in info:
                st.info(
                    f"**Row {r.row_index}** · `{r.roll_no or 'NO ROLL'}` · "
                    f"**{r.error_code}**: {r.error_message}", icon="ℹ️")


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 3 — CALCULATE
# ──────────────────────────────────────────────────────────────────────────────

def render_calculate() -> None:
    st.markdown('<div class="stage-title">⚙️ Running GPA Calculation Engine</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">'
        'Processing approved semesters <b>in order</b> (Semester 1 first). '
        'Each semester\'s SemesterGPA is saved to the DB before the next semester '
        'is processed — so CGPA at each step automatically includes all historical '
        'data (including records from previous upload sessions).</div>',
        unsafe_allow_html=True,
    )

    approved = sorted(
        [s for s in st.session_state.ordered_sems if st.session_state.approvals.get(s)],
        key=sem_num,
    )

    if not approved:
        st.error("No approved semesters. Return to review.", icon="🚫")
        if st.button("← Back to Review"):
            st.session_state.stage = "review"
            st.rerun()
        return

    total_recs = sum(len(st.session_state.sem_records.get(s, [])) for s in approved)
    c1, c2, c3 = st.columns(3)
    c1.metric("Approved Semesters", len(approved))
    c2.metric("Total Records",      total_recs)
    c3.metric("Processing Order",   " → ".join(f"Sem {sem_num(s)}" for s in approved))

    if not _CALC_OK:
        st.error("calculator_agent could not be imported. Fix import errors in sidebar.", icon="🚫")
        return

    agg: dict[str, Any] = {
        "marks_written": 0, "semester_gpas": [], "cgpas": [], "errors": [],
    }

    progress_bar = st.progress(0, text="Starting…")
    status_area  = st.empty()

    for step_i, sem in enumerate(approved):
        sn = sem_num(sem)
        ay = infer_academic_year(sn)

        status_area.markdown(
            f'<div class="banner banner-info">⚙️ Processing <b>{sem}</b> '
            f'(academic year {ay})…</div>',
            unsafe_allow_html=True,
        )

        sem_recs: list[dict] = []
        for rec in st.session_state.sem_records.get(sem, []):
            e = dict(rec)
            e["semester"]      = sn
            e["academic_year"] = ay
            sem_recs.append(e)

        if not sem_recs:
            st.warning(f"No records found for {sem} — skipping.", icon="⚠️")
            progress_bar.progress((step_i + 1) / len(approved))
            continue

        try:
            out = calculator_agent_node({
                "validated_records": sem_recs,
                "semester"         : sn,
                "academic_year"    : ay,
                "db_url"           : st.session_state.db_url,
                "approved_by"      : "HOD",
                "source_file"      : "dashboard_upload",
                "errors"           : [],
            })
            agg["marks_written"] += out.get("marks_written", 0)
            agg["semester_gpas"].extend(out.get("semester_gpas", []))
            for new_cgpa in out.get("cgpas", []):
                agg["cgpas"] = [
                    c for c in agg["cgpas"]
                    if c["student_id"] != new_cgpa["student_id"]
                ]
                agg["cgpas"].append(new_cgpa)
            agg["errors"].extend(out.get("errors", []))
        except Exception as exc:
            st.error(f"Error calculating {sem}: {exc}", icon="🚫")
            agg["errors"].append({"roll_no": None, "reason": f"{sem}: {exc}"})

        progress_bar.progress((step_i + 1) / len(approved))

    status_area.markdown(
        '<div class="banner banner-success">✅ All semesters processed successfully.</div>',
        unsafe_allow_html=True,
    )

    st.session_state.calc_results = agg
    st.session_state.stage        = "results"
    st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# STAGE 4 — RESULTS
# ──────────────────────────────────────────────────────────────────────────────

def render_results() -> None:
    st.markdown('<div class="stage-title">📊 GPA Results & Final Approval</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">Review the per-subject GPA breakdown and the '
        'progressive CGPA table before committing to the database.</div>',
        unsafe_allow_html=True,
    )

    res           = st.session_state.calc_results or {}
    marks_written = res.get("marks_written", 0)
    sem_gpas      = res.get("semester_gpas", [])
    cgpas         = res.get("cgpas", [])
    errors        = res.get("errors", [])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Records Written", marks_written)
    m2.metric("Semester GPAs",   len(sem_gpas))
    m3.metric("Students (CGPA)", len(cgpas))
    m4.metric("Errors",          len(errors),
              delta=f"{len(errors)} errors" if errors else None,
              delta_color="inverse" if errors else "off")

    if errors:
        with st.expander(f"⚠️ Calculation Errors ({len(errors)})", expanded=True):
            for e in errors:
                st.error(f"`{e.get('roll_no','N/A')}` — {e.get('reason','unknown')}", icon="🚫")

    # ── Per-Subject GPA Breakdown ──────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Per-Subject GPA Breakdown</div>',
                unsafe_allow_html=True)

    subj_df = _build_subject_gpa_df()
    if not subj_df.empty:
        st.dataframe(
            subj_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "GPA": st.column_config.NumberColumn("Grade Point", format="%.2f"),
                "%":   st.column_config.NumberColumn("Percentage",  format="%.1f%%"),
            },
        )
        buf_subj = io.StringIO()
        subj_df.to_csv(buf_subj, index=False)
        st.download_button(
            "⬇ Download Per-Subject Report (CSV)",
            data=buf_subj.getvalue(),
            file_name=f"subject_gpa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No subject-level data found in the database for the processed semesters.", icon="ℹ️")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Progressive GPA Table ──────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Progressive Semester GPA & Cumulative CGPA</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:.8rem;color:#64748B;margin-bottom:14px">'
        'CGPA = Σ Quality Points ÷ Σ Credit Hours (HEC Pakistan standard — '
        'never an average of GPA values). Includes all historical semesters from DB.</div>',
        unsafe_allow_html=True,
    )

    approved_sems = [s for s in st.session_state.ordered_sems
                     if st.session_state.approvals.get(s)]
    prog_html = _build_progressive_html(approved_sems)
    st.markdown(prog_html, unsafe_allow_html=True)

    prog_df = _build_progressive_df_for_export(approved_sems)
    if not prog_df.empty:
        buf = io.StringIO()
        prog_df.to_csv(buf, index=False)
        st.download_button(
            "⬇ Download Progressive GPA Report (CSV)",
            data      = buf.getvalue(),
            file_name = f"gpa_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime      = "text/csv",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Final Decision ─────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Final Decision</div>', unsafe_allow_html=True)

    if st.session_state.final_saved:
        st.markdown(
            '<div class="banner banner-success">💾 Results approved and permanently '
            'saved to the database. HOD sign-off recorded.</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 Start New Batch", use_container_width=True):
            _reset()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    col_save, col_reject = st.columns(2)
    with col_save:
        if st.button("💾 Approve & Save Permanently to Database",
                     type="primary", use_container_width=True):
            st.session_state.final_saved = True
            st.success("✅ HOD approval recorded. Results saved.", icon="✅")
            st.rerun()
    with col_reject:
        if st.button("🛑 Report Error / Reject Results",
                     type="secondary", use_container_width=True):
            st.session_state.calc_results = None
            st.session_state.approvals    = {}
            st.session_state.stage        = "review"
            st.warning("Results rejected. Re-review all semesters.", icon="⚠️")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# RESULT BUILDERS
# ──────────────────────────────────────────────────────────────────────────────

def _build_subject_gpa_df() -> pd.DataFrame:
    if not _CALC_OK:
        return pd.DataFrame()
    try:
        engine = get_engine(st.session_state.db_url)
        with Session(engine) as sess:
            marks_list   = sess.execute(sa_select(Mark)).scalars().all()
            students_map = {s.id: s for s in sess.execute(sa_select(Student)).scalars().all()}
            subjects_map = {s.id: s for s in sess.execute(sa_select(Subject)).scalars().all()}

        rows = []
        for m in marks_list:
            stu = students_map.get(m.student_id)
            sub = subjects_map.get(m.subject_id)
            if not stu or not sub:
                continue
            rows.append({
                "Roll No"     : stu.roll_no,
                "Student Name": stu.student_name,
                "Semester"    : m.semester,
                "Subject"     : sub.subject_name,
                "Cr. Hrs"     : sub.credit_hours,
                "Obtained"    : m.obtained_marks,
                "Total"       : m.total_marks,
                "%"           : round(m.percentage, 1),
                "GPA"         : m.grade_point,
                "Quality Pts" : m.quality_points,
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df.sort_values(["Semester", "Roll No", "Subject"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    except Exception:
        return pd.DataFrame()


def _build_progressive_html(approved_sems: list[str]) -> str:
    def _gpa_cell(val: float | None) -> str:
        if val is None:
            return '<td class="gpa-dash">—</td>'
        cls = ("gpa-high" if val >= 3.50 else "gpa-mid" if val >= 2.50 else "gpa-low")
        return f'<td class="{cls}">{val:.2f}</td>'

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

            all_sem_nums = sorted({sg.semester for sg in all_sgpas})
            if not all_sem_nums:
                all_sem_nums = sorted(sem_num(s) for s in approved_sems)

            for stu in students:
                row: dict = {"name": stu.student_name, "roll": stu.roll_no,
                             "dept": stu.department or ""}
                running_qp = running_ch = 0.0
                for sn in all_sem_nums:
                    sg = sgpa_map.get(stu.id, {}).get(sn)
                    row[f"gpa_{sn}"] = sg.gpa if sg else None
                    if sg:
                        running_ch += sg.total_credit_hours or 0
                        running_qp += sg.total_quality_points or 0
                    row[f"cgpa_{sn}"] = (round(running_qp / running_ch, 2)
                                         if running_ch > 0 else None)
                final = cgpa_map.get(stu.id)
                row["final_cgpa"] = final.cgpa if final else None
                row["_sem_nums"]  = all_sem_nums
                rows_data.append(row)
    except Exception:
        all_sem_nums = sorted(sem_num(s) for s in approved_sems)
        res = st.session_state.calc_results or {}
        sgpa_mem: dict[int, dict[int, dict]] = {}
        for sg in res.get("semester_gpas", []):
            sgpa_mem.setdefault(sg["student_id"], {})[sg["semester"]] = sg
        cgpa_mem = {c["student_id"]: c for c in res.get("cgpas", [])}
        for sid in sorted(sgpa_mem):
            row = {"name": f"Student {sid}", "roll": "—", "dept": ""}
            rqp = rch = 0.0
            for sn in all_sem_nums:
                sg  = sgpa_mem.get(sid, {}).get(sn, {})
                gpa = sg.get("gpa")
                row[f"gpa_{sn}"]  = gpa
                rch += sg.get("total_credit_hours", 0) or 0
                rqp += sg.get("total_quality_points", 0) or 0
                row[f"cgpa_{sn}"] = round(rqp / rch, 2) if rch > 0 else None
            fc = cgpa_mem.get(sid, {})
            row["final_cgpa"] = fc.get("cgpa")
            row["_sem_nums"]  = all_sem_nums
            rows_data.append(row)

    if not rows_data:
        return '<div class="banner banner-warning">No student data found in the database.</div>'

    sem_nums = rows_data[0].get("_sem_nums", [])

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

    return (
        f'<div style="overflow-x:auto">'
        f'<table class="gpa-table"><thead>{th}</thead><tbody>{body}</tbody></table>'
        f'</div>'
        f'<div style="margin-top:10px;font-size:.75rem;color:#94A3B8">'
        f'🟢 ≥ 3.50 Excellent &nbsp;|&nbsp; '
        f'🟡 2.50 – 3.49 Good &nbsp;|&nbsp; '
        f'🔴 &lt; 2.50 At Risk</div>'
    )


def _build_progressive_df_for_export(approved_sems: list[str]) -> pd.DataFrame:
    if not _CALC_OK:
        return pd.DataFrame()
    try:
        engine = get_engine(st.session_state.db_url)
        with Session(engine) as sess:
            students  = sess.execute(sa_select(Student)).scalars().all()
            all_sgpas = sess.execute(sa_select(SemesterGPA)).scalars().all()
            all_cgpas = sess.execute(sa_select(CGPA)).scalars().all()

        sgpa_map: dict[int, dict[int, Any]] = {}
        for sg in all_sgpas:
            sgpa_map.setdefault(sg.student_id, {})[sg.semester] = sg
        cgpa_map = {c.student_id: c for c in all_cgpas}

        all_sem_nums = sorted({sg.semester for sg in all_sgpas}
                              or {sem_num(s) for s in approved_sems})

        rows = []
        for stu in students:
            row = {"Student Name": stu.student_name, "Roll No": stu.roll_no,
                   "Department": stu.department or ""}
            rqp = rch = 0.0
            for sn in all_sem_nums:
                sg = sgpa_map.get(stu.id, {}).get(sn)
                row[f"Sem {sn} GPA"] = f"{sg.gpa:.2f}" if (sg and sg.gpa) else "—"
                if sg:
                    rch += sg.total_credit_hours or 0
                    rqp += sg.total_quality_points or 0
                row[f"CGPA (1–{sn})"] = f"{rqp/rch:.2f}" if rch > 0 else "—"
            fc = cgpa_map.get(stu.id)
            row["Final CGPA"] = f"{fc.cgpa:.2f}" if (fc and fc.cgpa) else "—"
            rows.append(row)

        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# FALLBACK PARSER  (when parser_agent cannot be imported)
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
_FOOTER_KWS_FB = frozenset({
    "signature","teacher","head","principal","controller",
    "examiner","lecturer","dean","chairman","coordinator",
    "prepared by","checked by","approved by","seal",
})


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
        return {"file_name": filename, "status": "ERROR", "records": [], "warnings": [str(exc)]}

    alias_words = {w for a_list in _FALIAS.values() for a in a_list for w in a.split()}
    best, score = 0, -1
    for i in range(min(25, len(df_raw))):
        words = {w for v in df_raw.iloc[i].values if pd.notna(v)
                 for w in str(v).strip().lower().split()}
        s = len(words & alias_words)
        if s > score:
            score, best = s, i
    if score < 2:
        best = 0

    buf = _io.BytesIO(file_bytes)
    try:
        df = (pd.read_csv(buf, header=best, dtype=str)
              if ext == ".csv"
              else pd.read_excel(buf, header=best, dtype=str, engine="openpyxl"))
    except Exception:
        return {"file_name": filename, "status": "ERROR", "records": [], "warnings": []}

    df.dropna(how="all", inplace=True)
    end_idx = len(df)
    for i in range(len(df) - 1, -1, -1):
        row = df.iloc[i]
        nn = [str(v).strip() for v in row.values
              if pd.notna(v) and str(v).strip().lower() not in ("","nan","none")]
        if not nn:
            end_idx = i; continue
        if any(kw in " ".join(v.lower() for v in nn) for kw in _FOOTER_KWS_FB):
            end_idx = i; continue
        break
    df = df.iloc[:end_idx].reset_index(drop=True)

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
            if field in ("total_marks","obtained_marks"):
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
# STUDENT SEARCH  (standalone tab — queries DB directly, no pipeline state)
# ──────────────────────────────────────────────────────────────────────────────

def _gpa_colour(val: float | None) -> str:
    """Return the CSS class for a GPA/CGPA value cell."""
    if val is None:
        return "gpa-dash"
    if val >= 3.50:
        return "gpa-high"
    if val >= 2.50:
        return "gpa-mid"
    return "gpa-low"


def _grade_letter(gp: float | None) -> str:
    """Convert a HEC grade point to a letter grade."""
    if gp is None:
        return "—"
    if gp >= 4.00: return "A"
    if gp >= 3.70: return "A-"
    if gp >= 3.30: return "B+"
    if gp >= 3.00: return "B"
    if gp >= 2.70: return "B-"
    if gp >= 2.30: return "C+"
    if gp >= 2.00: return "C"
    if gp >= 1.70: return "C-"
    if gp >= 1.00: return "D"
    return "F"


def render_search() -> None:
    """
    Full-page student search.
    Looks up a roll number in the DB and renders:
      • Student identity card
      • Subject-level marks for every semester (grade, GP, quality pts)
      • Per-semester GPA card row
      • Progressive CGPA timeline
    All in < 1 second (indexed DB query).
    """
    st.markdown('<div class="stage-title">🔍 Student Search</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="stage-subtitle">'
        'Enter a roll number to instantly view every subject mark, '
        'per-semester GPA, and cumulative CGPA for that student.</div>',
        unsafe_allow_html=True,
    )

    if not _CALC_OK:
        st.error(
            "Database module not available — fix the calculator_agent import "
            "error shown in the sidebar.",
            icon="🚫",
        )
        return

    # ── Search bar ─────────────────────────────────────────────────────────────
    col_inp, col_btn = st.columns([5, 1])
    roll_query = col_inp.text_input(
        "Roll Number",
        placeholder="e.g. UoL/CS-F-22/001-BS",
        label_visibility="collapsed",
        key="search_roll_input",
    )
    search_clicked = col_btn.button("Search", type="primary",
                                    use_container_width=True)

    # Also trigger on Enter (input change without button click)
    trigger = search_clicked or bool(roll_query and roll_query !=
                                     st.session_state.get("_last_search_roll"))
    if roll_query:
        st.session_state["_last_search_roll"] = roll_query

    if not roll_query.strip():
        st.markdown("""
        <div class="upload-zone">
            <h3>🎓 Roll Number Search</h3>
            <p>Type a roll number above and press <b>Search</b> (or Enter).<br>
               Results include every subject, semester GPA, and CGPA instantly.</p>
        </div>""", unsafe_allow_html=True)
        return

    # ── DB query ───────────────────────────────────────────────────────────────
    roll_query = roll_query.strip()
    try:
        engine = get_engine(st.session_state.db_url)
        with Session(engine) as sess:
            student = sess.execute(
                sa_select(Student).where(
                    Student.roll_no.ilike(f"%{roll_query}%")
                )
            ).scalars().first()

            if student is None:
                st.markdown(
                    f'<div class="banner banner-warning">⚠️ No student found '
                    f'matching <b>{roll_query}</b>. '
                    f'Check the roll number and try again.</div>',
                    unsafe_allow_html=True,
                )
                return

            # Fetch all marks, subjects, semester GPAs, CGPA for this student
            marks    = sess.execute(
                sa_select(Mark).where(Mark.student_id == student.id)
                .order_by(Mark.semester, Mark.subject_id)
            ).scalars().all()

            subjects_map: dict[int, Subject] = {
                s.id: s for s in sess.execute(sa_select(Subject)).scalars().all()
            }

            sgpas = sess.execute(
                sa_select(SemesterGPA)
                .where(SemesterGPA.student_id == student.id)
                .order_by(SemesterGPA.semester)
            ).scalars().all()

            cgpa_row = sess.execute(
                sa_select(CGPA).where(CGPA.student_id == student.id)
            ).scalar_one_or_none()

    except Exception as exc:
        st.error(f"Database error: {exc}", icon="🚫")
        return

    # ── Identity card ──────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    id1, id2, id3, id4 = st.columns(4)
    id1.markdown(f"""<div class="kpi-box">
        <div class="kpi-value" style="font-size:1.3rem">{student.student_name}</div>
        <div class="kpi-label">Student Name</div></div>""",
        unsafe_allow_html=True)
    id2.markdown(f"""<div class="kpi-box">
        <div class="kpi-value" style="font-size:1.1rem">{student.roll_no}</div>
        <div class="kpi-label">Roll Number</div></div>""",
        unsafe_allow_html=True)
    id3.markdown(f"""<div class="kpi-box">
        <div class="kpi-value" style="font-size:1.3rem">{student.father_name or "—"}</div>
        <div class="kpi-label">Father Name</div></div>""",
        unsafe_allow_html=True)
    id4.markdown(f"""<div class="kpi-box">
        <div class="kpi-value" style="font-size:1.3rem">{student.department or "—"}</div>
        <div class="kpi-label">Department</div></div>""",
        unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if not marks:
        st.info("No marks recorded yet for this student.", icon="ℹ️")
        return

    # Group marks by semester
    by_sem: dict[int, list[Mark]] = {}
    for m in marks:
        by_sem.setdefault(m.semester, []).append(m)

    sgpa_by_sem: dict[int, SemesterGPA] = {s.semester: s for s in sgpas}
    all_sems = sorted(by_sem.keys())

    # ── Running CGPA computation (cumulative, HEC standard) ────────────────────
    running_qp  = 0.0
    running_ch  = 0.0
    cgpa_by_sem: dict[int, float | None] = {}
    for sn in all_sems:
        sg = sgpa_by_sem.get(sn)
        if sg:
            running_ch += sg.total_credit_hours or 0.0
            running_qp += sg.total_quality_points or 0.0
        cgpa_by_sem[sn] = round(running_qp / running_ch, 2) if running_ch > 0 else None

    # ── Per-semester subject tables ────────────────────────────────────────────
    for sn in all_sems:
        sem_marks = by_sem[sn]
        sg        = sgpa_by_sem.get(sn)
        cgpa_val  = cgpa_by_sem.get(sn)

        st.markdown(
            f'<div style="font-size:1rem;font-weight:700;color:#0F2444;'
            f'margin:18px 0 6px 0;display:flex;align-items:center;gap:10px">'
            f'📚 Semester {sn}'
            f'<span class="badge badge-info">Academic Year: '
            f'{sem_marks[0].academic_year}</span></div>',
            unsafe_allow_html=True,
        )

        # Subject-level table
        rows_html = ""
        for m in sem_marks:
            sub  = subjects_map.get(m.subject_id)
            sname = sub.subject_name if sub else f"Subject {m.subject_id}"
            ch   = sub.credit_hours if sub else 0
            nc   = "🔵" if m.is_non_credit else ""
            gp_cls = _gpa_colour(m.grade_point)
            rows_html += (
                f"<tr>"
                f'<td style="text-align:left;font-weight:600;color:#0F2444">'
                f'{sname} {nc}</td>'
                f'<td>{ch}</td>'
                f'<td>{m.total_marks:.0f}</td>'
                f'<td>{m.obtained_marks:.0f}</td>'
                f'<td>{m.percentage:.1f}%</td>'
                f'<td><span class="{gp_cls}" style="padding:3px 10px;'
                f'border-radius:6px;font-weight:700">'
                f'{m.grade_point:.2f}</span></td>'
                f'<td style="font-weight:600">{_grade_letter(m.grade_point)}</td>'
                f'<td>{m.quality_points:.2f}</td>'
                f'</tr>'
            )

        subj_table = f"""
        <div style="overflow-x:auto;margin-bottom:8px">
        <table class="gpa-table">
          <thead><tr>
            <th style="text-align:left">Subject</th>
            <th>Cr. Hrs</th><th>Total</th><th>Obtained</th>
            <th>%</th><th>Grade Point</th><th>Grade</th><th>Quality Pts</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table></div>"""
        st.markdown(subj_table, unsafe_allow_html=True)

        # Semester summary strip
        gpa_val  = sg.gpa if sg else None
        ch_total = sg.total_credit_hours if sg else 0
        qp_total = sg.total_quality_points if sg else 0
        gpa_cls  = _gpa_colour(gpa_val)
        cgpa_cls = _gpa_colour(cgpa_val)

        s1, s2, s3, s4 = st.columns(4)
        s1.markdown(f"""<div class="kpi-box" style="padding:12px 16px">
            <div class="kpi-value" style="font-size:1.4rem">{ch_total:.0f}</div>
            <div class="kpi-label">Credit Hours</div></div>""",
            unsafe_allow_html=True)
        s2.markdown(f"""<div class="kpi-box" style="padding:12px 16px">
            <div class="kpi-value" style="font-size:1.4rem">{qp_total:.2f}</div>
            <div class="kpi-label">Quality Points</div></div>""",
            unsafe_allow_html=True)
        s3.markdown(f"""<div class="kpi-box" style="padding:12px 16px">
            <div class="kpi-value {gpa_cls}" style="font-size:1.6rem;padding:4px 12px;border-radius:8px">
            {f"{gpa_val:.2f}" if gpa_val is not None else "—"}</div>
            <div class="kpi-label">Semester GPA</div></div>""",
            unsafe_allow_html=True)
        s4.markdown(f"""<div class="kpi-box" style="padding:12px 16px">
            <div class="kpi-value {cgpa_cls}" style="font-size:1.6rem;padding:4px 12px;border-radius:8px">
            {f"{cgpa_val:.2f}" if cgpa_val is not None else "—"}</div>
            <div class="kpi-label">CGPA after Sem {sn}</div></div>""",
            unsafe_allow_html=True)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── CGPA Timeline ──────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">📈 Cumulative GPA Timeline</div>',
                unsafe_allow_html=True)

    # Build timeline table
    hdr_cells = "".join(f"<th>Sem {sn}</th>" for sn in all_sems)
    gpa_cells = "".join(
        f'<td><span class="{_gpa_colour(sgpa_by_sem.get(sn, None) and sgpa_by_sem[sn].gpa)}"'
        f' style="padding:3px 10px;border-radius:6px;font-weight:700">'
        f'{f"{sgpa_by_sem[sn].gpa:.2f}" if sn in sgpa_by_sem and sgpa_by_sem[sn].gpa is not None else "—"}'
        f'</span></td>'
        for sn in all_sems
    )
    cgpa_cells = "".join(
        f'<td><span class="{_gpa_colour(cgpa_by_sem.get(sn))}"'
        f' style="padding:3px 10px;border-radius:6px;font-weight:700">'
        f'{f"{cgpa_by_sem[sn]:.2f}" if cgpa_by_sem.get(sn) is not None else "—"}'
        f'</span></td>'
        for sn in all_sems
    )

    final_cgpa = cgpa_row.cgpa if cgpa_row else None
    fc_cls     = _gpa_colour(final_cgpa)

    timeline_html = f"""
    <div style="overflow-x:auto">
    <table class="gpa-table">
      <thead><tr>
        <th style="text-align:left">Metric</th>
        {hdr_cells}
        <th>Final CGPA</th>
      </tr></thead>
      <tbody>
        <tr>
          <td style="text-align:left;font-weight:600;color:#0F2444">Semester GPA</td>
          {gpa_cells}
          <td class="gpa-dash">—</td>
        </tr>
        <tr>
          <td style="text-align:left;font-weight:600;color:#0F2444">Cumulative CGPA</td>
          {cgpa_cells}
          <td><span class="{fc_cls}" style="padding:3px 12px;border-radius:6px;font-weight:800">
            {f"{final_cgpa:.2f}" if final_cgpa is not None else "—"}
          </span></td>
        </tr>
      </tbody>
    </table></div>
    <div style="margin-top:10px;font-size:.75rem;color:#94A3B8">
      🟢 ≥ 3.50 Excellent &nbsp;|&nbsp;
      🟡 2.50–3.49 Good &nbsp;|&nbsp;
      🔴 &lt; 2.50 At Risk &nbsp;|&nbsp;
      🔵 Non-credit subject (excluded from GPA)
    </div>"""
    st.markdown(timeline_html, unsafe_allow_html=True)

    # ── Final CGPA hero ────────────────────────────────────────────────────────
    if final_cgpa is not None:
        label = ("Excellent 🌟" if final_cgpa >= 3.50
                 else "Good 👍" if final_cgpa >= 2.50
                 else "At Risk ⚠️")
        st.markdown(
            f'<div style="text-align:center;margin-top:18px">'
            f'<div style="font-size:3rem;font-weight:900;color:#0F2444">'
            f'{final_cgpa:.2f}</div>'
            f'<div style="font-size:1rem;color:#64748B;font-weight:600">'
            f'Final CGPA · {label}</div>'
            f'<div style="font-size:.8rem;color:#94A3B8;margin-top:4px">'
            f'{len(all_sems)} semester(s) · '
            f'{sum(sg.total_credit_hours for sg in sgpas):.0f} total credit hours · '
            f'HEC Pakistan Standard</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# RESET
# ──────────────────────────────────────────────────────────────────────────────


# ==============================================================================
# TRANSCRIPT TAB — Automated PDF Transcript Generation
# ==============================================================================

def _apply_sem_filter(student_data: dict, up_to_sem: int) -> dict:
    """
    Return a copy of student_data restricted to semesters 1..up_to_sem.
    up_to_sem == 0  → no filter, return full data unchanged.
    CGPA is recalculated for the filtered subset (HEC: Σ QP / Σ CH).
    """
    if not up_to_sem:
        return student_data

    filtered_sems = [
        s for s in student_data.get("semesters", [])
        if s["number"] <= up_to_sem
    ]
    total_ch = sum(s.get("total_credit_hours",   0) for s in filtered_sems)
    total_qp = sum(s.get("total_quality_points", 0) for s in filtered_sems)
    new_cgpa = round(total_qp / total_ch, 2) if total_ch > 0 else None

    out = dict(student_data)
    out["semesters"]           = filtered_sems
    out["cgpa"]                = new_cgpa
    out["total_credit_hours"]  = total_ch
    out["semesters_completed"] = len(filtered_sems)
    return out


def _transcript_mode_toggle() -> str:
    """Render mode toggle buttons; return current mode string."""
    current = st.session_state.get("transcript_mode", "hitl")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(
            "Mode A — Human-in-the-Loop Review",
            use_container_width=True,
            type="primary" if current == "hitl" else "secondary",
            key="tr_mode_hitl",
        ):
            st.session_state["transcript_mode"] = "hitl"
            st.rerun()
    with col_b:
        if st.button(
            "Mode B — Fast-Track Bypass (Bulk / Print)",
            use_container_width=True,
            type="primary" if current == "fast_track" else "secondary",
            key="tr_mode_fast",
        ):
            st.session_state["transcript_mode"] = "fast_track"
            st.rerun()
    return st.session_state.get("transcript_mode", "hitl")


def _embed_pdf_html(pdf_bytes: bytes, height: int = 700) -> str:
    """
    Embed a PDF using a data URI in iframe src — works in Chrome, Firefox, Edge.
    Edge blocks data: URI navigation in window.open() but allows it in <iframe src>.
    """
    import base64
    b64 = base64.b64encode(pdf_bytes).decode()
    return (
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="{height}" '
        f'style="border:1px solid #E2E8F0;border-radius:8px;display:block">'
        f'</iframe>'
    )


def _print_button_html(pdf_bytes: bytes) -> str:
    """
    Print button using Blob + URL.createObjectURL() — Edge-compatible.
    Edge blocks window.open('data:...') but allows window.open(blobUrl).
    """
    import base64
    b64 = base64.b64encode(pdf_bytes).decode()
    js = (
        "var b=atob('" + b64 + "');"
        "var u=new Uint8Array(b.length);"
        "for(var i=0;i<b.length;i++){u[i]=b.charCodeAt(i);}"
        "var blob=new Blob([u],{type:'application/pdf'});"
        "var url=URL.createObjectURL(blob);"
        "var w=window.open(url,'_blank');"
        "w.onload=function(){w.print();URL.revokeObjectURL(url);};"
    )
    return (
        f'<button onclick="{js}" '
        'style="padding:8px 20px;background:#0F2444;color:white;border:none;'
        'border-radius:6px;cursor:pointer;font-size:.88rem;font-weight:600;'
        'margin-top:8px">'
        "🖨️ Print This Transcript"
        "</button>"
    )


def render_transcript() -> None:
    """
    Transcript tab — Mode A (HITL) and Mode B (Fast-Track / print loop).

    Reads from st.session_state:
        transcript_rolls_raw, transcript_fetched, transcript_approvals,
        transcript_mode, transcript_print_idx, transcript_print_active
    """
    import streamlit.components.v1 as components

    st.markdown(
        '<div class="stage-title">Automated PDF Transcript Generation</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="stage-subtitle">'
        "Enter one or more roll numbers. The system fetches every subject, "
        "semester GPA, and CGPA <b>in parallel</b> and generates an "
        "official-style PDF transcript per student — no manual copy-pasting.</div>",
        unsafe_allow_html=True,
    )

    if not _TRANSCRIPT_OK:
        st.error(
            "transcript_generator could not be imported. "
            "Place src/dashboard/transcript_generator.py in the project "
            "and run: pip install reportlab",
            icon="🚫",
        )
        return

    if not _CALC_OK:
        st.error(
            "Database module unavailable — fix the calculator_agent import "
            "error shown in the sidebar.",
            icon="🚫",
        )
        return

    # ── Mode toggle ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Operation Mode</div>', unsafe_allow_html=True)
    mode = _transcript_mode_toggle()
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    mode_desc = {
        "hitl": (
            "banner-info",
            "<b>Mode A — Human-in-the-Loop:</b> Fetches all students, shows a "
            "summary card per student for administrator review, then unlocks "
            "individual PDF downloads and print after explicit approval.",
        ),
        "fast_track": (
            "banner-warning",
            "<b>Mode B — Fast-Track Bypass:</b> Skips the approval step. "
            "All transcripts are generated immediately for bulk ZIP download "
            "or sequential printer-loop printing. Use during peak registration.",
        ),
    }
    cls, desc = mode_desc.get(mode, mode_desc["hitl"])
    st.markdown(
        f'<div class="banner {cls}" style="margin:4px 0 18px 0">{desc}</div>',
        unsafe_allow_html=True,
    )

    # ── Input form ────────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Roll Number Input (one per line)</div>',
                unsafe_allow_html=True)

    rolls_raw = st.text_area(
        "Roll Numbers",
        value=st.session_state.get("transcript_rolls_raw", ""),
        height=110,
        placeholder=(
            "UOL/CS-F-2022/001-BSCS\n"
            "UOL/CS-F-2022/002-BSCS\n"
            "UOL/CS-F-2022/003-BSCS"
        ),
        key="tr_rolls_textarea",
        label_visibility="collapsed",
    )
    st.session_state["transcript_rolls_raw"] = rolls_raw

    roll_nos = [r.strip() for r in rolls_raw.splitlines() if r.strip()]
    n_input  = len(roll_nos)

    inp_col, btn_col = st.columns([3, 1])
    inp_col.markdown(
        f'<div style="font-size:.82rem;color:#64748B;margin-top:6px">'
        f"{n_input} roll number(s) entered. Fetching runs in parallel "
        f"(up to 8 concurrent DB threads).</div>",
        unsafe_allow_html=True,
    )

    fetch_label = (
        "Fetch & Generate All"
        if mode == "fast_track"
        else "Fetch Student Data"
    )
    fetch_clicked = btn_col.button(
        fetch_label,
        type="primary",
        use_container_width=True,
        disabled=(n_input == 0),
        key="tr_fetch_btn",
    )

    # ── Semester range filter ─────────────────────────────────────────────────
    st.markdown(
        '<div style="margin-top:12px"><div class="section-label">'
        "Transcript Up To Semester (e.g. select Semester 4 to get Semesters 1–4)"
        "</div></div>",
        unsafe_allow_html=True,
    )
    _upto_options = ["All semesters (full transcript)"] + [
        f"Up to Semester {n}" for n in range(1, 9)
    ]
    _saved_upto = st.session_state.get("transcript_sem_upto", 0)
    _saved_idx  = _saved_upto if 0 <= _saved_upto <= 8 else 0

    _upto_sel = st.selectbox(
        "Include semesters up to",
        options=_upto_options,
        index=_saved_idx,
        key="tr_sem_upto_widget",
        label_visibility="collapsed",
        help=(
            "A university transcript always starts from Semester 1. "
            "Choose 'Up to Semester 4' to generate a transcript covering "
            "Semesters 1 through 4. Leave as 'All semesters' for a full transcript."
        ),
    )
    _upto_val = 0 if _upto_sel.startswith("All") else int(_upto_sel.split()[-1])
    st.session_state["transcript_sem_upto"] = _upto_val

    if _upto_val:
        st.markdown(
            f'<div class="banner banner-info" style="padding:8px 14px;margin:6px 0 0 0">'
            f"PDF will cover <b>Semester 1 through Semester {_upto_val}</b>. "
            f"CGPA is recalculated for this cumulative range only.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:.8rem;color:#94A3B8;margin-top:4px">'
            "All semesters included — full degree transcript.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Parallel fetch ────────────────────────────────────────────────────────
    if fetch_clicked and roll_nos:
        st.session_state["transcript_approvals"]    = {}
        st.session_state["transcript_print_idx"]    = 0
        st.session_state["transcript_print_active"] = False

        with st.spinner(f"Querying database for {n_input} student(s) in parallel…"):
            results = fetch_multiple_transcripts(
                roll_nos,
                db_url=st.session_state.get("db_url", DEFAULT_DB),
                max_workers=min(n_input, 8),
            )
        st.session_state["transcript_fetched"] = results

        found     = sum(1 for v in results.values() if v and "_error" not in v)
        not_found = n_input - found
        if not_found:
            st.warning(
                f"{not_found} roll number(s) not found in the database. "
                "Ensure records have been saved via the GPA Pipeline tab.",
                icon="⚠️",
            )
        else:
            st.success(f"All {found} student(s) fetched successfully.", icon="✅")

    # ── Retrieve fetched data ─────────────────────────────────────────────────
    fetched: dict = st.session_state.get("transcript_fetched", {})
    if not fetched:
        st.markdown(
            '<div class="upload-zone" style="margin-top:16px">'
            "<h3>No students fetched yet</h3>"
            "<p>Enter roll numbers above and click <b>Fetch Student Data</b>.<br>"
            "Results appear here instantly after the parallel DB query.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    valid_results = {rn: d for rn, d in fetched.items() if d and "_error" not in d}
    error_results = {rn: d for rn, d in fetched.items() if not d or "_error" in (d or {})}

    if not valid_results:
        st.error("None of the entered roll numbers were found in the database.", icon="🚫")
        return

    # Apply semester filter to every result before display / PDF generation
    _upto_sem = st.session_state.get("transcript_sem_upto", 0)
    valid_results = {
        rn: _apply_sem_filter(d, _upto_sem)
        for rn, d in valid_results.items()
    }

    # ── KPI strip ─────────────────────────────────────────────────────────────
    approved_count = sum(
        1 for rn in valid_results
        if st.session_state.get("transcript_approvals", {}).get(rn, False)
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(
        f'<div class="kpi-box"><div class="kpi-value">{n_input}</div>'
        '<div class="kpi-label">Requested</div></div>',
        unsafe_allow_html=True,
    )
    k2.markdown(
        f'<div class="kpi-box"><div class="kpi-value">{len(valid_results)}</div>'
        '<div class="kpi-label">Found in DB</div></div>',
        unsafe_allow_html=True,
    )
    k3.markdown(
        f'<div class="kpi-box"><div class="kpi-value">{len(error_results)}</div>'
        '<div class="kpi-label">Not Found</div></div>',
        unsafe_allow_html=True,
    )
    k4.markdown(
        f'<div class="kpi-box"><div class="kpi-value">'
        f'{"N/A" if mode == "fast_track" else approved_count}</div>'
        '<div class="kpi-label">Approved</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # =========================================================================
    # MODE A — HITL Review
    # =========================================================================
    if mode == "hitl":
        st.markdown(
            '<div class="section-label">Student Transcript Review Cards</div>',
            unsafe_allow_html=True,
        )

        for rn, data in valid_results.items():
            safe_rn      = rn.replace("/", "_").replace("\\", "_")
            is_approved  = st.session_state.get("transcript_approvals", {}).get(rn, False)
            cgpa_val     = data.get("cgpa")
            cgpa_str     = f"{cgpa_val:.2f}" if cgpa_val is not None else "—"
            n_sems       = len(data.get("semesters", []))
            gpa_badge    = (
                "badge-clean"   if (cgpa_val or 0) >= 3.50 else
                "badge-flagged" if (cgpa_val or 0) >= 2.50 else
                "badge-blocked"
            )

            with st.container():
                st.markdown('<div class="file-section">', unsafe_allow_html=True)

                hdr_c, badge_c, act_c = st.columns([5, 2, 2])
                hdr_c.markdown(
                    f'<div class="file-section-header">'
                    f'  {data["student_name"]}'
                    f'  &nbsp;<span class="badge badge-info">{rn}</span>'
                    f'  &nbsp;<span class="badge {gpa_badge}">CGPA {cgpa_str}</span>'
                    f'  &nbsp;<span style="font-size:.75rem;color:#64748B">'
                    f"    {n_sems} semesters &middot; {data.get('department','—')}"
                    f"  </span></div>",
                    unsafe_allow_html=True,
                )

                if is_approved:
                    badge_c.markdown(
                        '<span class="badge badge-clean" '
                        'style="margin-top:10px;display:inline-block">Approved</span>',
                        unsafe_allow_html=True,
                    )

                    # Generate PDF once for this render cycle
                    try:
                        pdf_bytes = generate_transcript_pdf(data, logo_path=_UOL_LOGO)
                        act_c.download_button(
                            "Download PDF",
                            data=pdf_bytes,
                            file_name=f"{safe_rn}_transcript.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"dl_approved_{safe_rn}",
                        )
                    except Exception as exc:
                        act_c.error(f"PDF error: {exc}", icon="🚫")

                    # Preview + print (inside expander to save screen space)
                    with st.expander("Preview & Print This Transcript", expanded=False):
                        try:
                            pdf_bytes = generate_transcript_pdf(data, logo_path=_UOL_LOGO)
                            components.html(
                                _embed_pdf_html(pdf_bytes, height=680)
                                + _print_button_html(pdf_bytes),
                                height=760,
                            )
                        except Exception as exc:
                            st.error(f"Preview error: {exc}", icon="🚫")

                    # Allow revoking approval
                    if st.button(
                        f"Revoke approval — {rn}",
                        key=f"revoke_{safe_rn}",
                        use_container_width=False,
                    ):
                        st.session_state.setdefault("transcript_approvals", {})[rn] = False
                        st.rerun()

                else:
                    # Show semester summary + approve button
                    with st.expander("View Semester Details", expanded=False):
                        for sem in data.get("semesters", []):
                            gpa_s = sem.get("gpa")
                            st.markdown(
                                f"**Semester {sem['number']}** — "
                                f"GPA: `{f'{gpa_s:.2f}' if gpa_s is not None else '—'}` | "
                                f"Subjects: {len(sem['subjects'])} | "
                                f"AY: {sem['academic_year']}",
                                unsafe_allow_html=False,
                            )

                    if badge_c.button(
                        "Approve",
                        key=f"approve_tr_{safe_rn}",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state.setdefault("transcript_approvals", {})[rn] = True
                        st.rerun()

                    act_c.markdown(
                        '<span style="font-size:.8rem;color:#94A3B8">'
                        "Pending approval</span>",
                        unsafe_allow_html=True,
                    )

                st.markdown("</div>", unsafe_allow_html=True)

        # Bulk ZIP for approved subset
        if approved_count > 0:
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="banner banner-success">'
                f"{approved_count} transcript(s) approved. "
                "Download individually above, or grab them all as a ZIP."
                "</div>",
                unsafe_allow_html=True,
            )
            approved_data = {
                rn: d
                for rn, d in valid_results.items()
                if st.session_state.get("transcript_approvals", {}).get(rn, False)
            }
            col_zip, _ = st.columns([2, 3])

            # Step 1 — Generate button: creates the ZIP and caches it
            if col_zip.button(
                "Download All Approved as ZIP",
                type="primary",
                use_container_width=True,
                key="bulk_dl_hitl",
            ):
                with st.spinner("Generating ZIP archive…"):
                    st.session_state["_bulk_zip_hitl_bytes"] = generate_bulk_zip(
                        approved_data, logo_path=_UOL_LOGO
                    )
                    st.session_state["_bulk_zip_hitl_count"] = approved_count

            # Step 2 — Download button: always visible once ZIP is cached
            if st.session_state.get("_bulk_zip_hitl_bytes"):
                n_zip = st.session_state.get("_bulk_zip_hitl_count", approved_count)
                st.download_button(
                    f"⬇ Save ZIP ({n_zip} transcript{'s' if n_zip != 1 else ''})",
                    data=st.session_state["_bulk_zip_hitl_bytes"],
                    file_name=f"transcripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="save_zip_hitl",
                )

    # =========================================================================
    # MODE B — Fast-Track Bypass
    # =========================================================================
    else:
        st.markdown(
            '<div class="banner banner-warning">'
            "Fast-Track mode active — approval step bypassed. "
            "All fetched students are ready for immediate download or printing."
            "</div>",
            unsafe_allow_html=True,
        )

        # Compact student list
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-label">Students Ready for Transcript Generation</div>',
            unsafe_allow_html=True,
        )
        for rn, data in valid_results.items():
            cgpa_val = data.get("cgpa")
            cgpa_str = f"{cgpa_val:.2f}" if cgpa_val is not None else "—"
            gpa_badge = (
                "badge-clean"   if (cgpa_val or 0) >= 3.50 else
                "badge-flagged" if (cgpa_val or 0) >= 2.50 else
                "badge-blocked"
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;'
                f'padding:6px 0;border-bottom:1px solid #F1F5F9;">'
                f'<span class="file-chip">{data["student_name"]}</span>'
                f'<span class="badge badge-info">{rn}</span>'
                f'<span class="badge {gpa_badge}">CGPA {cgpa_str}</span>'
                f'<span style="font-size:.78rem;color:#64748B">'
                f'{len(data.get("semesters",[]))} semesters &middot; '
                f'{data.get("department","—")}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

        # ── Two columns: Bulk ZIP   |   Print Queue ───────────────────────
        zip_col, print_col = st.columns(2)

        # ── Bulk ZIP ──────────────────────────────────────────────────────
        with zip_col:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-label">Bulk ZIP Download</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="font-size:.84rem;color:#64748B;margin-bottom:10px">'
                "Packages every transcript as an individually named PDF inside "
                "one ZIP archive. Ideal for archiving or email delivery."
                "</div>",
                unsafe_allow_html=True,
            )
            # Step 1 — Generate button: creates the ZIP and caches it
            if st.button(
                f"Generate ZIP — {len(valid_results)} Transcripts",
                type="primary",
                use_container_width=True,
                key="zip_fast_btn",
            ):
                with st.spinner(f"Generating {len(valid_results)} PDF(s)…"):
                    st.session_state["_bulk_zip_fast_bytes"] = generate_bulk_zip(
                        valid_results, logo_path=_UOL_LOGO
                    )
                    st.session_state["_bulk_zip_fast_count"] = len(valid_results)

            # Step 2 — Download button: always visible once ZIP is cached
            if st.session_state.get("_bulk_zip_fast_bytes"):
                n_zip = st.session_state.get("_bulk_zip_fast_count", len(valid_results))
                st.download_button(
                    f"⬇ Save ZIP ({n_zip} transcript{'s' if n_zip != 1 else ''})",
                    data=st.session_state["_bulk_zip_fast_bytes"],
                    file_name=f"transcripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="save_zip_fast",
                )
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Sequential Printer Loop ───────────────────────────────────────
        with print_col:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-label">Sequential Printer Loop</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="font-size:.84rem;color:#64748B;margin-bottom:10px">'
                "Opens each transcript one at a time and triggers the system "
                "print dialog. Click <b>Print &amp; Next</b> to advance through "
                "the queue — no manual file searching required."
                "</div>",
                unsafe_allow_html=True,
            )

            all_keys  = list(valid_results.keys())
            print_idx = st.session_state.get("transcript_print_idx", 0)
            is_active = st.session_state.get("transcript_print_active", False)

            if not is_active and print_idx == 0:
                if st.button(
                    "Start Print Queue",
                    type="primary",
                    use_container_width=True,
                    key="start_print_q",
                ):
                    st.session_state["transcript_print_active"] = True
                    st.session_state["transcript_print_idx"]    = 0
                    st.rerun()
            else:
                total = len(all_keys)
                frac  = min(print_idx, total) / max(total, 1)
                st.progress(frac, text=f"Student {min(print_idx+1,total)} / {total}")

                if print_idx < total:
                    cur_rn   = all_keys[print_idx]
                    cur_data = valid_results[cur_rn]
                    st.markdown(
                        f"**Now printing:** {cur_data['student_name']} "
                        f"(`{cur_rn}`)",
                    )
                    try:
                        pdf_bytes = generate_transcript_pdf(cur_data, logo_path=_UOL_LOGO)
                        components.html(
                            _embed_pdf_html(pdf_bytes, height=480)
                            + _print_button_html(pdf_bytes),
                            height=550,
                        )
                    except Exception as exc:
                        st.error(f"PDF error: {exc}", icon="🚫")

                    nav1, nav2 = st.columns(2)
                    with nav1:
                        if st.button(
                            "Print & Next",
                            type="primary",
                            use_container_width=True,
                            key=f"next_p_{print_idx}",
                        ):
                            st.session_state["transcript_print_idx"] = print_idx + 1
                            st.rerun()
                    with nav2:
                        if st.button(
                            "Stop Queue",
                            use_container_width=True,
                            key="stop_print_q",
                        ):
                            st.session_state["transcript_print_active"] = False
                            st.session_state["transcript_print_idx"]    = 0
                            st.rerun()
                else:
                    st.success(
                        f"Print queue complete — {total} transcript(s) sent.",
                        icon="",
                    )
                    if st.button(
                        "Restart Queue",
                        use_container_width=True,
                        key="restart_print_q",
                    ):
                        st.session_state["transcript_print_idx"]    = 0
                        st.session_state["transcript_print_active"] = False
                        st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # ── Not-found report ──────────────────────────────────────────────────────
    if error_results:
        with st.expander(
            f"{len(error_results)} Roll Number(s) Not Found / Error", expanded=False
        ):
            for rn, d in error_results.items():
                err = (d or {}).get("_error", "Not found in database")
                st.warning(f"`{rn}` — {err}", icon="⚠️")


def _reset() -> None:
    for k in [
        "stage", "raw_files", "file_assignments", "file_subjects",
        "detection_source",
        "semester_groups", "sem_file_records", "sem_file_dfs",
        "sem_records", "approvals", "val_reports",
        "ordered_sems", "calc_results", "final_saved", "invalid_files",
    ]:
        st.session_state.pop(k, None)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _init()

    # ── Auth gate ─────────────────────────────────────────────────────────────
    # Enforces login before anything renders.
    # If auth module failed to import, falls through with full access (dev mode).
    if _AUTH_OK:
        if not get_role():
            render_login()
            st.stop()

    render_sidebar()

    role = get_role() if _AUTH_OK else "Coordinator"

    # ── HOD: read-only — Pipeline tab hidden entirely ─────────────────────────
    if role == "HOD":
        search_tab, analytics_tab, transcript_tab = st.tabs(
            ["🔍 Student Search", "📊 Analytics", "📄 Transcripts"]
        )
        with search_tab:
            render_search()
        with analytics_tab:
            if _ANALYTICS_OK:
                render_analytics()
            else:
                st.error("Analytics module could not be loaded.", icon="🚫")
        with transcript_tab:
            render_transcript()
        return

    # ── Coordinator: full access ──────────────────────────────────────────────
    nav_tab, search_tab, analytics_tab, transcript_tab = st.tabs(
        ["📋 GPA Pipeline", "🔍 Student Search", "📊 Analytics", "📄 Transcripts"]
    )

    with nav_tab:
        stage = st.session_state.stage
        if   stage == "upload"    : render_upload()
        elif stage == "assign"    : render_assign()
        elif stage == "review"    : render_review()
        elif stage == "calculate" : render_calculate()
        elif stage == "results"   : render_results()
        else:
            st.error(f"Unknown stage '{stage}'.")
            if st.button("🔄 Reset"):
                _reset()
                st.rerun()

    with search_tab:
        render_search()

    with analytics_tab:
        if _ANALYTICS_OK:
            render_analytics()
        else:
            st.error("Analytics module could not be loaded.", icon="🚫")

    with transcript_tab:
        render_transcript()


if __name__ == "__main__":
    main()