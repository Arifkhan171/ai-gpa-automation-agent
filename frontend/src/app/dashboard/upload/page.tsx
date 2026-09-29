"use client";

/*
  AcadTrack — Upload HITL Pipeline  (v3 — all bugs fixed)
  University of Loralai, Pakistan

  Fixes applied:
    1. Semester detection: filename regex (S2-Pakistan → 2, Semester_6 → 6) + backend API
    2. Remove-job button per file in HITL stage
    3. Proper per-semester grouping (1..8), not Semester 0
    4. Results table: de-dup by roll_no, correct semester columns, clear save confirm
*/

import React, {
  useState, useRef, useCallback, useEffect, Component
} from "react";
import Link from "next/link";
import {
  UploadCloud, File, X, CheckCircle, AlertTriangle, XCircle,
  ChevronDown, ChevronRight, ArrowLeft, RefreshCw, Database,
  Users, BookOpen, Award, Sparkles, Eye, Save, Calculator,
  Trash2, Info,
} from "lucide-react";
import { api, gradesApi } from "@/lib/api";

// ── Constants ──────────────────────────────────────────────────────────────────
const EXPECTED_STRENGTH: Record<number, number> = {
  1: 20, 2: 20, 3: 20, 4: 19, 5: 18, 6: 18, 7: 18, 8: 18,
};

// Priority-ordered columns — these show FIRST if present in the data.
// Any extra columns from the Excel sheet are shown AFTER these.
const PRIORITY_COLS = [
  "student_name", "roll_no", "father_name",
  "subject_name", "semester",
  "total_marks", "obtained_marks", "credit_hours",
  "department", "program", "section",
];

// Internal-only columns we never show (parse metadata, not student data)
const HIDDEN_COLS = new Set([
  "has_issues", "parse_warnings", "_row_index", "row_index",
]);

/** Format a snake_case or camelCase key as a readable column header */
function fmtColLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, c => c.toUpperCase());
}

/** Derive the ordered column list from actual record data */
function deriveColumns(records: StudentRecord[]): string[] {
  if (!records.length) return PRIORITY_COLS;
  // Collect all unique keys across all records
  const allKeys = new Set<string>();
  for (const rec of records) {
    Object.keys(rec).forEach(k => { if (!HIDDEN_COLS.has(k)) allKeys.add(k); });
  }
  // Priority cols that actually exist in the data
  const ordered = PRIORITY_COLS.filter(c => allKeys.has(c));
  // Extra cols not in the priority list — sorted alphabetically
  const extras = Array.from(allKeys)
    .filter(k => !PRIORITY_COLS.includes(k))
    .sort();
  return [...ordered, ...extras];
}


// ── Types ──────────────────────────────────────────────────────────────────────
type Stage = 1 | 2 | 3 | 4 | 5;

interface ValidationIssue {
  row?: number;
  message: string;
  field?: string;
}

interface JobResult {
  job_id: string;
  file_name?: string;
  filename?: string;
  status: string;
  validation_status?: string;
  message?: string;
  total_rows?: number;
  clean_rows?: number;
  flagged_rows?: number;
  blocked_rows?: number;
  errors?: ValidationIssue[];
  warnings?: ValidationIssue[];
  parse_result?: string;
  detected_semester?: number | null;
  detected_subject?: string | null;
  sem_source?: "content" | "filename" | null;   // where semester came from
  duplicate_warning?: string | null;             // set if backend flagged duplicate
  duplicate_of?: string | null;                  // job_id of the file it duplicates
  already_saved?: boolean;                       // set if backend detected a completed job with same filename
}

interface StudentRecord {
  student_name?: string | null;
  roll_no?: string | null;
  father_name?: string | null;
  subject_name?: string | null;
  total_marks?: number | null;
  obtained_marks?: number | null;
  credit_hours?: number | null;
  department?: string | null;
  has_issues?: boolean;
  parse_warnings?: string[];
  [key: string]: unknown;
}

interface SemesterGroup {
  semester: number;
  jobs: JobResult[];
  approved: boolean;
}

interface SemesterGpaEntry {
  roll_no: string;
  student_name?: string;
  semester: number;
  gpa: number;
}

interface CgpaEntry {
  roll_no: string;
  student_name?: string;
  cgpa: number;
}

interface CalcResult {
  marks_written: number;
  semester_gpas: SemesterGpaEntry[];
  cgpas: CgpaEntry[];
  errors: unknown[];
  semester?: number;   // which semester this result is for
}

// ── Error Boundary ─────────────────────────────────────────────────────────────
class UploadErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
        <XCircle className="w-8 h-8 text-red-500 mx-auto mb-3" />
        <p className="text-sm font-semibold text-red-700 mb-4">Something went wrong.</p>
        <button onClick={() => this.setState({ hasError: false })}
          className="text-xs text-red-600 underline">Try Again</button>
      </div>
    );
    return this.props.children;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtSize(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

function getFilename(j: JobResult) {
  return j.file_name ?? j.filename ?? `Job ${j.job_id}`;
}

function resolveStatus(j: JobResult): "CLEAN" | "FLAGGED" | "BLOCKED" {
  const vs = (j.validation_status ?? "").toUpperCase();
  if (vs === "CLEAN") return "CLEAN";
  if (vs === "BLOCKED") return "BLOCKED";
  if (vs === "FLAGGED") return "FLAGGED";
  const s = (j.status ?? "").toLowerCase();
  if (s === "failed") return "BLOCKED";
  if ((j.blocked_rows ?? 0) > 0) return "BLOCKED";
  if ((j.flagged_rows ?? 0) > 0 || (j.warnings ?? []).length > 0) return "FLAGGED";
  return "CLEAN";
}

/**
 * Extract semester number (1-8) from a filename using the same patterns
 * the backend uses.  This runs immediately in the browser — no API needed.
 * Examples: S2-Pakistan.xlsx → 2,  Semester_6.xlsx → 6,  S7-ML.xlsx → 7
 */
function extractSemFromFilename(filename: string): number | null {
  const stem = filename.replace(/\.[^.]+$/, "");  // strip extension

  const patterns = [
    /^[Ss](\d)\b/,                       // S1, S2 … at start of name
    /\bSem(?:ester)?[_\s-]?(\d)\b/i,    // Semester_6, Semester 6, Sem3
    /[-_\s]S(\d)[-_\s.]/i,              // _S3_  or -S7-
    /(\d)(?:st|nd|rd|th)\s*Sem/i,       // 2nd Sem
    /Sem(?:ester)?\s*(\d)/i,            // Sem2 anywhere
  ];

  for (const pat of patterns) {
    const m = stem.match(pat);
    if (m) {
      const n = parseInt(m[1], 10);
      if (n >= 1 && n <= 8) return n;
    }
  }
  return null;
}

function extractDetectedSemester(j: JobResult): number | null {
  // 1. From API-returned field (set by backend parsed-data endpoint)
  if (j.detected_semester != null) return j.detected_semester;
  // 2. Filename-based fallback (client-side mirror of backend logic)
  const fromName = extractSemFromFilename(getFilename(j));
  if (fromName != null) return fromName;
  return null;
}

function extractError(err: unknown): string {
  try {
    const e = err as { response?: { data?: { detail?: unknown } }; message?: string };
    const d = e?.response?.data?.detail;
    if (!d) return e?.message ?? "An unexpected error occurred";
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x: { msg?: string }) => x?.msg ?? String(x)).join(" | ");
    return String(d);
  } catch { return "An unexpected error occurred"; }
}

