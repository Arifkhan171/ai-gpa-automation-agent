# """
# src/dashboard/analytics.py
# ==========================
# Analytics & Visualization Module — GPA Dashboard
# University of Loralai | CS Department
# Tech Lead: Arif Khan

# Provides a standalone, DB-driven Analytics tab with:
#   ─ Summary KPI strip  (students · subjects · marks · avg CGPA · excellent · at-risk)
#   ─ CGPA distribution histogram  (three HEC performance bands)
#   ─ Per-semester GPA trend  (combo bar + line chart)
#   ─ Subject performance ranking  (avg % horizontal bar, credit-only subjects)
#   ─ Grade-letter distribution  (donut chart with avg GP annotation)
#   ─ Performance-band breakdown  (pie: Excellent / Good / At Risk)
#   ─ Credit hours per semester  (bar)
#   ─ At-risk student table  (CGPA < 2.50)
#   ─ Top-performer table  (CGPA ≥ 3.50)
#   ─ Semester-by-semester detail  (expandable aggregate table)
#   ─ Three CSV export downloads

# Dependencies (in addition to project requirements):
#   pip install plotly          ← interactive charts; gracefully falls back to
#                                 st.bar_chart / st.line_chart when absent

# Wired into app.py:
#   from src.dashboard.analytics import render_analytics
#   # in main() → with analytics_tab: render_analytics()

# NEVER import validation_agent, edge_cases, or calculator internals here —
# only the DB engine helper and ORM models are needed.
# """

# from __future__ import annotations

# import io
# import sys
# from pathlib import Path
# from typing import Any

# import pandas as pd
# import streamlit as st

# # ─── Path resolution (mirrors app.py) ────────────────────────────────────────
# _ROOT = Path(__file__).resolve().parent.parent.parent
# if str(_ROOT) not in sys.path:
#     sys.path.insert(0, str(_ROOT))

# # ─── Database dependencies ─────────────────────────────────────────────────────
# _DB_OK  : bool = False
# _DB_ERR : str  = ""

# try:
#     from src.agents.calculator_agent import get_engine
#     from src.models.database_models import Student, Subject, Mark, SemesterGPA, CGPA
#     from sqlalchemy.orm import Session
#     from sqlalchemy import select as sa_select
#     _DB_OK = True
# except Exception as _db_e:
#     _DB_ERR = str(_db_e)

# # ─── Plotly (optional — graceful fallback when not installed) ─────────────────
# _PLOTLY_OK : bool = False
# try:
#     import plotly.express as px
#     import plotly.graph_objects as go
#     _PLOTLY_OK = True
# except ImportError:
#     pass

# # ─── Fallback DB path (mirrors DEFAULT_DB in app.py) ─────────────────────────
# _DEFAULT_DB = "sqlite:///./gpa_system.db"

# # ──────────────────────────────────────────────────────────────────────────────
# # DESIGN TOKENS  (aligned with enterprise CSS in app.py)
# # ──────────────────────────────────────────────────────────────────────────────
# _NAVY  = "#0F2444"
# _GREEN = "#16A34A"
# _AMBER = "#D97706"
# _RED   = "#DC2626"
# _SLATE = "#64748B"

# _FONT  = dict(family="Inter, Segoe UI, sans-serif", size=12, color="#374151")

# # Base plotly layout applied to every figure
# _LAYOUT_BASE : dict[str, Any] = dict(
#     plot_bgcolor  = "white",
#     paper_bgcolor = "white",
#     font          = _FONT,
#     margin        = dict(l=10, r=10, t=18, b=10),
# )

# # HEC Pakistan grade point → letter grade mapping (read-only, mirrors calculator_agent)
# _GP_TO_LETTER: list[tuple[float, str]] = [
#     (4.00, "A"), (3.70, "A-"), (3.30, "B+"), (3.00, "B"),
#     (2.70, "B-"), (2.30, "C+"), (2.00, "C"), (1.70, "C-"),
#     (1.00, "D"),
# ]
# _GRADE_COLOURS: dict[str, str] = {
#     "A": "#15803D", "A-": "#16A34A", "B+": "#4ADE80", "B": "#84CC16",
#     "B-": "#BEF264", "C+": "#EAB308", "C": "#F59E0B", "C-": "#D97706",
#     "D": "#F97316", "F": "#DC2626",
# }


# # ──────────────────────────────────────────────────────────────────────────────
# # PURE HELPERS
# # ──────────────────────────────────────────────────────────────────────────────

# def _grade_letter(gp: float | None) -> str:
#     """Convert a grade point (0.00–4.00) to the HEC letter grade string."""
#     if gp is None:
#         return "F"
#     for threshold, letter in _GP_TO_LETTER:
#         if gp >= threshold:
#             return letter
#     return "F"


# def _perf_band(cgpa: float | None) -> str:
#     """Return the HEC performance band label for a CGPA value."""
#     if cgpa is None:
#         return "No Data"
#     if cgpa >= 3.50:
#         return "Excellent (≥3.50)"
#     if cgpa >= 2.50:
#         return "Good (2.50–3.49)"
#     return "At Risk (<2.50)"


# def _band_colour(band: str) -> str:
#     return {
#         "Excellent (≥3.50)": _GREEN,
#         "Good (2.50–3.49)" : _AMBER,
#         "At Risk (<2.50)"  : _RED,
#     }.get(band, _SLATE)


# def _db_url() -> str:
#     return st.session_state.get("db_url", _DEFAULT_DB)


# def _kpi_html(value: Any, label: str, colour: str = _NAVY) -> str:
#     """Return the HTML string for a single KPI box (matches .kpi-box CSS in app.py)."""
#     return (
#         f'<div class="kpi-box">'
#         f'<div class="kpi-value" style="color:{colour}">{value}</div>'
#         f'<div class="kpi-label">{label}</div>'
#         f'</div>'
#     )


# def _card(fn, *args, **kwargs) -> None:
#     """Render *fn* wrapped inside a white .card div."""
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     fn(*args, **kwargs)
#     st.markdown('</div>', unsafe_allow_html=True)


# def _section_label(text: str) -> None:
#     st.markdown(
#         f'<div class="section-label">{text}</div>',
#         unsafe_allow_html=True,
#     )


# # ──────────────────────────────────────────────────────────────────────────────
# # DATA LAYER  — single session, convert to plain DataFrames before close
# # ──────────────────────────────────────────────────────────────────────────────

# def _fetch_dataframes() -> tuple[
#     pd.DataFrame,     # marks_df   — one row per Mark record
#     pd.DataFrame,     # sgpa_df    — one row per SemesterGPA (gpa IS NOT NULL)
#     pd.DataFrame,     # cgpa_df    — one row per student CGPA (cgpa IS NOT NULL)
#     dict[int, str],   # subj_map   — {subject.id: subject.subject_name}
# ]:
#     """
#     Open a single SQLAlchemy session, pull all analytics data,
#     and convert to pandas DataFrames before the session closes.

#     Only column attributes are accessed — no lazy-loaded relationships —
#     so detached-object warnings are never triggered.
#     """
#     engine = get_engine(_db_url())
#     with Session(engine) as sess:
#         students  = sess.execute(sa_select(Student)).scalars().all()
#         subjects  = sess.execute(sa_select(Subject)).scalars().all()
#         marks     = sess.execute(sa_select(Mark)).scalars().all()
#         sgpas     = sess.execute(sa_select(SemesterGPA)).scalars().all()
#         cgpas_orm = sess.execute(sa_select(CGPA)).scalars().all()

#     stu_map  = {s.id: s for s in students}
#     subj_map = {s.id: s.subject_name for s in subjects}

#     # ── marks_df ──────────────────────────────────────────────────────────────
#     marks_df = pd.DataFrame([
#         {
#             "student_id"    : m.student_id,
#             "subject_id"    : m.subject_id,
#             "semester"      : m.semester,
#             "academic_year" : m.academic_year,
#             "percentage"    : m.percentage,
#             "grade_point"   : m.grade_point,
#             "quality_points": m.quality_points,
#             "is_non_credit" : m.is_non_credit,
#         }
#         for m in marks
#     ]) if marks else pd.DataFrame()

#     # ── sgpa_df ───────────────────────────────────────────────────────────────
#     sgpa_df = pd.DataFrame([
#         {
#             "student_id"          : s.student_id,
#             "semester"            : s.semester,
#             "academic_year"       : s.academic_year,
#             "gpa"                 : s.gpa,
#             "total_credit_hours"  : s.total_credit_hours,
#             "total_quality_points": s.total_quality_points,
#         }
#         for s in sgpas
#         if s.gpa is not None                  # exclude all-non-credit semesters
#     ]) if sgpas else pd.DataFrame()

