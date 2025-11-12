# """
# src/dashboard/transcript_generator.py
# ======================================
# University of Loralai — Agentic GPA System
# Automated PDF Transcript Generator

# Responsibilities
# ----------------
# • fetch_student_transcript_data(roll_no, db_url) → dict | None
#   Single-student DB query (new SQLAlchemy session per call → thread-safe).

# • fetch_multiple_transcripts(roll_nos, db_url, max_workers) → dict
#   Parallel fetch using ThreadPoolExecutor.
#   Returns {roll_no: data_dict | None}.

# • generate_transcript_pdf(student_data) → bytes
#   Produces an official-style A4 PDF matching the University of Loralai
#   transcript format (see WhatsApp_Image_2026-09-11 reference scan).

# • generate_bulk_zip(results_map) → bytes
#   Packages multiple PDFs into a ZIP archive for bulk download.

# Design Rules
# ------------
# • NEVER imports from validation_agent, calculator_agent, database_models,
#   or edge_cases — only from SQLAlchemy + DB URL string.
# • SQLAlchemy models are imported conditionally so the module loads even if
#   the DB package is unavailable (graceful failure path).
# • ReportLab 4.x platypus API — no canvas-level drawing except borders.
# • All colours match the dashboard's enterprise design system (#0F2444 navy).

# Tech Lead : Arif Khan
# """

# from __future__ import annotations

# import concurrent.futures
# import io
# import zipfile
# from datetime import datetime
# from typing import Any

# # ─── ReportLab imports ────────────────────────────────────────────────────────
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# from reportlab.lib.units import mm
# from reportlab.platypus import (
#     HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
#     TableStyle,
# )

# # ─── Page geometry ────────────────────────────────────────────────────────────
# _MARGIN    = 15 * mm
# _PAGE_W, _ = A4

# # Exact column widths that sum to 180 mm (A4 − 2 × 15 mm margins)
# #  S.No | Subject | C.Hrs | Marks/100 | G.P | Grade
# _COL = [12*mm, 70*mm, 16*mm, 30*mm, 28*mm, 24*mm]

# # ─── Colour palette (matches enterprise dashboard) ────────────────────────────
# _NAVY   = colors.HexColor("#0F2444")
# _NAVY_L = colors.HexColor("#1E3A6E")
# _LIGHT  = colors.HexColor("#F1F5F9")
# _MID    = colors.HexColor("#E2E8F0")
# _GREEN  = colors.HexColor("#DCFCE7")
# _AMBER  = colors.HexColor("#FEF3C7")
# _RED    = colors.HexColor("#FEE2E2")
# _WHITE  = colors.white


# # ──────────────────────────────────────────────────────────────────────────────
# # GRADE TABLE  (HEC Pakistan — read-only, matches calculator_agent.py exactly)
# # ──────────────────────────────────────────────────────────────────────────────

# def _grade_letter(gp: float | None) -> str:
#     """Convert a HEC grade point to the standard letter grade."""
#     if gp is None:
#         return "—"
#     if gp >= 4.00: return "A"
#     if gp >= 3.70: return "A-"
#     if gp >= 3.30: return "B+"
#     if gp >= 3.00: return "B"
#     if gp >= 2.70: return "B-"
#     if gp >= 2.30: return "C+"
#     if gp >= 2.00: return "C"
#     if gp >= 1.70: return "C-"
#     if gp >= 1.00: return "D"
#     return "F"


# def _ordinal(n: int) -> str:
#     """Return e.g. '1st', '2nd', '3rd', '4th' …"""
#     suffix = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
#     return f"{n}{suffix}"


# # ──────────────────────────────────────────────────────────────────────────────
# # DATABASE FETCH
# # ──────────────────────────────────────────────────────────────────────────────

# def fetch_student_transcript_data(
#     roll_no: str,
#     db_url: str,
# ) -> dict[str, Any] | None:
#     """
#     Query the DB for one student and return a fully-denormalised transcript
#     dict, or None if the roll number is not found.

#     A new SQLAlchemy session is created and closed within this function so
#     that it is safe to call concurrently from multiple threads.
#     """
#     # Local imports so the module loads even when SQLAlchemy is absent
#     try:
#         from sqlalchemy import create_engine, select
#         from sqlalchemy.orm import sessionmaker
#         from src.models.database_models import (
#             CGPA, Mark, SemesterGPA, Student, Subject,
#         )
#     except ImportError as exc:
#         raise RuntimeError(f"DB dependencies not available: {exc}") from exc

#     connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
#     engine = create_engine(db_url, connect_args=connect_args)
#     Session = sessionmaker(bind=engine)
#     session = Session()

#     try:
#         student: Student | None = session.execute(
#             select(Student).where(Student.roll_no.ilike(f"%{roll_no.strip()}%"))
#         ).scalars().first()

#         if student is None:
#             return None

#         marks: list[Mark] = session.execute(
#             select(Mark)
#             .where(Mark.student_id == student.id)
#             .order_by(Mark.semester, Mark.subject_id)
#         ).scalars().all()

#         subjects_map: dict[int, Subject] = {
#             s.id: s
#             for s in session.execute(select(Subject)).scalars().all()
#         }

#         sgpas: list[SemesterGPA] = session.execute(
#             select(SemesterGPA)
#             .where(SemesterGPA.student_id == student.id)
#             .order_by(SemesterGPA.semester)
#         ).scalars().all()

#         cgpa_row: CGPA | None = session.execute(
#             select(CGPA).where(CGPA.student_id == student.id)
#         ).scalar_one_or_none()

#         # ── Infer session from semester-1 academic_year ────────────────────────
#         # e.g. "2022-2023" → session "2022-2026"  (4-year BS degree)
#         sem1_marks = [m for m in marks if m.semester == 1]
#         academic_session = "—"
#         if sem1_marks:
#             ay = sem1_marks[0].academic_year or ""
#             try:
#                 start_yr = int(ay.split("-")[0].strip())
#                 academic_session = f"{start_yr}-{start_yr + 4}"
#             except (ValueError, IndexError):
#                 academic_session = ay

#         # ── Group marks by semester ────────────────────────────────────────────
#         by_sem: dict[int, list[Mark]] = {}
#         for m in marks:
#             by_sem.setdefault(m.semester, []).append(m)

#         sgpa_map: dict[int, SemesterGPA] = {sg.semester: sg for sg in sgpas}

#         # Build running CGPA so each semester card shows it cumulatively
#         running_ch = running_qp = 0.0
#         cgpa_after: dict[int, float | None] = {}
#         for sn in sorted(by_sem.keys()):
#             sg = sgpa_map.get(sn)
#             if sg:
#                 running_ch += sg.total_credit_hours or 0.0
#                 running_qp += sg.total_quality_points or 0.0
#             cgpa_after[sn] = (
#                 round(running_qp / running_ch, 2) if running_ch > 0 else None
#             )

#         semesters_out = []
#         for sn in sorted(by_sem.keys()):
#             sg = sgpa_map.get(sn)
#             sem_marks = by_sem[sn]
#             subjects_out = []
#             for m in sem_marks:
#                 sub = subjects_map.get(m.subject_id)
#                 subjects_out.append(
#                     {
#                         "name"          : sub.subject_name if sub else f"Subject {m.subject_id}",
#                         "credit_hours"  : sub.credit_hours if sub else 0,
#                         "obtained_marks": m.obtained_marks,
#                         "total_marks"   : m.total_marks,
#                         "percentage"    : m.percentage,
#                         "grade_point"   : m.grade_point,
#                         "grade"         : _grade_letter(m.grade_point),
#                         "quality_points": m.quality_points,
#                         "is_non_credit" : m.is_non_credit,
#                     }
#                 )
#             semesters_out.append(
#                 {
#                     "number"              : sn,
#                     "academic_year"       : sem_marks[0].academic_year if sem_marks else "—",
#                     "subjects"            : subjects_out,
#                     "gpa"                 : sg.gpa if sg else None,
#                     "total_credit_hours"  : sg.total_credit_hours if sg else 0.0,
#                     "total_quality_points": sg.total_quality_points if sg else 0.0,
#                     "cgpa_after"          : cgpa_after.get(sn),
#                 }
#             )

#         return {
#             "student_id"         : student.id,
#             "student_name"       : student.student_name,
#             "roll_no"            : student.roll_no,
#             "father_name"        : student.father_name or "—",
#             "department"         : student.department or "BS Computer Science",
#             "session"            : academic_session,
#             "ref_no"             : f"CoE/UoL {student.id}",
#             "date"               : datetime.now().strftime("%d-%m-%Y"),
#             "semesters"          : semesters_out,
#             "cgpa"               : cgpa_row.cgpa if cgpa_row else None,
#             "total_credit_hours" : cgpa_row.total_credit_hours if cgpa_row else 0.0,
#             "semesters_completed": cgpa_row.semesters_completed if cgpa_row else len(semesters_out),
#         }

