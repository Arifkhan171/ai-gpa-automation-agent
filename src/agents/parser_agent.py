# """
# parser_agent.py
# ---------------
# LangGraph Node 2 — Excel Parser Agent.
# Reads a .xlsx mark sheet
#  and returns a list of
# Python dictionaries (one dict per student row).

# ASSIGNED TO : Engineer 1 (feature/parser-agent)
# STATUS      : NOT STARTED

# Expected output format:
# [
#     {
#         "student_name"  : str,
#         "roll_no"       : str,
#         "father_name"   : str,
#         "subject_name"  : str,
#         "total_marks"   : float,
#         "obtained_marks": float,
#         "credit_hours"  : int,
#         "department"    : str
#     },
#     ...
# ]
# """

# # ─────────────────────────────────────────────────────────────
# # parser_agent.py
# # Node 2 — Agentic GPA Calculation System
# # Job: Read an Excel mark sheet → return a list of dicts
# # Branch: feature/parser-agent
# # ─────────────────────────────────────────────────────────────

# import openpyxl
# from pathlib import Path
# from dotenv import load_dotenv

# load_dotenv()


# # ── FUNCTION 1 ───────────────────────────────────────────────
# def load_workbook_safe(file_path: str):
#     """Opens the Excel file safely. Raises clear errors if file
#     is missing, wrong format, or corrupted."""

#     path = Path(file_path)

#     if not path.exists():
#         raise FileNotFoundError(
#             f"[ParserAgent] File not found: {file_path}"
#         )

#     if path.suffix.lower() != ".xlsx":
#         raise ValueError(
#             f"[ParserAgent] Expected .xlsx file, got: {path.suffix}"
#         )

#     try:
#         workbook = openpyxl.load_workbook(file_path, data_only=True)
#         return workbook
#     except Exception as e:
#         raise RuntimeError(
#             f"[ParserAgent] Failed to open workbook: {e}"
#         )


# # ── FUNCTION 2 ───────────────────────────────────────────────
# def get_sheet_metadata(sheet) -> dict:
#     """Reads rows 1 and 2 of the sheet to extract subject-level
#     info: university, subject name, semester, credit hours."""

#     try:
#         row1 = sheet.cell(row=1, column=1).value or ""
#         row2 = sheet.cell(row=2, column=1).value or ""

#         metadata = {
#             "university_info": str(row1).strip(),
#             "subject_info":    str(row2).strip(),
#             "sheet_name":      sheet.title,
#         }
#         return metadata

#     except Exception as e:
#         raise RuntimeError(
#             f"[ParserAgent] Failed to read metadata: {e}"
#         )


# # ── FUNCTION 3 ───────────────────────────────────────────────
# def parse_sheet_rows(sheet) -> list[dict]:
#     """Reads from row 4 onward (row 3 is headers, rows 1-2 are
#     metadata). Converts each student row into a dictionary.
#     Does NOT skip or crash on bad data — passes everything forward
#     so the Validation Agent can decide what is valid."""

#     # These are the exact column positions in your Excel files
#     COLUMNS = {
#         "student_name":   1,
#         "roll_no":        2,
#         "father_name":    3,
#         "subject_name":   4,
#         "total_marks":    5,
#         "obtained_marks": 6,
#         "credit_hours":   7,
#         "department":     8,
#     }

#     records = []

#     # iter_rows starts at row 4 (skipping header rows 1, 2, 3)
#     # min_col=1, max_col=8 means only read the 8 columns we need
#     for row in sheet.iter_rows(min_row=4, min_col=1, max_col=8, values_only=True):

#                 # Skip completely empty rows
#         if all(cell is None for cell in row):
#             continue

#         # Skip note/comment rows — real students always have a roll number
#         if row[1] is None:
#             continue

#         record = {
#             "student_name":   str(row[0]).strip() if row[0] is not None else None,
#             "roll_no":        str(row[1]).strip() if row[1] is not None else None,
#             "father_name":    str(row[2]).strip() if row[2] is not None else None,
#             "subject_name":   str(row[3]).strip() if row[3] is not None else None,
#             "total_marks":    row[4],
#             "obtained_marks": row[5],   # intentionally kept as-is (could be None)
#             "credit_hours":   row[6],
#             "department":     str(row[7]).strip() if row[7] is not None else None,
#         }