#     # ── cgpa_df ───────────────────────────────────────────────────────────────
#     cgpa_rows: list[dict] = []
#     for c in cgpas_orm:
#         if c.cgpa is None:
#             continue
#         s = stu_map.get(c.student_id)
#         cgpa_rows.append({
#             "student_id"         : c.student_id,
#             "student_name"       : s.student_name          if s else "Unknown",
#             "roll_no"            : s.roll_no               if s else "—",
#             "department"         : (s.department or "—")   if s else "—",
#             "cgpa"               : c.cgpa,
#             "semesters_completed": c.semesters_completed,
#             "total_credit_hours" : c.total_credit_hours,
#         })
#     cgpa_df = pd.DataFrame(cgpa_rows) if cgpa_rows else pd.DataFrame()
#     if not cgpa_df.empty:
#         cgpa_df["band"] = cgpa_df["cgpa"].apply(_perf_band)

#     return marks_df, sgpa_df, cgpa_df, subj_map


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 1 — CGPA Distribution Histogram
# # ──────────────────────────────────────────────────────────────────────────────

# def _cgpa_histogram(cgpa_df: pd.DataFrame) -> None:
#     _section_label("📊 CGPA Distribution")
#     if cgpa_df.empty:
#         st.info("No CGPA records in the database yet.", icon="ℹ️")
#         return

#     if _PLOTLY_OK:
#         fig = px.histogram(
#             cgpa_df,
#             x            = "cgpa",
#             color        = "band",
#             nbins        = 20,
#             color_discrete_map={
#                 "Excellent (≥3.50)": _GREEN,
#                 "Good (2.50–3.49)" : _AMBER,
#                 "At Risk (<2.50)"  : _RED,
#             },
#             category_orders={"band": [
#                 "Excellent (≥3.50)", "Good (2.50–3.49)", "At Risk (<2.50)"
#             ]},
#             labels={"cgpa": "CGPA", "count": "Students", "band": "Band"},
#         )
#         fig.add_vline(
#             x=2.50, line_dash="dash", line_color=_RED, line_width=1.5,
#             annotation_text="2.50 Min.", annotation_position="top left",
#             annotation_font_color=_RED, annotation_font_size=11,
#         )
#         fig.add_vline(
#             x=3.50, line_dash="dash", line_color=_GREEN, line_width=1.5,
#             annotation_text="3.50 Excellent", annotation_position="top right",
#             annotation_font_color=_GREEN, annotation_font_size=11,
#         )
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height=340,
#             bargap=0.06,
#             legend_title_text="Band",
#             xaxis=dict(title="CGPA", range=[0, 4.1], dtick=0.5, tickformat=".1f"),
#             yaxis=dict(title="No. of Students"),
#         )
#         st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
#     else:
#         # Streamlit native fallback
#         bins = pd.cut(
#             cgpa_df["cgpa"],
#             bins=[0, 1, 2, 2.5, 3, 3.5, 4.01],
#             labels=["0–1", "1–2", "2–2.5", "2.5–3", "3–3.5", "3.5–4"],
#         )
#         st.bar_chart(bins.value_counts().sort_index())


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 2 — Per-Semester GPA Trend  (combo bar + line)
# # ──────────────────────────────────────────────────────────────────────────────

# def _semester_trend(sgpa_df: pd.DataFrame) -> None:
#     _section_label("📈 Per-Semester GPA Trend")
#     if sgpa_df.empty:
#         st.info("No semester GPA records yet.", icon="ℹ️")
#         return

#     trend = (
#         sgpa_df.groupby("semester")
#         .agg(
#             avg_gpa=("gpa", "mean"),
#             min_gpa=("gpa", "min"),
#             max_gpa=("gpa", "max"),
#             n      =("gpa", "count"),
#         )
#         .reset_index()
#     )
#     trend["avg_gpa"]   = trend["avg_gpa"].round(2)
#     trend["sem_label"] = "Sem " + trend["semester"].astype(str)

#     if _PLOTLY_OK:
#         bar_colours = [
#             _GREEN if v >= 3.50 else _AMBER if v >= 2.50 else _RED
#             for v in trend["avg_gpa"]
#         ]
#         fig = go.Figure()
#         fig.add_trace(go.Bar(
#             x            = trend["sem_label"],
#             y            = trend["avg_gpa"],
#             name         = "Avg GPA",
#             marker_color = bar_colours,
#             text         = trend["avg_gpa"].apply(lambda v: f"{v:.2f}"),
#             textposition = "outside",
#             opacity      = 0.82,
#             hovertemplate=(
#                 "%{x}<br>Avg: %{y:.2f}<br>"
#                 "Students: " + trend["n"].astype(str)
#                 + "<extra></extra>"
#             ),
#         ))
#         fig.add_trace(go.Scatter(
#             x      = trend["sem_label"],
#             y      = trend["avg_gpa"],
#             name   = "Trend",
#             mode   = "lines+markers",
#             line   = dict(color=_NAVY, width=2.5),
#             marker = dict(size=9, color=_NAVY,
#                           line=dict(width=2, color="white")),
#         ))
#         fig.add_hline(
#             y=2.50, line_dash="dot", line_color=_RED, line_width=1.2,
#             annotation_text="Min 2.50",
#             annotation_position="bottom right",
#             annotation_font_color=_RED, annotation_font_size=10,
#         )
#         fig.add_hline(
#             y=3.50, line_dash="dot", line_color=_GREEN, line_width=1.2,
#             annotation_text="Excellent 3.50",
#             annotation_position="top right",
#             annotation_font_color=_GREEN, annotation_font_size=10,
#         )
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height  = 340,
#             yaxis   = dict(title="Average GPA", range=[0, 4.5],
#                            tickformat=".1f"),
#             xaxis   = dict(title="Semester"),
#             legend  = dict(orientation="h", yanchor="bottom",
#                            y=1.01, xanchor="right", x=1),
#             barmode = "group",
#         )
#         st.plotly_chart(fig, use_container_width=True,
#                         config={"displayModeBar": False})
#     else:
#         st.line_chart(trend.set_index("sem_label")["avg_gpa"])


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 3 — Subject Performance  (avg % horizontal bar)
# # ──────────────────────────────────────────────────────────────────────────────

# def _subject_performance(marks_df: pd.DataFrame,
#                           subj_map: dict[int, str]) -> None:
#     _section_label("📚 Subject Performance (Avg %)")
#     if marks_df.empty:
#         st.info("No marks data yet.", icon="ℹ️")
#         return

#     # Exclude non-credit subjects (they have no GPA weight)
#     df = (
#         marks_df[~marks_df["is_non_credit"]]
#         if "is_non_credit" in marks_df.columns
#         else marks_df
#     )

#     perf = (
#         df.groupby("subject_id")
#         .agg(avg_pct=("percentage", "mean"),
#              n      =("student_id", "count"))
#         .reset_index()
#     )
#     perf["subject"] = perf["subject_id"].map(
#         lambda sid: subj_map.get(sid, f"Subject {sid}")
#     )
#     perf["avg_pct"] = perf["avg_pct"].round(1)
#     perf.sort_values("avg_pct", inplace=True, ascending=True)

#     if _PLOTLY_OK:
#         height = max(300, len(perf) * 40)
#         fig = px.bar(
#             perf,
#             x           = "avg_pct",
#             y           = "subject",
#             orientation = "h",
#             color       = "avg_pct",
#             color_continuous_scale=[
#                 [0.00, _RED],
#                 [0.50, _AMBER],
#                 [0.85, _GREEN],
#                 [1.00, "#14532D"],
#             ],
#             range_color = [0, 100],
#             text        = "avg_pct",
#             custom_data = ["n"],
#             labels      = {"avg_pct": "Avg %", "subject": ""},
#         )
#         fig.update_traces(
#             texttemplate  = "%{text:.1f}%",
#             textposition  = "outside",
#             hovertemplate = (
#                 "%{y}<br>Avg: %{x:.1f}%<br>"
#                 "Students: %{customdata[0]}<extra></extra>"
#             ),
#         )
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height              = height,
#             coloraxis_showscale = False,
#             xaxis=dict(title="Average Percentage", range=[0, 115]),
#             yaxis=dict(title=""),
#         )
#         st.plotly_chart(fig, use_container_width=True,
#                         config={"displayModeBar": False})
#     else:
#         st.bar_chart(perf.set_index("subject")["avg_pct"])


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 4 — Grade-Letter Distribution  (donut)
# # ──────────────────────────────────────────────────────────────────────────────