#     finally:
#         session.close()


# def fetch_multiple_transcripts(
#     roll_nos: list[str],
#     db_url: str,
#     max_workers: int = 8,
# ) -> dict[str, dict[str, Any] | None]:
#     """
#     Parallel fetch for a list of roll numbers.
#     Returns {roll_no: data_dict | None} — None means not found.
#     Order is preserved in the return dict.
#     """
#     results: dict[str, dict | None] = {}

#     with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
#         future_map = {
#             pool.submit(fetch_student_transcript_data, rn, db_url): rn
#             for rn in roll_nos
#         }
#         for future in concurrent.futures.as_completed(future_map):
#             rn = future_map[future]
#             try:
#                 results[rn] = future.result()
#             except Exception as exc:
#                 results[rn] = {"_error": str(exc)}

#     # Re-order to match the original input list
#     return {rn: results.get(rn) for rn in roll_nos}


# # ──────────────────────────────────────────────────────────────────────────────
# # PARAGRAPH STYLES
# # ──────────────────────────────────────────────────────────────────────────────

# def _make_styles() -> dict[str, ParagraphStyle]:
#     base = getSampleStyleSheet()["Normal"]
#     return {
#         "N"  : ParagraphStyle("N",  parent=base, fontSize=9,  leading=11),
#         "NR" : ParagraphStyle("NR", parent=base, fontSize=9,  leading=11, alignment=TA_RIGHT),
#         "NC" : ParagraphStyle("NC", parent=base, fontSize=9,  leading=11, alignment=TA_CENTER),
#         "NB" : ParagraphStyle("NB", parent=base, fontSize=9,  leading=11, fontName="Helvetica-Bold"),
#         "NBC": ParagraphStyle("NBC",parent=base, fontSize=9,  leading=11, fontName="Helvetica-Bold",
#                               alignment=TA_CENTER),
#         "NRL": ParagraphStyle("NRL",parent=base, fontSize=9,  leading=11, fontName="Helvetica-Bold",
#                               alignment=TA_LEFT),
#         "SM" : ParagraphStyle("SM", parent=base, fontSize=8,  leading=10, alignment=TA_CENTER),
#         "H1" : ParagraphStyle("H1", parent=base, fontSize=18, leading=22, fontName="Helvetica-Bold",
#                               alignment=TA_CENTER, spaceAfter=2),
#         "H2" : ParagraphStyle("H2", parent=base, fontSize=11, leading=14, alignment=TA_CENTER,
#                               spaceAfter=4),
#         "INFO": ParagraphStyle("INFO", parent=base, fontSize=9, leading=12, alignment=TA_LEFT),
#         "FIN" : ParagraphStyle("FIN", parent=base, fontSize=11, leading=14, fontName="Helvetica-Bold",
#                                alignment=TA_CENTER),
#     }


# # ──────────────────────────────────────────────────────────────────────────────
# # SEMESTER TABLE BUILDER
# # ──────────────────────────────────────────────────────────────────────────────

# def _semester_table(sem: dict[str, Any], st: dict[str, ParagraphStyle]) -> Table:
#     """Build one semester's ReportLab Table (header + rows + GPA footer)."""
#     N, NC, NB, NBC, SM = st["N"], st["NC"], st["NB"], st["NBC"], st["SM"]

#     sem_label = f"{_ordinal(sem['number'])} Semester"
#     subjects  = sem["subjects"]
#     gpa_val   = sem["gpa"]
#     n_rows    = len(subjects)

#     rows: list[list] = []

#     # Row 0 — Semester name header (spans S.No + Subject cols)
#     rows.append([
#         Paragraph(f"<b>{sem_label}</b>", NBC),
#         "",  # span
#         "",  # span
#         Paragraph("<b>Marks</b>", NBC),
#         Paragraph("<b>G.P</b>", NBC),
#         Paragraph("<b>Grade</b>", NBC),
#     ])

#     # Row 1 — Column sub-headers
#     rows.append([
#         Paragraph("<b>S. No</b>", NBC),
#         Paragraph("<b>Subject</b>", NB),
#         Paragraph("<b>C. Hrs</b>", NBC),
#         Paragraph("<b>100</b>", NBC),
#         Paragraph("", NBC),
#         Paragraph("", NBC),
#     ])

#     # Data rows
#     for i, subj in enumerate(subjects, 1):
#         nc_flag = " ●" if subj["is_non_credit"] else ""
#         marks_display = (
#             f"{subj['obtained_marks']:.0f}"
#             if subj["total_marks"] == 100
#             else f"{subj['percentage']:.1f}%"
#         )
#         rows.append([
#             Paragraph(str(i), NC),
#             Paragraph(f"{subj['name']}{nc_flag}", N),
#             Paragraph(str(subj["credit_hours"]), NC),
#             Paragraph(marks_display, NC),
#             Paragraph(f"{subj['grade_point']:.2f}", NC),
#             Paragraph(subj["grade"], NC),
#         ])

#     # GPA summary row
#     gpa_str = f"<b>{gpa_val:.2f}</b>" if gpa_val is not None else "<b>—</b>"
#     rows.append([
#         "",
#         Paragraph("<b>Grade Point Average (GPA)</b>", NB),
#         "",  # span over C.Hrs
#         "",  # span over Marks
#         Paragraph(gpa_str, NBC),
#         "",
#     ])

#     total_rows = len(rows)
#     last       = total_rows - 1

#     tbl = Table(rows, colWidths=_COL, repeatRows=2)

#     row_bg_cmds = []
#     for r in range(2, last):
#         bg = _WHITE if (r - 2) % 2 == 0 else colors.HexColor("#FAFBFC")
#         row_bg_cmds.append(("BACKGROUND", (0, r), (-1, r), bg))

#     tbl.setStyle(TableStyle([
#         # ── Merges ──────────────────────────────────────────────────────────
#         ("SPAN", (0, 0),    (2, 0)),               # semester label
#         ("SPAN", (1, last), (3, last)),            # GPA label span
#         ("SPAN", (4, last), (5, last)),            # GPA value span

#         # ── Background colours ───────────────────────────────────────────────
#         ("BACKGROUND", (0, 0),    (-1, 0),    _NAVY),
#         ("TEXTCOLOR",  (0, 0),    (-1, 0),    _WHITE),
#         ("BACKGROUND", (0, 1),    (-1, 1),    _LIGHT),
#         ("BACKGROUND", (0, last), (-1, last), _MID),

#         # ── Borders ─────────────────────────────────────────────────────────
#         ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),

#         # ── Alignment ───────────────────────────────────────────────────────
#         ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
#         ("ALIGN",   (1, 2), (1, last - 1), "LEFT"),
#         ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),

#         # ── Padding ─────────────────────────────────────────────────────────
#         ("TOPPADDING",    (0, 0), (-1, -1), 3),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
#         ("LEFTPADDING",   (1, 2), (1, last - 1), 4),
#         *row_bg_cmds,
#     ]))

#     return tbl


# # ──────────────────────────────────────────────────────────────────────────────
# # SIGNATURE BLOCK
# # ──────────────────────────────────────────────────────────────────────────────

# def _signature_table(st: dict[str, ParagraphStyle]) -> Table:
#     """Render the two-column signature / seal area at the bottom of a transcript."""
#     NC, N = st["NC"], st["N"]

#     sig_line = HRFlowable(width="85%", thickness=0.8, color=colors.black)
#     rows = [
#         [
#             Paragraph("", NC),
#             Paragraph("", NC),
#         ],
#         [
#             Paragraph("", NC),
#             Paragraph("", NC),
#         ],
#         [
#             Paragraph("_" * 28, NC),
#             Paragraph("_" * 28, NC),
#         ],
#         [
#             Paragraph("<b>Deputy Controller</b>", NC),
#             Paragraph("<b>Controller of Examinations</b>", NC),
#         ],
#     ]
#     tbl = Table(rows, colWidths=["50%", "50%"])
#     tbl.setStyle(TableStyle([
#         ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
#         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#         ("TOPPADDING",    (0, 0), (-1, -1), 4),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
#     ]))
#     return tbl


# # ──────────────────────────────────────────────────────────────────────────────
# # MAIN PDF GENERATOR
# # ──────────────────────────────────────────────────────────────────────────────