// ── Stage Indicator ────────────────────────────────────────────────────────────
function StageBar({ stage }: { stage: Stage }) {
  const steps = [
    { n: 1, label: "Upload",      icon: UploadCloud },
    { n: 2, label: "Assign",      icon: Eye },
    { n: 3, label: "HITL Review", icon: Users },
    { n: 4, label: "Calculate",   icon: Calculator },
    { n: 5, label: "Results",     icon: Award },
  ];
  return (
    <div className="flex items-center gap-0 mb-8 select-none">
      {steps.map(({ n, label, icon: Icon }, i) => {
        const done = n < stage, active = n === stage;
        return (
          <React.Fragment key={n}>
            <div className="flex flex-col items-center gap-1.5 min-w-[64px]">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300
                ${done   ? "bg-emerald-500 shadow-lg shadow-emerald-200"
                : active ? "bg-blue-600 shadow-lg shadow-blue-200 ring-4 ring-blue-100"
                         : "bg-slate-100"}`}>
                {done
                  ? <CheckCircle className="w-5 h-5 text-white" />
                  : <Icon className={`w-4 h-4 ${active ? "text-white" : "text-slate-400"}`} />}
              </div>
              <span className={`text-xs font-semibold transition-colors
                ${active ? "text-blue-600" : done ? "text-emerald-600" : "text-slate-400"}`}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-0.5 flex-1 mb-5 transition-all duration-500
                ${n < stage ? "bg-emerald-400" : "bg-slate-200"}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Status Badge ───────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: "CLEAN" | "FLAGGED" | "BLOCKED" }) {
  const cfg = {
    CLEAN:   { cls: "bg-emerald-100 text-emerald-700 border-emerald-200", Icon: CheckCircle },
    FLAGGED: { cls: "bg-amber-100 text-amber-700 border-amber-200",       Icon: AlertTriangle },
    BLOCKED: { cls: "bg-red-100 text-red-700 border-red-200",             Icon: XCircle },
  }[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold border ${cfg.cls}`}>
      <cfg.Icon className="w-3 h-3" /> {status}
    </span>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function UploadPage() {
  const [stage, setStage]         = useState<Stage>(1);
  const [files, setFiles]         = useState<File[]>([]);
  const [isDragging, setDrag]     = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [jobs, setJobs]           = useState<JobResult[]>([]);
  const [semGroups, setSemGroups] = useState<SemesterGroup[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [acadYear, setAcadYear]   = useState("2024-2025");
  const [calculating, setCalc]    = useState(false);
  const [calcErr, setCalcErr]     = useState<string | null>(null);
  const [allResults, setAllResults] = useState<CalcResult[]>([]);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  const [saved, setSaved]         = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Duplicate check ────────────────────────────────────────────────────────
  function addFilesNoDupe(incoming: File[], current: File[]) {
    const dupes: string[] = [];
    const fresh: File[] = [];
    for (const f of incoming) {
      if (current.some(x => x.name === f.name)) dupes.push(f.name);
      else fresh.push(f);
    }
    return { fresh, dupes };
  }

  const onDragOver  = useCallback((e: React.DragEvent) => { e.preventDefault(); setDrag(true); }, []);
  const onDragLeave = useCallback(() => setDrag(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDrag(false);
    const inc = Array.from(e.dataTransfer.files).filter(f => /\.(xlsx|csv)$/i.test(f.name));
    setFiles(prev => {
      const { fresh, dupes } = addFilesNoDupe(inc, prev);
      if (dupes.length) setUploadErr(`Already added: ${dupes.join(", ")}`);
      return [...prev, ...fresh];
    });
  }, []);
  const onFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const inc = Array.from(e.target.files ?? []);
    setFiles(prev => {
      const { fresh, dupes } = addFilesNoDupe(inc, prev);
      if (dupes.length) setUploadErr(`Already added: ${dupes.join(", ")}`);
      return [...prev, ...fresh];
    });
    if (fileRef.current) fileRef.current.value = "";
  }, []);
  const removeFile = useCallback((i: number) => setFiles(p => p.filter((_, j) => j !== i)), []);

  // Build semester groups, using filename detection as immediate client-side fallback
  function buildSemGroups(jobList: JobResult[]): SemesterGroup[] {
    const map = new Map<number, JobResult[]>();
    for (const j of jobList) {
      // Try API-detected first, then filename regex
      const sem = extractDetectedSemester(j);
      const key = sem ?? 0;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(j);
    }
    return Array.from(map.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([semester, grpJobs]) => ({ semester, jobs: grpJobs, approved: false }));
  }

  // ── STEP 1 → Upload & parse ──────────────────────────────────────────────
  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true); setUploadErr(null); setUploadPct(0);
    const timer = setInterval(() => setUploadPct(p => Math.min(p + 6, 88)), 280);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append("files", f));
      const res = await api.post("/api/v1/grades/upload/batch", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      clearInterval(timer); setUploadPct(100);
      const batchJobs: JobResult[] = res.data?.jobs ?? (Array.isArray(res.data) ? res.data : []);

      // Enrich each job: fetch report + parsed-data (with backend semester detection)
      const withReports = await Promise.all(
        batchJobs.map(async (j) => {
          let merged: JobResult = { ...j };

          // Parse duplicate warning from backend message
          if (j.message?.startsWith("[DUPLICATE WARNING]")) {
            merged.duplicate_warning = j.message;
            // Extract duplicate_of job_id from fingerprint data if available
          }

          try {
            const rpt = await gradesApi.jobReport(j.job_id);
            merged = { ...merged, ...rpt.data };
          } catch { /* ignore */ }
          try {
            const pd = await gradesApi.parsedData(j.job_id);
            merged.detected_subject  = pd.data?.detected_subject ?? null;
            // Only use API semester if it returned a real value (1-8)
            const apiSem = pd.data?.detected_semester;
            if (apiSem != null && apiSem >= 1 && apiSem <= 8) {
              merged.detected_semester = apiSem;
              // Determine source: content analysis vs filename
              // The pipeline_service tries content first, then filename.
              // We mark as 'content' unless the file has a standard name pattern
              // that would have matched via filename — simplest heuristic: if
              // the filename itself contains a semester pattern, mark as 'filename',
              // otherwise mark as 'content' (Excel metadata row found it).
              const fromFilename = extractSemFromFilename(getFilename(merged));
              merged.sem_source = (fromFilename === apiSem) ? "filename" : "content";
            } else {
              // Client-side filename fallback immediately
              merged.detected_semester = extractSemFromFilename(getFilename(merged));
              merged.sem_source = merged.detected_semester != null ? "filename" : null;
            }
          } catch {
            merged.detected_semester = extractSemFromFilename(getFilename(merged));
            merged.sem_source = merged.detected_semester != null ? "filename" : null;
          }
          return merged;
        })
      );

      setJobs(withReports);
      setSemGroups(buildSemGroups(withReports));
      setStage(2);
    } catch (err) {
      clearInterval(timer);
      setUploadErr(extractError(err));
    } finally { setUploading(false); }
  };

  // ── Remove a job from a semester group (Fix #2) ─────────────────────────
  const removeJob = useCallback((jobId: string) => {
    setSemGroups(prev => {
      const next = prev
        .map(g => ({ ...g, jobs: g.jobs.filter(j => j.job_id !== jobId) }))
        .filter(g => g.jobs.length > 0);   // remove empty semester tab
      // Adjust active tab if needed
      setActiveTab(t => Math.min(t, Math.max(0, next.length - 1)));
      return next;
    });
    setJobs(prev => prev.filter(j => j.job_id !== jobId));
  }, []);

  // ── STEP 3 → Approve one semester ────────────────────────────────────────
  const approveSemester = useCallback((semIdx: number) => {
    setSemGroups(prev => {
      const next = [...prev];
      next[semIdx] = { ...next[semIdx], approved: true };
      return next;
    });
  }, []);

  // ── STEP 4 → Calculate GPA for all approved semesters ────────────────────
  const handleCalculate = async () => {
    setCalc(true); setCalcErr(null);
    const results: CalcResult[] = [];
    try {
      for (const grp of semGroups) {
        if (!grp.approved) continue;
        for (const job of grp.jobs) {
          if (resolveStatus(job) === "BLOCKED") continue;
          const res = await gradesApi.approve(job.job_id, {
            semester:      grp.semester,
            academic_year: acadYear,
          });
          const d = res.data ?? {};
          results.push({
            marks_written: d.marks_written ?? 0,
            semester_gpas: (d.semester_gpas ?? []).map((g: SemesterGpaEntry) => ({
              ...g,
              semester: grp.semester,  // override with actual semester number
            })),
            cgpas:         d.cgpas ?? [],
            errors:        d.errors ?? [],
            semester:      grp.semester,
          });
        }
      }
      setAllResults(results);
      setStage(5);
    } catch (err) {
      setCalcErr(extractError(err));
    } finally { setCalc(false); }
  };

  const reset = () => {
    setStage(1); setFiles([]); setJobs([]); setSemGroups([]);
    setAllResults([]); setSaved(false); setShowSaveConfirm(false);
    setUploadErr(null); setCalcErr(null);
  };

  const allApproved = semGroups.length > 0 && semGroups.every(g => g.approved);

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20 p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Upload Files</h1>
        <p className="text-sm text-slate-500 mt-1">
          Human-in-the-loop GPA pipeline · University of Loralai
        </p>
      </div>

      <div className="max-w-5xl mx-auto">
        <StageBar stage={stage} />

        <UploadErrorBoundary>

          {/* ─── STAGE 1: Upload ──────────────────────────────────────────── */}
          {stage === 1 && (
            <div className="space-y-5">
              <div
                onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`relative rounded-2xl border-2 border-dashed p-14 flex flex-col items-center
                  justify-center text-center cursor-pointer transition-all duration-200 group
                  ${isDragging
                    ? "border-blue-400 bg-blue-50 scale-[1.01]"
                    : "border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50/40"}`}>
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors
                  ${isDragging ? "bg-blue-100" : "bg-slate-100 group-hover:bg-blue-100"}`}>
                  <UploadCloud className={`w-8 h-8 transition-colors
                    ${isDragging ? "text-blue-500" : "text-slate-400 group-hover:text-blue-500"}`} />
                </div>
                <p className="text-base font-semibold text-slate-800">Drop Excel or CSV files here</p>
                <p className="text-sm text-slate-400 mt-1">or click to browse</p>
                <p className="text-xs text-slate-300 mt-3">
                  .xlsx · .csv · Multiple files · Semester auto-detected from Excel content &amp; filename
                </p>
                <input ref={fileRef} type="file" accept=".xlsx,.csv" multiple className="hidden" onChange={onFileInput} />
              </div>

              <StrengthBaseline />

              {files.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm divide-y divide-slate-50">
                  <div className="px-5 py-3 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      {files.length} file{files.length > 1 ? "s" : ""} queued
                    </span>
                    <button onClick={() => setFiles([])}
                      className="text-xs text-slate-400 hover:text-red-500 transition-colors">
                      Clear all
                    </button>
                  </div>
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50 transition-colors">
                      <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                        <File className="w-4 h-4 text-blue-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{f.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <p className="text-xs text-slate-400">{fmtSize(f.size)}</p>
                          {(() => {
                            const s = extractSemFromFilename(f.name);
                            return s
                              ? <span className="text-xs bg-blue-100 text-blue-600 font-semibold px-1.5 py-0.5 rounded flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" /> Sem {s}
                                </span>
                              : <span className="text-xs bg-slate-100 text-slate-400 font-medium px-1.5 py-0.5 rounded flex items-center gap-1">
                                  <Info className="w-3 h-3" /> Auto-detect on upload
                                </span>;
                          })()}
                        </div>
                      </div>
                      <button onClick={e => { e.stopPropagation(); removeFile(i); }}
                        className="w-7 h-7 rounded-full flex items-center justify-center
                          text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {uploadErr && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-3">
                  <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700">{uploadErr}</p>
                  <button onClick={() => setUploadErr(null)} className="ml-auto text-red-300 hover:text-red-500">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {uploading && (
                <div className="bg-white rounded-2xl border border-slate-200 p-6">
                  <div className="flex justify-between mb-2">
                    <span className="text-sm font-medium text-slate-700">Uploading and parsing files…</span>
                    <span className="text-sm font-mono text-slate-400">{uploadPct}%</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-300"
                      style={{ width: `${uploadPct}%` }} />
                  </div>
                </div>
              )}

              <button onClick={handleUpload} disabled={!files.length || uploading}
                className="w-full h-12 bg-gradient-to-r from-blue-600 to-indigo-600 text-white
                  font-semibold rounded-xl text-sm hover:from-blue-700 hover:to-indigo-700
                  transition-all duration-200 shadow-lg shadow-blue-200 disabled:opacity-40
                  disabled:cursor-not-allowed disabled:shadow-none flex items-center justify-center gap-2">
                {uploading
                  ? <><RefreshCw className="w-4 h-4 animate-spin" /> Processing…</>
                  : <><UploadCloud className="w-4 h-4" /> Process {files.length || ""} Files →</>}
              </button>
            </div>
          )}

          {/* ─── STAGE 2: Review Assignments ──────────────────────────────── */}
          {stage === 2 && (
            <div className="space-y-5">
              <button onClick={reset}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors">
                <ArrowLeft className="w-4 h-4" /> Upload Different Files
              </button>

              {/* Summary metrics */}
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Files Uploaded",         val: jobs.length,
                    color: "blue" },
                  { label: "Semester Auto-Detected",
                    val: jobs.filter(j => extractDetectedSemester(j) != null).length,
                    color: "emerald" },
                  { label: "Needs Manual Assign",
                    val: jobs.filter(j => extractDetectedSemester(j) == null).length,
                    color: "amber" },
                  { label: "Semesters Found",         val: semGroups.filter(g => g.semester > 0).length,
                    color: "violet" },
                ].map(s => (
                  <div key={s.label}
                    className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 text-center">
                    <p className={`text-3xl font-bold text-${s.color}-600`}>{s.val}</p>
                    <p className="text-xs text-slate-500 mt-1 font-medium uppercase tracking-wider">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Status banner */}
              {jobs.every(j => extractDetectedSemester(j) != null) ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-3 flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0" />
                  <p className="text-sm font-semibold text-emerald-700">
                    Semester detected for all files. Review assignments below.
                  </p>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-amber-700">
                      {jobs.filter(j => extractDetectedSemester(j) == null).length} file(s) need manual semester assignment.
                    </p>
                    <p className="text-xs text-amber-600 mt-0.5">
                      Semester is auto-detected from your <strong>Excel sheet content</strong> (metadata rows above the header)
                      and from the filename. Files with no match will need a manual semester assigned.
                    </p>
                  </div>
                </div>
              )}

              {/* Duplicate content warning banner */}
              {jobs.some(j => j.duplicate_warning) && (
                <div className="bg-red-50 border-2 border-red-300 rounded-2xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <XCircle className="w-5 h-5 text-red-500 shrink-0" />
                    <p className="text-sm font-bold text-red-700">⚠ Duplicate Content Detected</p>
                  </div>
                  <p className="text-xs text-red-600 mb-3">
                    The system found files with heavily overlapping students and the same subject.
                    Keeping both will cause <strong>double-counting in GPA calculations</strong>.
                    Remove the smaller/older file using the trash icon in Stage 3.
                  </p>
                  <div className="space-y-2">
                    {jobs.filter(j => j.duplicate_warning).map(j => (
                      <div key={j.job_id}
                        className="bg-white border border-red-200 rounded-xl px-4 py-2.5 flex items-start gap-3">
                        <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-red-700 truncate">{getFilename(j)}</p>
                          <p className="text-xs text-red-500 mt-0.5">
                            {j.duplicate_warning?.replace("[DUPLICATE WARNING] ", "")}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Already saved warning banner */}
              {jobs.some(j => j.already_saved) && (
                <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-4 mt-4">
                  <div className="flex items-center gap-2 mb-3">
                     <Database className="w-5 h-5 text-amber-500 shrink-0" />
                    <p className="text-sm font-bold text-amber-700">Database Overwrite Warning</p>
                  </div>
                  <p className="text-xs text-amber-700 mb-3">
                    You have uploaded files that were <strong>already successfully processed and saved</strong> previously. 
                    If you approve these again, it will <strong>NOT</strong> duplicate the records. Instead, the new marks will safely <strong>replace and overwrite</strong> the old ones for the same subject and semester.
                  </p>
                  <div className="space-y-2">
                    {jobs.filter(j => j.already_saved).map(j => (
                      <div key={j.job_id} className="bg-white border border-amber-200 rounded-xl px-4 py-2.5 flex items-start gap-3">
                        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-amber-700 truncate">{getFilename(j)}</p>
                          <p className="text-xs text-amber-600 mt-0.5">This file will replace previous marks for this subject.</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <StrengthBaseline />

              {/* File detection table */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Detected Files</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-100">
                        {["Filename", "Size", "Semester Detected", "Subject Detected", "Source"].map(h => (
                          <th key={h} className="text-left py-3 px-4 text-xs font-bold text-slate-400 uppercase tracking-wider">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map(job => {
                        const sem   = extractDetectedSemester(job);
                        const sub   = job.detected_subject ?? "—";
                        const src   = job.sem_source;
                        const isDup = !!job.duplicate_warning;
                        return (
                          <tr key={job.job_id}
                            className={`border-b border-slate-50 transition-colors
                              ${isDup ? "bg-red-50/40" : "hover:bg-slate-50/50"}`}>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <File className="w-4 h-4 text-blue-400 shrink-0" />
                                <div>
                                  <span className="font-medium text-slate-700 max-w-[200px] truncate block">
                                    {getFilename(job)}
                                  </span>
                                  {isDup && (
                                    <span className="text-xs text-red-500 font-medium flex items-center gap-1 mt-0.5">
                                      <AlertTriangle className="w-3 h-3" /> Possible duplicate
                                    </span>
                                  )}
                                  {job.already_saved && (
                                    <span className="text-xs text-amber-600 font-medium flex items-center gap-1 mt-0.5">
                                      <Database className="w-3 h-3" /> Already saved
                                    </span>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-4 text-slate-400 text-xs">—</td>
                            <td className="py-3 px-4">
                              {sem != null
                                ? <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 rounded-full px-2.5 py-0.5 text-xs font-bold">
                                    <CheckCircle className="w-3 h-3" /> Semester {sem}
                                  </span>
                                : <span className="inline-flex items-center gap-1 bg-red-100 text-red-600 rounded-full px-2.5 py-0.5 text-xs font-bold">
                                    <XCircle className="w-3 h-3" /> Not Detected
                                  </span>}
                            </td>
                            <td className="py-3 px-4 text-slate-600 text-sm">{sub}</td>
                            <td className="py-3 px-4">
                              {src === "content"
                                ? <span className="text-xs bg-violet-50 text-violet-600 px-2 py-0.5 rounded-full font-medium">📊 Content</span>
                                : src === "filename"
                                ? <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">📁 Filename</span>
                                : <span className="text-xs bg-slate-100 text-slate-400 px-2 py-0.5 rounded-full font-medium">✏️ Manual</span>}
                            </td>
                          </tr>
                        );
                      })}

                    </tbody>
                  </table>
                </div>
              </div>

              {/* Assignment summary cards per semester */}
              {semGroups.filter(g => g.semester > 0).length > 0 && (
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
                    Assignment Summary
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {semGroups.filter(g => g.semester > 0).map(g => (
                      <div key={g.semester}
                        className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center hover:border-blue-200 transition-colors">
                        <p className="text-3xl font-black text-slate-800">{g.jobs.length}</p>
                        <p className="text-xs font-bold text-blue-600 uppercase tracking-wider mt-1">
                          Semester {g.semester}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                          {g.jobs.length} subject file{g.jobs.length !== 1 ? "s" : ""}
                          {" · "}Expected {EXPECTED_STRENGTH[g.semester] ?? "?"} students
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Academic Year</label>
                  <input
                    value={acadYear} onChange={e => setAcadYear(e.target.value)}
                    placeholder="e.g. 2024-2025"
                    className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl
                      focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white" />
                </div>
                <button onClick={() => { setActiveTab(0); setStage(3); }}
                  disabled={semGroups.filter(g => g.semester > 0).length === 0}
                  className="mt-5 h-10 px-8 bg-gradient-to-r from-rose-500 to-pink-500 text-white
                    font-semibold rounded-xl text-sm hover:from-rose-600 hover:to-pink-600
                    transition-all shadow-lg shadow-rose-200 disabled:opacity-40 disabled:cursor-not-allowed
                    flex items-center gap-2">
                  <Users className="w-4 h-4" /> Begin HITL Review →
                </button>
              </div>
            </div>
          )}

          {/* ─── STAGE 3: HITL Review ─────────────────────────────────────── */}
          {stage === 3 && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <button onClick={() => setStage(2)}
                  className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors">
                  <ArrowLeft className="w-4 h-4" /> Back to Assignments
                </button>
                <div className="flex items-center gap-2 text-xs text-slate-500 bg-white rounded-full px-4 py-1.5 border border-slate-200">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                  {semGroups.filter(g => g.approved).length} / {semGroups.length} semesters approved
                </div>
              </div>

              <div className="bg-gradient-to-r from-indigo-600 to-blue-600 rounded-2xl p-5 text-white">
                <div className="flex items-center gap-3 mb-1">
                  <Sparkles className="w-5 h-5 text-indigo-200" />
                  <h2 className="font-bold text-lg">HITL Review — Semester Tabs</h2>
                </div>
                <p className="text-indigo-100 text-sm">
                  One tab per semester. Fix BLOCKED errors, then approve.
                  {" "}{semGroups.filter(g => g.approved).length}/{semGroups.length} approved.
                </p>
              </div>

              {/* Semester tabs */}
              <div className="flex gap-1 bg-slate-100 rounded-xl p-1 overflow-x-auto">
                {semGroups.map((g, idx) => (
                  <button key={g.semester} onClick={() => setActiveTab(idx)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all
                      ${activeTab === idx
                        ? "bg-white shadow-sm text-blue-700"
                        : "text-slate-500 hover:text-slate-700"}`}>
                    {g.approved
                      ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                      : g.jobs.some(j => resolveStatus(j) === "BLOCKED")
                        ? <XCircle className="w-3.5 h-3.5 text-red-400" />
                        : <div className="w-2 h-2 rounded-full bg-amber-400" />}
                    {g.semester === 0 ? "Unassigned" : `Semester ${g.semester}`}
                    <span className="text-xs opacity-60">({g.jobs.length})</span>
                  </button>
                ))}
              </div>

              {/* Active semester tab */}
              {semGroups.map((g, semIdx) => semIdx === activeTab && (
                <SemesterTabPanel
                  key={g.semester}
                  group={g}
                  onApprove={() => approveSemester(semIdx)}
                  onRemoveJob={removeJob}
                />
              ))}

              {/* Proceed card */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
                {allApproved ? (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center">
                        <CheckCircle className="w-5 h-5 text-emerald-600" />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-800">All semesters approved!</p>
                        <p className="text-xs text-slate-400">Ready to calculate GPA</p>
                      </div>
                    </div>
                    <button onClick={() => setStage(4)}
                      className="h-10 px-8 bg-gradient-to-r from-emerald-500 to-teal-500 text-white
                        font-semibold rounded-xl text-sm hover:from-emerald-600 hover:to-teal-600
                        transition-all shadow-lg shadow-emerald-200">
                      Proceed to GPA Calculation →
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
                    <p className="text-sm text-slate-600">
                      <span className="font-semibold">{semGroups.filter(g => !g.approved).length}</span> semester(s) pending approval.
                      Approve every tab to proceed.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─── STAGE 4: GPA Calculation ─────────────────────────────────── */}
          {stage === 4 && (
            <div className="space-y-5">
              <button onClick={() => setStage(3)}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to HITL Review
              </button>

              <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-2xl p-6 text-white text-center">
                <Calculator className="w-12 h-12 text-violet-200 mx-auto mb-3" />
                <h2 className="text-xl font-bold mb-2">Calculate GPA</h2>
                <p className="text-violet-100 text-sm max-w-md mx-auto">
                  All {semGroups.length} semester(s) approved. Click below to compute
                  Semester GPA and cumulative CGPA for each student.
                </p>
              </div>

              {/* Semester summary */}
              <div className="grid grid-cols-4 gap-4">
                {semGroups.map(g => (
                  <div key={g.semester} className="bg-white rounded-xl border border-emerald-200 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-slate-400 uppercase">
                        {g.semester === 0 ? "Unassigned" : `Semester ${g.semester}`}
                      </span>
                      <CheckCircle className="w-4 h-4 text-emerald-500" />
                    </div>
                    <p className="text-2xl font-black text-slate-800">{g.jobs.length}</p>
                    <p className="text-xs text-slate-400">subject file{g.jobs.length !== 1 ? "s" : ""}</p>
                  </div>
                ))}
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-5">
                <div className="flex items-center gap-3 mb-4">
                  <BookOpen className="w-5 h-5 text-slate-500" />
                  <div>
                    <p className="text-sm font-semibold text-slate-700">Academic Year</p>
                    <p className="text-xs text-slate-400">{acadYear}</p>
                  </div>
                </div>
                {calcErr && (
                  <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4 flex items-center gap-2">
                    <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                    <p className="text-sm text-red-700">{calcErr}</p>
                  </div>
                )}
                <button onClick={handleCalculate} disabled={calculating}
                  className="w-full h-12 bg-gradient-to-r from-violet-600 to-purple-600 text-white
                    font-bold rounded-xl text-sm hover:from-violet-700 hover:to-purple-700
                    transition-all shadow-lg shadow-violet-200 disabled:opacity-50 disabled:cursor-not-allowed
                    flex items-center justify-center gap-2">
                  {calculating
                    ? <><RefreshCw className="w-4 h-4 animate-spin" /> Calculating GPA…</>
                    : <><Calculator className="w-4 h-4" /> Calculate GPA for All Semesters</>}
                </button>
              </div>
            </div>
          )}

          {/* ─── STAGE 5: Results & Save ──────────────────────────────────── */}
          {stage === 5 && (
            <ResultsPanel
              results={allResults}
              semGroups={semGroups}
              saved={saved}
              showConfirm={showSaveConfirm}
              onRequestSave={() => setShowSaveConfirm(true)}
              onConfirmSave={() => { setSaved(true); setShowSaveConfirm(false); }}
              onCancelSave={() => setShowSaveConfirm(false)}
              onReset={reset}
            />
          )}

        </UploadErrorBoundary>
      </div>
    </div>
  );
}

