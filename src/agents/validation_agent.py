"""
validation_agent.py
-------------------
LangGraph Node 3 — Validation Agent.
Receives parsed data from the Parser Agent,
runs all edge case checks, and returns a
structured validation report.

ASSIGNED TO : Engineer 2 (feature/validation-agent)
STATUS      : NOT STARTED

Expected output format:
{
    "status"      : "CLEAN" | "FLAGGED" | "BLOCKED",
    "clean_rows"  : [...],
    "flagged_rows": [...],
    "summary"     : {
        "total_rows": int,
        "clean"     : int,
        "flagged"   : int,
        "blocked"   : int
    }
}
"""

# Your code goes here