# def generate_transcript_pdf(
#     student_data: dict[str, Any],
#     unofficial: bool = True,
# ) -> bytes:
#     """
#     Generate an A4 PDF transcript byte stream for one student.

#     Parameters
#     ----------
#     student_data : dict returned by fetch_student_transcript_data()
#     unofficial   : if True, stamps "Unofficial Transcript" in the header.
#                    Set to False for official prints (future use).

#     Returns
#     -------
#     bytes — raw PDF bytes ready for Streamlit download_button().
#     """
#     buf = io.BytesIO()
#     doc = SimpleDocTemplate(
#         buf,
#         pagesize=A4,
#         leftMargin=_MARGIN,
#         rightMargin=_MARGIN,
#         topMargin=_MARGIN,
#         bottomMargin=_MARGIN,
#         title=f"Transcript – {student_data.get('roll_no', '')}",
#         author="University of Loralai – CoE Office",
#     )

#     st = _make_styles()
#     story: list = []

#     # ── University header ──────────────────────────────────────────────────────
#     story.append(Paragraph("<b>UNIVERSITY OF LORALAI</b>", st["H1"]))
#     label = "Unofficial Transcript" if unofficial else "Official Transcript"
#     story.append(Paragraph(f"<u>{label}</u>", st["H2"]))
#     story.append(HRFlowable(width="100%", thickness=2, color=_NAVY, spaceAfter=4))
#     story.append(Spacer(1, 2 * mm))

#     # ── Ref No + Date ──────────────────────────────────────────────────────────
#     ref_date = Table(
#         [[
#             Paragraph(f"Ref No: {student_data.get('ref_no', '—')}", st["N"]),
#             Paragraph(f"Date: {student_data.get('date', datetime.now().strftime('%d-%m-%Y'))}",
#                       st["NR"]),
#         ]],
#         colWidths=["50%", "50%"],
#     )
#     ref_date.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
#     story.append(ref_date)
#     story.append(Spacer(1, 3 * mm))

#     # ── Student information ────────────────────────────────────────────────────
#     stu_info = Table(
#         [
#             [
#                 Paragraph(f"<b>Name of Student:</b>  {student_data['student_name']}", st["INFO"]),
#                 Paragraph(f"<b>Father Name:</b>  {student_data.get('father_name', '—')}", st["INFO"]),
#             ],
#             [
#                 Paragraph(f"<b>Registration No:</b>  {student_data['roll_no']}", st["INFO"]),
#                 Paragraph(f"<b>Session:</b>  {student_data.get('session', '—')}", st["INFO"]),
#             ],
#             [
#                 Paragraph(
#                     f"<b>Program of Study:</b>  {student_data.get('department', '—')}",
#                     st["INFO"],
#                 ),
#                 Paragraph("", st["INFO"]),
#             ],
#         ],
#         colWidths=["55%", "45%"],
#     )
#     stu_info.setStyle(TableStyle([
#         ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
#         ("TOPPADDING",    (0, 0), (-1, -1), 3),
#     ]))
#     story.append(stu_info)
#     story.append(Spacer(1, 5 * mm))

#     # ── Per-semester tables ────────────────────────────────────────────────────
#     for i, sem in enumerate(student_data.get("semesters", [])):
#         sem_tbl = _semester_table(sem, st)
#         story.append(KeepTogether([sem_tbl]))
#         story.append(Spacer(1, 4 * mm))

#     # ── CGPA footer ───────────────────────────────────────────────────────────
#     cgpa_val = student_data.get("cgpa")
#     cgpa_str = f"{cgpa_val:.2f}" if cgpa_val is not None else "—"
#     ch_total = student_data.get("total_credit_hours", 0)

#     cgpa_tbl = Table(
#         [[
#             Paragraph("", st["N"]),
#             Paragraph(
#                 f"<b>Cumulative Grade Point Average (CGPA):  {cgpa_str}</b>",
#                 st["FIN"],
#             ),
#             Paragraph("", st["N"]),
#         ]],
#         colWidths=["10%", "80%", "10%"],
#     )
#     cgpa_tbl.setStyle(TableStyle([
#         ("BOX",           (0, 0), (-1, -1), 1.5, _NAVY),
#         ("BACKGROUND",    (0, 0), (-1, -1), _LIGHT),
#         ("TOPPADDING",    (0, 0), (-1, -1), 6),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
#     ]))
#     story.append(cgpa_tbl)
#     story.append(Spacer(1, 3 * mm))

#     # Credit hours note
#     story.append(Paragraph(
#         f"Total Credit Hours Completed: {ch_total:.0f}  "
#         f"| Semesters Completed: {student_data.get('semesters_completed', 0)}  "
#         f"| ● = Non-credit subject (excluded from GPA weight)",
#         ParagraphStyle(
#             "note", parent=_make_styles()["N"], fontSize=7.5,
#             textColor=colors.HexColor("#64748B"), alignment=TA_CENTER,
#         ),
#     ))
#     story.append(Spacer(1, 10 * mm))

#     # ── Signature area ────────────────────────────────────────────────────────
#     story.append(HRFlowable(width="100%", thickness=0.5, color=_MID))
#     story.append(Spacer(1, 6 * mm))
#     story.append(_signature_table(st))

#     doc.build(story)
#     return buf.getvalue()


# # ──────────────────────────────────────────────────────────────────────────────
# # BULK ZIP CREATOR
# # ──────────────────────────────────────────────────────────────────────────────

# def generate_bulk_zip(
#     results_map: dict[str, dict[str, Any] | None],
#     unofficial: bool = True,
# ) -> bytes:
#     """
#     Package multiple generated PDFs into one ZIP archive.

#     Parameters
#     ----------
#     results_map : {roll_no: student_data_dict | None}
#                   None entries (not found) are skipped silently.
#     unofficial  : forwarded to generate_transcript_pdf().

#     Returns
#     -------
#     bytes — ZIP file bytes ready for Streamlit download_button().
#     """
#     buf = io.BytesIO()
#     with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
#         for roll_no, data in results_map.items():
#             if data is None or "_error" in (data or {}):
#                 continue
#             try:
#                 pdf_bytes = generate_transcript_pdf(data, unofficial=unofficial)
#                 safe_name = roll_no.replace("/", "_").replace("\\", "_")
#                 zf.writestr(f"{safe_name}_transcript.pdf", pdf_bytes)
#             except Exception:
#                 pass  # skip failed individual PDFs — caller sees partial ZIP
#     return buf.getvalue()



# """
# src/dashboard/transcript_generator.py
# ======================================
# University of Loralai — Agentic GPA System
# Automated PDF Transcript Generator  (v3 — exact official format match)

# Key design goals
# ----------------
# * Layout, fonts, borders, and proportions match the UoL official transcript
#   (reference: WhatsApp_Image_2026-09-11 scan).
# * Times-Roman / Times-Bold throughout (matches the scanned document font).
# * University crest logo embedded top-left.
# * Semester table structure:
#     Row 0 : "Nth Semester" (spans S.No+Subject) | C.Hrs | Marks | G.P | Grade
#     Row 1 : S.No | Subject | blank | 100 | blank | blank
#     Data rows  …
#     GPA row : blank | "Grade Point Average (GPA)" (span) | | value | blank
# * CGPA section followed by dual-signature area.
# * generate_transcript_pdf() accepts an optional logo_path; falls back cleanly
#   when no logo file exists.

# Tech Lead : Arif Khan
# """

# from __future__ import annotations

# import concurrent.futures
# import io
# import os
# import re
# import zipfile
# from datetime import datetime
# from typing import Any

# # ── ReportLab ────────────────────────────────────────────────────────────────
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# from reportlab.lib.units import mm
# from reportlab.platypus import (
#     HRFlowable, Image, KeepTogether, Paragraph,
#     SimpleDocTemplate, Spacer, Table, TableStyle,
# )

# # ── Page geometry ─────────────────────────────────────────────────────────────
# _MARGIN     = 15 * mm
# _PAGE_W, _  = A4

# # Column widths — sum = 180 mm (A4 − 2 × 15 mm margins)
# # S.No | Subject | C.Hrs | Marks | G.P | Grade
# _COL = [12*mm, 82*mm, 20*mm, 26*mm, 22*mm, 18*mm]

# # ── Colours (match the printed document — minimal / black-on-white) ───────────
# _BLACK      = colors.black
# _SEM_HDR_BG = colors.HexColor("#E8E8E8")   # semester header row — light gray
# _SUB_HDR_BG = colors.HexColor("#F5F5F5")   # S.No / Subject sub-header — very light
# _GPA_ROW_BG = colors.HexColor("#EFEFEF")   # GPA summary row
# _WHITE      = colors.white