# def _grade_donut(marks_df: pd.DataFrame) -> None:
#     _section_label("🎓 Grade Distribution")
#     if marks_df.empty:
#         st.info("No marks data yet.", icon="ℹ️")
#         return

#     df = marks_df.copy()
#     df["grade"] = df["grade_point"].apply(_grade_letter)
#     counts = df["grade"].value_counts().reset_index()
#     counts.columns = ["Grade", "Count"]

#     order = [g for _, g in [(0, "A"), (1, "A-"), (2, "B+"), (3, "B"),
#                              (4, "B-"), (5, "C+"), (6, "C"), (7, "C-"),
#                              (8, "D"), (9, "F")]]
#     counts["_ord"] = counts["Grade"].map(
#         {g: i for i, g in enumerate(order)}
#     ).fillna(99)
#     counts.sort_values("_ord", inplace=True)
#     avg_gp = df["grade_point"].mean()

#     if _PLOTLY_OK:
#         fig = go.Figure(go.Pie(
#             labels    = counts["Grade"],
#             values    = counts["Count"],
#             hole      = 0.46,
#             marker    = dict(
#                 colors=[_GRADE_COLOURS.get(g, _SLATE) for g in counts["Grade"]],
#                 line  = dict(color="white", width=2),
#             ),
#             textinfo  = "percent+label",
#             hovertemplate=(
#                 "%{label}<br>Count: %{value}<br>%{percent}<extra></extra>"
#             ),
#         ))
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height     = 360,
#             showlegend = True,
#             legend     = dict(orientation="v", yanchor="middle", y=0.5),
#             annotations=[dict(
#                 text      = f"Avg GP<br><b>{avg_gp:.2f}</b>",
#                 x=0.5, y=0.5,
#                 font_size = 14,
#                 showarrow = False,
#                 font_color= _NAVY,
#             )],
#         )
#         st.plotly_chart(fig, use_container_width=True,
#                         config={"displayModeBar": False})
#     else:
#         st.bar_chart(counts.set_index("Grade")["Count"])


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 5 — Performance-Band Pie  (Excellent / Good / At Risk)
# # ──────────────────────────────────────────────────────────────────────────────

# def _band_pie(cgpa_df: pd.DataFrame) -> None:
#     _section_label("🏅 Performance Band Breakdown")
#     if cgpa_df.empty:
#         st.info("No CGPA data yet.", icon="ℹ️")
#         return

#     band_counts = cgpa_df["band"].value_counts().reset_index()
#     band_counts.columns = ["Band", "Students"]

#     if _PLOTLY_OK:
#         fig = px.pie(
#             band_counts,
#             names  = "Band",
#             values = "Students",
#             color  = "Band",
#             color_discrete_map={
#                 "Excellent (≥3.50)": _GREEN,
#                 "Good (2.50–3.49)" : _AMBER,
#                 "At Risk (<2.50)"  : _RED,
#             },
#             hole   = 0.42,
#         )
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height=300,
#             showlegend=True,
#             legend=dict(orientation="v", yanchor="middle", y=0.5),
#         )
#         st.plotly_chart(fig, use_container_width=True,
#                         config={"displayModeBar": False})
#     else:
#         st.bar_chart(band_counts.set_index("Band")["Students"])


# # ──────────────────────────────────────────────────────────────────────────────
# # CHART 6 — Credit Hours per Semester
# # ──────────────────────────────────────────────────────────────────────────────

# def _credit_hours_bar(sgpa_df: pd.DataFrame) -> None:
#     _section_label("📐 Total Credit Hours per Semester")
#     if sgpa_df.empty:
#         st.info("No semester data yet.", icon="ℹ️")
#         return

#     ch = (
#         sgpa_df.groupby("semester")["total_credit_hours"]
#         .sum()
#         .reset_index()
#     )
#     ch["sem_label"] = "Sem " + ch["semester"].astype(str)

#     if _PLOTLY_OK:
#         fig = px.bar(
#             ch,
#             x                   = "sem_label",
#             y                   = "total_credit_hours",
#             text                = "total_credit_hours",
#             color_discrete_sequence=[_NAVY],
#             labels={
#                 "total_credit_hours": "Credit Hours",
#                 "sem_label"         : "Semester",
#             },
#         )
#         fig.update_traces(
#             texttemplate = "%{text:.0f}",
#             textposition = "outside",
#         )
#         fig.update_layout(
#             **_LAYOUT_BASE,
#             height = 300,
#             yaxis  = dict(title="Credit Hours"),
#             xaxis  = dict(title="Semester"),
#         )
#         st.plotly_chart(fig, use_container_width=True,
#                         config={"displayModeBar": False})
#     else:
#         st.bar_chart(ch.set_index("sem_label")["total_credit_hours"])


# # ──────────────────────────────────────────────────────────────────────────────
# # TABLE — At-Risk Students  (CGPA < 2.50)
# # ──────────────────────────────────────────────────────────────────────────────

# def _at_risk_table(cgpa_df: pd.DataFrame) -> None:
#     _section_label("⚠️ At-Risk Students (CGPA < 2.50)")
#     if cgpa_df.empty:
#         st.info("No student data yet.", icon="ℹ️")
#         return

#     at_risk = cgpa_df[cgpa_df["cgpa"] < 2.50].copy()
#     if at_risk.empty:
#         st.markdown(
#             '<div class="banner banner-success">✅ No at-risk students — '
#             'every CGPA is ≥ 2.50.</div>',
#             unsafe_allow_html=True,
#         )
#         return

#     st.markdown(
#         f'<div class="banner banner-critical">🚨 '
#         f'<b>{len(at_risk)}</b> student(s) below the 2.50 academic-probation '
#         f'threshold.</div>',
#         unsafe_allow_html=True,
#     )
#     display = at_risk[
#         ["student_name", "roll_no", "department", "cgpa", "semesters_completed"]
#     ].copy()
#     display.columns = ["Student Name", "Roll No", "Department", "CGPA", "Semesters"]
#     display["CGPA"] = display["CGPA"].apply(lambda v: f"{v:.2f}")
#     st.dataframe(
#         display.sort_values("CGPA"),
#         use_container_width=True,
#         hide_index=True,
#     )


# # ──────────────────────────────────────────────────────────────────────────────
# # TABLE — Top Performers  (CGPA ≥ 3.50)
# # ──────────────────────────────────────────────────────────────────────────────

# def _top_performers_table(cgpa_df: pd.DataFrame) -> None:
#     _section_label("🌟 Top Performers (CGPA ≥ 3.50)")
#     if cgpa_df.empty:
#         st.info("No student data yet.", icon="ℹ️")
#         return

#     top = cgpa_df[cgpa_df["cgpa"] >= 3.50].copy()
#     if top.empty:
#         st.info("No students with CGPA ≥ 3.50 yet.", icon="ℹ️")
#         return

#     display = top[
#         ["student_name", "roll_no", "department", "cgpa", "semesters_completed"]
#     ].copy()
#     display.columns = ["Student Name", "Roll No", "Department", "CGPA", "Semesters"]
#     display["CGPA"] = display["CGPA"].apply(lambda v: f"{v:.2f}")
#     st.dataframe(
#         display.sort_values("CGPA", ascending=False),
#         use_container_width=True,
#         hide_index=True,
#     )


# # ──────────────────────────────────────────────────────────────────────────────
# # EXPANDABLE — Semester-by-Semester Aggregate Detail
# # ──────────────────────────────────────────────────────────────────────────────

# def _semester_detail_expander(sgpa_df: pd.DataFrame) -> None:
#     if sgpa_df.empty:
#         return
#     with st.expander("📋 Semester-by-Semester Aggregate Detail", expanded=False):
#         detail = (
#             sgpa_df.groupby("semester")
#             .agg(
#                 Students         = ("student_id"         , "nunique"),
#                 Avg_GPA          = ("gpa"                , "mean"),
#                 Min_GPA          = ("gpa"                , "min"),
#                 Max_GPA          = ("gpa"                , "max"),
#                 Total_Cr_Hrs     = ("total_credit_hours"  , "sum"),
#                 Total_Quality_Pts= ("total_quality_points", "sum"),
#             )
#             .reset_index()
#             .rename(columns={
#                 "semester"        : "Semester",
#                 "Avg_GPA"         : "Avg GPA",
#                 "Min_GPA"         : "Min GPA",
#                 "Max_GPA"         : "Max GPA",
#                 "Total_Cr_Hrs"    : "Total Cr. Hrs",
#                 "Total_Quality_Pts": "Total Quality Pts",
#             })
#         )
#         for col in ["Avg GPA", "Min GPA", "Max GPA"]:
#             detail[col] = detail[col].round(2)
#         detail["Total Quality Pts"] = detail["Total Quality Pts"].round(2)
#         st.dataframe(detail, use_container_width=True, hide_index=True)