#         records.append(record)

#     return records


# # ── FUNCTION 4 ───────────────────────────────────────────────
# def parse_excel_file(file_path: str) -> dict:
#     """Master function. This is what LangGraph calls as Node 2.
#     Takes a file path, runs all 3 functions above, and returns
#     a clean result package containing metadata + all student rows."""

#     # Step 1: open the file
#     workbook = load_workbook_safe(file_path)

#     # Step 2: get the active sheet
#     sheet = workbook.active

#     # Step 3: read metadata from rows 1-2
#     metadata = get_sheet_metadata(sheet)

#     # Step 4: read all student rows from row 4 onward
#     records = parse_sheet_rows(sheet)

#     # Step 5: package everything together
#     result = {
#         "status":    "parsed",
#         "file_path": str(file_path),
#         "metadata":  metadata,
#         "row_count": len(records),
#         "records":   records,
#     }

#     print(f"[ParserAgent] ✅ Parsed '{metadata['sheet_name']}' "
#           f"— {len(records)} rows found.")

#     return result


# # ── QUICK TEST (only runs when you execute this file directly) ─
# if __name__ == "__main__":
#     import json
#     import os

#     # Change this path to any of your 5 Excel files
#     TEST_FILE = os.path.join("data", "sample_sheets", "Sheet3_Calculus_Sem3.xlsx")

#     result = parse_excel_file(TEST_FILE)

#     # Pretty print the full output
#     print(json.dumps(result, indent=2, ensure_ascii=False))




# ─────────────────────────────────────────────────────────────
# parser_agent.py
# Node 2 — Agentic GPA Calculation System
# Job: Connect to Google Drive → find all Excel/CSV files →
#      download temporarily → parse → delete → return dicts
# Branch: feature/parser-agent
# ─────────────────────────────────────────────────────────────
"""
parser_agent.py
---------------
LangGraph Node 2 — Excel Parser Agent.
Reads .xlsx and .csv mark sheets from Google Drive.
Returns a list of result dicts — one per file.

ASSIGNED TO : Engineer 1 (feature/parser-agent)
STATUS      : FIXED — pandas added, CSV warnings aligned with XLSX
"""

import os
import tempfile
import openpyxl
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

load_dotenv()

# ── CONSTANTS ─────────────────────────────────────────────────
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
DRIVE_FOLDER_NAME = os.getenv("DRIVE_FOLDER_NAME", "GPA-MarkSheets")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_XLSX   = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_CSV    = "text/csv"
SUPPORTED_MIMES = [MIME_XLSX, MIME_CSV]


# ── FUNCTION 1 ────────────────────────────────────────────────
def connect_to_drive():
    """
    Connects to Google Drive using credentials.json.
    Returns a Drive service object.
    """
    creds_path = Path(CREDENTIALS_PATH)

    if not creds_path.exists():
        raise FileNotFoundError(
            f"[ParserAgent] credentials.json not found at: {CREDENTIALS_PATH}\n"
            f"Download it from Google Cloud Console."
        )

    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)
    print("[ParserAgent] ✅ Connected to Google Drive successfully.")
    return service


