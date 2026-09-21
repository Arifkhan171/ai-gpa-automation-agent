"use client";

import React, { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { PageTitle } from "@/components/shared/PageTitle";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { CGPAGauge } from "@/components/shared/CGPAGauge";
import { studentsApi } from "@/lib/api";

import type { SemesterDetail, SubjectMark } from "@/types";

// ── Local types ────────────────────────────────────────────────────────────
interface StudentPortalData {
  student_name: string;
  roll_no: string;
  department: string | null;
  cgpa: number | null;
  total_credit_hours: number;
  semesters_completed: number;
  status: string;
}

interface CgpaHistoryItem {
  semester: number;
  academic_year: string;
  semester_gpa: number | null;
  cgpa_after_semester: number;
  total_credit_hours_so_far: number;
}

interface PortalGradesData {
  student_name?: string;
  roll_no?: string;
  cgpa?: number | null;
  total_credit_hours?: number;
  semesters?: SemesterDetail[];
}

// ── Helpers ────────────────────────────────────────────────────────────────
function getGradePointClass(gp: number): string {
  if (gp >= 3.7) return "text-[#16A34A] font-bold";
  if (gp >= 2.7) return "text-[#D97706] font-bold";
  if (gp >= 1.0) return "text-[#64748B]";
  return "text-[#DC2626] font-bold";
}

function getGradeBadge(grade: string): { bg: string; text: string } {
  const g = grade?.toUpperCase().trim() ?? "";
  if (g === "A" || g === "A-")
    return { bg: "bg-[#DCFCE7]", text: "text-[#16A34A]" };
  if (["B+", "B", "B-"].includes(g))
    return { bg: "bg-[#DBEAFE]", text: "text-[#2563EB]" };
  if (["C+", "C", "C-"].includes(g))
    return { bg: "bg-[#FEF3C7]", text: "text-[#D97706]" };
  if (g === "D") return { bg: "bg-[#FFEDD5]", text: "text-[#EA580C]" };
  if (g === "F") return { bg: "bg-[#FEE2E2]", text: "text-[#DC2626]" };
  if (g === "NC") return { bg: "bg-[#F1F5F9]", text: "text-[#64748B]" };
  return { bg: "bg-[#F1F5F9]", text: "text-[#64748B]" };
}

function cgpaValueColor(cgpa: number | null): string {
  if (cgpa === null) return "text-[#94A3B8]";
  if (cgpa >= 3.5) return "text-[#16A34A]";
  if (cgpa >= 2.0) return "text-[#D97706]";
  return "text-[#DC2626]";
}

// ── Custom Tooltip ─────────────────────────────────────────────────────────
function ChartTooltip({
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
      <p className="text-xs text-[#64748B]">{label}</p>
      <p className="text-sm font-semibold text-[#0F172A]">
        CGPA: {payload[0]?.value?.toFixed(2)}
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function GradesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [meData, setMeData] = useState<StudentPortalData | null>(null);
  const [gradesData, setGradesData] = useState<PortalGradesData | null>(null);
  const [historyData, setHistoryData] = useState<CgpaHistoryItem[]>([]);
  const [activeTab, setActiveTab] = useState(0);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [meRes, gradesRes] = await Promise.all([
        studentsApi.portalMe(),
        studentsApi.portalGrades(),
      ]);

      const me = meRes.data as StudentPortalData;
      const grades = gradesRes.data as PortalGradesData;
      setMeData(me);
      setGradesData(grades);

      if (me?.roll_no) {
        try {
          const histRes = await studentsApi.cgpaHistory(me.roll_no);
          const raw = histRes.data;
          if (Array.isArray(raw)) {
            setHistoryData(raw as CgpaHistoryItem[]);
          } else if (raw && typeof raw === "object") {
            const nested = (raw as Record<string, unknown>).history;
            setHistoryData(Array.isArray(nested) ? (nested as CgpaHistoryItem[]) : []);
          }
        } catch {
          // History is not critical — continue without it
        }
      }
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          "Failed to load academic record"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" text="Loading your academic record…" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorMessage
        message={`Could not load grades: ${error}`}
        onRetry={loadData}
      />
    );
  }

  // Normalise semesters
  const semesters: SemesterDetail[] = Array.isArray(gradesData?.semesters)
    ? [...gradesData!.semesters].sort((a, b) => a.semester - b.semester)
    : [];

  const cgpa = meData?.cgpa ?? gradesData?.cgpa ?? null;
  const totalCH = meData?.total_credit_hours ?? gradesData?.total_credit_hours ?? 0;
  const rollNo = meData?.roll_no ?? "";

  // Chart data
  const chartData = historyData.map((h) => ({
    name: `Sem ${h.semester}`,
    cgpa: h.cgpa_after_semester ?? 0,
  }));

  return (
    <div className="space-y-6">
      <PageTitle
        title="My Academic Record"
        subtitle={rollNo}
      />

      {/* ── CGPA Summary Card ─────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <div className="flex flex-col md:flex-row gap-6">
          {/* Left: CGPA Gauge */}
          <div className="flex flex-col items-center justify-center gap-2 md:border-r md:border-[#E2E8F0] md:pr-6 md:min-w-[180px]">
            <CGPAGauge cgpa={cgpa} size="lg" />
            <div className="text-center mt-1">
              <p className="text-xs text-[#94A3B8] font-medium">
                Cumulative GPA
              </p>
              <p className="text-xs text-[#64748B] mt-0.5">
                {totalCH} credit hours earned
              </p>
            </div>
          </div>

          {/* Right: Chart */}
          <div className="flex-1 min-h-[200px]">
            <h3 className="text-sm font-semibold text-[#0F172A] mb-4">
              CGPA Progression
            </h3>
            {chartData.length < 1 ? (
              <div className="h-44 flex items-center justify-center text-sm text-[#94A3B8]">
                No progression data yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={190}>
                <AreaChart
                  data={chartData}
                  margin={{ top: 8, right: 12, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="cgpaAreaGrad"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="#2563EB"
                        stopOpacity={0.15}
                      />
                      <stop
                        offset="95%"
                        stopColor="#2563EB"
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#F1F5F9"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "#64748B" }}
                  />
                  <YAxis
                    domain={[0, 4]}
                    tickCount={5}
                    tick={{ fontSize: 11, fill: "#64748B" }}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <ReferenceLine
                    y={2.0}
                    stroke="#DC2626"
                    strokeDasharray="6 3"
                    strokeWidth={1.5}
                    label={{
                      value: "Min Required",
                      position: "insideTopRight",
                      fontSize: 10,
                      fill: "#DC2626",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="cgpa"
                    stroke="#2563EB"
                    strokeWidth={2.5}
                    fill="url(#cgpaAreaGrad)"
                    dot={{ fill: "#2563EB", r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: "#2563EB" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* ── No grades state ───────────────────────────────────────────── */}
      {semesters.length === 0 ? (
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-12 flex flex-col items-center justify-center text-center gap-4">
          <div className="w-16 h-16 bg-[#F1F5F9] rounded-2xl flex items-center justify-center">
            <GraduationCap className="w-8 h-8 text-[#94A3B8]" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[#0F172A]">
              No grades recorded yet
            </h3>
            <p className="text-sm text-[#64748B] mt-1 max-w-sm">
              Your results will appear here after your semester grades are
              uploaded by the GPA coordinator.
            </p>
          </div>
        </div>
      ) : (
        /* ── Semester Tabs ──────────────────────────────────────────── */
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          {/* Tab bar */}
          <div className="overflow-x-auto border-b border-[#E2E8F0]">
            <div className="flex min-w-max">
              {semesters.map((sem, idx) => (
                <button
                  key={sem.semester}
                  onClick={() => setActiveTab(idx)}
                  className={[
                    "px-5 py-3.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2",
                    activeTab === idx
                      ? "border-[#2563EB] text-[#2563EB] bg-[#EFF6FF]"
                      : "border-transparent text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]",
                  ].join(" ")}
                >
                  Semester {sem.semester}
                </button>
              ))}
            </div>
          </div>

          {/* Active semester content */}
          {(() => {
            const sem = semesters[activeTab];
            if (!sem) return null;
            const gpaColor = cgpaValueColor(sem.gpa);

            return (
              <div className="p-6 space-y-4">
                {/* Semester info row */}
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span className="text-[#64748B]">
                    Academic Year:{" "}
                    <span className="font-medium text-[#0F172A]">
                      {sem.academic_year || "—"}
                    </span>
                  </span>
                  <span className="text-[#64748B]">
                    Semester GPA:{" "}
                    <span className={`font-semibold ${gpaColor}`}>
                      {sem.gpa !== null ? sem.gpa.toFixed(2) : "—"}
                    </span>
                  </span>
                  <span className="text-[#64748B]">
                    Credit Hours:{" "}
                    <span className="font-medium text-[#0F172A]">
                      {sem.total_credit_hours}
                    </span>
                  </span>
                </div>

                {/* Subject table */}
                <div className="overflow-x-auto rounded-lg border border-[#E2E8F0]">
                  <table className="w-full text-sm min-w-[560px]">
                    <thead className="bg-[#F8FAFC]">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider w-10">
                          #
                        </th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          Subject
                        </th>
                        <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          Cr. Hrs
                        </th>
                        <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          Marks
                        </th>
                        <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          Grade Point
                        </th>
                        <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          Grade
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sem.subjects.map((subj: SubjectMark, i: number) => {
                        const badge = getGradeBadge(
                          subj.is_non_credit ? "NC" : subj.grade
                        );
                        const gpClass = subj.is_non_credit
                          ? "text-[#94A3B8]"
                          : getGradePointClass(subj.grade_point);
                        return (
                          <tr
                            key={i}
                            className="border-t border-[#F1F5F9] hover:bg-[#FAFBFC] transition-colors"
                          >
                            <td className="px-4 py-3 text-[#94A3B8]">
                              {i + 1}
                            </td>
                            <td className="px-4 py-3 text-[#0F172A] font-medium">
                              {subj.subject_name}
                              {subj.is_non_credit && (
                                <span className="text-[#94A3B8] font-normal">
                                  {" "}*
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-center text-[#64748B]">
                              {subj.credit_hours}
                            </td>
                            <td className="px-4 py-3 text-center text-[#64748B]">
                              {subj.is_non_credit
                                ? "—"
                                : `${subj.obtained_marks}/100`}
                            </td>
                            <td
                              className={`px-4 py-3 text-center ${gpClass}`}
                            >
                              {subj.is_non_credit
                                ? "—"
                                : subj.grade_point.toFixed(1)}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span
                                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}
                              >
                                {subj.is_non_credit ? "NC" : subj.grade}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="bg-[#F1F5F9] border-t-2 border-[#E2E8F0]">
                        <td
                          colSpan={4}
                          className="px-4 py-3 text-sm font-semibold text-[#0F172A]"
                        >
                          Grade Point Average
                        </td>
                        <td
                          className={`px-4 py-3 text-center text-sm font-bold ${gpaColor}`}
                        >
                          {sem.gpa !== null ? sem.gpa.toFixed(2) : "—"}
                        </td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {sem.subjects.some((s) => s.is_non_credit) && (
                  <p className="text-xs text-[#94A3B8]">
                    * Non-credit subject — not counted in GPA calculation
                  </p>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
