# Parser Agent — Developer Notes
**Node 2 | Branch: feature/parser-agent**  
**Author: Junior Dev A**  
**Status: Complete and Tested**

---

## What This Agent Does

Connects to Google Drive, finds all Excel and CSV mark sheet files,
downloads them temporarily, converts every student row into a Python
dictionary, then deletes the temp file. Returns a clean list of
dictionaries to the next node in the LangGraph pipeline.

---

## Functions Summary

### Function 1 — `connect_to_drive()`
Reads `credentials.json` and logs the service account into Google
Drive. Returns a service object used by all other functions.
- Raises clear error if credentials.json is missing
- Must be called before any other function

### Function 2 — `find_root_folder()`
Searches Google Drive for the root folder by name defined in `.env`.
Returns the folder ID which is used to start crawling.
- Raises error if folder is not found in Drive
- Folder must be shared with the service account email

### Function 3 — `crawl_folder_recursively()`
Smart crawler that opens any folder and scans every item inside.
- If item is a folder → goes inside it (no matter how deep)
- If item is `.xlsx` or `.csv` → adds to the file list
- If item is anything else (pdf, mp3, txt, jpg) → skips silently
- Does not depend on any specific folder structure

### Function 4 — `download_and_parse_file()`
Downloads one file from Drive into a temporary location, calls the
correct parser based on file type, then deletes the temp file.
- Temp file is always deleted even if parsing crashes (finally block)
- Requires active internet connection to download from Drive

### Function 5 — `parse_xlsx_file()`
Parses `.xlsx` files using openpyxl.
- Row 1 and Row 2 are metadata (university info, subject info)
- Row 3 is the column header row
- Data starts from Row 4
- Reads all 8 columns: student_name, roll_no, father_name,
  subject_name, total_marks, obtained_marks, credit_hours, department
- Skips only fully empty rows
- Never skips incomplete rows — flags them instead

### Function 6 — `parse_csv_file()`
Parses `.csv` files using pandas.
- Normalizes column names automatically (case and spaces)
- Same 8 column structure as xlsx files
- Same flagging logic for missing fields

### Function 7 — `parse_drive_files()`
Master function. This is what LangGraph calls as Node 2.
Runs all functions in order and returns a list of results,
one result dict per file parsed.

---

## Edge Cases This Parser Handles

| Case | How Parser Handles It |
|------|-----------------------|
| Missing student name | Kept in records, flagged in parse_warnings |
| Missing roll number | Kept in records, flagged in parse_warnings |
| Missing obtained marks (absent student) | Kept, flagged as possibly absent |
| Marks > Total marks (e.g. 112/100) | Passed as-is, not parser's job to validate |
| Duplicate roll number in same sheet | Both rows kept and passed forward |
| Credit hours = 0 (non-credit subject) | Passed as-is, not filtered out |
| Marks below passing (e.g. 38/100) | Passed as-is, valid data |
| Unsupported files (pdf, mp3, txt) | Skipped silently, never crash |
| Nested folders in Drive | Handled automatically by recursive crawler |
| Fully empty row | Only case that is skipped completely |
| Note/comment rows in Excel | Now included with has_issues flag |

---

## Output Structure

Every record in the output list looks like this:

```json
{
  "student_name":   "Muhammad Arif Khan",
  "roll_no":        "CS-2021-01",
  "father_name":    "Ghulam Khan",
  "subject_name":   "Data Structures",
  "total_marks":    100,
  "obtained_marks": 72,
  "credit_hours":   3,
  "department":     "CS",
  "has_issues":     false,
  "parse_warnings": []
}
```

When a row has missing or problematic data:

```json
{
  "student_name":   null,
  "roll_no":        null,
  "obtained_marks": null,
  "has_issues":     true,
  "parse_warnings": [
    "student_name is missing",
    "roll_no is missing — student cannot be identified",
    "obtained_marks is missing — student may be absent"
  ]
}
```

---

## Important Notes for Engineer 2 (Validation Agent)

1. **Check `has_issues` field first.** If `true`, this record needs
   attention before GPA calculation. Send it to HITL dashboard.

2. **Never calculate GPA on incomplete records.** If `roll_no` is
   null, the student cannot be identified. Administrator must fill
   this before calculation runs.

3. **`obtained_marks = null` means absent** — not zero. Treat
   differently from a student who scored 0.

4. **`credit_hours = 0` means non-credit subject** (e.g. Holy Quran).
   This subject must be excluded from GPA calculation but must still
   be stored in the database as an audit record.

5. **Marks > total_marks** (e.g. obtained=112, total=100) is a data
   entry error. Flag it as EC-05. Do not calculate GPA for this row
   until administrator corrects it.

6. **Duplicate roll numbers** in the same sheet are passed through.
   Your validator must detect and flag them as EC-03.

7. **All numeric fields** (total_marks, obtained_marks, credit_hours)
   may come as int, float, or None. Always check type before math.

8. **`parse_warnings` is a list.** It can have multiple warnings on
   one record. Check all of them, not just the first one.

---

## Setup Requirements

credentials.json — Google Cloud service account key (never commit to Git)
.env — contains GOOGLE_CREDENTIALS_PATH and DRIVE_FOLDER_NAME


## Install Command

```bash
pip install google-api-python-client google-auth-httplib2 \
            google-auth-oauthlib openpyxl python-dotenv pandas
```

## Run Command

```bash
python src/agents/parser_agent.py
```