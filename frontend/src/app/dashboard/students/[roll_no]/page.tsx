"use client";

import React, { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Download } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { studentsApi, transcriptsApi } from "@/lib/api";
import { formatCGPA, cn, downloadBlob } from "@/lib/utils";
import type { StudentDetail, SemesterDetail } from "@/types";

// ── Local types ─────────────────────────────────────────────────────────────
interface CGPAHistoryItem {
  semester: number;
  cgpa: number | null;
  gpa?: number | null;
  academic_year?: string;
}

interface CGPAHistoryResponse {
  history?: CGPAHistoryItem[];
  data?: CGPAHistoryItem[];
}

// ── CGPA colour ──────────────────────────────────────────────────────────────
function cgpaColor(v: number | null): string {
  if (v == null) return "text-[#94A3B8]";
  if (v >= 3.5) return "text-[#16A34A]";
  if (v >= 2.0) return "text-[#D97706]";
  return "text-[#DC2626]";
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
function CGPATooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg shadow-lg px-3 py-2">
      <p className="text-xs text-[#64748B]">Semester {label}</p>
      <p className="text-sm font-semibold text-[#0F172A]">
        CGPA: {Number(payload[0].value).toFixed(2)}
      </p>
    </div>
  );
}

// ── Semester tab content ──────────────────────────────────────────────────────
function SemesterTab({ sem }: { sem: SemesterDetail }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#E2E8F0]">
            {["S.No", "Subject", "C.Hrs", "Marks", "G.P", "Grade"].map((h) => (
              <th
                key={h}
                className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sem.subjects.map((subj, i) => (
            <tr
              key={i}
              className={cn(
                "border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC] transition-colors",
                subj.is_non_credit ? "opacity-60 italic" : ""
              )}
            >
              <td className="py-3 px-4 text-[#94A3B8] text-xs">{i + 1}</td>
              <td className="py-3 px-4 text-[#0F172A] font-medium max-w-[200px] truncate">
                {subj.subject_name}
                {subj.is_non_credit && (
                  <span className="ml-2 text-xs text-[#94A3B8] font-normal">
                    (non-credit)
                  </span>
                )}
              </td>
              <td className="py-3 px-4 text-[#64748B]">{subj.credit_hours}</td>
              <td className="py-3 px-4 text-[#64748B]">
                {subj.obtained_marks}/{subj.total_marks}
                <span className="text-xs text-[#94A3B8] ml-1">
                  ({subj.percentage?.toFixed(0)}%)
                </span>
              </td>
              <td className="py-3 px-4 text-[#64748B]">
                {subj.grade_point?.toFixed(2)}
              </td>
              <td className="py-3 px-4">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
                    subj.grade === "A" || subj.grade === "A+"
                      ? "bg-[#DCFCE7] text-[#16A34A]"
                      : subj.grade?.startsWith("B")
                      ? "bg-[#DBEAFE] text-[#2563EB]"
                      : subj.grade?.startsWith("C")
                      ? "bg-[#FEF3C7] text-[#D97706]"
                      : subj.grade === "F"
                      ? "bg-[#FEE2E2] text-[#DC2626]"
                      : "bg-[#F1F5F9] text-[#64748B]"
                  )}
                >
                  {subj.grade}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-[#F8FAFC] border-t-2 border-[#E2E8F0]">
            <td
              colSpan={2}
              className="py-3 px-4 text-xs font-semibold text-[#64748B] uppercase"
            >
              Semester Summary
            </td>
            <td className="py-3 px-4 font-semibold text-[#0F172A]">
              {sem.total_credit_hours}
            </td>
            <td className="py-3 px-4 text-[#64748B]">—</td>
            <td className="py-3 px-4 text-[#64748B]">—</td>
            <td className="py-3 px-4 font-bold text-[#0F172A]">
              GPA: {sem.gpa != null ? sem.gpa.toFixed(2) : "—"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────
export default function StudentDetailPage() {
  const router = useRouter();
  const params = useParams();
  // BUG 13 FIX: decode the URL-encoded roll_no (e.g. "UoL%2FCS-F-22%2F001-BS" → "UoL/CS-F-22/001-BS")
  const roll_no = decodeURIComponent(params?.roll_no as string ?? "");
  // Re-encode for embedding in API URL paths to avoid path-splitting on "/"
  const encodedRollNo = encodeURIComponent(roll_no);

  const [activeTab, setActiveTab] = useState(0);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [upToSem, setUpToSem] = useState<string>("all");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // Fetch student detail
  const {
    data: student,
    isLoading: studentLoading,
    error: studentError,
    refetch: studentRefetch,
  } = useApi<StudentDetail>(
    () => studentsApi.detail(encodedRollNo).then((r) => r.data),
    [encodedRollNo]
  );

  // Fetch CGPA history
  const { data: rawHistory, isLoading: historyLoading } = useApi<
    CGPAHistoryItem[] | CGPAHistoryResponse
  >(
    () => studentsApi.cgpaHistory(encodedRollNo).then((r) => r.data),
    [encodedRollNo]
  );

  const historyItems: CGPAHistoryItem[] = Array.isArray(rawHistory)
    ? rawHistory
    : (rawHistory as CGPAHistoryResponse)?.history ??
      (rawHistory as CGPAHistoryResponse)?.data ?? [];

  const chartData = historyItems.map((h) => ({
    name: String(h.semester),
    // BUG FIX: backend returns 'cgpa_after_semester', not 'cgpa'
    cgpa: (h as unknown as { cgpa_after_semester?: number }).cgpa_after_semester ?? h.cgpa ?? h.gpa ?? 0,
  }));

  // Generate transcript
  const handleGenerateTranscript = async () => {
    setIsGenerating(true);
    setGenError(null);
    try {
      const res = await transcriptsApi.generate({
        roll_no: roll_no,
        up_to_semester: upToSem === "all" ? null : Number(upToSem),
        is_unofficial: false,
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      downloadBlob(blob, `transcript-${encodedRollNo}.pdf`);
      setTranscriptOpen(false);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setGenError(e?.response?.data?.detail ?? e?.message ?? "Failed to generate transcript");
    } finally {
      setIsGenerating(false);
    }
  };

  // ── Loading / error states ───────────────────────────────────────────────
  if (studentLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <LoadingSpinner size="lg" text="Loading student profile…" />
      </div>
    );
  }

  if (studentError || !student) {
    // BUG 13 FIX: show friendly error, never render raw error objects
    const safeError = (() => {
      try {
        if (!studentError) return "Student not found.";
        if (typeof studentError === "string") return studentError;
        return "Failed to load student profile. Please try again.";
      } catch {
        return "An unexpected error occurred.";
      }
    })();
    return (
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-sm text-[#64748B] hover:text-[#0F172A] mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <ErrorMessage
          message={safeError}
          onRetry={studentRefetch}
        />
      </div>
    );
  }

  const semesters: SemesterDetail[] = student.semesters ?? [];

  return (
    <div className="space-y-5">
      {/* Back + header */}
      <div>
        <button
          onClick={() => router.push("/dashboard/students")}
          className="flex items-center gap-2 text-sm text-[#64748B] hover:text-[#0F172A] mb-3 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Students
        </button>
        <PageTitle
          title={student.student_name}
          subtitle={student.roll_no}
          action={
            <div className="flex items-center gap-3">
              <StatusBadge status={student.status} />
              <button
                onClick={() => setTranscriptOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                Generate Transcript
              </button>
            </div>
          }
        />
      </div>

      {/* Section 1 — Identity cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Father Name", value: student.father_name ?? "—" },
          { label: "Department", value: student.department ?? "—" },
          { label: "Semesters Completed", value: student.semesters_completed ?? 0 },
          { label: "Total Credits", value: student.total_credit_hours ?? 0 },
        ].map((item) => (
          <div
            key={item.label}
            className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5"
          >
            <p className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-1">
              {item.label}
            </p>
            <p className="text-lg font-bold text-[#0F172A] truncate">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Section 2 + 3 — CGPA display + chart */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Large CGPA display */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col items-center justify-center text-center">
          <p className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">
            Cumulative GPA
          </p>
          <p
            className={cn(
              "text-6xl font-black leading-none",
              cgpaColor(student.cgpa)
            )}
          >
            {formatCGPA(student.cgpa)}
          </p>
          <p className="text-xs text-[#94A3B8] mt-3">out of 4.00</p>
        </div>

        {/* CGPA Progress Chart */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-[#0F172A]">
              CGPA Progress
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Cumulative GPA after each semester
            </p>
          </div>

          {historyLoading ? (
            <div className="h-44 animate-pulse bg-[#F1F5F9] rounded-lg" />
          ) : chartData.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-sm text-[#94A3B8]">
              No CGPA history yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart
                data={chartData}
                margin={{ top: 5, right: 10, left: -20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "#64748B" }}
                  tickFormatter={(v) => `Sem ${v}`}
                />
                <YAxis
                  domain={[0, 4]}
                  tick={{ fontSize: 11, fill: "#64748B" }}
                  tickCount={5}
                />
                <Tooltip content={<CGPATooltip />} />
                <ReferenceLine
                  y={2.0}
                  stroke="#DC2626"
                  strokeDasharray="4 4"
                  label={{ value: "Min 2.0", fontSize: 10, fill: "#DC2626", position: "insideTopLeft" }}
                />
                <ReferenceLine
                  y={3.5}
                  stroke="#16A34A"
                  strokeDasharray="4 4"
                  label={{ value: "Dean's 3.5", fontSize: 10, fill: "#16A34A", position: "insideTopLeft" }}
                />
                <Line
                  type="monotone"
                  dataKey="cgpa"
                  stroke="#2563EB"
                  strokeWidth={2.5}
                  dot={{ fill: "#2563EB", r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Section 4 — Semester Tabs */}
      {semesters.length > 0 && (
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          {/* Tab headers */}
          <div className="flex overflow-x-auto border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 pt-0">
            {semesters.map((sem, idx) => (
              <button
                key={sem.semester}
                onClick={() => setActiveTab(idx)}
                className={cn(
                  "shrink-0 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
                  activeTab === idx
                    ? "border-[#2563EB] text-[#2563EB]"
                    : "border-transparent text-[#64748B] hover:text-[#0F172A]"
                )}
              >
                Semester {sem.semester}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {semesters[activeTab] && (
            <div>
              <div className="flex items-center justify-between px-4 pt-3 pb-1">
                <p className="text-xs text-[#64748B]">
                  Academic Year:{" "}
                  <span className="font-medium text-[#0F172A]">
                    {semesters[activeTab].academic_year ?? "—"}
                  </span>
                </p>
              </div>
              <SemesterTab sem={semesters[activeTab]} />
            </div>
          )}
        </div>
      )}

      {semesters.length === 0 && !studentLoading && (
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 text-center text-[#94A3B8] text-sm">
          No semester data available yet
        </div>
      )}

      {/* ── Transcript Modal ────────────────────────────────────────────── */}
      <Dialog open={transcriptOpen} onOpenChange={setTranscriptOpen}>
        <DialogContent className="bg-white border border-[#E2E8F0] max-w-md sm:rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-[#0F172A] text-lg font-semibold">
              Generate Transcript
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            <div>
              <label className="block text-sm font-medium text-[#0F172A] mb-1.5">
                Up to Semester
              </label>
              <select
                value={upToSem}
                onChange={(e) => setUpToSem(e.target.value)}
                className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              >
                <option value="all">All Semesters</option>
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>
                    Up to Semester {n}
                  </option>
                ))}
              </select>
            </div>

            {genError && (
              <div className="bg-[#FEE2E2] border border-[#DC2626]/20 rounded-lg p-3 text-sm text-[#DC2626]">
                {genError}
              </div>
            )}

            <button
              onClick={handleGenerateTranscript}
              disabled={isGenerating}
              className="w-full flex items-center justify-center gap-2 h-11 bg-[#2563EB] text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating ? (
                <>
                  <LoadingSpinner size="sm" />
                  Generating PDF…
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Generate and Download
                </>
              )}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
