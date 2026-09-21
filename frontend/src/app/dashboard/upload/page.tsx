"use client";

import React, { useState, useRef, useCallback } from "react";
import Link from "next/link";
import {
  UploadCloud, File, X, CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronRight,
} from "lucide-react";
import { PageTitle }      from "@/components/shared/PageTitle";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage }   from "@/components/shared/ErrorMessage";
import { api, gradesApi } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────
interface ValidationIssue { row?: number; message: string; field?: string; }

interface JobResult {
  job_id: string;
  file_name?: string;
  filename?: string;
  status: string;           // "awaiting_approval" | "failed" | etc.
  validation_status?: string; // "CLEAN" | "FLAGGED" | "BLOCKED"
  message?: string;
  // report fields
  total_rows?: number;  clean_rows?: number;  flagged_rows?: number;  blocked_rows?: number;
  errors?:   ValidationIssue[];
  warnings?: ValidationIssue[];
}

interface ApprovalResult {
  marks_written?: number;
  semester_gpas?: unknown[];
  cgpas?: unknown[];
  errors?: unknown[];
}

// ── Extract a safe string from FastAPI errors (detail can be array or string)
function extractError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = e?.response?.data?.detail;
  if (!detail)                        return e?.message ?? "Request failed";
  if (typeof detail === "string")     return detail;
  if (Array.isArray(detail))          return detail.map((d: { msg?: string; message?: string }) =>
                                        d?.msg ?? d?.message ?? JSON.stringify(d)).join(" | ");
  return JSON.stringify(detail);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtSize(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b/1024).toFixed(1)} KB`;
  return `${(b/1048576).toFixed(1)} MB`;
}

function getFilename(j: JobResult) { return j.file_name ?? j.filename ?? `Job ${j.job_id}`; }

// Derive a simple 3-state status from whatever the backend gives us
function resolveStatus(j: JobResult): "CLEAN" | "FLAGGED" | "BLOCKED" {
  const vs = (j.validation_status ?? "").toUpperCase();
  if (vs === "CLEAN")   return "CLEAN";
  if (vs === "BLOCKED") return "BLOCKED";
  if (vs === "FLAGGED") return "FLAGGED";
  const s = (j.status ?? "").toLowerCase();
  if (s === "failed")   return "BLOCKED";
  // Has blocking errors?
  if ((j.errors ?? []).length   > 0 && (j.blocked_rows ?? 0) > 0) return "BLOCKED";
  if ((j.warnings ?? []).length > 0 || (j.flagged_rows ?? 0) > 0) return "FLAGGED";
  return "CLEAN";
}

// ── Step Indicator ─────────────────────────────────────────────────────────
function Steps({ step }: { step: number }) {
  const labels = ["Upload", "Validate", "Approve", "Done"];
  return (
    <div className="flex items-center gap-0 mb-8">
      {labels.map((label, i) => {
        const n = i + 1; const done = n < step; const active = n === step;
        return (
          <React.Fragment key={label}>
            <div className="flex flex-col items-center gap-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold
                ${done ? "bg-[#16A34A] text-white" : active ? "bg-[#2563EB] text-white" : "bg-[#E2E8F0] text-[#94A3B8]"}`}>
                {done ? "✓" : n}
              </div>
              <span className={`text-xs font-medium
                ${active ? "text-[#2563EB]" : done ? "text-[#16A34A]" : "text-[#94A3B8]"}`}>
                {label}
              </span>
            </div>
            {i < labels.length - 1 && (
              <div className={`h-px flex-1 mb-4 ${done ? "bg-[#16A34A]" : "bg-[#E2E8F0]"}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Collapsible warnings ───────────────────────────────────────────────────
function Collapsible({ issues, label }: { issues: ValidationIssue[]; label: string }) {
  const [open, setOpen] = useState(false);
  if (!issues.length) return null;
  return (
    <div>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs font-medium text-[#D97706]">
        {open ? <ChevronDown className="w-3.5 h-3.5"/> : <ChevronRight className="w-3.5 h-3.5"/>}
        {label} ({issues.length})
      </button>
      {open && (
        <ul className="mt-2 space-y-1 ml-4">
          {issues.map((iss, i) => (
            <li key={i} className="text-xs text-[#D97706]">
              {iss.row != null && <span className="font-mono font-semibold mr-1">Row {iss.row}:</span>}
              {iss.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function UploadPage() {
  const [step, setStep]       = useState<1|2|3|4>(1);
  const [files, setFiles]     = useState<File[]>([]);
  const [department, setDept] = useState("");
  const [semLabel, setSemLabel]= useState("");
  const [isDragging, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadErr, setUploadErr] = useState<string|null>(null);
  const [jobs, setJobs]       = useState<JobResult[]>([]);
  const [semNumber, setSemNum]= useState(1);
  const [acadYear, setAcadYear]= useState("2024-2025");
  const [approving, setApproving]= useState(false);
  const [approveErr, setApproveErr]= useState<string|null>(null);
  const [result, setResult]   = useState<ApprovalResult|null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Drag & drop ─────────────────────────────────────────────────────────
  const onDragOver  = useCallback((e: React.DragEvent) => { e.preventDefault(); setDrag(true);  }, []);
  const onDragLeave = useCallback(() => setDrag(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDrag(false);
    const valid = Array.from(e.dataTransfer.files).filter(f =>
      f.name.toLowerCase().endsWith(".xlsx") || f.name.toLowerCase().endsWith(".csv"));
    setFiles(p => [...p, ...valid]);
  }, []);
  const onFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(p => [...p, ...Array.from(e.target.files ?? [])]);
    if (fileRef.current) fileRef.current.value = "";
  }, []);
  const removeFile = useCallback((i: number) => setFiles(p => p.filter((_,j) => j !== i)), []);

  // ── STEP 1 → Upload & get reports ────────────────────────────────────────
  // FIX: backend URL is /api/v1/grades/upload/batch  (not /upload-batch)
  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true); setUploadErr(null); setUploadPct(0);
    const timer = setInterval(() => setUploadPct(p => Math.min(p + 8, 85)), 250);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append("files", f));
      if (department) fd.append("department", department);
      if (semLabel)   fd.append("semester_label", semLabel);

      // ✅ Correct URL: /upload/batch  (backend uses slash, not dash)
      const res = await api.post("/api/v1/grades/upload/batch", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      clearInterval(timer); setUploadPct(100);

      // Response: { total_files, succeeded, failed, jobs: [...] }
      const batchJobs: JobResult[] = res.data?.jobs ?? (Array.isArray(res.data) ? res.data : []);

      // Fetch full validation report for each job
      const withReports = await Promise.all(
        batchJobs.map(async (j) => {
          try {
            const rpt = await gradesApi.jobReport(j.job_id);
            return { ...j, ...rpt.data } as JobResult;
          } catch {
            return j; // use basic info if report fetch fails
          }
        })
      );

      setJobs(withReports);
      setStep(2);
    } catch (err: unknown) {
      clearInterval(timer);
      setUploadErr(extractError(err));
    } finally {
      setUploading(false);
    }
  };

  // ── STEP 3 → Approve each non-blocked job individually ───────────────────
  // FIX: backend has /jobs/{job_id}/approve per job (no batch approve endpoint)
  const handleApprove = async () => {
    setApproving(true); setApproveErr(null);
    const agg: ApprovalResult = { marks_written: 0, semester_gpas: [], cgpas: [] };
    try {
      const eligible = jobs.filter(j => resolveStatus(j) !== "BLOCKED");
      for (const job of eligible) {
        const res = await gradesApi.approve(job.job_id, {
          semester:      semNumber,   // ✅ correct field name (backend uses "semester" not "semester_number")
          academic_year: acadYear,
        });
        const d = res.data ?? {};
        agg.marks_written! += d.marks_written ?? 0;
        agg.semester_gpas!  = [...(agg.semester_gpas ?? []), ...(d.semester_gpas ?? [])];
        agg.cgpas!          = [...(agg.cgpas         ?? []), ...(d.cgpas         ?? [])];
      }
      setResult(agg);
      setStep(4);
    } catch (err: unknown) {
      setApproveErr(extractError(err));
    } finally {
      setApproving(false);
    }
  };

  const reset = () => {
    setStep(1); setFiles([]); setDept(""); setSemLabel("");
    setJobs([]); setResult(null); setUploadErr(null); setApproveErr(null);
  };

  const hasBlocked = jobs.some(j => resolveStatus(j) === "BLOCKED");
  const totalClean = jobs.reduce((s,j) => s + (j.clean_rows ?? 0), 0);

  return (
    <div>
      <PageTitle title="Upload Files"
        subtitle="Upload and validate grade sheets for your department" />
      <div className="max-w-3xl mx-auto">
        <Steps step={step} />

        {/* ─── STEP 1: Upload ──────────────────────────────────────────── */}
        {step === 1 && (
          <div className="space-y-5">
            {/* Drop zone */}
            <div
              onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              className={`bg-white rounded-xl border-2 border-dashed p-12 flex flex-col items-center
                justify-center text-center cursor-pointer transition-colors
                ${isDragging ? "border-[#2563EB] bg-[#EFF6FF]" : "border-[#CBD5E1] hover:border-[#2563EB] hover:bg-[#F8FAFC]"}`}>
              <UploadCloud className={`w-12 h-12 mb-4 ${isDragging ? "text-[#2563EB]" : "text-[#94A3B8]"}`} />
              <p className="text-base font-semibold text-[#0F172A]">Drop Excel or CSV files here</p>
              <p className="text-sm text-[#64748B] mt-1">or click to browse</p>
              <p className="text-xs text-[#94A3B8] mt-3">Supports .xlsx and .csv · Multiple files allowed</p>
              <input ref={fileRef} type="file" accept=".xlsx,.csv" multiple className="hidden" onChange={onFileInput}/>
            </div>

            {/* File list */}
            {files.length > 0 && (
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm divide-y divide-[#F1F5F9]">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3">
                    <File className="w-4 h-4 text-[#2563EB] shrink-0"/>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[#0F172A] truncate">{f.name}</p>
                      <p className="text-xs text-[#64748B]">{fmtSize(f.size)}</p>
                    </div>
                    <button onClick={e => { e.stopPropagation(); removeFile(i); }}
                      className="text-[#94A3B8] hover:text-[#DC2626]">
                      <X className="w-4 h-4"/>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Dept + Semester */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Department</label>
                <input value={department} onChange={e => setDept(e.target.value)}
                  placeholder="e.g. CS"
                  className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg
                    focus:outline-none focus:ring-2 focus:ring-[#2563EB]"/>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Semester Label</label>
                <input value={semLabel} onChange={e => setSemLabel(e.target.value)}
                  placeholder="e.g. Semester 1"
                  className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg
                    focus:outline-none focus:ring-2 focus:ring-[#2563EB]"/>
              </div>
            </div>

            {uploadErr && <ErrorMessage message={uploadErr} onRetry={() => setUploadErr(null)}/>}

            {uploading && (
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-[#0F172A]">Uploading and validating…</span>
                  <span className="text-sm text-[#64748B]">{uploadPct}%</span>
                </div>
                <div className="h-2 bg-[#F1F5F9] rounded-full overflow-hidden">
                  <div className="h-full bg-[#2563EB] rounded-full transition-all duration-300"
                    style={{ width: `${uploadPct}%` }}/>
                </div>
              </div>
            )}

            <button onClick={handleUpload} disabled={!files.length || uploading}
              className="w-full flex items-center justify-center gap-2 h-11 bg-[#2563EB] text-white
                text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed">
              {uploading ? <><LoadingSpinner size="sm"/> Processing…</> : "Upload and Validate →"}
            </button>
          </div>
        )}

        {/* ─── STEP 2: Validation Results ─────────────────────────────── */}
        {step === 2 && (
          <div className="space-y-5">
            {jobs.map(job => {
              const status = resolveStatus(job);
              return (
                <div key={job.job_id} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
                  {/* Header */}
                  <div className="flex items-center justify-between p-5 border-b border-[#F1F5F9]">
                    <div>
                      <p className="font-semibold text-[#0F172A]">{getFilename(job)}</p>
                      <p className="text-xs text-[#64748B] mt-0.5">
                        {job.total_rows ?? "?"} total ·{" "}
                        {job.clean_rows ?? 0} clean ·{" "}
                        {job.flagged_rows ?? 0} flagged ·{" "}
                        {job.blocked_rows ?? 0} blocked
                      </p>
                    </div>
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold
                      ${status === "CLEAN"   ? "bg-[#DCFCE7] text-[#16A34A]" :
                        status === "FLAGGED" ? "bg-[#FEF3C7] text-[#D97706]" :
                                               "bg-[#FEE2E2] text-[#DC2626]"}`}>
                      {status === "CLEAN"   && <CheckCircle   className="w-3.5 h-3.5"/>}
                      {status === "FLAGGED" && <AlertTriangle className="w-3.5 h-3.5"/>}
                      {status === "BLOCKED" && <XCircle       className="w-3.5 h-3.5"/>}
                      {status}
                    </span>
                  </div>

                  {/* Banners */}
                  <div className="p-5 space-y-3">
                    {status === "BLOCKED" && (
                      <div className="bg-[#FEE2E2] border border-[#DC2626]/20 rounded-lg p-4">
                        <p className="text-sm font-semibold text-[#DC2626] mb-2 flex items-center gap-1.5">
                          <XCircle className="w-4 h-4"/> Critical errors — must fix before proceeding
                        </p>
                        {(job.errors ?? []).map((e,i) => (
                          <p key={i} className="text-xs text-[#DC2626] ml-5">
                            {e.row != null && <span className="font-mono font-semibold mr-1">Row {e.row}:</span>}
                            {e.message}
                          </p>
                        ))}
                        {job.message && !job.errors?.length && (
                          <p className="text-xs text-[#DC2626] ml-5">{job.message}</p>
                        )}
                      </div>
                    )}
                    {status === "FLAGGED" && (
                      <div className="bg-[#FEF3C7] border border-[#D97706]/20 rounded-lg p-4">
                        <p className="text-sm font-semibold text-[#D97706] mb-2 flex items-center gap-1.5">
                          <AlertTriangle className="w-4 h-4"/> Some records need review
                        </p>
                        <Collapsible issues={job.warnings ?? []} label="Show warnings"/>
                      </div>
                    )}
                    {status === "CLEAN" && (
                      <div className="bg-[#DCFCE7] border border-[#16A34A]/20 rounded-lg p-3">
                        <p className="text-sm font-semibold text-[#16A34A] flex items-center gap-1.5">
                          <CheckCircle className="w-4 h-4"/> All records are valid
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Bottom action */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
              {hasBlocked ? (
                <div className="space-y-3">
                  <p className="text-sm text-[#64748B]">
                    One or more files have critical errors. Fix and re-upload them before proceeding.
                  </p>
                  <button onClick={reset}
                    className="w-full h-10 border border-[#E2E8F0] text-sm font-medium
                      text-[#0F172A] rounded-lg hover:bg-[#F8FAFC] transition-colors">
                    Re-upload Blocked Files
                  </button>
                </div>
              ) : (
                <button onClick={() => setStep(3)}
                  className="w-full h-11 bg-[#2563EB] text-white text-sm font-semibold
                    rounded-xl hover:bg-blue-700 transition-colors">
                  Proceed to Approval →
                </button>
              )}
            </div>
          </div>
        )}

        {/* ─── STEP 3: Approve ─────────────────────────────────────────── */}
        {step === 3 && (
          <div className="space-y-5">
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 space-y-5">
              <h3 className="text-base font-semibold text-[#0F172A]">Approval Details</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Semester Number</label>
                  <select value={semNumber} onChange={e => setSemNum(Number(e.target.value))}
                    className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white
                      focus:outline-none focus:ring-2 focus:ring-[#2563EB]">
                    {[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Semester {n}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Academic Year</label>
                  <input value={acadYear} onChange={e => setAcadYear(e.target.value)}
                    placeholder="e.g. 2024-2025"
                    className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg
                      focus:outline-none focus:ring-2 focus:ring-[#2563EB]"/>
                </div>
              </div>
            </div>

            {/* Summary */}
            <div className="bg-[#F8FAFC] rounded-xl border border-[#E2E8F0] p-5 space-y-2">
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-3">Approval Summary</p>
              <div className="flex justify-between text-sm">
                <span className="text-[#64748B]">Files to approve</span>
                <span className="font-semibold text-[#0F172A]">
                  {jobs.filter(j => resolveStatus(j) !== "BLOCKED").length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#64748B]">Total clean records</span>
                <span className="font-semibold text-[#16A34A]">{totalClean}</span>
              </div>
              <div className="h-px bg-[#E2E8F0] my-2"/>
              <p className="text-xs text-[#64748B]">Records will be saved and GPA will be recalculated.</p>
            </div>

            {approveErr && <ErrorMessage message={approveErr} onRetry={() => setApproveErr(null)}/>}

            <button onClick={handleApprove} disabled={approving}
              className="w-full flex items-center justify-center gap-2 h-11 bg-[#16A34A] text-white
                text-sm font-semibold rounded-xl hover:bg-green-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed">
              {approving ? <><LoadingSpinner size="sm"/> Calculating GPA…</> : "Approve and Calculate GPA"}
            </button>
          </div>
        )}

        {/* ─── STEP 4: Results ─────────────────────────────────────────── */}
        {step === 4 && result && (
          <div className="space-y-5">
            <div className="bg-[#DCFCE7] border border-[#16A34A]/30 rounded-xl p-6 flex items-start gap-4">
              <div className="w-12 h-12 bg-[#16A34A] rounded-full flex items-center justify-center shrink-0">
                <CheckCircle className="w-6 h-6 text-white"/>
              </div>
              <div>
                <p className="text-lg font-bold text-[#16A34A]">GPA Calculation Complete</p>
                <p className="text-sm text-[#16A34A]/80 mt-0.5">All grades saved and GPAs recalculated.</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Marks Written",     val: result.marks_written ?? 0 },
                { label: "GPAs Calculated",   val: result.semester_gpas?.length ?? 0 },
                { label: "CGPAs Updated",     val: result.cgpas?.length ?? 0 },
              ].map(s => (
                <div key={s.label} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 text-center">
                  <p className="text-3xl font-bold text-[#0F172A]">{s.val.toLocaleString()}</p>
                  <p className="text-xs text-[#64748B] mt-1 uppercase tracking-wider">{s.label}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button onClick={reset}
                className="flex-1 h-11 border border-[#E2E8F0] text-sm font-semibold
                  text-[#0F172A] rounded-xl hover:bg-[#F8FAFC] transition-colors">
                Upload More Files
              </button>
              <Link href="/dashboard/students"
                className="flex-1 flex items-center justify-center h-11 bg-[#2563EB] text-white
                  text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors">
                View Students →
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