# ── FUNCTION 2 ────────────────────────────────────────────────
def find_root_folder(service, folder_name: str) -> str:
    """
    Searches Google Drive for the root folder by name.
    Returns the folder ID.
    """
    query = (
        f"name = '{folder_name}' "
        f"and mimeType = '{MIME_FOLDER}' "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    folders = results.get("files", [])

    if not folders:
        raise FileNotFoundError(
            f"[ParserAgent] Folder '{folder_name}' not found in Google Drive.\n"
            f"Make sure you created it and shared it with the service account."
        )

    folder_id = folders[0]["id"]
    print(f"[ParserAgent] ✅ Found root folder: '{folder_name}' (ID: {folder_id})")
    return folder_id


# ── FUNCTION 3 ────────────────────────────────────────────────
def crawl_folder_recursively(service, folder_id: str, all_files: list):
    """
    Recursively crawls a Google Drive folder.
    Collects all .xlsx and .csv files no matter how deep.
    """
    query = (
        f"'{folder_id}' in parents "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()

    items = results.get("files", [])

    for item in items:
        name    = item["name"]
        mime    = item["mimeType"]
        file_id = item["id"]

        if mime == MIME_FOLDER:
            print(f"[ParserAgent] 📁 Entering folder: {name}")
            crawl_folder_recursively(service, file_id, all_files)

        elif mime in SUPPORTED_MIMES:
            print(f"[ParserAgent] 📄 Found file: {name}")
            all_files.append({"id": file_id, "name": name, "mime": mime})

        else:
            print(f"[ParserAgent] ⏭️  Skipping unsupported file: {name}")


# ── FUNCTION 4 ────────────────────────────────────────────────
def download_and_parse_file(service, file_info: dict) -> dict:
    """
    Downloads one file from Google Drive into a temp folder,
    parses it, deletes the temp file, returns the result dict.
    """
    file_id   = file_info["id"]
    file_name = file_info["name"]
    mime      = file_info["mime"]

    print(f"[ParserAgent] ⬇️  Downloading: {file_name}")

    request    = service.files().get_media(fileId=file_id)
    buffer     = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)

    suffix = ".xlsx" if mime == MIME_XLSX else ".csv"

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, prefix="gpa_temp_"
    ) as tmp_file:
        tmp_file.write(buffer.read())
        tmp_path = tmp_file.name

    print(f"[ParserAgent] 💾 Saved temporarily to: {tmp_path}")

    try:
        if suffix == ".xlsx":
            result = parse_xlsx_file(tmp_path, file_name)
        else:
            result = parse_csv_file(tmp_path, file_name)
    finally:
        os.unlink(tmp_path)
        print(f"[ParserAgent] 🗑️  Deleted temp file: {tmp_path}")

    return result


# ── HELPER: build warnings for one record ────────────────────
def _build_warnings(record: dict) -> list[str]:
    """
    Checks all 8 required fields and returns a list of
    warning strings for any that are missing or None.
    Used by both XLSX and CSV parsers so the warning format
    is always identical — Engineer 2 receives consistent data
    regardless of file type.
    """
    warnings = []

    if not record.get("student_name"):
        warnings.append("student_name is missing")

    if not record.get("roll_no"):
        warnings.append("roll_no is missing — student cannot be identified")

    if not record.get("father_name"):
        warnings.append("father_name is missing")

    if not record.get("subject_name"):
        warnings.append("subject_name is missing")

    if record.get("total_marks") is None:
        warnings.append("total_marks is missing")

    if record.get("obtained_marks") is None:
        warnings.append("obtained_marks is missing — student may be absent")

    if record.get("credit_hours") is None:
        warnings.append("credit_hours is missing")

    if not record.get("department"):
        warnings.append("department is missing")

    return warnings


# ── FUNCTION 5 ────────────────────────────────────────────────
def parse_xlsx_file(file_path: str, file_name: str) -> dict:
    """
    Parses an .xlsx file using openpyxl.
    Reads metadata from rows 1-2.
    Reads ALL student rows from row 4 onward.
    Never skips incomplete rows — passes everything to
    Engineer 2 with warnings attached for HITL review.
    """
    workbook = openpyxl.load_workbook(file_path, data_only=True)
    sheet    = workbook.active

    metadata = {
        "university_info": str(sheet.cell(row=1, column=1).value or "").strip(),
        "subject_info":    str(sheet.cell(row=2, column=1).value or "").strip(),
        "sheet_name":      sheet.title,
        "source_file":     file_name,
    }

    records = []

    for row in sheet.iter_rows(
        min_row=4, min_col=1, max_col=8, values_only=True
    ):
        # Skip only fully empty rows
        if all(cell is None for cell in row):
            continue

        record = {
            "student_name":   str(row[0]).strip() if row[0] is not None else None,
            "roll_no":        str(row[1]).strip() if row[1] is not None else None,
            "father_name":    str(row[2]).strip() if row[2] is not None else None,
            "subject_name":   str(row[3]).strip() if row[3] is not None else None,
            "total_marks":    row[4],
            "obtained_marks": row[5],
            "credit_hours":   row[6],
            "department":     str(row[7]).strip() if row[7] is not None else None,
        }

        warnings = _build_warnings(record)
        record["has_issues"]     = len(warnings) > 0
        record["parse_warnings"] = warnings

        records.append(record)

    return {
        "status":    "parsed",
        "file_name": file_name,
        "file_type": "xlsx",
        "metadata":  metadata,
        "row_count": len(records),
        "records":   records,
    }