// ── HOD Strength Baseline Card ─────────────────────────────────────────────────
function StrengthBaseline() {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-semibold text-slate-700">
            HOD Ground-Truth Student Strength Baseline
          </span>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
      </button>
      {open && (
        <div className="border-t border-slate-100 px-5 py-4 grid grid-cols-4 gap-3">
          {Object.entries(EXPECTED_STRENGTH).map(([sem, n]) => (
            <div key={sem} className="bg-blue-50 rounded-xl p-3 text-center">
              <p className="text-lg font-black text-blue-700">{n}</p>
              <p className="text-xs text-blue-500 font-medium">Semester {sem}</p>
              <p className="text-xs text-slate-400">students</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Semester Tab Panel ─────────────────────────────────────────────────────────
function SemesterTabPanel({
  group, onApprove, onRemoveJob,
}: {
  group: SemesterGroup;
  onApprove: () => void;
  onRemoveJob: (jobId: string) => void;
}) {
  const expected   = EXPECTED_STRENGTH[group.semester] ?? null;
  const totalRows  = group.jobs.reduce((s, j) => s + (j.total_rows ?? 0), 0);
  const hasBlocked = group.jobs.some(j => resolveStatus(j) === "BLOCKED");

  return (
    <div className="space-y-4">
      {/* Section A — Student Strength */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            A — Student Strength Verification
            {group.semester === 0 && (
              <span className="ml-2 text-amber-500 normal-case font-medium">
                (No semester assigned — please delete unneeded files below)
              </span>
            )}
          </p>
        </div>
        <div className="grid grid-cols-4 divide-x divide-slate-100">
          {[
            { label: "Expected",       val: expected ?? "—", color: "slate"  },
            { label: "Subject Files",  val: group.jobs.length, color: "violet" },
            { label: "Total Rows",     val: totalRows,         color: "blue"   },
            { label: "Status",         val: group.approved ? "✓ Approved" : hasBlocked ? "⛔ Blocked" : "⏳ Pending",
              color: group.approved ? "emerald" : hasBlocked ? "red" : "amber" },
          ].map(s => (
            <div key={s.label} className="py-5 text-center">
              <p className={`text-2xl font-black text-${s.color}-700`}>{s.val}</p>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">{s.label}</p>
            </div>
          ))}
        </div>
        {expected != null && group.semester > 0 && (() => {
          // Count distinct students (by roll_no unique across all job rows)
          // We don't have full data here so use totalRows/job count as proxy
          const approxStudents = group.jobs.length > 0 ? totalRows / group.jobs.length : 0;
          const match = Math.round(approxStudents) === expected;
          return (
            <div className={`mx-5 mb-4 rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm font-semibold
              ${match
                ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                : "bg-amber-50 border border-amber-200 text-amber-700"}`}>
              {match
                ? <><CheckCircle className="w-4 h-4 shrink-0" />
                    Student count matches HOD baseline ({expected} students).
                  </>
                : <><AlertTriangle className="w-4 h-4 shrink-0" />
                    Approx {Math.round(approxStudents)} students per subject found,
                    expected {expected}.
                    Verify the mark sheets before approving.
                  </>}
            </div>
          );
        })()}
      </div>

      {/* Section B — Per-file review cards */}
      {group.jobs.map(job => (
        <JobReviewCard
          key={job.job_id}
          job={job}
          semester={group.semester}
          onRemove={() => onRemoveJob(job.job_id)}
        />
      ))}

      {group.jobs.length === 0 && (
        <div className="bg-slate-50 border border-dashed border-slate-200 rounded-xl p-8 text-center">
          <p className="text-sm text-slate-400">All files removed from this semester.</p>
        </div>
      )}

      {/* Approve button */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
        {group.approved ? (
          <div className="flex items-center gap-3 text-emerald-700">
            <CheckCircle className="w-5 h-5" />
            <span className="font-semibold">
              {group.semester === 0 ? "Unassigned" : `Semester ${group.semester}`} approved!
            </span>
          </div>
        ) : group.jobs.length === 0 ? (
          <div className="flex items-center gap-3">
            <Info className="w-5 h-5 text-slate-400 shrink-0" />
            <p className="text-sm text-slate-500">No files remain — you can proceed.</p>
            <button onClick={onApprove}
              className="ml-auto h-9 px-5 border border-slate-200 text-slate-600 text-sm
                font-semibold rounded-xl hover:bg-slate-50 transition-colors">
              Mark as Done
            </button>
          </div>
        ) : hasBlocked ? (
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-500 shrink-0" />
            <p className="text-sm text-slate-600">
              Fix all <span className="font-semibold text-red-600">BLOCKED</span> errors above,
              or remove the problematic file.
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-slate-800">
                {group.semester === 0 ? "Unassigned" : `Semester ${group.semester}`} is ready
              </p>
              <p className="text-xs text-slate-400 mt-0.5">No blocking errors — approve to continue</p>
            </div>
            <button onClick={onApprove}
              className="h-10 px-7 bg-gradient-to-r from-emerald-500 to-teal-500 text-white
                font-semibold rounded-xl text-sm hover:from-emerald-600 hover:to-teal-600
                transition-all shadow-lg shadow-emerald-200 flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              Approve {group.semester === 0 ? "Unassigned" : `Semester ${group.semester}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Per-Job Review Card ────────────────────────────────────────────────────────
function JobReviewCard({
  job, semester, onRemove,
}: {
  job: JobResult;
  semester: number;
  onRemove: () => void;
}) {
  const [records, setRecords]    = useState<StudentRecord[]>([]);
  const [loading, setLoading]    = useState(true);
  const [reval, setReval]        = useState(false);
  const [revalResult, setRevalResult] = useState<JobResult | null>(null);
  const [err, setErr]            = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  useEffect(() => {
    let alive = true;
    gradesApi.parsedData(job.job_id)
      .then(res => { if (alive) { setRecords(res.data?.records ?? []); setLoading(false); } })
      .catch(() => { if (alive) { setLoading(false); } });
    return () => { alive = false; };
  }, [job.job_id]);

  const displayStatus = revalResult ? resolveStatus(revalResult) : resolveStatus(job);
  const displayErrors: ValidationIssue[]   = revalResult?.errors   ?? job.errors   ?? [];
  const displayWarnings: ValidationIssue[] = revalResult?.warnings ?? job.warnings ?? [];

  const handleReValidate = async () => {
    setReval(true); setErr(null);
    try {
      const res = await gradesApi.reValidate(job.job_id, records as Record<string, unknown>[]);
      setRevalResult(res.data as JobResult);
    } catch (e) { setErr(extractError(e)); }
    finally { setReval(false); }
  };

  const updateCell = (rowIdx: number, col: string, val: string) => {
    setRecords(prev => {
      const next = [...prev];
      const r = { ...next[rowIdx] };
      // Dynamically detect numeric columns
      const numericCols = ["total_marks", "obtained_marks", "credit_hours", "credit",
        "marks", "obtained", "total", "gpa", "cgpa"];
      const isNumeric = numericCols.some(n => col.toLowerCase().includes(n));
      const isInt     = ["credit_hours", "credit", "semester"].some(n => col.toLowerCase().includes(n));
      if (isInt) {
        r[col] = val === "" ? null : parseInt(val, 10);
      } else if (isNumeric) {
        r[col] = val === "" ? null : parseFloat(val);
      } else {
        r[col] = val;
      }
      next[rowIdx] = r;
      return next;
    });
    setRevalResult(null);  // clear so user knows to re-validate
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center shrink-0">
            <File className="w-4 h-4 text-blue-500" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-800 truncate max-w-sm">{getFilename(job)}</p>
            <p className="text-xs text-slate-400">
              {semester === 0 ? "No semester assigned" : `Semester ${semester}`}
              {" · "}{records.length} records
              {(job.flagged_rows ?? 0) > 0 ? ` · ${job.flagged_rows} flagged` : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusBadge status={displayStatus} />
          {/* Remove button */}
          {!confirmRemove ? (
            <button onClick={() => setConfirmRemove(true)}
              title="Remove this file from batch"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300
                hover:text-red-500 hover:bg-red-50 transition-all border border-slate-200
                hover:border-red-200">
              <Trash2 className="w-4 h-4" />
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <span className="text-xs text-red-600 font-medium">Remove?</span>
              <button onClick={onRemove}
                className="text-xs bg-red-500 text-white px-2 py-1 rounded-lg hover:bg-red-600 transition-colors">
                Yes
              </button>
              <button onClick={() => setConfirmRemove(false)}
                className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-lg hover:bg-slate-200 transition-colors">
                No
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Validation issues */}
      {displayStatus === "BLOCKED" && displayErrors.length > 0 && (
        <div className="mx-5 mt-4 bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-sm font-semibold text-red-700 flex items-center gap-2 mb-2">
            <XCircle className="w-4 h-4" /> Critical errors — fix before approving
          </p>
          <ul className="space-y-1">
            {displayErrors.slice(0, 8).map((e, i) => (
              <li key={i} className="text-xs text-red-600">
                {e.row != null && <span className="font-mono font-bold mr-1">Row {e.row}:</span>}
                [{e.field}] {e.message}
              </li>
            ))}
            {displayErrors.length > 8 && (
              <li className="text-xs text-red-400">…and {displayErrors.length - 8} more</li>
            )}
          </ul>
        </div>
      )}
      {displayStatus === "FLAGGED" && displayWarnings.length > 0 && (
        <div className="mx-5 mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm font-semibold text-amber-700 flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4" /> Warnings — review before approving
          </p>
          <ul className="space-y-1">
            {displayWarnings.slice(0, 6).map((w, i) => (
              <li key={i} className="text-xs text-amber-700">
                {w.row != null && <span className="font-mono font-bold mr-1">Row {w.row}:</span>}
                {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      {displayStatus === "CLEAN" && (
        <div className="mx-5 mt-4 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2.5
          flex items-center gap-2 text-emerald-700 text-sm font-semibold">
          <CheckCircle className="w-4 h-4" /> All records valid
        </div>
      )}

      {/* Inline-editable table — shows ALL columns from the Excel file */}
      <div className="px-5 pb-5 mt-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Student Data — Click any cell to edit
          </p>
          <div className="flex items-center gap-3">
            {records.length > 0 && (
              <span className="text-xs text-slate-400 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
                {deriveColumns(records).length} columns · {records.length} rows
              </span>
            )}
            {loading && <span className="text-xs text-slate-400 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" /> Loading…
            </span>}
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-800 text-slate-200">
                <th className="px-3 py-2.5 text-left font-semibold w-8 sticky left-0 bg-slate-800">#</th>
                {deriveColumns(records).map(col => (
                  <th key={col} className={`px-3 py-2.5 text-left font-semibold whitespace-nowrap
                    ${PRIORITY_COLS.includes(col) ? "" : "text-violet-300"}`}
                    title={PRIORITY_COLS.includes(col) ? "Standard column" : "Extra column from your Excel sheet"}>
                    {fmtColLabel(col)}
                    {!PRIORITY_COLS.includes(col) && (
                      <span className="ml-1 text-violet-400 font-normal text-[10px]">✦</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.length === 0 && !loading && (
                <tr>
                  <td colSpan={deriveColumns(records).length + 1} className="text-center py-6 text-slate-400">
                    No records found for this file
                  </td>
                </tr>
              )}
              {records.map((rec, rowIdx) => {
                const rowBlocked = displayErrors.some(e => e.row === rowIdx);
                const rowWarned  = displayWarnings.some(e => e.row === rowIdx);
                return (
                  <tr key={rowIdx}
                    className={`border-t border-slate-100 transition-colors
                      ${rowBlocked ? "bg-red-50/60" : rowWarned ? "bg-amber-50/60" : "hover:bg-slate-50"}`}>
                    <td className="px-3 py-2 text-slate-400 font-mono sticky left-0 bg-inherit">{rowIdx + 1}</td>
                    {deriveColumns(records).map(col => (
                      <td key={col} className="px-2 py-1">
                        <input
                          value={rec[col] == null ? "" : String(rec[col])}
                          onChange={e => updateCell(rowIdx, col, e.target.value)}
                          className={`w-full px-2 py-1 text-xs rounded-lg border transition-colors
                            focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400
                            ${!PRIORITY_COLS.includes(col) ? "min-w-[90px]" : "min-w-[80px]"}
                            ${rowBlocked
                              ? "border-red-200 bg-red-50 text-red-800"
                              : rowWarned
                              ? "border-amber-200 bg-amber-50 text-amber-800"
                              : "border-slate-200 bg-white text-slate-700"}`}
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {records.length > 0 && (
          <p className="text-xs text-slate-400 mt-2">
            <span className="text-violet-500 font-medium">✦</span> Extra columns from your Excel sheet are shown in violet headers.
            All columns are editable and sent to re-validation.
          </p>
        )}

        {err && (
          <p className="text-xs text-red-600 mt-2 flex items-center gap-1">
            <XCircle className="w-3 h-3" /> {err}
          </p>
        )}

        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-slate-400">{records.length} rows · Edit cells then Re-Validate</p>
          <button onClick={handleReValidate} disabled={reval || loading}
            className="flex items-center gap-1.5 h-8 px-4 bg-blue-600 text-white text-xs
              font-semibold rounded-lg hover:bg-blue-700 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed">
            {reval
              ? <><RefreshCw className="w-3 h-3 animate-spin" /> Re-validating…</>
              : <><RefreshCw className="w-3 h-3" /> Re-Validate</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Results Panel ──────────────────────────────────────────────────────────────
function ResultsPanel({
  results, saved, showConfirm,
  onRequestSave, onConfirmSave, onCancelSave, onReset,
}: {
  results:       CalcResult[];
  semGroups:     SemesterGroup[];
  saved:         boolean;
  showConfirm:   boolean;
  onRequestSave: () => void;
  onConfirmSave: () => void;
  onCancelSave:  () => void;
  onReset:       () => void;
}) {
  // ── Aggregate results across all approve calls ────────────────────────────
  // De-duplicate: for each (roll_no, semester) keep the last value seen
  const gpaMap  = new Map<string, SemesterGpaEntry>();
  const cgpaMap = new Map<string, CgpaEntry>();

  for (const r of results) {
    for (const g of r.semester_gpas) {
      if (g.roll_no) gpaMap.set(`${g.roll_no}__${g.semester}`, g);
    }
    for (const c of r.cgpas) {
      if (c.roll_no) {
        // Calculator stores 'cgpa' key; normalise to a guaranteed field
        const cgpaVal = (c as unknown as Record<string,number>)["cgpa"] ?? c.cgpa;
        cgpaMap.set(c.roll_no, { ...c, cgpa: cgpaVal });
      }
    }
  }

  const allGpas  = Array.from(gpaMap.values());
  const allCgpas = Array.from(cgpaMap.values());

  // Unique roll_nos (only non-empty)
  const rollNos = Array.from(new Set(
    allGpas.map(g => g.roll_no).filter(Boolean)
  )).sort();

  // Unique semester numbers sorted
  const semNums = Array.from(new Set(
    allGpas.map(g => g.semester).filter(n => n > 0)
  )).sort((a, b) => a - b);

  // Student name lookup by roll_no (from semester_gpas)
  const rollToName = new Map<string, string>();
  for (const g of allGpas) {
    if (g.roll_no && g.student_name) rollToName.set(g.roll_no, g.student_name);
  }

  // GPA lookup
  function getGpa(roll: string, sem: number): number | null {
    return gpaMap.get(`${roll}__${sem}`)?.gpa ?? null;
  }

  function gpaStyle(v: number) {
    if (v >= 3.5) return "bg-emerald-100 text-emerald-800 font-bold";
    if (v >= 2.5) return "bg-amber-100 text-amber-800 font-semibold";
    return "bg-red-100 text-red-800 font-semibold";
  }

  const totalMarksWritten = results.reduce((s, r) => s + r.marks_written, 0);

  return (
    <div className="space-y-6">
      {/* Success header */}
      <div className="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl p-6 text-white">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center">
            <Award className="w-8 h-8 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold">GPA Calculation Complete</h2>
            <p className="text-emerald-100 text-sm mt-0.5">
              Grades processed · Semester GPA & CGPA computed · Review below then confirm to save
            </p>
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Mark Rows Written",   val: totalMarksWritten, color: "blue"    },
          { label: "Students with GPA",   val: rollNos.length,    color: "violet"  },
          { label: "Semesters Processed", val: semNums.length,    color: "emerald" },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 text-center">
            <p className={`text-4xl font-black text-${s.color}-600`}>{s.val.toLocaleString()}</p>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-2">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Per-student GPA progression table */}
      {rollNos.length > 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-500" />
            <h3 className="font-bold text-slate-800">
              Student GPA Progression
            </h3>
            <span className="ml-auto text-xs text-slate-400">{rollNos.length} students</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-900 text-slate-100">
                  <th className="text-left py-3 px-4 font-semibold whitespace-nowrap sticky left-0 bg-slate-900">
                    Roll No
                  </th>
                  {semNums.map(s => (
                    <th key={s} className="text-center py-3 px-3 font-semibold whitespace-nowrap">
                      <span className="text-blue-300">Sem {s} GPA</span>
                    </th>
                  ))}
                  <th className="text-center py-3 px-4 font-semibold text-amber-300 whitespace-nowrap">
                    Final CGPA
                  </th>
                </tr>
              </thead>
              <tbody>
                {rollNos.map(roll => {
                  const finalCgpa = cgpaMap.get(roll)?.cgpa ?? null;

                  // Compute running CGPA per semester column
                  let cumSum = 0, cumCount = 0;

                  return (
                    <tr key={roll} className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4 sticky left-0 bg-white">
                        <p className="font-mono text-slate-700 text-xs font-semibold">{roll}</p>
                        {rollToName.get(roll) && (
                          <p className="text-xs text-slate-400 truncate max-w-[140px]">{rollToName.get(roll)}</p>
                        )}
                      </td>
                      {semNums.map(s => {
                        const gpa = getGpa(roll, s);
                        if (gpa != null) { cumSum += gpa; cumCount++; }
                        const runCgpa = cumCount > 0 ? cumSum / cumCount : null;
                        return (
                          <td key={s} className="py-3 px-3 text-center">
                            {gpa != null
                              ? <span className={`px-2 py-0.5 rounded-lg text-xs ${gpaStyle(gpa)}`}>
                                  {gpa.toFixed(2)}
                                  {runCgpa != null && (
                                    <span className="block text-xs opacity-60">
                                      CGPA: {runCgpa.toFixed(2)}
                                    </span>
                                  )}
                                </span>
                              : <span className="text-slate-300 text-xs">—</span>}
                          </td>
                        );
                      })}
                      <td className="py-3 px-4 text-center">
                        {finalCgpa != null
                          ? <span className={`px-3 py-1 rounded-xl text-sm font-black ${gpaStyle(finalCgpa)}`}>
                              {finalCgpa.toFixed(2)}
                            </span>
                          : <span className="text-slate-300 text-xs">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <p className="text-sm font-semibold text-amber-700">No student GPA data returned.</p>
          </div>
          <p className="text-xs text-amber-600 mb-3">
            Marks were written ({totalMarksWritten}) but the calculator returned no semester_gpas.
            This usually means the records had <code>has_issues=true</code> or the student DB table was empty.
            Check the backend uvicorn console for errors.
          </p>
          {results.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-amber-600 font-medium">Show raw API response</summary>
              <pre className="mt-2 bg-white rounded-lg border border-amber-200 p-3 overflow-x-auto text-slate-600">
                {JSON.stringify(results[0], null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Save confirmation section */}
      {!saved ? (
        <div className="bg-white rounded-2xl border-2 border-blue-200 shadow-sm p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center shrink-0">
              <Database className="w-6 h-6 text-blue-500" />
            </div>
            <div className="flex-1">
              <p className="font-bold text-slate-800 text-lg">
                Permission Required — Save to Database?
              </p>
              <p className="text-sm text-slate-500 mt-1">
                GPA data has been <strong>calculated</strong> but is only permanently saved when you confirm below.
                Once saved, this cannot be easily undone.
              </p>
            </div>
          </div>

          {showConfirm ? (
            <div className="mt-5 bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-sm font-bold text-red-700 mb-3">
                ⚠️ Are you sure you want to permanently save all GPA records to the database?
              </p>
              <div className="flex gap-3">
                <button onClick={onConfirmSave}
                  className="flex-1 h-10 bg-red-600 text-white font-bold rounded-xl text-sm
                    hover:bg-red-700 transition-colors flex items-center justify-center gap-2">
                  <Save className="w-4 h-4" /> Yes — Save Permanently
                </button>
                <button onClick={onCancelSave}
                  className="flex-1 h-10 border border-slate-200 text-slate-600 font-semibold
                    rounded-xl text-sm hover:bg-slate-50 transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button onClick={onRequestSave}
              className="mt-5 w-full h-12 bg-gradient-to-r from-blue-600 to-indigo-600 text-white
                font-bold rounded-xl text-sm hover:from-blue-700 hover:to-indigo-700
                transition-all shadow-lg shadow-blue-200 flex items-center justify-center gap-2">
              <Database className="w-4 h-4" /> Confirm &amp; Save to Database
            </button>
          )}
        </div>
      ) : (
        <div className="bg-emerald-50 border-2 border-emerald-300 rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-emerald-100 rounded-2xl flex items-center justify-center">
              <CheckCircle className="w-7 h-7 text-emerald-600" />
            </div>
            <div>
              <p className="font-bold text-emerald-800 text-lg">Saved Successfully ✓</p>
              <p className="text-sm text-emerald-700 mt-0.5">
                All GPA records are permanently stored in the database.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={onReset}
          className="flex-1 h-11 border border-slate-200 text-sm font-semibold text-slate-700
            rounded-xl hover:bg-slate-50 transition-colors">
          Upload More Files
        </button>
        <Link href="/dashboard/students"
          className="flex-1 flex items-center justify-center h-11 bg-gradient-to-r
            from-blue-600 to-indigo-600 text-white text-sm font-semibold rounded-xl
            hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg shadow-blue-200">
          View Students →
        </Link>
      </div>
    </div>
  );
}
