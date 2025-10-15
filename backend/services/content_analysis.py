"""
AcadTrack — Content Analysis Service
University of Loralai, Pakistan

Intelligent content-level analysis of uploaded mark-sheet files.
No dependency on src/ agents — pure pandas + stdlib.

Public API
----------
  extract_semester_from_content(file_bytes, filename) → int | None
      Scans the raw Excel/CSV rows for semester information BEFORE the
      student-data header row.  Returns 1-8 or None.

  compute_content_fingerprint(records) → dict
      Derives a fingerprint from parsed records: subject name + roll_no set.

  detect_duplicates_in_batch(fingerprints) → list[dict]
      Finds pairs/groups within a batch that likely represent the same
      mark-sheet uploaded under different filenames.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ── Semester patterns (evaluated on raw cell text) ────────────────────────────
# Ordered: most specific first.
_SEM_CONTENT_PATTERNS: list[re.Pattern] = [
    re.compile(r"sem(?:ester)?\s*(?:no\.?|#|:)?\s*([1-8])\b",    re.I),
    re.compile(r"\b([1-8])(?:st|nd|rd|th)\s+sem(?:ester)?\b",     re.I),
    re.compile(r"semester\s+([1-8])\b",                            re.I),
    re.compile(r"\bsem\s*([1-8])\b",                               re.I),
    re.compile(r"\bclass\s+([1-8])\b",                             re.I),
    # Last resort: a standalone digit 1-8 in a cell that also contains "sem"
    # handled separately below
]

# How many raw rows to scan for metadata (before the student header)
_META_SCAN_ROWS = 25


def extract_semester_from_content(
    file_bytes: bytes,
    filename: str,
) -> int | None:
    """
    Read the raw Excel/CSV file and detect the semester number.

    Three-pass strategy (in order of priority):

    Pass 1 — Data column scan
        Look for a column named 'Semester', 'Sem', 'semester_no' etc.
        in the student data table itself.  Read the first non-null value.
        This handles: Excel files where each row has a 'Semester' column.

    Pass 2 — Metadata row scan (rows ABOVE the student data header)
        Scan cells in rows 0–25 for patterns like 'Semester: 2',
        '2nd Semester', 'Sem # 4', etc.
        This handles: university letterhead / exam paper metadata blocks.

    Pass 3 — Structural two-cell scan
        Find any row where one cell contains 'sem' AND an adjacent cell
        is a lone digit 1–8.

    Returns an integer (1–8) or None if nothing was found.
    """
    ext = Path(filename).suffix.lower()
    buf = io.BytesIO(file_bytes)

    # ── Pass 1: data-column scan ──────────────────────────────────────────────
    # Column names that mean "semester" in student mark-sheets
    _SEM_COL_ALIASES = {
        "semester", "sem", "semester no", "semester no.", "sem no",
        "sem no.", "semester_no", "sem_no", "semester number",
        "semester #", "class", "term",
    }

    try:
        buf.seek(0)
        df_raw_col: pd.DataFrame = (
            pd.read_csv(buf, header=None, dtype=str, nrows=_META_SCAN_ROWS)
            if ext == ".csv"
            else pd.read_excel(
                buf, header=None, dtype=str, nrows=_META_SCAN_ROWS, engine="openpyxl"
            )
        )

        # Find the best header row (same logic as parser_agent)
        _col_words = _SEM_COL_ALIASES | {
            "student", "name", "roll", "marks", "obtained", "total", "credit"
        }
        best_row, best_score = 0, -1
        for i in range(min(_META_SCAN_ROWS, len(df_raw_col))):
            row_words = {
                w for v in df_raw_col.iloc[i].values
                if pd.notna(v)
                for w in re.sub(r"\s+", " ", str(v).strip().lower()).split()
            }
            score = len(row_words & _col_words)
            if score > best_score:
                best_score, best_row = score, i

        if best_score >= 2:
            buf.seek(0)
            df_data: pd.DataFrame = (
                pd.read_csv(buf, header=best_row, dtype=str)
                if ext == ".csv"
                else pd.read_excel(
                    buf, header=best_row, dtype=str, engine="openpyxl"
                )
            )

            # Normalise column names and find semester column
            col_norm = {
                re.sub(r"\s+", " ", str(c).strip().lower()): c
                for c in df_data.columns
            }
            sem_col_raw: str | None = None
            for alias in _SEM_COL_ALIASES:
                if alias in col_norm:
                    sem_col_raw = col_norm[alias]
                    break

            if sem_col_raw and sem_col_raw in df_data.columns:
                for val in df_data[sem_col_raw].dropna():
                    val_str = str(val).strip()
                    # Try direct int
                    try:
                        n = int(float(val_str))
                        if 1 <= n <= 8:
                            return n
                    except (ValueError, TypeError):
                        pass
                    # Try regex on text like "Semester 2", "2nd"
                    for pat in _SEM_CONTENT_PATTERNS:
                        m = pat.search(val_str)
                        if m:
                            n = int(m.group(1))
                            if 1 <= n <= 8:
                                return n
    except Exception:
        pass  # non-fatal, move to pass 2

    # ── Pass 2: metadata row scan (top N rows, before student data) ───────────
    buf.seek(0)
    try:
        df_meta: pd.DataFrame = (
            pd.read_csv(buf, header=None, dtype=str, nrows=_META_SCAN_ROWS)
            if ext == ".csv"
            else pd.read_excel(
                buf, header=None, dtype=str, nrows=_META_SCAN_ROWS, engine="openpyxl"
            )
        )
    except Exception:
        return None

    for row_idx in range(min(_META_SCAN_ROWS, len(df_meta))):
        row_vals = [
            str(v).strip()
            for v in df_meta.iloc[row_idx].values
            if pd.notna(v) and str(v).strip() not in ("", "nan", "None")
        ]
        for cell in row_vals:
            for pat in _SEM_CONTENT_PATTERNS:
                m = pat.search(cell)
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= 8:
                        return n

    # ── Pass 3: two-cell structural scan ─────────────────────────────────────
    for row_idx in range(min(_META_SCAN_ROWS, len(df_meta))):
        row_vals = [
            str(v).strip().lower()
            for v in df_meta.iloc[row_idx].values
            if pd.notna(v) and str(v).strip() not in ("", "nan", "None")
        ]
        row_text = " ".join(row_vals)
        if "sem" in row_text:
            digits = re.findall(r"\b([1-8])\b", row_text)
            if len(digits) == 1:
                return int(digits[0])

    return None



# ── Content fingerprinting ─────────────────────────────────────────────────────

def compute_content_fingerprint(records: list[dict]) -> dict[str, Any]:
    """
    Derive a content fingerprint from a list of parsed student records.

    Returns
    -------
    {
        "subject_name"  : str | None,
        "roll_nos"      : list[str],   # sorted, de-duplicated
        "student_count" : int,
        "content_hash"  : str,         # hex SHA-1 of sorted roll_nos + subject
    }
    """
    subject_name: str | None = None
    roll_nos: set[str] = set()

    for rec in records:
        sn = rec.get("subject_name")
        if sn and not subject_name:
            subject_name = str(sn).strip()

        rn = rec.get("roll_no")
        if rn and str(rn).strip() not in ("", "None", "nan"):
            roll_nos.add(str(rn).strip())

    sorted_rolls = sorted(roll_nos)
    fingerprint_str = f"{(subject_name or '').lower()}|{'|'.join(sorted_rolls)}"
    content_hash = hashlib.sha1(fingerprint_str.encode()).hexdigest()

    return {
        "subject_name"  : subject_name,
        "roll_nos"      : sorted_rolls,
        "student_count" : len(sorted_rolls),
        "content_hash"  : content_hash,
    }


def detect_duplicates_in_batch(
    job_fingerprints: list[dict],
    overlap_threshold: float = 0.70,
) -> list[dict]:
    """
    Given a list of {job_id, subject_name, roll_nos, student_count, content_hash}
    dicts for every job in a batch, return a list of duplicate-warning dicts.

    Duplicate criteria (either condition):
      A) Identical content_hash (exact match)
      B) Same subject_name AND roll_no overlap ≥ overlap_threshold

    Returns
    -------
    list of {
        "job_id"          : str,   # the newer/smaller file (keep the other)
        "duplicate_of"    : str,   # job_id of the earlier file in the batch
        "overlap_pct"     : float, # 0.0 – 1.0
        "message"         : str,
        "subject_name"    : str,
        "this_count"      : int,
        "other_count"     : int,
        "common_count"    : int,
    }
    """
    warnings: list[dict] = []

    n = len(job_fingerprints)
    for i in range(n):
        a = job_fingerprints[i]
        for j in range(i + 1, n):
            b = job_fingerprints[j]

            # Exact hash match
            if a["content_hash"] == b["content_hash"]:
                warnings.append(_make_dup_warning(a, b, 1.0))
                continue

            # Same subject + roll_no overlap
            if not a["subject_name"] or not b["subject_name"]:
                continue
            if a["subject_name"].lower() != b["subject_name"].lower():
                continue

            set_a = set(a["roll_nos"])
            set_b = set(b["roll_nos"])
            if not set_a or not set_b:
                continue

            common = set_a & set_b
            # Jaccard-like: overlap / union
            overlap = len(common) / len(set_a | set_b)
            if overlap >= overlap_threshold:
                # Mark the one with fewer students as the "duplicate" (prefer bigger)
                if len(set_a) >= len(set_b):
                    warnings.append(_make_dup_warning(b, a, overlap))
                else:
                    warnings.append(_make_dup_warning(a, b, overlap))

    return warnings


def _make_dup_warning(
    dup: dict,     # the file being flagged
    ref: dict,     # the reference file it duplicates
    overlap: float,
) -> dict:
    common = len(set(dup["roll_nos"]) & set(ref["roll_nos"]))
    return {
        "job_id"       : dup["job_id"],
        "duplicate_of" : ref["job_id"],
        "overlap_pct"  : round(overlap, 3),
        "subject_name" : dup.get("subject_name", ""),
        "this_count"   : dup["student_count"],
        "other_count"  : ref["student_count"],
        "common_count" : common,
        "message": (
            f"'{dup.get('job_filename', dup['job_id'])}' appears to duplicate "
            f"'{ref.get('job_filename', ref['job_id'])}' "
            f"({int(overlap * 100)}% student overlap, same subject: "
            f"{dup.get('subject_name', '?')})"
        ),
    }
