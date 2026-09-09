"""
src/agents/parser_agent.py
==========================
LangGraph Node 2 — Excel / CSV Parser Agent
University of Loralai — CS Department
Tech Lead: Arif Khan

Accepts ANY .xlsx or .csv file — no naming convention required.
Detects semester number and subject name from filename heuristics,
then falls back to file content when heuristics fail.

Public API used by the dashboard
──────────────────────────────────
  detect_semester_and_subject(filename)  → (semester_label, subject_name)
  parse_file_to_records(file_bytes, filename, subject_hint) → result_dict
  parser_agent_node(state)               → state  (LangGraph wrapper)

Output record format (per student row)
──────────────────────────────────────
  {
      "student_name"  : str | None,
      "roll_no"       : str | None,
      "father_name"   : str | None,
      "subject_name"  : str | None,
      "total_marks"   : float | None,
      "obtained_marks": float | None,
      "credit_hours"  : int | None,
      "department"    : str | None,
      "has_issues"    : bool,
      "parse_warnings": list[str],
  }
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pandas as pd

# ─── Semester detection patterns (evaluated in order, first match wins) ────────
# Each tuple: (compiled regex, capturing group index for the digit)
_SEM_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^[Ss](\d)\b"),               1),   # S1, S2 … S8  at start
    (re.compile(r"\bSem(?:ester)?[\s_-]?(\d)", re.I), 1),  # Sem1, Semester_2
    (re.compile(r"(\d)(?:st|nd|rd|th)\b", re.I),      1),  # 1st, 2nd …
    (re.compile(r"[-_\s](\d)[-_\s.]"),         1),   # word-3-word
    (re.compile(r"_S(\d)[A-Z_]"),              1),   # _S3_ interior
]

# ─── Column alias map ─────────────────────────────────────────────────────────
_COL_ALIASES: dict[str, list[str]] = {
    "student_name"  : ["student name", "name", "student", "sname",
                       "student_name", "full name", "candidate name"],
    "roll_no"       : ["roll no", "roll number", "rollno", "roll_no",
                       "reg no", "registration no", "registration number",
                       "reg. no", "reg#", "reg number"],
    "father_name"   : ["father name", "father's name", "fathers name",
                       "father_name", "guardian name", "parent name", "fname"],
    "subject_name"  : ["subject name", "subject", "course name", "course",
                       "subject_name", "paper name", "paper", "paper title"],
    "total_marks"   : ["total marks", "total", "max marks", "maximum marks",
                       "full marks", "total_marks", "out of", "max", "max. marks"],
    "obtained_marks": ["obtained marks", "obtained", "marks", "marks obtained",
                       "scored", "obtained_marks", "score", "marks scored"],
    "credit_hours"  : ["credit hours", "credits", "ch", "credit hour",
                       "credit_hours", "cr. hrs", "cr hrs", "credit hrs"],
    "department"    : ["department", "dept", "program", "programme",
                       "faculty", "dept."],
}

_EXPECTED_FIELDS: list[str] = list(_COL_ALIASES.keys())


# ─── Private helpers ──────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase + collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _map_columns(df_cols: list[str]) -> dict[str, str]:
    """Return {canonical_field: actual_df_column} for every detectable field."""
    n2raw = {_norm(c): c for c in df_cols}
    result: dict[str, str] = {}
    for field, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in n2raw:
                result[field] = n2raw[alias]
                break
    return result


def _find_header_row(df_raw: pd.DataFrame) -> int:
    """Scan first 12 rows and return the row most likely to be the header."""
    alias_words: set[str] = {
        word
        for aliases in _COL_ALIASES.values()
        for a in aliases
        for word in a.split()
    }
    best_row, best_score = 0, -1
    for i in range(min(12, len(df_raw))):
        row_words: set[str] = {
            word
            for v in df_raw.iloc[i].values
            if pd.notna(v)
            for word in _norm(str(v)).split()
        }
        score = len(row_words & alias_words)
        if score > best_score:
            best_score, best_row = score, i
    return best_row


def _prettify_subject(raw: str) -> str:
    """
    Convert CamelCase / raw filename segment to a readable subject name.
    'SoftEng' → 'Soft Eng' | 'DataStructures' → 'Data Structures' | 'OS' → 'OS'
    """
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)   # camelCase split
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)  # ABCWord split
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() if len(s) > 2 else s.upper()


# ─── Public: semester + subject detector ──────────────────────────────────────

def detect_semester_and_subject(filename: str) -> tuple[str | None, str | None]:
    """
    Extract semester label and subject hint from a filename.

    Examples
    --------
    'S2-English2.xlsx'       → ('Semester 2', 'English 2')
    'S5-SoftEng.xlsx'        → ('Semester 5', 'Soft Eng')
    'S4-OS.xlsx'             → ('Semester 4', 'OS')
    'Semester_3_DS.xlsx'     → ('Semester 3', 'DS')
    'marks_data.xlsx'        → (None, None)
    """
    stem = Path(filename).stem   # drop extension

    # ── 1. Semester detection ─────────────────────────────────────────────────
    semester_label: str | None = None
    match_end = 0
    for pattern, grp in _SEM_PATTERNS:
        m = pattern.search(stem)
        if m:
            n = int(m.group(grp))
            if 1 <= n <= 8:
                semester_label = f"Semester {n}"
                match_end = m.end()
                break

    # ── 2. Subject extraction (text after the semester token) ─────────────────
    subject_hint: str | None = None
    if semester_label and match_end:
        remainder = re.sub(r"^[-_\s]+", "", stem[match_end:])
        if remainder:
            subject_hint = _prettify_subject(remainder)

    return semester_label, subject_hint


# ─── Public: file parser ──────────────────────────────────────────────────────

def parse_file_to_records(
    file_bytes: bytes,
    filename: str,
    subject_hint: str | None = None,
    department: str = "",
) -> dict[str, Any]:
    """
    Parse a single xlsx / csv file and return a standardised result dict.

    Parameters
    ----------
    file_bytes   : Raw bytes of the file.
    filename     : Original filename (used for extension detection only).
    subject_hint : Subject name to inject when the sheet has no subject column.
    department   : Department name to inject when the sheet has no dept column.

    Returns
    -------
    {
        "file_name" : str,
        "status"    : "OK" | "ERROR",
        "records"   : list[dict],
        "warnings"  : list[str],
    }
    """
    warnings_out: list[str] = []
    ext = Path(filename).suffix.lower()
    buf = io.BytesIO(file_bytes)

    # ── Raw read ──────────────────────────────────────────────────────────────
    try:
        df_raw = (
            pd.read_csv(buf, header=None, dtype=str)
            if ext == ".csv"
            else pd.read_excel(buf, header=None, dtype=str, engine="openpyxl")
        )
    except Exception as exc:
        return {"file_name": filename, "status": "ERROR", "records": [],
                "warnings": [f"Cannot open file: {exc}"]}

    if df_raw.empty:
        return {"file_name": filename, "status": "ERROR", "records": [],
                "warnings": ["File appears to be empty."]}

    # ── Detect header row ─────────────────────────────────────────────────────
    header_idx = _find_header_row(df_raw)

    buf = io.BytesIO(file_bytes)
    try:
        df = (
            pd.read_csv(buf, header=header_idx, dtype=str)
            if ext == ".csv"
            else pd.read_excel(buf, header=header_idx, dtype=str, engine="openpyxl")
        )
    except Exception as exc:
        return {"file_name": filename, "status": "ERROR", "records": [],
                "warnings": [f"Re-read after header detection failed: {exc}"]}

    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if header_idx > 0:
        warnings_out.append(
            f"Header row detected at row {header_idx + 1}; "
            f"{header_idx} title row(s) skipped."
        )

    # ── Column mapping ────────────────────────────────────────────────────────
    col_map = _map_columns(list(df.columns))

    if not col_map:
        return {
            "file_name": filename,
            "status"   : "ERROR",
            "records"  : [],
            "warnings" : [
                "No recognisable column headers found. "
                "Expected: Student Name, Roll No, Subject Name, "
                "Total Marks, Obtained Marks, Credit Hours."
            ],
        }

    unmapped = [f for f in _EXPECTED_FIELDS if f not in col_map]
    if unmapped:
        warnings_out.append(
            f"Columns not found (will default to None): {', '.join(unmapped)}."
        )

    # ── Build record list ─────────────────────────────────────────────────────
    records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        rec: dict[str, Any] = {
            "student_name"  : None,
            "roll_no"       : None,
            "father_name"   : None,
            "subject_name"  : subject_hint,   # pre-fill from filename hint
            "total_marks"   : None,
            "obtained_marks": None,
            "credit_hours"  : None,
            "department"    : department or None,
            "has_issues"    : False,
            "parse_warnings": [],
        }

        all_null = True
        for field, col in col_map.items():
            raw = row.get(col)
            if pd.isna(raw) or str(raw).strip() in ("", "nan", "NaN", "None"):
                continue
            all_null = False
            val = str(raw).strip()

            if field in ("total_marks", "obtained_marks"):
                try:
                    rec[field] = float(val)
                except ValueError:
                    rec[field] = val           # keep raw; validator will flag EC-16/EC-20
                    rec["has_issues"] = True
                    rec["parse_warnings"].append(
                        f"'{val}' is not numeric for '{field}'."
                    )
            elif field == "credit_hours":
                try:
                    rec[field] = int(float(val))
                except ValueError:
                    rec[field] = val
                    rec["has_issues"] = True
                    rec["parse_warnings"].append(
                        f"'{val}' is not an integer for 'credit_hours'."
                    )
            else:
                rec[field] = val

        if all_null:
            continue   # skip blank rows silently

        records.append(rec)

    return {
        "file_name": filename,
        "status"   : "OK" if records else "ERROR",
        "records"  : records,
        "warnings" : warnings_out,
    }


# ─── LangGraph Node 2 ─────────────────────────────────────────────────────────

def parser_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph pipeline node.

    Reads from state
    ----------------
    uploaded_files : list[dict]  with keys:
                       file_name, file_bytes, subject_hint (optional),
                       department (optional)

    Writes to state
    ---------------
    parsed_files : list[dict]  — one result dict per uploaded file
    """
    uploaded: list[dict[str, Any]] = state.get("uploaded_files", [])
    results: list[dict[str, Any]] = []

    for f in uploaded:
        result = parse_file_to_records(
            file_bytes   = f["file_bytes"],
            filename     = f["file_name"],
            subject_hint = f.get("subject_hint"),
            department   = f.get("department", ""),
        )
        results.append(result)

    state["parsed_files"] = results
    return state
