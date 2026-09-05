"""
calculator_agent.py
-------------------
LangGraph Node 5 — GPA Calculator Agent.
Applies the HEC Pakistan GPA formula to clean
validated student records.

ASSIGNED TO : Engineer 3 (feature/calculator-db)
STATUS      : NOT STARTED

Formula:
  percentage  = (obtained_marks / total_marks) * 100
  grade_point = lookup from HEC grading table
  quality_pts = credit_hours * grade_point
  GPA         = sum(quality_pts) / sum(credit_hours)
  CGPA        = sum(ALL quality_pts) / sum(ALL credit_hours)
"""

# Your code goes here