# # ── Fonts ─────────────────────────────────────────────────────────────────────
# _F  = "Times-Roman"
# _FB = "Times-Bold"
# _FI = "Times-Italic"


# # ─────────────────────────────────────────────────────────────────────────────
# # GRADE HELPERS
# # ─────────────────────────────────────────────────────────────────────────────

# def _grade_letter(gp: float | None) -> str:
#     if gp is None: return "—"
#     if gp >= 4.00: return "A"
#     if gp >= 3.70: return "A-"
#     if gp >= 3.30: return "B+"
#     if gp >= 3.00: return "B"
#     if gp >= 2.70: return "B-"
#     if gp >= 2.30: return "C+"
#     if gp >= 2.00: return "C"
#     if gp >= 1.70: return "C-"
#     if gp >= 1.00: return "D"
#     return "F"


# def _ordinal(n: int) -> str:
#     sfx = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
#     return f"{n}{sfx}"


# # ─────────────────────────────────────────────────────────────────────────────
# # DATABASE FETCH  (one session per call — thread-safe for parallel use)
# # ─────────────────────────────────────────────────────────────────────────────

# def fetch_student_transcript_data(
#     roll_no: str,
#     db_url: str,
# ) -> dict[str, Any] | None:
#     """Query DB and return a fully-denormalised transcript dict, or None."""
#     try:
#         from sqlalchemy import create_engine, select
#         from sqlalchemy.orm import sessionmaker
#         from src.models.database_models import CGPA, Mark, SemesterGPA, Student, Subject
#     except ImportError as exc:
#         raise RuntimeError(f"DB dependencies not available: {exc}") from exc

#     kwargs = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
#     engine  = create_engine(db_url, connect_args=kwargs)
#     session = sessionmaker(bind=engine)()

#     try:
#         student = session.execute(
#             select(Student).where(Student.roll_no.ilike(f"%{roll_no.strip()}%"))
#         ).scalars().first()
#         if student is None:
#             return None

#         marks = session.execute(
#             select(Mark)
#             .where(Mark.student_id == student.id)
#             .order_by(Mark.semester, Mark.subject_id)
#         ).scalars().all()

#         subj_map = {
#             s.id: s
#             for s in session.execute(select(Subject)).scalars().all()
#         }
#         sgpas = session.execute(
#             select(SemesterGPA)
#             .where(SemesterGPA.student_id == student.id)
#             .order_by(SemesterGPA.semester)
#         ).scalars().all()
#         cgpa_row = session.execute(
#             select(CGPA).where(CGPA.student_id == student.id)
#         ).scalar_one_or_none()

#         # ── Session inference (prefer roll-number year over academic_year) ────
#         # Pattern: UoL/CS-F-22/001-BS → enrollment year 2022
#         m = re.search(r"[/-]F[-/](\d{2})[/-]", student.roll_no or "")
#         if m:
#             yr = 2000 + int(m.group(1))
#             academic_session = f"{yr}-{yr + 4}"
#         else:
#             sem1 = [mk for mk in marks if mk.semester == 1]
#             academic_session = "—"
#             if sem1:
#                 try:
#                     yr = int(sem1[0].academic_year.split("-")[0])
#                     academic_session = f"{yr}-{yr + 4}"
#                 except Exception:
#                     academic_session = sem1[0].academic_year or "—"

#         # ── Build per-semester structure ──────────────────────────────────────
#         by_sem: dict[int, list] = {}
#         for mk in marks:
#             by_sem.setdefault(mk.semester, []).append(mk)

#         sgpa_map = {sg.semester: sg for sg in sgpas}
#         run_ch = run_qp = 0.0
#         cgpa_after: dict[int, float | None] = {}
#         for sn in sorted(by_sem):
#             sg = sgpa_map.get(sn)
#             if sg:
#                 run_ch += sg.total_credit_hours or 0.0
#                 run_qp += sg.total_quality_points or 0.0
#             cgpa_after[sn] = round(run_qp / run_ch, 2) if run_ch > 0 else None

#         semesters_out = []
#         for sn in sorted(by_sem):
#             sg   = sgpa_map.get(sn)
#             smks = by_sem[sn]
#             subjects_out = []
#             for mk in smks:
#                 sub = subj_map.get(mk.subject_id)
#                 subjects_out.append({
#                     "name"          : sub.subject_name if sub else f"Subject {mk.subject_id}",
#                     "credit_hours"  : sub.credit_hours if sub else 0,
#                     "obtained_marks": mk.obtained_marks,
#                     "total_marks"   : mk.total_marks,
#                     "percentage"    : mk.percentage,
#                     "grade_point"   : mk.grade_point,
#                     "grade"         : _grade_letter(mk.grade_point),
#                     "quality_points": mk.quality_points,
#                     "is_non_credit" : mk.is_non_credit,
#                 })
#             semesters_out.append({
#                 "number"              : sn,
#                 "academic_year"       : smks[0].academic_year if smks else "—",
#                 "subjects"            : subjects_out,
#                 "gpa"                 : sg.gpa if sg else None,
#                 "total_credit_hours"  : sg.total_credit_hours if sg else 0.0,
#                 "total_quality_points": sg.total_quality_points if sg else 0.0,
#                 "cgpa_after"          : cgpa_after.get(sn),
#             })

#         # ── Expand department label ───────────────────────────────────────────
#         dept_raw = (student.department or "").strip()
#         dept_label = (
#             "BS Computer Science" if dept_raw.upper() in ("CS", "BSCS")
#             else dept_raw if dept_raw else "BS Computer Science"
#         )

#         return {
#             "student_id"         : student.id,
#             "student_name"       : student.student_name,
#             "roll_no"            : student.roll_no,
#             "father_name"        : student.father_name or "—",
#             "department"         : dept_label,
#             "session"            : academic_session,
#             "ref_no"             : f"CoE/UoL {student.id}",
#             "date"               : datetime.now().strftime("%d-%m-%Y"),
#             "semesters"          : semesters_out,
#             "cgpa"               : cgpa_row.cgpa if cgpa_row else None,
#             "total_credit_hours" : cgpa_row.total_credit_hours if cgpa_row else 0.0,
#             "semesters_completed": cgpa_row.semesters_completed if cgpa_row else len(semesters_out),
#         }
#     finally:
#         session.close()


# def fetch_multiple_transcripts(
#     roll_nos: list[str],
#     db_url: str,
#     max_workers: int = 8,
# ) -> dict[str, dict | None]:
#     """Parallel fetch for multiple roll numbers. Returns {roll_no: data | None}."""
#     results: dict[str, dict | None] = {}
#     with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
#         fmap = {pool.submit(fetch_student_transcript_data, rn, db_url): rn for rn in roll_nos}
#         for fut in concurrent.futures.as_completed(fmap):
#             rn = fmap[fut]
#             try:
#                 results[rn] = fut.result()
#             except Exception as exc:
#                 results[rn] = {"_error": str(exc)}
#     return {rn: results.get(rn) for rn in roll_nos}


# # ─────────────────────────────────────────────────────────────────────────────
# # PARAGRAPH STYLES  (Times-Roman throughout to match official)
# # ─────────────────────────────────────────────────────────────────────────────

# def _styles() -> dict[str, ParagraphStyle]:
#     base = getSampleStyleSheet()["Normal"]
#     def P(name, font=_F, **kw):
#         return ParagraphStyle(name, parent=base, fontName=font, **kw)

#     return {
#         # ── University header ─────────────────────────────────────────────────
#         "UNI"  : P("UNI",   font=_FB, fontSize=16, leading=20, alignment=TA_CENTER),
#         "SUB"  : P("SUB",   font=_F,  fontSize=11, leading=14, alignment=TA_CENTER),
#         # ── Reference / student info ──────────────────────────────────────────
#         "INFO" : P("INFO",  font=_F,  fontSize=9.5, leading=13),
#         "INFOR": P("INFOR", font=_F,  fontSize=9.5, leading=13, alignment=TA_RIGHT),
#         # ── Table cells ───────────────────────────────────────────────────────
#         "TC"   : P("TC",    font=_F,  fontSize=9, leading=11, alignment=TA_CENTER),
#         "TL"   : P("TL",    font=_F,  fontSize=9, leading=11, alignment=TA_LEFT),
#         "TBC"  : P("TBC",   font=_FB, fontSize=9, leading=11, alignment=TA_CENTER),
#         "TBL"  : P("TBL",   font=_FB, fontSize=9, leading=11, alignment=TA_LEFT),
#         "TBR"  : P("TBR",   font=_FB, fontSize=9, leading=11, alignment=TA_RIGHT),
#         # ── CGPA line ─────────────────────────────────────────────────────────
#         "CGPA" : P("CGPA",  font=_FB, fontSize=10, leading=13, alignment=TA_LEFT),
#         "CGPAR": P("CGPAR", font=_FB, fontSize=10, leading=13, alignment=TA_RIGHT),
#         # ── Signature labels ──────────────────────────────────────────────────
#         "SIG"  : P("SIG",   font=_F,  fontSize=9,  leading=11, alignment=TA_CENTER),
#         "NOTE" : P("NOTE",  font=_F,  fontSize=7.5, leading=10, alignment=TA_CENTER,
#                    textColor=colors.HexColor("#555555")),
#     }