# # ──────────────────────────────────────────────────────────────────────────────
# # EXPORT SECTION — three CSV downloads
# # ──────────────────────────────────────────────────────────────────────────────

# def _export_section(
#     cgpa_df : pd.DataFrame,
#     marks_df: pd.DataFrame,
#     sgpa_df : pd.DataFrame,
# ) -> None:
#     with st.expander("⬇ Export Analytics Data (CSV)", expanded=False):
#         c1, c2, c3 = st.columns(3)

#         # 1 — CGPA summary
#         if not cgpa_df.empty:
#             exp = cgpa_df[[
#                 "student_name", "roll_no", "department",
#                 "cgpa", "semesters_completed", "total_credit_hours", "band",
#             ]].copy()
#             exp.columns = [
#                 "Student Name", "Roll No", "Department",
#                 "CGPA", "Semesters", "Cr. Hrs", "Performance Band",
#             ]
#             buf = io.StringIO()
#             exp.to_csv(buf, index=False)
#             c1.download_button(
#                 "CGPA Summary (CSV)",
#                 data             = buf.getvalue(),
#                 file_name        = "analytics_cgpa_summary.csv",
#                 mime             = "text/csv",
#                 use_container_width=True,
#             )

#         # 2 — Semester trends
#         if not sgpa_df.empty:
#             sem_exp = (
#                 sgpa_df.groupby("semester")
#                 .agg(
#                     Students=("student_id"        , "nunique"),
#                     Avg_GPA =("gpa"               , "mean"),
#                     Min_GPA =("gpa"               , "min"),
#                     Max_GPA =("gpa"               , "max"),
#                     Total_CH=("total_credit_hours" , "sum"),
#                 )
#                 .reset_index()
#             )
#             for col in ["Avg_GPA", "Min_GPA", "Max_GPA"]:
#                 sem_exp[col] = sem_exp[col].round(2)
#             buf2 = io.StringIO()
#             sem_exp.to_csv(buf2, index=False)
#             c2.download_button(
#                 "Semester Trends (CSV)",
#                 data             = buf2.getvalue(),
#                 file_name        = "analytics_semester_trends.csv",
#                 mime             = "text/csv",
#                 use_container_width=True,
#             )

#         # 3 — Grade distribution
#         if not marks_df.empty:
#             gd = marks_df.copy()
#             gd["grade"] = gd["grade_point"].apply(_grade_letter)
#             grade_counts = gd["grade"].value_counts().reset_index()
#             grade_counts.columns = ["Grade", "Count"]
#             buf3 = io.StringIO()
#             grade_counts.to_csv(buf3, index=False)
#             c3.download_button(
#                 "Grade Distribution (CSV)",
#                 data             = buf3.getvalue(),
#                 file_name        = "analytics_grade_distribution.csv",
#                 mime             = "text/csv",
#                 use_container_width=True,
#             )


# # ──────────────────────────────────────────────────────────────────────────────
# # PUBLIC ENTRY POINT
# # ──────────────────────────────────────────────────────────────────────────────

# def render_analytics() -> None:
#     """
#     Render the full Analytics tab.
#     Called from app.py:
#         with analytics_tab:
#             render_analytics()
#     """
#     st.markdown(
#         '<div class="stage-title">📊 Analytics Dashboard</div>',
#         unsafe_allow_html=True,
#     )
#     st.markdown(
#         '<div class="stage-subtitle">'
#         'Live insights from the GPA database — CGPA distribution, semester '
#         'GPA trends, subject performance, grade breakdown, and performance '
#         'bands. Updates automatically as new batches are saved.</div>',
#         unsafe_allow_html=True,
#     )

#     # ── Guard: DB module ──────────────────────────────────────────────────────
#     if not _DB_OK:
#         st.error(
#             f"Database module unavailable — fix import errors shown in the "
#             f"sidebar. Detail: {_DB_ERR}",
#             icon="🚫",
#         )
#         return

#     # ── Plotly notice (non-blocking) ──────────────────────────────────────────
#     if not _PLOTLY_OK:
#         st.warning(
#             "📦 `plotly` is not installed — charts fall back to basic "
#             "Streamlit visuals. Run `pip install plotly` for interactive charts.",
#             icon="⚠️",
#         )

#     # ── Load all data ─────────────────────────────────────────────────────────
#     try:
#         marks_df, sgpa_df, cgpa_df, subj_map = _fetch_dataframes()
#     except Exception as exc:
#         st.error(f"Database query failed: {exc}", icon="🚫")
#         st.info(
#             "Run the **GPA Pipeline** tab to save records first, "
#             "then reload Analytics.",
#             icon="ℹ️",
#         )
#         return

#     # ── Empty-state guard ─────────────────────────────────────────────────────
#     if cgpa_df.empty and marks_df.empty:
#         st.markdown("""
#         <div class="upload-zone">
#             <h3>📊 No Data Yet</h3>
#             <p>Process at least one batch through the <b>GPA Pipeline</b> tab.<br>
#                Analytics populate automatically once records are saved to the DB.</p>
#         </div>""", unsafe_allow_html=True)
#         return

#     # ─────────────────────────────────────────────────────────────────────────
#     # KPI STRIP
#     # ─────────────────────────────────────────────────────────────────────────
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     n_stu    = len(cgpa_df)
#     n_sub    = len(subj_map)
#     n_marks  = len(marks_df)
#     n_sems   = sgpa_df["semester"].nunique() if not sgpa_df.empty else 0
#     avg_cgpa = cgpa_df["cgpa"].mean() if not cgpa_df.empty else None
#     n_excel  = int((cgpa_df["cgpa"] >= 3.50).sum()) if not cgpa_df.empty else 0
#     n_risk   = int((cgpa_df["cgpa"] <  2.50).sum()) if not cgpa_df.empty else 0

#     k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
#     for col, val, lbl, clr in [
#         (k1, n_stu,                                   "Students",     _NAVY),
#         (k2, n_sub,                                   "Subjects",     _NAVY),
#         (k3, n_marks,                                 "Mark Records", _NAVY),
#         (k4, n_sems,                                  "Semesters",    _NAVY),
#         (k5, f"{avg_cgpa:.2f}" if avg_cgpa else "—", "Avg CGPA",     _NAVY),
#         (k6, f"🌟 {n_excel}",                         "Excellent",    _GREEN),
#         (k7, f"⚠️ {n_risk}",                          "At Risk",      _RED),
#     ]:
#         col.markdown(_kpi_html(val, lbl, clr), unsafe_allow_html=True)
#     st.markdown('</div>', unsafe_allow_html=True)

#     # Refresh button (right-aligned)
#     _, rbtn = st.columns([8, 1])
#     if rbtn.button("🔄 Refresh", key="analytics_refresh"):
#         st.rerun()

#     st.markdown("<hr class='divider'>", unsafe_allow_html=True)

#     # ─────────────────────────────────────────────────────────────────────────
#     # ROW 1  |  CGPA Histogram  +  Semester Trend
#     # ─────────────────────────────────────────────────────────────────────────
#     col_l1, col_r1 = st.columns(2)
#     with col_l1:
#         _card(_cgpa_histogram, cgpa_df)
#     with col_r1:
#         _card(_semester_trend, sgpa_df)

#     # ─────────────────────────────────────────────────────────────────────────
#     # ROW 2  |  Grade Donut  +  Subject Performance
#     # ─────────────────────────────────────────────────────────────────────────
#     col_l2, col_r2 = st.columns([1, 2])
#     with col_l2:
#         _card(_grade_donut, marks_df)
#     with col_r2:
#         _card(_subject_performance, marks_df, subj_map)

#     # ─────────────────────────────────────────────────────────────────────────
#     # ROW 3  |  Band Pie  +  Credit Hours Bar
#     # ─────────────────────────────────────────────────────────────────────────
#     col_l3, col_r3 = st.columns([1, 2])
#     with col_l3:
#         _card(_band_pie, cgpa_df)
#     with col_r3:
#         _card(_credit_hours_bar, sgpa_df)

