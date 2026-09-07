"""
src/validators/edge_cases.py
============================
Single source of truth for every EC rule constant, severity level,
and error message template used by the Validation Agent.

Imported by: validation_agent.py
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# SEVERITY LEVEL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_BLOCKED : str = "BLOCKED"
SEVERITY_FLAGGED : str = "FLAGGED"
SEVERITY_INFO    : str = "INFO"


# ─────────────────────────────────────────────────────────────────────────────
# SEVERITY RANK
# Used to compare which severity is worse across multiple flags on one record.
# Higher value = worse.
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_RANK: dict[str, int] = {
    SEVERITY_INFO    : 1,
    SEVERITY_FLAGGED : 2,
    SEVERITY_BLOCKED : 3,
}


# ─────────────────────────────────────────────────────────────────────────────
# STATUS RANK
# Used to compare overall report statuses across files in the LangGraph node.
# Higher value = worse.
# ─────────────────────────────────────────────────────────────────────────────

STATUS_RANK: dict[str, int] = {
    "CLEAN"  : 0,
    "FLAGGED": 1,
    "BLOCKED": 2,
}


# ─────────────────────────────────────────────────────────────────────────────
# ERROR CODE REGISTRY
#
# Keys   : EC code strings (e.g. "EC-01")
# Values : dict with two keys:
#            "message"  — str.format() template; placeholders filled by _make_flag()
#            "severity" — one of the SEVERITY_* constants above
# ─────────────────────────────────────────────────────────────────────────────

ERROR_REGISTRY: dict[str, dict[str, str]] = {

    # ── Identity ──────────────────────────────────────────────────────────────
    "EC-01": {
        "message" : "student_name is missing or empty",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-02": {
        "message" : "roll_no is missing or empty",
        "severity": SEVERITY_BLOCKED,
    },

    # ── Duplicate detection ───────────────────────────────────────────────────
    "EC-03": {
        "message" : "Duplicate roll_no '{roll_no}' found in the same sheet",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-11": {
        "message" : "Duplicate entry: roll_no '{roll_no}' + subject '{subject}' appears more than once",
        "severity": SEVERITY_BLOCKED,
    },

    # ── Marks validation ──────────────────────────────────────────────────────
    "EC-05": {
        "message" : "obtained_marks ({obtained}) exceeds total_marks ({total})",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-06": {
        "message" : "obtained_marks is negative ({obtained})",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-07": {
        "message" : "total_marks is zero — percentage cannot be computed",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-16": {
        "message" : "obtained_marks is not a number (received: {value!r})",
        "severity": SEVERITY_BLOCKED,
    },

    # ── Credit hours ──────────────────────────────────────────────────────────
    "EC-08": {
        "message" : "credit_hours = 0 — treated as a non-credit subject (informational)",
        "severity": SEVERITY_INFO,
    },
    "EC-09": {
        "message" : "credit_hours is None or negative — GPA weight cannot be computed",
        "severity": SEVERITY_BLOCKED,
    },
    "EC-04": {
    "message" : "subject_name is missing or empty",
    "severity": SEVERITY_BLOCKED,
},

    # ── Format / consistency ──────────────────────────────────────────────────
    "EC-12": {
        "message" : "subject_name has extra whitespace or inconsistent casing: '{subject}'",
        "severity": SEVERITY_FLAGGED,
    },
    "EC-13": {
    "message" : "roll_no '{roll_no}' does not match expected pattern UoL/DEPT-S-YY/SERIAL-DEGREE (e.g. UoL/CS-F-22/123-BS)",
    "severity": SEVERITY_FLAGGED,
},
    # ── Sheet-level ───────────────────────────────────────────────────────────
    "EC-17": {
        "message" : "Sheet has zero data rows — nothing to validate",
        "severity": SEVERITY_BLOCKED,
    },

    # ── Database existence ────────────────────────────────────────────────────
    "EC-18": {
        "message" : "roll_no '{roll_no}' already exists in the database for this semester",
        "severity": SEVERITY_FLAGGED,
    },
    "EC-19": {
    "message" : "student_name contains invalid characters: '{name}'",
    "severity": SEVERITY_FLAGGED,
},
"EC-04": {
    "message" : "subject_name is missing or empty",
    "severity": SEVERITY_BLOCKED,
},
"EC-19": {
    "message" : "student_name contains invalid characters: '{name}'",
    "severity": SEVERITY_FLAGGED,
},
"EC-20": {
    "message" : "total_marks is not a number (received: {value!r})",
    "severity": SEVERITY_BLOCKED,
},
"EC-21": {
    "message" : "credit_hours is not a number (received: {value!r})",
    "severity": SEVERITY_BLOCKED,
},
"EC-22": {
    "message" : "subject_name contains invalid characters: '{subject}'",
    "severity": SEVERITY_FLAGGED,
},
}


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC / INTERNAL CODES
# Not triggered by student data — emitted by the orchestrator itself
# for shape errors and Engineer 1 parse warnings.
# ─────────────────────────────────────────────────────────────────────────────

INTERNAL_CODE_SHAPE     : str = "EC-SHAPE"      # Pydantic shape validation failure
INTERNAL_CODE_PARSE_WARN: str = "EC-PARSE-WARN" # Carried forward from Engineer 1


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE SETS  (for isinstance-style membership checks in tests / rules)
# ─────────────────────────────────────────────────────────────────────────────

ALL_EC_CODES: frozenset[str] = frozenset(ERROR_REGISTRY.keys())

BLOCKED_CODES: frozenset[str] = frozenset(
    code for code, meta in ERROR_REGISTRY.items()
    if meta["severity"] == SEVERITY_BLOCKED
)

FLAGGED_CODES: frozenset[str] = frozenset(
    code for code, meta in ERROR_REGISTRY.items()
    if meta["severity"] == SEVERITY_FLAGGED
)

INFO_CODES: frozenset[str] = frozenset(
    code for code, meta in ERROR_REGISTRY.items()
    if meta["severity"] == SEVERITY_INFO
)