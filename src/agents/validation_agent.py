"""
validation_agent.py
===================
LangGraph — Node 3: Validation Agent
Agentic GPA Calculation System

WHAT  : Pure rule-based validation of student records produced by Engineer 1's
        parser.  No AI / LLM involved — deterministic, auditable, reproducible.
WHY   : Catch data quality issues (missing names, impossible marks, duplicate
        entries, format violations) before they corrupt GPA calculations.
HOW   : Each EC rule lives in its own checker function.  The orchestrator
        validate_records() runs them all in the correct order and assembles a
        ValidationReport.  The LangGraph wrapper validation_agent_node() wires
        everything into Node 3 of the pipeline.

Tech Lead  : Arif Khan
Branch     : feature/validation-agent
Python     : 3.11
Libraries  : Pydantic v2, re (stdlib only — no LLM / AI dependency)
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
# re        — stdlib regex for roll_no pattern check (EC-13)
# Any       — used in StudentRecord so Pydantic accepts any incoming type;
#             WE do the type-checking inside the EC functions, not Pydantic
# BaseModel — Pydantic v2; gives us model_validate() and model_dump()
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


from src.validators.edge_cases import (
    SEVERITY_BLOCKED,
    SEVERITY_FLAGGED,
    SEVERITY_INFO,
    SEVERITY_RANK   as _SEVERITY_RANK,
    STATUS_RANK     as _STATUS_RANK,
    ERROR_REGISTRY,
    INTERNAL_CODE_SHAPE,
    INTERNAL_CODE_PARSE_WARN,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════
# WHAT: Runtime-enforced schemas for the three main data shapes.
# WHY:  If Engineer 1's parser ever changes a field name, model_validate()
#       raises ValidationError immediately — you never silently compute a
#       wrong GPA from misread data.
# HOW:  StudentRecord uses `Any` for all student-data fields because OUR EC
#       functions decide validity; Pydantic only enforces the presence of keys.

class StudentRecord(BaseModel):
    """
    One record from Engineer 1's parser output.
    All student-data fields are typed Any so our EC checkers decide
    validity (rather than Pydantic auto-rejecting e.g. a None
    obtained_marks before EC-16 even gets to inspect it).
    """
    student_name   : Any  = None
    roll_no        : Any  = None
    father_name    : Any  = None
    subject_name   : Any  = None
    total_marks    : Any  = None
    obtained_marks : Any  = None
    credit_hours   : Any  = None
    department     : Any  = None
    has_issues     : bool = False
    parse_warnings : list = []

    # Extra keys from Engineer 1 are allowed (future-proof).
    model_config = {"extra": "allow"}


class FlaggedRow(BaseModel):
    """One violation entry in the flagged_rows list of ValidationReport."""
    row_index     : int
    roll_no       : str | None
    student_name  : str | None
    error_code    : str
    error_message : str
    severity      : str       # BLOCKED | FLAGGED | INFO


class ValidationSummary(BaseModel):
    """Row-level counts — each row counted exactly once in one category."""
    total_rows : int
    clean      : int
    flagged    : int   # worst severity FLAGGED or INFO (but not BLOCKED)
    blocked    : int   # worst severity BLOCKED


class ValidationReport(BaseModel):
    """
    Full output of the Validation Agent — passed to the HITL dashboard
    and forwarded to Node 4 (GPA Calculator) for the clean_rows.

    Overall status follows the worst severity found across ALL records:
        any BLOCKED  → "BLOCKED"
        any FLAGGED / INFO → "FLAGGED"
        nothing at all     → "CLEAN"
    """
    status       : str               # "CLEAN" | "FLAGGED" | "BLOCKED"
    clean_rows   : list[dict]        # original record dicts with zero violations
    flagged_rows : list[FlaggedRow]  # one entry per violation (a record may appear multiple times)
    summary      : ValidationSummary


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _make_flag(
    error_code : str,
    row_index  : int,
    record     : dict,
    **fmt_kwargs,       # keyword arguments to fill message template placeholders
) -> dict:
    """
    WHAT: Factory that builds one violation dict from the ERROR_REGISTRY.
    WHY:  Without this, every checker would copy-paste the same 5-key dict
          construction — 18 copies = 18 places to get wrong.
    HOW:  Looks up the template, calls .format(**fmt_kwargs) if placeholders
          exist, returns a plain dict (Pydantic validates in bulk at the end).
    """
    entry   = ERROR_REGISTRY[error_code]
    message = entry["message"].format(**fmt_kwargs) if fmt_kwargs else entry["message"]

    return {
        "row_index"    : row_index,
        "roll_no"      : str(record.get("roll_no")      or ""),
        "student_name" : str(record.get("student_name") or ""),
        "error_code"   : error_code,
        "error_message": message,
        "severity"     : entry["severity"],
    }


def _maybe_append(lst: list, item: dict | None) -> None:
    """Append item to lst only when item is not None. Keeps the main loop readable."""
    if item is not None:
        lst.append(item)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — EC RULE CHECKER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# WHAT: One function per EC rule.
#         Returns None  → rule passed (no violation found)
#         Returns dict  → one violation entry to add to flagged_rows
# WHY:  One function = one responsibility = individually testable with pytest,
#       independently reviewable in code review, easy to extend or disable.
# HOW:  Functions needing cross-row state (EC-03, EC-11, EC-18) accept extra
#       context arguments that the orchestrator builds before the per-row loop.

# ── EC-01 ──────────────────────────────────────────────────────────────────────
def check_ec01(record: dict, idx: int) -> dict | None:
    """
    WHAT: student_name is missing or empty → BLOCKED
    WHY:  A GPA record with no name cannot be attributed to anyone.
    HOW:  Strip whitespace, check for any falsy value.
    """
    name = record.get("student_name")
    if not name or not str(name).strip():
        return _make_flag("EC-01", idx, record)
    return None


# ── EC-02 ──────────────────────────────────────────────────────────────────────
def check_ec02(record: dict, idx: int) -> dict | None:
    """
    WHAT: roll_no is missing or empty → BLOCKED
    WHY:  roll_no is the primary key; without it the record is unidentifiable.
    HOW:  Strip whitespace, check for any falsy value.
    """
    roll = record.get("roll_no")
    if not roll or not str(roll).strip():
        return _make_flag("EC-02", idx, record)
    return None


# ── EC-03 ──────────────────────────────────────────────────────────────────────
def check_ec03(record: dict, idx: int, seen_rolls: set[str]) -> dict | None:
    """
    WHAT: Duplicate roll_no within the same sheet → BLOCKED
    WHY:  Two rows with the same roll_no = one student's marks counted twice.
    HOW:  seen_rolls is updated AFTER this check runs, so the first occurrence
          is always clean; the second fires EC-03.
    """
    roll = str(record.get("roll_no") or "").strip()
    if roll and roll in seen_rolls:
        return _make_flag("EC-03", idx, record, roll_no=roll)
    return None


# ── EC-05 ──────────────────────────────────────────────────────────────────────
def check_ec05(record: dict, idx: int) -> dict | None:
    """
    WHAT: obtained_marks > total_marks (impossible score) → BLOCKED
    WHY:  You cannot score more than the maximum — clear data entry error.
    HOW:  Only called when obtained_marks is already confirmed numeric (EC-16 gate).
          total_marks can still be non-numeric here, so we guard it too.
    """
    obtained = record.get("obtained_marks")
    total    = record.get("total_marks")
    if isinstance(obtained, (int, float)) and isinstance(total, (int, float)):
        if obtained > total:
            return _make_flag("EC-05", idx, record, obtained=obtained, total=total)
    return None


# ── EC-06 ──────────────────────────────────────────────────────────────────────
def check_ec06(record: dict, idx: int) -> dict | None:
    """
    WHAT: obtained_marks is negative → BLOCKED
    WHY:  Negative marks are physically impossible on a standard exam.
    HOW:  Only called when obtained_marks is confirmed numeric (EC-16 gate).
    """
    obtained = record.get("obtained_marks")
    if isinstance(obtained, (int, float)) and obtained < 0:
        return _make_flag("EC-06", idx, record, obtained=obtained)
    return None


# ── EC-07 ──────────────────────────────────────────────────────────────────────
def check_ec07(record: dict, idx: int) -> dict | None:
    """
    WHAT: total_marks is zero → BLOCKED
    WHY:  Division by zero when computing percentage (obtained / total × 100).
    HOW:  Explicit zero check on a numeric value.
    """
    total = record.get("total_marks")
    if isinstance(total, (int, float)) and total == 0:
        return _make_flag("EC-07", idx, record)
    return None


# ── EC-08 ──────────────────────────────────────────────────────────────────────
def check_ec08(record: dict, idx: int) -> dict | None:
    """
    WHAT: credit_hours = 0 → INFO only (non-credit subject)
    WHY:  Non-credit subjects (labs, seminars) are valid; we just flag them so
          the GPA Calculator knows to exclude this row from GPA weight.
    HOW:  Only called when EC-09 did NOT fire (credit_hours is not None/negative).
    """
    ch = record.get("credit_hours")
    if isinstance(ch, (int, float)) and ch == 0:
        return _make_flag("EC-08", idx, record)
    return None


# ── EC-09 ──────────────────────────────────────────────────────────────────────
def check_ec09(record: dict, idx: int) -> dict | None:
    """
    WHAT: credit_hours is None or negative → BLOCKED
    WHY:  None = data is missing; negative credit hours are impossible.
          Either way the GPA weight contribution cannot be computed.
    HOW:  Check None first, then numeric negativity.
    """
    ch = record.get("credit_hours")
    if ch is None:
        return _make_flag("EC-09", idx, record)
    if isinstance(ch, (int, float)) and ch < 0:
        return _make_flag("EC-09", idx, record)
    return None


# ── EC-11 ──────────────────────────────────────────────────────────────────────
def check_ec11(
    record     : dict,
    idx        : int,
    seen_combos: set[tuple[str, str]],
) -> dict | None:
    """
    WHAT: Same roll_no + same subject_name appears twice → BLOCKED
    WHY:  Re-appearing in the same subject means the grade is double-counted.
    HOW:  Combo key = (roll_no, subject_name.lower()) so that "data structures"
          and "Data Structures" are treated as the SAME subject — EC-12 handles
          the casing warning separately.
          seen_combos is updated AFTER this check (same pattern as EC-03).
    """
    roll    = str(record.get("roll_no")      or "").strip()
    subject = str(record.get("subject_name") or "").strip().lower()
    combo   = (roll, subject)
    if roll and subject and combo in seen_combos:
        return _make_flag("EC-11", idx, record, roll_no=roll, subject=subject)
    return None


# ── EC-12 ──────────────────────────────────────────────────────────────────────
def check_ec12(record: dict, idx: int) -> dict | None:
    """
    WHAT: subject_name has extra whitespace or inconsistent casing → FLAGGED
    WHY:  "data structures " ≠ "Data Structures" in downstream string
          comparisons, making two spellings of the same subject look like
          different courses — which breaks GPA aggregation.
    HOW:  Two separate triggers:
            1. Leading/trailing spaces OR two consecutive spaces anywhere.
            2. Stripped value differs from its .title() version
               (e.g. "data structures" vs "Data Structures").
          Either one → FLAGGED.
    """
    subject = record.get("subject_name")
    if not isinstance(subject, str) or not subject:
        return None     # absent subject_name → handled elsewhere

    has_extra_space = (subject != subject.strip()) or ("  " in subject)
    has_bad_casing  = subject.strip() != subject.strip().title()

    if has_extra_space or has_bad_casing:
        return _make_flag("EC-12", idx, record, subject=subject)
    return None


# ── EC-13 ──────────────────────────────────────────────────────────────────────
# Regex breakdown:
#   ^CS-      must start with the literal "CS-"
#   \d{4}-    exactly 4-digit year followed by "-"
#   \d{2,}$   at least 2-digit serial (allows CS-2021-001 for batches > 99)
_ROLL_PATTERN = re.compile(
    r"^UoL\/[A-Z]{2,4}-[A-Z]-\d{2}\/\d{1,4}-[A-Z]{2,4}$"
)

def check_ec13(record: dict, idx: int) -> dict | None:
    """
    WHAT: roll_no does not match the standard pattern CS-YYYY-NN → FLAGGED
    WHY:  Non-standard roll numbers may be data entry errors or records from
          a different department's CSV accidentally mixed into this sheet.
    HOW:  Regex match against _ROLL_PATTERN.
          Only fires when roll_no is non-empty (EC-02 handles the empty case).
    """
    roll = str(record.get("roll_no") or "").strip()
    if roll and not _ROLL_PATTERN.match(roll):
        return _make_flag("EC-13", idx, record, roll_no=roll)
    return None

def check_ec04(record: dict, idx: int) -> dict | None:
    subject = record.get("subject_name")
    if not subject or not str(subject).strip():
        return _make_flag("EC-04", idx, record)
    return None
# ── EC-16 ──────────────────────────────────────────────────────────────────────
def check_ec16(record: dict, idx: int) -> dict | None:
    """
    WHAT: obtained_marks is not a number → BLOCKED
    WHY:  Must run BEFORE EC-05 and EC-06. If obtained_marks is "N/A" or None,
          a comparison like `obtained > total` raises TypeError and crashes.
    HOW:  isinstance check for int or float.
          Booleans are explicitly excluded: isinstance(True, int) is True in
          Python, but True / False are not valid mark values.
    """
    val = record.get("obtained_marks")
    # Guard: bool subclasses int in Python — True would pass isinstance(val, int)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return _make_flag("EC-16", idx, record, value=val)
    return None


# ── EC-17 (sheet-level, not per-row) ───────────────────────────────────────────
def check_ec17_sheet(records: list[dict]) -> bool:
    """
    WHAT: The sheet has zero data rows → BLOCKED (sheet-level check).
    WHY:  Nothing to validate; an empty sheet is almost always an upload error.
    HOW:  Returns True if the records list is empty.
          Called ONCE by the orchestrator before the per-row loop begins.
    """
    return len(records) == 0


# ── EC-18 ──────────────────────────────────────────────────────────────────────
def _query_existing_students(semester: str | None = None) -> set[str]:
    """
    STUB — replace with your real database / API call.
    Must return a set of roll_no strings already recorded for this semester.

    Example real implementation:
        from db import session
        rows = session.execute(
            "SELECT roll_no FROM enrollments WHERE semester = :s",
            {"s": semester},
        ).fetchall()
        return {row.roll_no for row in rows}
    """
    return set()   # safe default during development: no students in DB yet


def check_ec18(
    record           : dict,
    idx              : int,
    existing_students: set[str],
) -> dict | None:
    """
    WHAT: roll_no already exists in the database for this semester → FLAGGED
    WHY:  Re-uploading the same student's data could silently overwrite a
          finalised GPA record — needs human review before the pipeline proceeds.
    HOW:  Looks up in the `existing_students` set that the orchestrator
          pre-fetched once (one DB call per sheet, not one per row).
    """
    roll = str(record.get("roll_no") or "").strip()
    if roll and roll in existing_students:
        return _make_flag("EC-18", idx, record, roll_no=roll)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — CORE ORCHESTRATOR: validate_records()
# ═══════════════════════════════════════════════════════════════════════════════
# WHAT: Runs ALL EC checks on a list of record dicts and returns ValidationReport.
# WHY:  One orchestrator = guaranteed that no rule is accidentally skipped and
#       that the check ORDER is always correct.
#
# Execution order (matters — do not reorder without understanding why):
#   1. EC-17 sheet-level check → bail immediately with BLOCKED if zero rows.
#   2. Pre-fetch DB students once (EC-18 needs this set).
#   3. Initialise cross-row tracking sets (EC-03, EC-11 need these).
#   4. Per-row loop:
#        a. Pydantic shape validation (catch malformed records before EC checks).
#        b. Carry forward Engineer 1's parse_warnings if has_issues = True.
#        c. EC-16 FIRST → gate EC-05 / EC-06 behind "obtained_marks is numeric".
#        d. Identity checks: EC-01, EC-02.
#        e. Cross-row duplicates: EC-03, EC-11.
#        f. Numeric mark checks EC-05, EC-06 (only if EC-16 did not fire).
#        g. Total marks: EC-07.
#        h. Credit hours: EC-09 (BLOCKED) takes priority over EC-08 (INFO).
#        i. Format / consistency: EC-12, EC-13.
#        j. DB existence: EC-18.
#        k. Update seen_rolls / seen_combos AFTER checks (first occurrence = clean).
#        l. Route: no flags → clean_rows; any flag → extend all_flagged.
#   5. Compute per-category summary counts and overall status.
#   6. Return validated ValidationReport.

def validate_records(
    records  : list[dict],
    semester : str | None = None,
) -> ValidationReport:
    """
    Parameters
    ----------
    records  : list of record dicts — the 'records' key from one parse result
    semester : semester label (e.g. "Fall-2024") forwarded to the DB stub (EC-18)

    Returns
    -------
    ValidationReport — ready to pass to the HITL dashboard or LangGraph state.
    """

    # ── 1. Sheet-level EC-17 ─────────────────────────────────────────────────
    if check_ec17_sheet(records):
        return ValidationReport(
            status="BLOCKED",
            clean_rows=[],
            flagged_rows=[
                FlaggedRow(
                    row_index=0,
                    roll_no=None,
                    student_name=None,
                    error_code="EC-17",
                    error_message=ERROR_REGISTRY["EC-17"]["message"],
                    severity=SEVERITY_BLOCKED,
                )
            ],
            summary=ValidationSummary(total_rows=0, clean=0, flagged=0, blocked=1),
        )

    # ── 2. Pre-fetch DB state for EC-18 ──────────────────────────────────────
    # One DB call for the whole sheet — not one per row.
    existing_students: set[str] = _query_existing_students(semester)

    # ── 3. Cross-row tracking sets ────────────────────────────────────────────
    seen_rolls  : set[str]             = set()   # for EC-03
    seen_combos : set[tuple[str, str]] = set()   # for EC-11

    all_flagged : list[dict] = []   # every violation dict across all rows
    clean_rows  : list[dict] = []   # original record dicts with zero violations

    count_clean   : int = 0
    count_flagged : int = 0   # worst severity FLAGGED or INFO
    count_blocked : int = 0   # worst severity BLOCKED

    # ── 4. Per-row loop ───────────────────────────────────────────────────────
    for idx, raw_record in enumerate(records):

        # 4a — Pydantic shape validation ──────────────────────────────────────
        # Catches missing keys or malformed structures from Engineer 1's parser
        # before any EC check runs.
        try:
            record: dict = StudentRecord.model_validate(raw_record).model_dump()
        except Exception as exc:
            all_flagged.append({
                "row_index"    : idx,
                "roll_no"      : str(raw_record.get("roll_no",      "")),
                "student_name" : str(raw_record.get("student_name", "")),
                "error_code"   : INTERNAL_CODE_SHAPE,
                "error_message": f"Record failed Pydantic shape validation: {exc}",
                "severity"     : SEVERITY_BLOCKED,
            })
            count_blocked += 1
            continue   # nothing else to check on a malformed record

        row_flags: list[dict] = []   # violations found for THIS row only

        # 4b — Carry forward Engineer 1's parse_warnings ──────────────────────
        # DESIGN RULE: records with has_issues=True must appear in flagged_rows.
        if record.get("has_issues"):
            for warning in (record.get("parse_warnings") or []):
                row_flags.append({
                    "row_index"    : idx,
                    "roll_no"      : str(record.get("roll_no")      or ""),
                    "student_name" : str(record.get("student_name") or ""),
                    "error_code"   : INTERNAL_CODE_PARSE_WARN,
                    "error_message": str(warning),
                    "severity"     : SEVERITY_FLAGGED,
                })

        # 4c — EC-16 FIRST: obtained_marks type check ─────────────────────────
        # WHY first? If obtained_marks is "N/A" or None, EC-05 / EC-06
        # comparisons raise TypeError and crash. Gate them behind this flag.
        ec16 = check_ec16(record, idx)
        obtained_is_numeric: bool = (ec16 is None)
        if ec16:
            row_flags.append(ec16)

        # 4d — Identity checks ────────────────────────────────────────────────
        # EC-01: student_name missing or empty
        # EC-02: roll_no missing or empty
        # EC-04: subject_name missing or empty       ← ADDED
        # EC-19: student_name has digits or symbols  ← ADDED
        _maybe_append(row_flags, check_ec01(record, idx))
        _maybe_append(row_flags, check_ec02(record, idx))
        _maybe_append(row_flags, check_ec04(record, idx))
        _maybe_append(row_flags, check_ec19(record, idx))

        # 4e — Cross-row duplicate checks ─────────────────────────────────────
        # EC-03: same roll_no appears twice in this sheet
        # EC-11: same roll_no + same subject appears twice
        _maybe_append(row_flags, check_ec03(record, idx, seen_rolls))
        _maybe_append(row_flags, check_ec11(record, idx, seen_combos))

        # 4f — Numeric obtained_marks checks (gated behind EC-16) ─────────────
        # EC-05: obtained > total (impossible score)
        # EC-06: obtained is negative
        # Only runs when obtained_marks is confirmed to be a number.
        if obtained_is_numeric:
            _maybe_append(row_flags, check_ec05(record, idx))
            _maybe_append(row_flags, check_ec06(record, idx))

        # 4g — total_marks: type check first, zero check second ───────────────
        # EC-20: total_marks is not a number ("eighty", None, etc.) → BLOCKED  ← ADDED
        # EC-07: total_marks is zero → BLOCKED
        # EC-07 only runs when total_marks is confirmed numeric.
        ec20 = check_ec20(record, idx)
        total_is_numeric: bool = (ec20 is None)
        if ec20:
            row_flags.append(ec20)
        if total_is_numeric:
            _maybe_append(row_flags, check_ec07(record, idx))

        # 4h — credit_hours: three-level priority chain ───────────────────────
        # EC-21: credit_hours is not a number (string "889", bool, etc.) → BLOCKED  ← ADDED
        # EC-09: credit_hours is None or negative → BLOCKED
        # EC-08: credit_hours is exactly 0 → INFO
        #
        # Each level only runs if the level above it passed.
        # WHY this order? EC-21 catches wrong TYPE first. If type is fine,
        # EC-09 checks for None / negative. If that passes, EC-08 checks zero.
        ec21 = check_ec21(record, idx)
        if ec21:
            row_flags.append(ec21)
        else:
            ec09 = check_ec09(record, idx)
            if ec09:
                row_flags.append(ec09)
            else:
                _maybe_append(row_flags, check_ec08(record, idx))

        # 4i — Format / consistency checks ────────────────────────────────────
        # EC-12: subject_name has extra whitespace or wrong casing
        # EC-13: roll_no does not match pattern CS-YYYY-NN
        _maybe_append(row_flags, check_ec12(record, idx))
        _maybe_append(row_flags, check_ec13(record, idx))
        _maybe_append(row_flags, check_ec22(record, idx))

        # 4j — Database existence check ───────────────────────────────────────
        # EC-18: roll_no already in DB for this semester
        _maybe_append(row_flags, check_ec18(record, idx, existing_students))

        # 4k — Update cross-row tracking sets AFTER all checks ────────────────
        # WHY after? The FIRST occurrence of a roll_no must not self-flag.
        # Adding to seen_rolls BEFORE the check would flag row 0 as its own duplicate.
        roll    = str(record.get("roll_no")      or "").strip()
        subject = str(record.get("subject_name") or "").strip().lower()
        if roll:
            seen_rolls.add(roll)
        if roll and subject:
            seen_combos.add((roll, subject))

        # 4l — Route record ───────────────────────────────────────────────────
        # Zero violations → clean_rows
        # Any violation  → all flags go to all_flagged; record NOT in clean_rows
        if not row_flags:
            clean_rows.append(raw_record)   # original dict, not Pydantic dump
            count_clean += 1
        else:
            all_flagged.extend(row_flags)

            # Count this row once under its WORST severity.
            worst_sev = max(
                row_flags,
                key=lambda f: _SEVERITY_RANK.get(f["severity"], 0),
            )["severity"]

            if worst_sev == SEVERITY_BLOCKED:
                count_blocked += 1
            else:
                count_flagged += 1   # FLAGGED or INFO

    # ── 5. Overall status ─────────────────────────────────────────────────────
    all_severities = {f["severity"] for f in all_flagged}

    if SEVERITY_BLOCKED in all_severities:
        overall_status = "BLOCKED"
    elif all_severities:        # FLAGGED or INFO present, no BLOCKED
        overall_status = "FLAGGED"
    else:
        overall_status = "CLEAN"

    # ── 6. Assemble and return ValidationReport ───────────────────────────────
    return ValidationReport(
        status=overall_status,
        clean_rows=clean_rows,
        flagged_rows=[FlaggedRow(**f) for f in all_flagged],
        summary=ValidationSummary(
            total_rows=len(records),
            clean=count_clean,
            flagged=count_flagged,
            blocked=count_blocked,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — LANGGRAPH NODE WRAPPER: validation_agent_node()
# ═══════════════════════════════════════════════════════════════════════════════
# WHAT: The function LangGraph registers as Node 3 of the pipeline.
# WHY:  LangGraph nodes accept one state dict and return an updated state dict.
#       All business logic lives in validate_records() — this wrapper is
#       intentionally thin: it wires state keys in, calls the orchestrator,
#       and writes the results back out.
#
# State key flow:
#   IN  → state["parsed_files"]   : list[dict]  (parse_drive_files() output)
#       → state["semester"]        : str | None
#   OUT → state["validation_reports"] : list[dict]  (one report per file)
#       → state["validation_status"]  : str         (worst across all files)

def validation_agent_node(state: dict) -> dict:
    """
    LangGraph Node 3 — Validation Agent.

    Reads from state
    ----------------
    parsed_files : list[dict]  — output of parse_drive_files(); each dict has
                                 at minimum: file_name, status, records
    semester     : str | None  — current semester string forwarded to EC-18

    Writes to state
    ---------------
    validation_reports : list[dict]  — one ValidationReport (as dict) per file
    validation_status  : str         — worst status across all processed files
    """
    parsed_files : list[dict] = state.get("parsed_files", [])
    semester     : str | None = state.get("semester", None)

    all_reports  : list[dict] = []
    worst_status : str        = "CLEAN"   # will escalate toward BLOCKED as needed

    for file_result in parsed_files:

        file_name: str = file_result.get("file_name", "unknown")

        # Skip files that Engineer 1's parser already marked as ERROR.
        # We emit a BLOCKED report so the HITL dashboard sees them.
        if file_result.get("status") == "ERROR":
            all_reports.append({
                "file_name"   : file_name,
                "status"      : "BLOCKED",
                "error"       : "Parser reported ERROR for this file — skipped validation",
                "clean_rows"  : [],
                "flagged_rows": [],
                "summary"     : {
                    "total_rows": 0,
                    "clean"     : 0,
                    "flagged"   : 0,
                    "blocked"   : 0,
                },
            })
            worst_status = "BLOCKED"
            continue

        records: list[dict]       = file_result.get("records", [])
        report : ValidationReport = validate_records(records, semester=semester)

        report_dict: dict         = report.model_dump()
        report_dict["file_name"]  = file_name

        all_reports.append(report_dict)

        # Escalate worst_status if this file's status is worse.
        if _STATUS_RANK.get(report.status, 0) > _STATUS_RANK.get(worst_status, 0):
            worst_status = report.status

    return {
        **state,                               # preserve all existing state keys
        "validation_reports": all_reports,
        "validation_status" : worst_status,
    }

import re

_VALID_NAME_PATTERN = re.compile(r"^[A-Za-z\s\.\-]+$")
# Allows: letters, spaces, dots (for initials), hyphens (for double names)
# Blocks: digits, @, #, !, numbers etc.

def check_ec19(record: dict, idx: int) -> dict | None:
    name = str(record.get("student_name") or "").strip()
    if name and not _VALID_NAME_PATTERN.match(name):
        return _make_flag("EC-19", idx, record, name=name)
    return None



# ── EC-04 ──────────────────────────────────────────────────────────────────────
def check_ec04(record: dict, idx: int) -> dict | None:
    """subject_name missing or empty → BLOCKED"""
    subject = record.get("subject_name")
    if not subject or not str(subject).strip():
        return _make_flag("EC-04", idx, record)
    return None


# ── EC-19 ──────────────────────────────────────────────────────────────────────
_VALID_NAME_PATTERN = re.compile(r"^[A-Za-z\s\.\-]+$")
# Allows: letters, spaces, dots (initials), hyphens (double-barrel names)
# Blocks: digits, @, #, <, >, symbols

def check_ec19(record: dict, idx: int) -> dict | None:
    """student_name contains digits or symbols → FLAGGED"""
    name = str(record.get("student_name") or "").strip()
    if name and not _VALID_NAME_PATTERN.match(name):
        return _make_flag("EC-19", idx, record, name=name)
    return None


# ── EC-20 ──────────────────────────────────────────────────────────────────────
def check_ec20(record: dict, idx: int) -> dict | None:
    """total_marks is not a number → BLOCKED"""
    val = record.get("total_marks")
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return _make_flag("EC-20", idx, record, value=val)
    return None


# ── EC-21 ──────────────────────────────────────────────────────────────────────
def check_ec21(record: dict, idx: int) -> dict | None:
    """
    credit_hours is not a number (wrong type — string, bool, etc.) → BLOCKED
    Note: None is intentionally excluded here — EC-09 handles None.
    """
    val = record.get("credit_hours")
    if val is None:
        return None   # EC-09 owns the None case
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return _make_flag("EC-21", idx, record, value=val)
    return None
# ── EC-22 ──────────────────────────────────────────────────────────────────────
# Allows : letters, digits, spaces, hyphens, dots, parentheses, forward slash
#          e.g. "Data Structures", "Mathematics-I", "CS301", "Programming (Lab)"
# Blocks : @  #  $  %  ^  &  *  !  <  >  ~  and all other special symbols
_VALID_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\.\(\)\/]+$")

def check_ec22(record: dict, idx: int) -> dict | None:
    """subject_name contains symbols or invalid characters → FLAGGED"""
    subject = str(record.get("subject_name") or "").strip()
    if subject and not _VALID_SUBJECT_PATTERN.match(subject):
        return _make_flag("EC-22", idx, record, subject=subject)
    return None

if __name__ == "__main__":

    # Fake Engineer 1 output — paste your own sample here
    

    test_records = [

       

        # ── Record 6: roll_no wrong format → EC-13 FLAGGED ───────────────
        {
            "student_name"  : "K5",
            "roll_no"       : "UoL/CS-F-22/123-BS",
            "subject_name"  : "K",
            "total_marks"   : 700,
            "obtained_marks": 700,
            "credit_hours"  : 667,
            "has_issues"    : False,
            "parse_warnings": []
        },

    ]

    report = validate_records(test_records)

    print("=" * 55)
    print(f"  Overall Status : {report.status}")
    print(f"  Total Rows     : {report.summary.total_rows}")
    print(f"  Clean          : {report.summary.clean}")
    print(f"  Flagged        : {report.summary.flagged}")
    print(f"  Blocked        : {report.summary.blocked}")
    print("=" * 55)

    if report.flagged_rows:
        print("\n  VIOLATIONS FOUND:\n")
        for row in report.flagged_rows:
            print(f"  Row {row.row_index} | {row.roll_no or 'NO ROLL'} | {row.error_code} | {row.severity}")
            print(f"         → {row.error_message}")
            print()