# # ─────────────────────────────────────────────────────────────────────────────
# # SEMESTER TABLE  — exact match to official UoL format
# # ─────────────────────────────────────────────────────────────────────────────

# def _semester_table(sem: dict, st: dict) -> Table:
#     """
#     Builds one semester section as a ReportLab Table.

#     Column order : S.No | Subject | C.Hrs | Marks/100 | G.P | Grade
#     Row 0        : "Nth Semester" (span cols 0-1) | C.Hrs | Marks | G.P | Grade
#     Row 1        : S. No | Subject | blank | 100 | blank | blank
#     Rows 2..N-1  : data
#     Row N        : GPA summary
#     """
#     TC, TL, TBC, TBL = st["TC"], st["TL"], st["TBC"], st["TBL"]

#     sn        = sem["number"]
#     subjects  = sem["subjects"]
#     gpa_val   = sem["gpa"]
#     n_data    = len(subjects)
#     last      = n_data + 2     # row index of GPA row

#     rows: list[list] = []

#     # ── Row 0 : semester header ───────────────────────────────────────────────
#     rows.append([
#         Paragraph(f"<b>{_ordinal(sn)} Semester</b>", TBC),
#         "",   # SPAN with col 0
#         Paragraph("<b>C. Hrs</b>", TBC),
#         Paragraph("<b>Marks</b>",  TBC),
#         Paragraph("<b>G.P</b>",    TBC),
#         Paragraph("<b>Grade</b>",  TBC),
#     ])

#     # ── Row 1 : sub-header ───────────────────────────────────────────────────
#     rows.append([
#         Paragraph("<b>S. No</b>", TBC),
#         Paragraph("<b>Subject</b>", TBL),
#         Paragraph("", TBC),
#         Paragraph("<b>100</b>",   TBC),
#         Paragraph("", TBC),
#         Paragraph("", TBC),
#     ])

#     # ── Data rows ─────────────────────────────────────────────────────────────
#     for i, subj in enumerate(subjects, 1):
#         nc_mark = "*" if subj["is_non_credit"] else ""
#         marks_str = (
#             str(int(subj["obtained_marks"]))
#             if subj["total_marks"] == 100
#             else f"{subj['percentage']:.1f}%"
#         )
#         rows.append([
#             Paragraph(str(i), TC),
#             Paragraph(subj["name"] + nc_mark, TL),
#             Paragraph(str(subj["credit_hours"]), TC),
#             Paragraph(marks_str,                TC),
#             Paragraph(f"{subj['grade_point']:.2f}", TC),
#             Paragraph(subj["grade"],            TC),
#         ])

#     # ── GPA row ───────────────────────────────────────────────────────────────
#     gpa_str = f"{gpa_val:.2f}" if gpa_val is not None else "—"
#     rows.append([
#         Paragraph("", TC),
#         Paragraph("<b>Grade Point Average (GPA)</b>", TBL),
#         Paragraph("", TC),   # will be merged into GPA label span
#         Paragraph("", TC),   # will be merged into GPA label span
#         Paragraph(f"<b>{gpa_str}</b>", TBC),
#         Paragraph("", TC),
#     ])

#     tbl = Table(rows, colWidths=_COL, repeatRows=2)

#     # ── Alternating row backgrounds for data rows ─────────────────────────────
#     alt_bg = []
#     for r in range(2, last):
#         bg = _WHITE if (r - 2) % 2 == 0 else colors.HexColor("#FAFAFA")
#         alt_bg.append(("BACKGROUND", (0, r), (-1, r), bg))

#     tbl.setStyle(TableStyle([
#         # Merges
#         ("SPAN", (0, 0),    (1, 0)),            # "Nth Semester" label
#         ("SPAN", (1, last), (3, last)),         # GPA label

#         # Header backgrounds
#         ("BACKGROUND", (0, 0), (-1, 0), _SEM_HDR_BG),
#         ("BACKGROUND", (0, 1), (-1, 1), _SUB_HDR_BG),
#         ("BACKGROUND", (0, last), (-1, last), _GPA_ROW_BG),

#         # Grid — thin black borders everywhere
#         ("BOX",  (0, 0), (-1, -1), 0.6, _BLACK),
#         ("GRID", (0, 0), (-1, -1), 0.4, _BLACK),

#         # Alignment
#         ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
#         ("ALIGN",  (1, 2), (1, last), "LEFT"),
#         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

#         # Padding
#         ("TOPPADDING",    (0, 0), (-1, -1), 3),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
#         ("LEFTPADDING",   (1, 2), (1, last), 3),

#         *alt_bg,
#     ]))
#     return tbl


# # ─────────────────────────────────────────────────────────────────────────────
# # PDF GENERATOR  — main public function
# # ─────────────────────────────────────────────────────────────────────────────

# # Default logo path — set once here; app.py overrides via the logo_path param
# _DEFAULT_LOGO = os.path.join(
#     os.path.dirname(__file__), "assets", "uol_logo.png"
# )


# def generate_transcript_pdf(
#     student_data: dict[str, Any],
#     unofficial: bool = True,
#     logo_path: str | None = None,
# ) -> bytes:
#     """
#     Generate an A4 PDF transcript that exactly matches the UoL official format.

#     Parameters
#     ----------
#     student_data : dict from fetch_student_transcript_data()
#     unofficial   : True → "Unofficial Transcript" header
#     logo_path    : path to university crest PNG; None → auto-detect

#     Returns
#     -------
#     bytes — raw PDF ready for Streamlit download_button()
#     """
#     buf = io.BytesIO()
#     doc = SimpleDocTemplate(
#         buf,
#         pagesize=A4,
#         leftMargin=_MARGIN, rightMargin=_MARGIN,
#         topMargin=_MARGIN,  bottomMargin=_MARGIN,
#         title=f"Transcript – {student_data.get('roll_no', '')}",
#         author="University of Loralai – Controller of Examinations",
#     )

#     st   = _styles()
#     story: list = []

#     # ── Resolve logo ──────────────────────────────────────────────────────────
#     logo_img = None
#     for candidate in [logo_path, _DEFAULT_LOGO]:
#         if candidate and os.path.isfile(candidate):
#             try:
#                 logo_img = Image(candidate, width=22*mm, height=24*mm)
#                 break
#             except Exception:
#                 pass

#     # ── Document header : logo + university name ──────────────────────────────
#     title_label = "Unofficial Transcript" if unofficial else "Official Transcript"
#     uni_block = [
#         Paragraph("<b>UNIVERSITY OF LORALAI</b>", st["UNI"]),
#         Paragraph(f"<u>{title_label}</u>", st["SUB"]),
#     ]

#     if logo_img:
#         from reportlab.platypus import KeepTogether as KT
#         hdr_data = [[
#             logo_img,
#             [uni_block[0], Spacer(1, 2), uni_block[1]],
#             Paragraph("", st["INFO"]),   # right spacer
#         ]]
#         hdr_tbl = Table(hdr_data, colWidths=[28*mm, 124*mm, 28*mm])
#         hdr_tbl.setStyle(TableStyle([
#             ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
#             ("ALIGN",       (0, 0), (0, 0),   "LEFT"),
#             ("ALIGN",       (1, 0), (1, 0),   "CENTER"),
#             ("TOPPADDING",  (0, 0), (-1, -1), 0),
#             ("BOTTOMPADDING",(0,0), (-1, -1), 0),
#             ("LEFTPADDING", (0, 0), (-1, -1), 0),
#             ("RIGHTPADDING",(0, 0), (-1, -1), 0),
#         ]))
#         story.append(hdr_tbl)
#     else:
#         for blk in uni_block:
#             story.append(blk)

#     story.append(HRFlowable(width="100%", thickness=1.2, color=_BLACK, spaceAfter=3))
#     story.append(Spacer(1, 2*mm))

