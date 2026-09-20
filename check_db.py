"""
AcadTrack — Database Diagnostic Script
Run from project root:
    python check_db.py
"""

import sqlite3
import os

# Find the database file
DB_PATH = "gpa_system.db"

if not os.path.exists(DB_PATH):
    print(f"ERROR: {DB_PATH} not found!")
    print("Make sure you run this from:")
    print("  D:\\gpa-agentic-system\\gpa-agentic-system\\")
    exit()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 50)
print("STUDENTS TABLE")
print("=" * 50)
cur.execute("SELECT id, roll_no, student_name, department FROM students LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  id={r[0]}  roll_no={r[1]}  name={r[2]}  dept={r[3]}")
else:
    print("  NO STUDENTS FOUND")

print()
print("=" * 50)
print("SEMESTER GPA TABLE")
print("=" * 50)
cur.execute("SELECT student_id, semester, academic_year, gpa FROM semester_gpa LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  student_id={r[0]}  semester={r[1]}  year={r[2]}  gpa={r[3]}")
else:
    print("  NO SEMESTER GPA RECORDS FOUND")

print()
print("=" * 50)
print("CGPA TABLE")
print("=" * 50)
cur.execute("SELECT student_id, cgpa, semesters_completed FROM cgpa LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  student_id={r[0]}  cgpa={r[1]}  semesters={r[2]}")
else:
    print("  NO CGPA RECORDS FOUND")

print()
print("=" * 50)
print("UPLOAD JOBS TABLE")
print("=" * 50)
cur.execute("SELECT job_id, file_name, status, semester, academic_year FROM upload_jobs LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  job={r[0][:8]}...  file={r[1]}  status={r[2]}  sem={r[3]}  year={r[4]}")
else:
    print("  NO UPLOAD JOBS FOUND")

print()
print("=" * 50)
print("AUDIT LOG TABLE")
print("=" * 50)
try:
    cur.execute("SELECT id, username, action, timestamp FROM audit_log LIMIT 10")
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  id={r[0]}  user={r[1]}  action={r[2]}  time={r[3]}")
    else:
        print("  NO AUDIT LOGS YET")
except Exception as e:
    print(f"  TABLE NOT FOUND YET: {e}")

print()
print("=" * 50)
print("NOTIFICATION QUEUE TABLE")
print("=" * 50)
try:
    cur.execute("SELECT id, notification_type, channel, status FROM notification_queue LIMIT 10")
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  id={r[0]}  type={r[1]}  channel={r[2]}  status={r[3]}")
    else:
        print("  QUEUE IS EMPTY")
except Exception as e:
    print(f"  TABLE NOT FOUND YET: {e}")

print()
print("=" * 50)
print("WHAT TO USE IN NOTIFICATIONS ENDPOINT")
print("=" * 50)
cur.execute("SELECT DISTINCT semester, academic_year FROM semester_gpa")
rows = cur.fetchall()
if rows:
    print("  Use these exact values:")
    for r in rows:
        print(f"  semester={r[0]}  academic_year={r[1]}")
else:
    print("  No semester_gpa data found — upload and approve a file first")

cur.execute("SELECT DISTINCT department FROM students")
rows = cur.fetchall()
if rows:
    print()
    print("  Use one of these department values:")
    for r in rows:
        print(f"  department={r[0]}")

conn.close()
print()
print("Done.")