#     st.markdown("<hr class='divider'>", unsafe_allow_html=True)

#     # ─────────────────────────────────────────────────────────────────────────
#     # ROW 4  |  At-Risk Table  +  Top Performers Table
#     # ─────────────────────────────────────────────────────────────────────────
#     col_l4, col_r4 = st.columns(2)
#     with col_l4:
#         _card(_at_risk_table, cgpa_df)
#     with col_r4:
#         _card(_top_performers_table, cgpa_df)

#     # ─────────────────────────────────────────────────────────────────────────
#     # EXPANDABLE detail + CSV exports
#     # ─────────────────────────────────────────────────────────────────────────
#     _semester_detail_expander(sgpa_df)
#     _export_section(cgpa_df, marks_df, sgpa_df)

"""
src/dashboard/analytics.py
==========================
Analytics tab — University of Loralai GPA Dashboard
Tech Lead: Arif Khan

Same chart layout as v1.
Surgical upgrades only:
  • CSS-driven entrance animation on every card
  • Bold section headers with left-accent bar + gradient underline
  • Gradient separator between sections
  • Improved KPI boxes — coloured top-border, hover-lift
  • Premium dark-header table cards
  • All chart functions and column layout left untouched
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DB_OK  : bool = False
_DB_ERR : str  = ""
try:
    from src.agents.calculator_agent import get_engine
    from src.models.database_models import Student, Subject, Mark, SemesterGPA, CGPA
    from sqlalchemy.orm import Session
    from sqlalchemy import select as sa_select
    _DB_OK = True
except Exception as _e:
    _DB_ERR = str(_e)

_PLOTLY_OK : bool = False
try:
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    pass

_DEFAULT_DB = "sqlite:///./gpa_system.db"

# ══════════════════════════════════════════════════════════════════════════════
# CSS  —  injected once per render, scoped under .anl-* so nothing leaks
# ══════════════════════════════════════════════════════════════════════════════
_CSS = """
<style>
/* ── entrance animation ─────────────────────────────────────────────────── */
@keyframes anlUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0);    }
}

/* ── page title block ───────────────────────────────────────────────────── */
.anl-page-title {
    font-size: 1.85rem;
    font-weight: 900;
    color: #0F2444;
    letter-spacing: -0.8px;
    line-height: 1.15;
    margin-bottom: 4px;
}
.anl-page-sub {
    font-size: 0.88rem;
    color: #64748B;
    font-weight: 400;
    margin-bottom: 28px;
}