#     # ── Ref No + Date ─────────────────────────────────────────────────────────
#     ref_tbl = Table(
#         [[
#             Paragraph(f"Ref No: {student_data.get('ref_no', '—')}", st["INFO"]),
#             Paragraph(f"Date: {student_data.get('date', datetime.now().strftime('%d-%m-%Y'))}", st["INFOR"]),
#         ]],
#         colWidths=["50%", "50%"],
#     )
#     ref_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
#     story.append(ref_tbl)
#     story.append(Spacer(1, 2*mm))

#     # ── Student info ──────────────────────────────────────────────────────────
#     def _info(label: str, val: str) -> Paragraph:
#         return Paragraph(f"<b>{label}:</b>  {val}", st["INFO"])

#     info_tbl = Table(
#         [
#             [_info("Name of Student", student_data["student_name"]),
#              _info("Father Name", student_data.get("father_name", "—"))],
#             [_info("Registration No", student_data["roll_no"]),
#              _info("Session", student_data.get("session", "—"))],
#             [_info("Program of Study", student_data.get("department", "—")),
#              Paragraph("", st["INFO"])],
#         ],
#         colWidths=["55%", "45%"],
#     )
#     info_tbl.setStyle(TableStyle([
#         ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
#         ("BOTTOMPADDING", (0,0), (-1,-1), 2),
#         ("TOPPADDING",    (0,0), (-1,-1), 2),
#     ]))
#     story.append(info_tbl)
#     story.append(Spacer(1, 4*mm))

#     # ── Per-semester tables ───────────────────────────────────────────────────
#     for sem in student_data.get("semesters", []):
#         story.append(KeepTogether([_semester_table(sem, st)]))
#         story.append(Spacer(1, 3*mm))

#     # ── CGPA section ──────────────────────────────────────────────────────────
#     cgpa_val = student_data.get("cgpa")
#     cgpa_str = f"{cgpa_val:.2f}" if cgpa_val is not None else "—"
#     ch_total = student_data.get("total_credit_hours", 0)
#     n_sems   = student_data.get("semesters_completed", 0)

#     cgpa_row_data = [[
#         Paragraph(
#             f"<b>Cumulative Grade Point Average (CGPA)</b>",
#             st["CGPA"],
#         ),
#         Paragraph(f"<b>{cgpa_str}</b>", st["CGPAR"]),
#     ]]
#     cgpa_tbl = Table(cgpa_row_data, colWidths=["75%", "25%"])
#     cgpa_tbl.setStyle(TableStyle([
#         ("BOX",           (0,0), (-1,-1), 0.8, _BLACK),
#         ("BACKGROUND",    (0,0), (-1,-1), _GPA_ROW_BG),
#         ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
#         ("TOPPADDING",    (0,0), (-1,-1), 5),
#         ("BOTTOMPADDING", (0,0), (-1,-1), 5),
#         ("LEFTPADDING",   (0,0), (0,0),   4),
#         ("RIGHTPADDING",  (1,0), (1,0),   4),
#     ]))
#     story.append(cgpa_tbl)
#     story.append(Spacer(1, 2*mm))

#     # Credit-hours / non-credit note
#     story.append(Paragraph(
#         f"Total Credit Hours: {ch_total:.0f}  |  "
#         f"Semesters: {n_sems}  |  "
#         "* = Non-credit subject (excluded from GPA calculation)",
#         st["NOTE"],
#     ))
#     story.append(Spacer(1, 12*mm))

#     # ── Signature section ─────────────────────────────────────────────────────
#     sig_tbl = Table(
#         [
#             [Paragraph("", st["SIG"]), Paragraph("", st["SIG"])],
#             [Paragraph("_" * 30, st["SIG"]), Paragraph("_" * 30, st["SIG"])],
#             [Paragraph("<b>Deputy Controller</b>", st["SIG"]),
#              Paragraph("<b>Controller of Examinations</b>", st["SIG"])],
#         ],
#         colWidths=["50%", "50%"],
#     )
#     sig_tbl.setStyle(TableStyle([
#         ("ALIGN",  (0,0), (-1,-1), "CENTER"),
#         ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
#         ("TOPPADDING",    (0,0), (-1,-1), 4),
#         ("BOTTOMPADDING", (0,0), (-1,-1), 4),
#     ]))
#     story.append(sig_tbl)

#     doc.build(story)
#     return buf.getvalue()


# # ─────────────────────────────────────────────────────────────────────────────
# # BULK ZIP
# # ─────────────────────────────────────────────────────────────────────────────

# def generate_bulk_zip(
#     results_map: dict[str, dict | None],
#     unofficial: bool = True,
#     logo_path: str | None = None,
# ) -> bytes:
#     """Package multiple PDFs into one ZIP archive."""
#     buf = io.BytesIO()
#     with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
#         for roll_no, data in results_map.items():
#             if not data or "_error" in data:
#                 continue
#             try:
#                 pdf = generate_transcript_pdf(data, unofficial=unofficial, logo_path=logo_path)
#                 safe = roll_no.replace("/", "_").replace("\\", "_")
#                 zf.writestr(f"{safe}_transcript.pdf", pdf)
#             except Exception:
#                 pass
#     return buf.getvalue()


"""
src/dashboard/transcript_generator.py
======================================
University of Loralai — Agentic GPA System
Automated PDF Transcript Generator  (v3 — exact official format match)

Key design goals
----------------
* Layout, fonts, borders, and proportions match the UoL official transcript
  (reference: WhatsApp_Image_2026-09-11 scan).
* Times-Roman / Times-Bold throughout (matches the scanned document font).
* University crest logo embedded top-left.
* Semester table structure:
    Row 0 : "Nth Semester" (spans S.No+Subject) | C.Hrs | Marks | G.P | Grade
    Row 1 : S.No | Subject | blank | 100 | blank | blank
    Data rows  …
    GPA row : blank | "Grade Point Average (GPA)" (span) | | value | blank
* CGPA section followed by dual-signature area.
* generate_transcript_pdf() accepts an optional logo_path; falls back cleanly
  when no logo file exists.

Tech Lead : Arif Khan
"""

from __future__ import annotations

import concurrent.futures
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Any

# ── ReportLab ────────────────────────────────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── Page geometry ─────────────────────────────────────────────────────────────
_MARGIN     = 15 * mm
_PAGE_W, _  = A4

# Column widths — sum = 180 mm (A4 − 2 × 15 mm margins)
# S.No | Subject | C.Hrs | Marks | G.P | Grade
_COL = [12*mm, 82*mm, 20*mm, 26*mm, 22*mm, 18*mm]

# ── Colours (match the printed document — minimal / black-on-white) ───────────
_BLACK      = colors.black
_SEM_HDR_BG = colors.HexColor("#E8E8E8")   # semester header row — light gray
_SUB_HDR_BG = colors.HexColor("#F5F5F5")   # S.No / Subject sub-header — very light
_GPA_ROW_BG = colors.HexColor("#EFEFEF")   # GPA summary row
_WHITE      = colors.white

# ── Fonts ─────────────────────────────────────────────────────────────────────
_F  = "Times-Roman"
_FB = "Times-Bold"
_FI = "Times-Italic"


# ─────────────────────────────────────────────────────────────────────────────
# GRADE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _grade_letter(gp: float | None) -> str:
    if gp is None: return "—"
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