# ── FUNCTION 6 ────────────────────────────────────────────────
def parse_csv_file(file_path: str, file_name: str) -> dict:
    """
    Parses a .csv file using pandas.
    Expects the same 8 columns as the xlsx files.

    FIX APPLIED: Never skips rows — even rows with missing
    roll_no are passed through with warnings attached.
    This preserves all student records for HITL review.
    If we silently skip rows here, those students disappear
    from the system with no record of why.

    FIX APPLIED: Every record now carries has_issues and
    parse_warnings — identical structure to XLSX records.
    Engineer 2 receives consistent data regardless of
    whether the source file was .xlsx or .csv.
    """
    df = pd.read_csv(file_path)

    # Normalize column names
    df.columns = [
        col.strip().lower().replace(" ", "_") for col in df.columns
    ]

    # Skip only rows where every single column is NaN
    df = df.dropna(how="all")

    records = []

    for _, row in df.iterrows():

        record = {
            "student_name":   str(row.get("student_name", "")).strip() or None,
            "roll_no":        str(row.get("roll_no",       "")).strip() or None,
            "father_name":    str(row.get("father_name",   "")).strip() or None,
            "subject_name":   str(row.get("subject_name",  "")).strip() or None,
            "total_marks":    row.get("total_marks",    None) if pd.notna(row.get("total_marks",    None)) else None,
            "obtained_marks": row.get("obtained_marks", None) if pd.notna(row.get("obtained_marks", None)) else None,
            "credit_hours":   row.get("credit_hours",   None) if pd.notna(row.get("credit_hours",   None)) else None,
            "department":     str(row.get("department",    "")).strip() or None,
        }

        # Same warning system as XLSX — consistent for Engineer 2
        warnings = _build_warnings(record)
        record["has_issues"]     = len(warnings) > 0
        record["parse_warnings"] = warnings

        records.append(record)

    return {
        "status":    "parsed",
        "file_name": file_name,
        "file_type": "csv",
        "metadata":  {"source_file": file_name},
        "row_count": len(records),
        "records":   records,
    }


# ── FUNCTION 7 ────────────────────────────────────────────────
def parse_drive_files(folder_name: str = None) -> list[dict]:
    """
    MASTER FUNCTION — LangGraph calls this as Node 2.

    Full pipeline:
    1. Connect to Google Drive
    2. Find the root folder
    3. Crawl all folders recursively
    4. Download, parse, delete each file
    5. Return all results as a list of dicts
    """
    folder_name = folder_name or DRIVE_FOLDER_NAME

    service        = connect_to_drive()
    root_folder_id = find_root_folder(service, folder_name)

    all_files = []
    crawl_folder_recursively(service, root_folder_id, all_files)

    if not all_files:
        print(f"[ParserAgent] ⚠️  No Excel or CSV files found in '{folder_name}'.")
        return []

    print(f"\n[ParserAgent] 📊 Total files found: {len(all_files)}")

    all_results = []
    for file_info in all_files:
        try:
            result = download_and_parse_file(service, file_info)
            all_results.append(result)
            print(
                f"[ParserAgent] ✅ Parsed '{file_info['name']}' "
                f"— {result['row_count']} rows\n"
            )
        except Exception as e:
            print(f"[ParserAgent] ❌ Failed to parse '{file_info['name']}': {e}\n")
            continue

    print(f"[ParserAgent] 🎉 Done! Parsed {len(all_results)} files successfully.")
    return all_results


# ── QUICK TEST ────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    results = parse_drive_files()
    for r in results:
        print(json.dumps({
            "file":      r["file_name"],
            "rows":      r["row_count"],
            "first_row": r["records"][0] if r["records"] else None
        }, indent=2, ensure_ascii=False))
        
        #python src/agents/parser_agent.py