/* ── KPI boxes ──────────────────────────────────────────────────────────── */
.anl-kpi {
    background: #ffffff;
    border-radius: 14px;
    padding: 22px 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 18px rgba(0,0,0,.07);
    border: 1px solid #E2E8F0;
    border-top: 3px solid #0F2444;
    animation: anlUp 0.45s ease-out both;
    transition: transform .18s ease, box-shadow .18s ease;
}
.anl-kpi:hover {
    transform: translateY(-4px);
    box-shadow: 0 6px 18px rgba(0,0,0,.10), 0 18px 40px rgba(0,0,0,.07);
}
.anl-kpi.c-green  { border-top-color: #16A34A; }
.anl-kpi.c-red    { border-top-color: #DC2626; }
.anl-kpi.c-blue   { border-top-color: #2563EB; }
.anl-kpi.c-amber  { border-top-color: #D97706; }

.anl-kpi-val {
    font-size: 2.5rem;
    font-weight: 900;
    color: #0F2444;
    line-height: 1;
    letter-spacing: -1.2px;
}
.anl-kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    color: #64748B;
    margin-top: 7px;
}
.anl-kpi-hint {
    font-size: 0.75rem;
    color: #94A3B8;
    margin-top: 3px;
    line-height: 1.4;
}

/* pulse dot for at-risk count */
@keyframes anlPulse {
    0%, 100% { box-shadow: 0 0 0 0   rgba(220,38,38,.45); }
    55%       { box-shadow: 0 0 0 9px rgba(220,38,38,0);   }
}
.anl-dot {
    display: inline-block;
    width: 9px; height: 9px;
    background: #EF4444;
    border-radius: 50%;
    animation: anlPulse 2.2s ease-in-out infinite;
    margin-right: 5px;
    vertical-align: middle;
    position: relative; top: -1px;
}

/* ── section separator ──────────────────────────────────────────────────── */
.anl-sep {
    height: 2px;
    border: none;
    background: linear-gradient(
        90deg,
        #0F2444   0%,
        #2563EB  28%,
        #CBD5E1  68%,
        transparent 100%
    );
    margin: 40px 0 0 0;
    border-radius: 2px;
}

/* ── section header ─────────────────────────────────────────────────────── */
.anl-sec-wrap {
    display: flex;
    align-items: flex-start;
    gap: 13px;
    margin: 20px 0 22px 0;
}
.anl-sec-bar {
    width: 4px;
    min-height: 42px;
    background: linear-gradient(180deg, #2563EB, #0F2444);
    border-radius: 4px;
    flex-shrink: 0;
}
.anl-sec-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: #0F2444;
    letter-spacing: -0.4px;
    line-height: 1.25;
}
.anl-sec-sub {
    font-size: 0.80rem;
    color: #64748B;
    margin-top: 4px;
    font-weight: 400;
    line-height: 1.5;
}

/* ── chart card ─────────────────────────────────────────────────────────── */
.anl-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px 26px 20px 26px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 20px rgba(0,0,0,.07);
    border: 1px solid rgba(226,232,240,.85);
    margin-bottom: 18px;
    animation: anlUp 0.45s ease-out both;
    transition: box-shadow .20s ease, transform .20s ease;
}
.anl-card:hover {
    box-shadow: 0 4px 14px rgba(0,0,0,.08), 0 16px 40px rgba(0,0,0,.08);
    transform: translateY(-3px);
}
.anl-card-title {
    font-size: 0.98rem;
    font-weight: 800;
    color: #0F2444;
    letter-spacing: -0.3px;
    margin-bottom: 2px;
}
.anl-card-sub {
    font-size: 0.74rem;
    color: #94A3B8;
    margin-bottom: 14px;
    line-height: 1.4;
}

/* ── table card ─────────────────────────────────────────────────────────── */
.anl-tbl {
    background: #ffffff;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 20px rgba(0,0,0,.07);
    border: 1px solid #E2E8F0;
    margin-bottom: 18px;
    animation: anlUp 0.45s ease-out both;
}
.anl-tbl-hd {
    background: linear-gradient(90deg, #0B1E3D 0%, #1E3A6E 100%);
    padding: 16px 22px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.anl-tbl-hd-title {
    font-size: 0.90rem;
    font-weight: 700;
    color: #F1F5F9;
    letter-spacing: -0.15px;
}
.anl-tbl-hd-badge {
    background: rgba(255,255,255,.13);
    color: #CBD5E1;
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 20px;
}
.anl-tbl-body { padding: 14px 18px; }

/* alert banners inside tables */
.anl-alert-r {
    background: linear-gradient(135deg,#FEF2F2,#FEE2E2);
    border: 1px solid #FECACA;
    border-left: 4px solid #DC2626;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.84rem;
    color: #7F1D1D;
    font-weight: 500;
    margin-bottom: 12px;
    line-height: 1.5;
}
.anl-alert-g {
    background: linear-gradient(135deg,#F0FDF4,#DCFCE7);
    border: 1px solid #BBF7D0;
    border-left: 4px solid #16A34A;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.84rem;
    color: #14532D;
    font-weight: 500;
}
</style>
"""

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS  (plotly)
# ══════════════════════════════════════════════════════════════════════════════
_NAVY  = "#0F2444"
_BLUE  = "#2563EB"
_GREEN = "#059669"
_AMBER = "#D97706"
_RED   = "#DC2626"
_SLATE = "#64748B"

_PL: dict[str, Any] = dict(
    plot_bgcolor  = "white",
    paper_bgcolor = "white",
    font          = dict(family="Inter, Segoe UI, sans-serif",
                         size=13, color="#374151"),
    margin        = dict(l=8, r=8, t=8, b=8),
    hoverlabel    = dict(bgcolor="white", font_size=13,
                         font_family="Inter, Segoe UI"),
)

_GP_LETTERS = [
    (4.00,"A"),(3.70,"A-"),(3.30,"B+"),(3.00,"B"),
    (2.70,"B-"),(2.30,"C+"),(2.00,"C"),(1.70,"C-"),(1.00,"D"),
]
_GRADE_CLR = {
    "A":"#15803D","A-":"#16A34A","B+":"#4ADE80","B":"#84CC16",
    "B-":"#BEF264","C+":"#EAB308","C":"#F59E0B","C-":"#D97706",
    "D":"#F97316","F":"#DC2626",
}

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _letter(gp: float | None) -> str:
    if gp is None: return "F"
    for thr, l in _GP_LETTERS:
        if gp >= thr: return l
    return "F"


def _band(cgpa: float | None) -> str:
    if cgpa is None: return "No Data"
    if cgpa >= 3.50: return "Excellent (≥3.50)"
    if cgpa >= 2.50: return "Good (2.50–3.49)"
    return "At Risk (<2.50)"


def _db_url() -> str:
    return st.session_state.get("db_url", _DEFAULT_DB)


def _md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _sep() -> None:
    """Gradient separator between sections."""
    _md('<div class="anl-sep"></div>')


def _sec(title: str, sub: str) -> None:
    """Bold section header with left-accent bar."""
    _md(f"""
    <div class="anl-sec-wrap">
      <div class="anl-sec-bar"></div>
      <div>
        <div class="anl-sec-title">{title}</div>
        <div class="anl-sec-sub">{sub}</div>
      </div>
    </div>""")


def _card_open(title: str, sub: str) -> None:
    _md(f"""<div class="anl-card">
  <div class="anl-card-title">{title}</div>
  <div class="anl-card-sub">{sub}</div>""")


def _card_close() -> None:
    _md("</div>")


# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def _fetch() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[int,str]]:
    engine = get_engine(_db_url())
    with Session(engine) as sess:
        students  = sess.execute(sa_select(Student)).scalars().all()
        subjects  = sess.execute(sa_select(Subject)).scalars().all()
        marks     = sess.execute(sa_select(Mark)).scalars().all()
        sgpas     = sess.execute(sa_select(SemesterGPA)).scalars().all()
        cgpas_orm = sess.execute(sa_select(CGPA)).scalars().all()

    stu_map  = {s.id: s for s in students}
    subj_map = {s.id: s.subject_name for s in subjects}

    marks_df = pd.DataFrame([{
        "student_id"   : m.student_id, "subject_id": m.subject_id,
        "semester"     : m.semester,   "percentage": m.percentage,
        "grade_point"  : m.grade_point,"quality_points": m.quality_points,
        "is_non_credit": m.is_non_credit,
    } for m in marks]) if marks else pd.DataFrame()

    sgpa_df = pd.DataFrame([{
        "student_id"          : s.student_id, "semester": s.semester,
        "gpa"                 : s.gpa,
        "total_credit_hours"  : s.total_credit_hours,
        "total_quality_points": s.total_quality_points,
    } for s in sgpas if s.gpa is not None]) if sgpas else pd.DataFrame()

    rows = []
    for c in cgpas_orm:
        if c.cgpa is None: continue
        s = stu_map.get(c.student_id)
        rows.append({
            "student_id"         : c.student_id,
            "student_name"       : s.student_name        if s else "Unknown",
            "roll_no"            : s.roll_no             if s else "—",
            "department"         : (s.department or "—") if s else "—",
            "cgpa"               : c.cgpa,
            "semesters_completed": c.semesters_completed,
            "total_credit_hours" : c.total_credit_hours,
        })
    cgpa_df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not cgpa_df.empty:
        cgpa_df["band"] = cgpa_df["cgpa"].apply(_band)

    return marks_df, sgpa_df, cgpa_df, subj_map


# ══════════════════════════════════════════════════════════════════════════════
# KPI ROW
# ══════════════════════════════════════════════════════════════════════════════

def _kpi_row(n_stu: int, n_sub: int, n_marks: int, n_sems: int,
             avg_cgpa: float|None, n_excel: int, n_risk: int) -> None:
    avg  = f"{avg_cgpa:.2f}" if avg_cgpa else "—"
    dot  = '<span class="anl-dot"></span>' if n_risk > 0 else ""
    pex  = f"{round(n_excel/n_stu*100)}%" if n_stu else "—"
    prsk = f"{round(n_risk /n_stu*100)}%" if n_stu else "—"

    specs = [
        ("c-blue",  str(n_stu),        "Students",          f"{n_sems} semester(s) processed"),
        ("c-blue",  str(n_sub),         "Subjects",          "Unique credit-bearing courses"),
        ("",        str(n_marks),       "Mark Records",      "Individual subject records saved"),
        ("",        str(n_sems),        "Semesters",         "Academic semesters in database"),
        ("c-amber", avg,               "Average CGPA",       "Quality pts ÷ credit hrs (HEC)"),
        ("c-green", str(n_excel),      "Distinction",        f"{pex} of students ≥ 3.50"),
        ("c-red",   dot+str(n_risk),   "At Risk",            f"{prsk} of students < 2.50"),
    ]
    cols = st.columns(7)
    for col, (cls, val, lbl, hint) in zip(cols, specs):
        col.markdown(f"""
        <div class="anl-kpi {cls}">
          <div class="anl-kpi-val">{val}</div>
          <div class="anl-kpi-label">{lbl}</div>
          <div class="anl-kpi-hint">{hint}</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CHART FUNCTIONS  — identical chart logic to v1, now inside anl-card wrappers
# ══════════════════════════════════════════════════════════════════════════════

# ── CGPA Distribution ─────────────────────────────────────────────────────────
def _cgpa_histogram(cgpa_df: pd.DataFrame) -> None:
    _card_open("CGPA Distribution",
               "How final CGPAs cluster across the three HEC performance bands")
    if cgpa_df.empty:
        st.info("No CGPA records yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        fig = px.histogram(
            cgpa_df, x="cgpa", color="band", nbins=20,
            color_discrete_map={
                "Excellent (≥3.50)": _GREEN,
                "Good (2.50–3.49)" : _AMBER,
                "At Risk (<2.50)"  : _RED,
            },
            category_orders={"band":["Excellent (≥3.50)","Good (2.50–3.49)","At Risk (<2.50)"]},
            labels={"cgpa":"CGPA","count":"Students","band":""},
        )
        fig.add_vline(x=2.50, line_dash="dash", line_color=_RED,   line_width=1.6,
                      annotation_text="Probation 2.50",
                      annotation_position="top left",
                      annotation_font_color=_RED, annotation_font_size=11)
        fig.add_vline(x=3.50, line_dash="dash", line_color=_GREEN, line_width=1.6,
                      annotation_text="Distinction 3.50",
                      annotation_position="top right",
                      annotation_font_color=_GREEN, annotation_font_size=11)
        fig.update_layout(**_PL, height=380, bargap=0.07,
                          legend=dict(orientation="h", y=-0.14, x=0, title=""),
                          xaxis=dict(title="CGPA", range=[0,4.1], dtick=0.5,
                                     tickformat=".1f", showgrid=False),
                          yaxis=dict(title="Students", gridcolor="#F1F5F9"))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        bins = pd.cut(cgpa_df["cgpa"],
                      bins=[0,1,2,2.5,3,3.5,4.01],
                      labels=["0–1","1–2","2–2.5","2.5–3","3–3.5","3.5–4"])
        st.bar_chart(bins.value_counts().sort_index())
    _card_close()


# ── Semester GPA Trend ────────────────────────────────────────────────────────
def _semester_trend(sgpa_df: pd.DataFrame) -> None:
    _card_open("Per-Semester GPA Trend",
               "Average GPA per semester — bar height with overlay trend line")
    if sgpa_df.empty:
        st.info("No semester GPA data yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        tr = (sgpa_df.groupby("semester")
              .agg(avg=("gpa","mean"), mn=("gpa","min"),
                   mx=("gpa","max"), n=("gpa","count"))
              .reset_index())
        tr["avg"] = tr["avg"].round(2)
        tr["lbl"] = "Sem " + tr["semester"].astype(str)

        clrs = [_GREEN if v>=3.5 else _AMBER if v>=2.5 else _RED
                for v in tr["avg"]]
        fig = go.Figure()
        # shaded min–max range
        fig.add_trace(go.Scatter(
            x=list(tr["lbl"])+list(tr["lbl"][::-1]),
            y=list(tr["mx"])+list(tr["mn"][::-1]),
            fill="toself", fillcolor="rgba(37,99,235,.07)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Bar(
            x=tr["lbl"], y=tr["avg"], name="Avg GPA",
            marker_color=clrs, opacity=0.80,
            text=tr["avg"].apply(lambda v: f"{v:.2f}"),
            textposition="outside",
            textfont=dict(size=13, color=_NAVY),
            hovertemplate="<b>%{x}</b><br>Avg GPA: %{y:.2f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=tr["lbl"], y=tr["avg"], name="Trend",
            mode="lines+markers",
            line=dict(color=_NAVY, width=2.6),
            marker=dict(size=9, color=_NAVY,
                        line=dict(width=2.2, color="white")),
        ))
        fig.add_hline(y=2.50, line_dash="dot", line_color=_RED,   line_width=1.1,
                      annotation_text="2.50 min",
                      annotation_position="bottom right",
                      annotation_font_color=_RED)
        fig.add_hline(y=3.50, line_dash="dot", line_color=_GREEN, line_width=1.1,
                      annotation_text="3.50 distinction",
                      annotation_position="top right",
                      annotation_font_color=_GREEN)
        fig.update_layout(**_PL, height=380,
                          yaxis=dict(title="Avg GPA", range=[0,4.5],
                                     tickformat=".1f", gridcolor="#F1F5F9"),
                          xaxis=dict(title="", showgrid=False),
                          legend=dict(orientation="h", y=-0.14, x=0),
                          barmode="group")
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.line_chart(sgpa_df.groupby("semester")["gpa"].mean())
    _card_close()


# ── Grade Distribution (Donut) ────────────────────────────────────────────────
def _grade_donut(marks_df: pd.DataFrame) -> None:
    _card_open("Grade Distribution",
               "Letter-grade frequency across all students and subjects")
    if marks_df.empty:
        st.info("No marks data yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        df = marks_df.copy()
        df["grade"] = df["grade_point"].apply(_letter)
        cts = df["grade"].value_counts().reset_index()
        cts.columns = ["Grade","Count"]
        order = [l for _,l in _GP_LETTERS]+["F"]
        cts["_o"] = cts["Grade"].map({g:i for i,g in enumerate(order)}).fillna(99)
        cts.sort_values("_o", inplace=True)
        avg_gp = df["grade_point"].mean()

        fig = go.Figure(go.Pie(
            labels=cts["Grade"], values=cts["Count"], hole=0.46,
            marker=dict(
                colors=[_GRADE_CLR.get(g, _SLATE) for g in cts["Grade"]],
                line=dict(color="white", width=2.4),
            ),
            textinfo="percent+label", textfont_size=12,
            hovertemplate="%{label}<br>%{value} students — %{percent}<extra></extra>",
        ))
        fig.update_layout(**_PL, height=380, showlegend=True,
                          legend=dict(orientation="v", yanchor="middle",
                                      y=0.5, font_size=12),
                          annotations=[dict(
                              text=f"<b>{avg_gp:.2f}</b><br>avg GP",
                              x=0.5, y=0.5, showarrow=False,
                              font=dict(size=15, color=_NAVY),
                          )])
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        df2 = marks_df.copy()
        df2["grade"] = df2["grade_point"].apply(_letter)
        st.bar_chart(df2["grade"].value_counts())
    _card_close()


# ── Subject Performance ───────────────────────────────────────────────────────
def _subject_bar(marks_df: pd.DataFrame, subj_map: dict[int,str]) -> None:
    _card_open("Subject Performance",
               "Average percentage per subject (credit-bearing), class average marked")
    if marks_df.empty:
        st.info("No marks data yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        df = (marks_df[~marks_df["is_non_credit"]]
              if "is_non_credit" in marks_df.columns else marks_df)
        p = (df.groupby("subject_id")
             .agg(avg=("percentage","mean"), n=("student_id","count"))
             .reset_index())
        p["name"] = p["subject_id"].map(
            lambda i: subj_map.get(i, f"Subject {i}"))
        p["avg"]  = p["avg"].round(1)
        p.sort_values("avg", ascending=True, inplace=True)

        class_avg = p["avg"].mean()
        height    = max(320, len(p) * 44)
        fig = px.bar(
            p, x="avg", y="name", orientation="h",
            color="avg",
            color_continuous_scale=[
                [0.00, _RED],[0.50, _AMBER],[0.85, _GREEN],[1.00,"#14532D"]
            ],
            range_color=[0,100],
            text="avg", custom_data=["n"],
            labels={"avg":"Avg %","name":""},
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%", textposition="outside",
            textfont_size=12,
            hovertemplate=(
                "<b>%{y}</b><br>Avg: %{x:.1f}%<br>"
                "Students: %{customdata[0]}<extra></extra>"),
        )
        fig.add_vline(x=class_avg, line_dash="dot", line_color=_NAVY,
                      line_width=1.3,
                      annotation_text=f"avg {class_avg:.1f}%",
                      annotation_position="top right",
                      annotation_font_color=_NAVY, annotation_font_size=10)
        fig.update_layout(**_PL, height=height,
                          coloraxis_showscale=False,
                          xaxis=dict(title="Average Percentage",
                                     range=[0,115], showgrid=False),
                          yaxis=dict(title="", gridcolor="#F1F5F9"))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.bar_chart(marks_df.groupby("subject_id")["percentage"].mean())
    _card_close()


# ── Performance Band Pie ──────────────────────────────────────────────────────
def _band_pie(cgpa_df: pd.DataFrame) -> None:
    _card_open("Performance Band Breakdown",
               "Share of students in each HEC academic standing tier")
    if cgpa_df.empty:
        st.info("No CGPA data yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        bc = cgpa_df["band"].value_counts().reset_index()
        bc.columns = ["Band","Students"]
        fig = px.pie(
            bc, names="Band", values="Students", color="Band", hole=0.44,
            color_discrete_map={
                "Excellent (≥3.50)": _GREEN,
                "Good (2.50–3.49)" : _AMBER,
                "At Risk (<2.50)"  : _RED,
            },
        )
        fig.update_traces(
            textinfo="percent+label", textfont_size=12,
            marker=dict(line=dict(color="white", width=2.4)),
        )
        fig.update_layout(**_PL, height=380, showlegend=False)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.bar_chart(cgpa_df["band"].value_counts())
    _card_close()


# ── Credit Hours per Semester ─────────────────────────────────────────────────
def _credit_bar(sgpa_df: pd.DataFrame) -> None:
    _card_open("Credit Hours per Semester",
               "Total academic credit hours processed and stored per semester")
    if sgpa_df.empty:
        st.info("No semester data yet.", icon="ℹ️")
    elif _PLOTLY_OK:
        ch = (sgpa_df.groupby("semester")["total_credit_hours"]
              .sum().reset_index())
        ch["lbl"] = "Sem " + ch["semester"].astype(str)
        fig = px.bar(ch, x="lbl", y="total_credit_hours",
                     text="total_credit_hours",
                     color_discrete_sequence=[_NAVY],
                     labels={"total_credit_hours":"Credit Hours","lbl":""})
        fig.update_traces(
            texttemplate="%{text:.0f}", textposition="outside",
            textfont=dict(size=13, color=_NAVY),
            marker_line_color="white", marker_line_width=1.5,
        )
        fig.update_layout(**_PL, height=380,
                          yaxis=dict(title="Credit Hours",
                                     gridcolor="#F1F5F9"),
                          xaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.bar_chart(sgpa_df.groupby("semester")["total_credit_hours"].sum())
    _card_close()


# ══════════════════════════════════════════════════════════════════════════════
# TABLE CARDS
# ══════════════════════════════════════════════════════════════════════════════

def _at_risk_table(cgpa_df: pd.DataFrame) -> None:
    at_risk = cgpa_df[cgpa_df["cgpa"] < 2.50] if not cgpa_df.empty else pd.DataFrame()
    n = len(at_risk)
    _md(f"""
    <div class="anl-tbl">
      <div class="anl-tbl-hd">
        <div class="anl-tbl-hd-title">At-Risk Monitor</div>
        <div class="anl-tbl-hd-badge">{n} student{'s' if n!=1 else ''}</div>
      </div>
      <div class="anl-tbl-body">""")

    if n == 0:
        _md('<div class="anl-alert-g">No students below the 2.50 probation threshold.</div>')
    else:
        _md(f'<div class="anl-alert-r"><span class="anl-dot"></span>'
            f'<strong>{n} student{"s" if n>1 else ""}</strong> '
            f'below the 2.50 academic probation threshold.</div>')
        d = at_risk[["student_name","roll_no","department",
                     "cgpa","semesters_completed"]].copy()
        d.columns = ["Student Name","Roll No","Department","CGPA","Semesters"]
        d["CGPA"] = d["CGPA"].apply(lambda v: f"{v:.2f}")
        st.dataframe(d.sort_values("CGPA"),
                     use_container_width=True, hide_index=True)

    _md('</div></div>')


def _top_table(cgpa_df: pd.DataFrame) -> None:
    top = cgpa_df[cgpa_df["cgpa"] >= 3.50] if not cgpa_df.empty else pd.DataFrame()
    n   = len(top)
    _md(f"""
    <div class="anl-tbl">
      <div class="anl-tbl-hd">
        <div class="anl-tbl-hd-title">Honours List</div>
        <div class="anl-tbl-hd-badge">{n} student{'s' if n!=1 else ''}</div>
      </div>
      <div class="anl-tbl-body">""")

    if n == 0:
        st.info("No students with CGPA ≥ 3.50 yet.", icon="ℹ️")
    else:
        d = top[["student_name","roll_no","department",
                 "cgpa","semesters_completed"]].copy()
        d.columns = ["Student Name","Roll No","Department","CGPA","Semesters"]
        d["CGPA"] = d["CGPA"].apply(lambda v: f"{v:.2f}")
        st.dataframe(d.sort_values("CGPA", ascending=False),
                     use_container_width=True, hide_index=True)

    _md('</div></div>')


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def _export(cgpa_df: pd.DataFrame, marks_df: pd.DataFrame,
            sgpa_df: pd.DataFrame) -> None:
    with st.expander("⬇ Download Analytics Data (CSV)", expanded=False):
        c1, c2, c3 = st.columns(3)
        if not cgpa_df.empty:
            e = cgpa_df[["student_name","roll_no","department",
                         "cgpa","semesters_completed","total_credit_hours","band"]].copy()
            e.columns = ["Student","Roll No","Dept","CGPA",
                         "Semesters","Cr. Hrs","Band"]
            buf = io.StringIO(); e.to_csv(buf, index=False)
            c1.download_button("CGPA Summary (CSV)", buf.getvalue(),
                               "analytics_cgpa.csv","text/csv",
                               use_container_width=True)
        if not sgpa_df.empty:
            s = (sgpa_df.groupby("semester")
                 .agg(Students=("student_id","nunique"),
                      Avg_GPA=("gpa","mean"),
                      Total_CH=("total_credit_hours","sum"))
                 .reset_index())
            s["Avg_GPA"] = s["Avg_GPA"].round(2)
            buf2 = io.StringIO(); s.to_csv(buf2, index=False)
            c2.download_button("Semester Trends (CSV)", buf2.getvalue(),
                               "analytics_semesters.csv","text/csv",
                               use_container_width=True)
        if not marks_df.empty:
            gd = marks_df.copy()
            gd["grade"] = gd["grade_point"].apply(_letter)
            gc = gd["grade"].value_counts().reset_index()
            gc.columns = ["Grade","Count"]
            buf3 = io.StringIO(); gc.to_csv(buf3, index=False)
            c3.download_button("Grade Distribution (CSV)", buf3.getvalue(),
                               "analytics_grades.csv","text/csv",
                               use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render_analytics() -> None:
    """Called from app.py → with analytics_tab: render_analytics()"""

    # inject CSS
    _md(_CSS)

    if not _DB_OK:
        st.error(f"Database unavailable: {_DB_ERR}", icon="🚫"); return
    if not _PLOTLY_OK:
        st.warning("Run `pip install plotly` for interactive charts.", icon="⚠️")

    # ── load data ─────────────────────────────────────────────────────────────
    try:
        marks_df, sgpa_df, cgpa_df, subj_map = _fetch()
    except Exception as exc:
        st.error(f"Database error: {exc}", icon="🚫")
        st.info("Run the GPA Pipeline first to populate the database.", icon="ℹ️")
        return

    if cgpa_df.empty and marks_df.empty:
        st.markdown("""
        <div style="text-align:center;padding:72px 0">
          <div style="font-size:2.8rem;margin-bottom:14px">📊</div>
          <div style="font-size:1.4rem;font-weight:800;color:#0F2444;margin-bottom:8px">
            No Data Yet</div>
          <div style="font-size:.9rem;color:#64748B">
            Process students through the GPA Pipeline first.<br>
            Analytics populate automatically once records are saved.</div>
        </div>""", unsafe_allow_html=True)
        return

    # ── scalars ───────────────────────────────────────────────────────────────
    n_stu   = len(cgpa_df)
    n_sub   = len(subj_map)
    n_marks = len(marks_df)
    n_sems  = sgpa_df["semester"].nunique() if not sgpa_df.empty else 0
    avg_cgpa= cgpa_df["cgpa"].mean() if not cgpa_df.empty else None
    n_excel = int((cgpa_df["cgpa"] >= 3.50).sum()) if not cgpa_df.empty else 0
    n_risk  = int((cgpa_df["cgpa"] <  2.50).sum()) if not cgpa_df.empty else 0

    # ── page title ────────────────────────────────────────────────────────────
    _md("""
    <div class="anl-page-title">Analytics Dashboard</div>
    <div class="anl-page-sub">
      Live academic performance intelligence — updated automatically
      as GPA batches are saved to the database.
    </div>""")

    # ── KPI row ───────────────────────────────────────────────────────────────
    _kpi_row(n_stu, n_sub, n_marks, n_sems, avg_cgpa, n_excel, n_risk)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Distribution & Trends
    # ══════════════════════════════════════════════════════════════════════════
    _sep()
    _sec("Distribution & Trends",
         "CGPA histogram across HEC bands and average GPA trend per semester")

    col1, col2 = st.columns(2)
    with col1:
        _cgpa_histogram(cgpa_df)
    with col2:
        _semester_trend(sgpa_df)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Grade & Subject Analysis
    # ══════════════════════════════════════════════════════════════════════════
    _sep()
    _sec("Grade & Subject Analysis",
         "Letter-grade frequency and per-subject average percentage ranking")

    col3, col4 = st.columns([1, 2])
    with col3:
        _grade_donut(marks_df)
    with col4:
        _subject_bar(marks_df, subj_map)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Standing Breakdown & Load
    # ══════════════════════════════════════════════════════════════════════════
    _sep()
    _sec("Standing Breakdown & Credit Load",
         "Performance tier proportions and total credit hours processed per semester")

    col5, col6 = st.columns([1, 2])
    with col5:
        _band_pie(cgpa_df)
    with col6:
        _credit_bar(sgpa_df)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — Student Watchlist
    # ══════════════════════════════════════════════════════════════════════════
    _sep()
    _sec("Student Watchlist",
         "Academic risk monitor (CGPA < 2.50) and honours list (CGPA ≥ 3.50)")

    col7, col8 = st.columns(2)
    with col7:
        _at_risk_table(cgpa_df)
    with col8:
        _top_table(cgpa_df)

    # ══════════════════════════════════════════════════════════════════════════
    # EXPANDABLE DETAIL + EXPORT
    # ══════════════════════════════════════════════════════════════════════════
    _md('<div style="height:12px"></div>')

    if not sgpa_df.empty:
        with st.expander("Semester-by-Semester Aggregate Detail", expanded=False):
            det = (sgpa_df.groupby("semester")
                   .agg(Students=("student_id","nunique"),
                        Avg_GPA=("gpa","mean"),
                        Min=("gpa","min"), Max=("gpa","max"),
                        Total_CH=("total_credit_hours","sum"),
                        Quality_Pts=("total_quality_points","sum"))
                   .reset_index()
                   .rename(columns={"semester":"Semester",
                                    "Avg_GPA":"Avg GPA",
                                    "Total_CH":"Cr. Hrs",
                                    "Quality_Pts":"Quality Pts"}))
            for c in ["Avg GPA","Min","Max"]:
                det[c] = det[c].round(2)
            det["Quality Pts"] = det["Quality Pts"].round(2)
            st.dataframe(det, use_container_width=True, hide_index=True)

    _export(cgpa_df, marks_df, sgpa_df)

    # refresh + footer
    _md('<div style="height:8px"></div>')
    _, rc = st.columns([9,1])
    if rc.button("🔄 Refresh", key="anl_refresh"):
        st.rerun()

    _md("""
    <div style="text-align:center;padding:28px 0 6px;
                font-size:.66rem;color:#CBD5E1;letter-spacing:1.4px;
                text-transform:uppercase">
      HEC Pakistan GPA Standard &nbsp;·&nbsp;
      University of Loralai — CS Department
    </div>""")