def _ordinal(n: int) -> str:
    sfx = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
    return f"{n}{sfx}"


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE FETCH  (one session per call — thread-safe for parallel use)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_student_transcript_data(
    roll_no: str,
    db_url: str,
) -> dict[str, Any] | None:
    """Query DB and return a fully-denormalised transcript dict, or None."""
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker
        from src.models.database_models import CGPA, Mark, SemesterGPA, Student, Subject
    except ImportError as exc:
        raise RuntimeError(f"DB dependencies not available: {exc}") from exc

    kwargs = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine  = create_engine(db_url, connect_args=kwargs)
    session = sessionmaker(bind=engine)()

    try:
        student = session.execute(
            select(Student).where(Student.roll_no.ilike(f"%{roll_no.strip()}%"))
        ).scalars().first()
        if student is None:
            return None

        marks = session.execute(
            select(Mark)
            .where(Mark.student_id == student.id)
            .order_by(Mark.semester, Mark.subject_id)
        ).scalars().all()

        subj_map = {
            s.id: s
            for s in session.execute(select(Subject)).scalars().all()
        }
        sgpas = session.execute(
            select(SemesterGPA)
            .where(SemesterGPA.student_id == student.id)
            .order_by(SemesterGPA.semester)
        ).scalars().all()
        cgpa_row = session.execute(
            select(CGPA).where(CGPA.student_id == student.id)
        ).scalar_one_or_none()

        # ── Session inference (prefer roll-number year over academic_year) ────
        # Pattern: UoL/CS-F-22/001-BS → enrollment year 2022
        m = re.search(r"[/-]F[-/](\d{2})[/-]", student.roll_no or "")
        if m:
            yr = 2000 + int(m.group(1))
            academic_session = f"{yr}-{yr + 4}"
        else:
            sem1 = [mk for mk in marks if mk.semester == 1]
            academic_session = "—"
            if sem1:
                try:
                    yr = int(sem1[0].academic_year.split("-")[0])
                    academic_session = f"{yr}-{yr + 4}"
                except Exception:
                    academic_session = sem1[0].academic_year or "—"

        # ── Build per-semester structure ──────────────────────────────────────
        by_sem: dict[int, list] = {}
        for mk in marks:
            by_sem.setdefault(mk.semester, []).append(mk)

        sgpa_map = {sg.semester: sg for sg in sgpas}
        run_ch = run_qp = 0.0
        cgpa_after: dict[int, float | None] = {}
        for sn in sorted(by_sem):
            sg = sgpa_map.get(sn)
            if sg:
                run_ch += sg.total_credit_hours or 0.0
                run_qp += sg.total_quality_points or 0.0
            cgpa_after[sn] = round(run_qp / run_ch, 2) if run_ch > 0 else None

        semesters_out = []
        for sn in sorted(by_sem):
            sg   = sgpa_map.get(sn)
            smks = by_sem[sn]
            subjects_out = []
            for mk in smks:
                sub = subj_map.get(mk.subject_id)
                subjects_out.append({
                    "name"          : sub.subject_name if sub else f"Subject {mk.subject_id}",
                    "credit_hours"  : sub.credit_hours if sub else 0,
                    "obtained_marks": mk.obtained_marks,
                    "total_marks"   : mk.total_marks,
                    "percentage"    : mk.percentage,
                    "grade_point"   : mk.grade_point,
                    "grade"         : _grade_letter(mk.grade_point),
                    "quality_points": mk.quality_points,
                    "is_non_credit" : mk.is_non_credit,
                })
            semesters_out.append({
                "number"              : sn,
                "academic_year"       : smks[0].academic_year if smks else "—",
                "subjects"            : subjects_out,
                "gpa"                 : sg.gpa if sg else None,
                "total_credit_hours"  : sg.total_credit_hours if sg else 0.0,
                "total_quality_points": sg.total_quality_points if sg else 0.0,
                "cgpa_after"          : cgpa_after.get(sn),
            })

        # ── Expand department label ───────────────────────────────────────────
        dept_raw = (student.department or "").strip()
        dept_label = (
            "BS Computer Science" if dept_raw.upper() in ("CS", "BSCS")
            else dept_raw if dept_raw else "BS Computer Science"
        )

        return {
            "student_id"         : student.id,
            "student_name"       : student.student_name,
            "roll_no"            : student.roll_no,
            "father_name"        : student.father_name or "—",
            "department"         : dept_label,
            "session"            : academic_session,
            "ref_no"             : f"CoE/UoL {student.id}",
            "date"               : datetime.now().strftime("%d-%m-%Y"),
            "semesters"          : semesters_out,
            "cgpa"               : cgpa_row.cgpa if cgpa_row else None,
            "total_credit_hours" : cgpa_row.total_credit_hours if cgpa_row else 0.0,
            "semesters_completed": cgpa_row.semesters_completed if cgpa_row else len(semesters_out),
        }
    finally:
        session.close()


def fetch_multiple_transcripts(
    roll_nos: list[str],
    db_url: str,
    max_workers: int = 8,
) -> dict[str, dict | None]:
    """Parallel fetch for multiple roll numbers. Returns {roll_no: data | None}."""
    results: dict[str, dict | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fmap = {pool.submit(fetch_student_transcript_data, rn, db_url): rn for rn in roll_nos}
        for fut in concurrent.futures.as_completed(fmap):
            rn = fmap[fut]
            try:
                results[rn] = fut.result()
            except Exception as exc:
                results[rn] = {"_error": str(exc)}
    return {rn: results.get(rn) for rn in roll_nos}


# ─────────────────────────────────────────────────────────────────────────────
# PARAGRAPH STYLES  (Times-Roman throughout to match official)
# ─────────────────────────────────────────────────────────────────────────────

def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    def P(name, font=_F, **kw):
        return ParagraphStyle(name, parent=base, fontName=font, **kw)

    return {
        # ── University header ─────────────────────────────────────────────────
        "UNI"  : P("UNI",   font=_FB, fontSize=16, leading=20, alignment=TA_CENTER),
        "SUB"  : P("SUB",   font=_F,  fontSize=11, leading=14, alignment=TA_CENTER),
        # ── Reference / student info ──────────────────────────────────────────
        "INFO" : P("INFO",  font=_F,  fontSize=9.5, leading=13),
        "INFOR": P("INFOR", font=_F,  fontSize=9.5, leading=13, alignment=TA_RIGHT),
        # ── Table cells ───────────────────────────────────────────────────────
        "TC"   : P("TC",    font=_F,  fontSize=9, leading=11, alignment=TA_CENTER),
        "TL"   : P("TL",    font=_F,  fontSize=9, leading=11, alignment=TA_LEFT),
        "TBC"  : P("TBC",   font=_FB, fontSize=9, leading=11, alignment=TA_CENTER),
        "TBL"  : P("TBL",   font=_FB, fontSize=9, leading=11, alignment=TA_LEFT),
        "TBR"  : P("TBR",   font=_FB, fontSize=9, leading=11, alignment=TA_RIGHT),
        # ── CGPA line ─────────────────────────────────────────────────────────
        "CGPA" : P("CGPA",  font=_FB, fontSize=10, leading=13, alignment=TA_LEFT),
        "CGPAR": P("CGPAR", font=_FB, fontSize=10, leading=13, alignment=TA_RIGHT),
        # ── Signature labels ──────────────────────────────────────────────────
        "SIG"  : P("SIG",   font=_F,  fontSize=9,  leading=11, alignment=TA_CENTER),
        "NOTE" : P("NOTE",  font=_F,  fontSize=7.5, leading=10, alignment=TA_CENTER,
                   textColor=colors.HexColor("#555555")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SEMESTER TABLE  — exact match to official UoL format
# ─────────────────────────────────────────────────────────────────────────────

def _build_all_semesters_table(semesters: list, st: dict) -> Table:
    """
    Build ONE continuous connected table for ALL semesters — exactly matching
    the official UoL transcript where every semester runs into the next with
    no gap or border break.

    Structure per semester
    ──────────────────────
    Row 0 : "Nth Semester"  ← spans ALL 6 cols, gray background (full width)
    Row 1 : S.No | Subject | C.Hrs | Marks / 100 | G.P | Grade  ← col headers
    Row 2+ : data rows (white / very-light alternating)
    Last  : Grade Point Average (GPA) row  ← light gray
    """
    TC, TL, TBC, TBL = st["TC"], st["TL"], st["TBC"], st["TBL"]

    all_rows:   list       = []   # flat list of all rows across every semester
    style_cmds: list       = []   # accumulated TableStyle commands

    # ── Base style applied once across the whole table ────────────────────────
    style_cmds += [
        ("BOX",             (0, 0), (-1, -1), 0.7, _BLACK),
        ("INNERGRID",       (0, 0), (-1, -1), 0.4, _BLACK),
        ("ALIGN",           (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",          (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",      (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",   (0, 0), (-1, -1), 3),
        ("LEFTPADDING",     (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",    (0, 0), (-1, -1), 3),
    ]

    for sem in semesters:
        sn       = sem["number"]
        subjects = sem["subjects"]
        gpa_val  = sem["gpa"]

        # ── Row 0 : semester name — spans ALL 6 columns ──────────────────────
        sem_row = len(all_rows)
        all_rows.append([
            Paragraph(f"<b>{_ordinal(sn)} Semester</b>", TBC),
            "", "", "", "", "",          # merged into col 0
        ])
        style_cmds += [
            ("SPAN",       (0, sem_row), (5, sem_row)),
            ("BACKGROUND", (0, sem_row), (5, sem_row), _SEM_HDR_BG),
            ("FONTNAME",   (0, sem_row), (5, sem_row), _FB),
        ]

        # ── Row 1 : column headers ────────────────────────────────────────────
        col_row = len(all_rows)
        all_rows.append([
            Paragraph("<b>S. No</b>",             TBC),
            Paragraph("<b>Subject</b>",            TBL),
            Paragraph("<b>C. Hrs</b>",             TBC),
            Paragraph("<b>Marks</b><br/><b>100</b>", TBC),
            Paragraph("<b>G.P</b>",               TBC),
            Paragraph("<b>Grade</b>",             TBC),
        ])
        style_cmds += [
            ("BACKGROUND", (0, col_row), (5, col_row), _SUB_HDR_BG),
            ("ALIGN",      (1, col_row), (1, col_row), "LEFT"),
        ]

        # ── Data rows ─────────────────────────────────────────────────────────
        for i, subj in enumerate(subjects, 1):
            data_row = len(all_rows)
            nc_mark  = "*" if subj["is_non_credit"] else ""
            marks_str = (
                str(int(subj["obtained_marks"]))
                if subj["total_marks"] == 100
                else f"{subj['percentage']:.1f}%"
            )
            all_rows.append([
                Paragraph(str(i),                            TC),
                Paragraph(subj["name"] + nc_mark,           TL),
                Paragraph(str(subj["credit_hours"]),         TC),
                Paragraph(marks_str,                         TC),
                Paragraph(f"{subj['grade_point']:.2f}",     TC),
                Paragraph(subj["grade"],                     TC),
            ])
            style_cmds += [
                ("ALIGN", (1, data_row), (1, data_row), "LEFT"),
            ]
            # Subtle alternating row shade
            if (i % 2) == 0:
                style_cmds.append(
                    ("BACKGROUND", (0, data_row), (5, data_row),
                     colors.HexColor("#FAFAFA"))
                )

        # ── GPA summary row ───────────────────────────────────────────────────
        gpa_row = len(all_rows)
        gpa_str = f"{gpa_val:.2f}" if gpa_val is not None else "—"
        all_rows.append([
            Paragraph("", TC),
            Paragraph("<b>Grade Point Average (GPA)</b>", TBL),
            Paragraph("", TC),
            Paragraph("", TC),
            Paragraph(f"<b>{gpa_str}</b>", TBC),
            Paragraph("", TC),
        ])
        style_cmds += [
            ("SPAN",       (1, gpa_row), (3, gpa_row)),
            ("ALIGN",      (1, gpa_row), (3, gpa_row), "LEFT"),
            ("BACKGROUND", (0, gpa_row), (5, gpa_row), _GPA_ROW_BG),
        ]

    tbl = Table(all_rows, colWidths=_COL)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATOR  — main public function
# ─────────────────────────────────────────────────────────────────────────────

# Default logo path — set once here; app.py overrides via the logo_path param
_DEFAULT_LOGO = os.path.join(
    os.path.dirname(__file__), "assets", "uol_logo.png"
)


def generate_transcript_pdf(
    student_data: dict[str, Any],
    unofficial: bool = True,
    logo_path: str | None = None,
) -> bytes:
    """
    Generate an A4 PDF transcript that exactly matches the UoL official format.

    Parameters
    ----------
    student_data : dict from fetch_student_transcript_data()
    unofficial   : True → "Unofficial Transcript" header
    logo_path    : path to university crest PNG; None → auto-detect

    Returns
    -------
    bytes — raw PDF ready for Streamlit download_button()
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=_MARGIN,  bottomMargin=_MARGIN,
        title=f"Transcript – {student_data.get('roll_no', '')}",
        author="University of Loralai – Controller of Examinations",
    )

    st   = _styles()
    story: list = []

    # ── Resolve logo ──────────────────────────────────────────────────────────
    logo_img = None
    for candidate in [logo_path, _DEFAULT_LOGO]:
        if candidate and os.path.isfile(candidate):
            try:
                logo_img = Image(candidate, width=22*mm, height=24*mm)
                break
            except Exception:
                pass

    # ── Document header : logo + university name ──────────────────────────────
    title_label = "Unofficial Transcript" if unofficial else "Official Transcript"
    uni_block = [
        Paragraph("<b>UNIVERSITY OF LORALAI</b>", st["UNI"]),
        Paragraph(f"<u>{title_label}</u>", st["SUB"]),
    ]

    if logo_img:
        from reportlab.platypus import KeepTogether as KT
        hdr_data = [[
            logo_img,
            [uni_block[0], Spacer(1, 2), uni_block[1]],
            Paragraph("", st["INFO"]),   # right spacer
        ]]
        hdr_tbl = Table(hdr_data, colWidths=[28*mm, 124*mm, 28*mm])
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",       (0, 0), (0, 0),   "LEFT"),
            ("ALIGN",       (1, 0), (1, 0),   "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0,0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_tbl)
    else:
        for blk in uni_block:
            story.append(blk)

    story.append(Spacer(1, 3*mm))

    # ── Ref No + Date ─────────────────────────────────────────────────────────
    ref_tbl = Table(
        [[
            Paragraph(f"Ref No: {student_data.get('ref_no', '—')}", st["INFO"]),
            Paragraph(f"Date: {student_data.get('date', datetime.now().strftime('%d-%m-%Y'))}", st["INFOR"]),
        ]],
        colWidths=["50%", "50%"],
    )
    ref_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(ref_tbl)
    story.append(Spacer(1, 1*mm))

    # ── Student info ──────────────────────────────────────────────────────────
    def _info(label: str, val: str) -> Paragraph:
        return Paragraph(f"<b>{label}:</b>  {val}", st["INFO"])

    info_tbl = Table(
        [
            [_info("Name of Student", student_data["student_name"]),
             _info("Father Name", student_data.get("father_name", "—"))],
            [_info("Registration No", student_data["roll_no"]),
             _info("Session", student_data.get("session", "—"))],
            [_info("Program of Study", student_data.get("department", "—")),
             Paragraph("", st["INFO"])],
        ],
        colWidths=["55%", "45%"],
    )
    info_tbl.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 4*mm))

    # ── All semesters in ONE connected table (matches official UoL format) ────
    semesters = student_data.get("semesters", [])
    if semesters:
        story.append(_build_all_semesters_table(semesters, st))
        story.append(Spacer(1, 4*mm))

    # ── CGPA section ──────────────────────────────────────────────────────────
    cgpa_val = student_data.get("cgpa")
    cgpa_str = f"{cgpa_val:.2f}" if cgpa_val is not None else "—"
    ch_total = student_data.get("total_credit_hours", 0)
    n_sems   = student_data.get("semesters_completed", 0)

    cgpa_row_data = [[
        Paragraph(
            f"<b>Cumulative Grade Point Average (CGPA)</b>",
            st["CGPA"],
        ),
        Paragraph(f"<b>{cgpa_str}</b>", st["CGPAR"]),
    ]]
    cgpa_tbl = Table(cgpa_row_data, colWidths=["75%", "25%"])
    cgpa_tbl.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.8, _BLACK),
        ("BACKGROUND",    (0,0), (-1,-1), _GPA_ROW_BG),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (0,0),   4),
        ("RIGHTPADDING",  (1,0), (1,0),   4),
    ]))
    story.append(cgpa_tbl)
    story.append(Spacer(1, 2*mm))

    # Credit-hours / non-credit note
    story.append(Paragraph(
        f"Total Credit Hours: {ch_total:.0f}  |  "
        f"Semesters: {n_sems}  |  "
        "* = Non-credit subject (excluded from GPA calculation)",
        st["NOTE"],
    ))
    story.append(Spacer(1, 12*mm))

    # ── Signature section ─────────────────────────────────────────────────────
    sig_tbl = Table(
        [
            [Paragraph("", st["SIG"]), Paragraph("", st["SIG"])],
            [Paragraph("_" * 30, st["SIG"]), Paragraph("_" * 30, st["SIG"])],
            [Paragraph("<b>Deputy Controller</b>", st["SIG"]),
             Paragraph("<b>Controller of Examinations</b>", st["SIG"])],
        ],
        colWidths=["50%", "50%"],
    )
    sig_tbl.setStyle(TableStyle([
        ("ALIGN",  (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(sig_tbl)

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# BULK ZIP
# ─────────────────────────────────────────────────────────────────────────────

def generate_bulk_zip(
    results_map: dict[str, dict | None],
    unofficial: bool = True,
    logo_path: str | None = None,
) -> bytes:
    """Package multiple PDFs into one ZIP archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for roll_no, data in results_map.items():
            if not data or "_error" in data:
                continue
            try:
                pdf = generate_transcript_pdf(data, unofficial=unofficial, logo_path=logo_path)
                safe = roll_no.replace("/", "_").replace("\\", "_")
                zf.writestr(f"{safe}_transcript.pdf", pdf)
            except Exception:
                pass
    return buf.getvalue()