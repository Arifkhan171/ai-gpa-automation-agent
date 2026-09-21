"use client";

import React, { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import {
  Users,
  TrendingUp,
  AlertTriangle,
  Award,
  BookOpen,
  Layers,
  Medal,
  Download,
  Send,
} from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatCard } from "@/components/shared/StatCard";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ChartCard } from "@/components/shared/ChartCard";
import { useApi } from "@/hooks/useApi";
import { analyticsApi, studentsApi, notificationsApi, api } from "@/lib/api";
import { formatCGPA, downloadBlob } from "@/lib/utils";
import type { KPIData, CGPATrendItem, GradeDistributionItem, Student } from "@/types";

// ── Local types ─────────────────────────────────────────────────────────────
interface SubjectDifficultyItem {
  subject_name: string;
  department?: string;
  average_grade?: string;
  avg_grade?: string;
  average_percentage?: number;
  avg_percentage?: number;
  fail_rate: number;
  difficulty?: string;
}

interface MeritListItem {
  rank: number;
  student_name: string;
  roll_no: string;
  cgpa: number;
  department?: string;
}

interface DeptBreakdownItem {
  department: string;
  average_cgpa?: number;
  avg_cgpa?: number;
  student_count?: number;
}

interface AtRiskResponse {
  students?: Student[];
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function failRateBadge(rate: number) {
  if (rate >= 30)
    return <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold bg-[#FEE2E2] text-[#DC2626]">High</span>;
  if (rate >= 15)
    return <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold bg-[#FEF3C7] text-[#D97706]">Medium</span>;
  return <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold bg-[#DCFCE7] text-[#16A34A]">Low</span>;
}

function rankIcon(rank: number) {
  if (rank === 1) return <Medal className="w-4 h-4 text-yellow-500" />;
  if (rank === 2) return <Medal className="w-4 h-4 text-slate-400" />;
  if (rank === 3) return <Medal className="w-4 h-4 text-amber-700" />;
  return <span className="w-4 h-4 flex items-center justify-center text-xs font-bold text-[#94A3B8]">{rank}</span>;
}

function deptBarColor(cgpa: number): string {
  if (cgpa >= 3.5) return "#16A34A";
  if (cgpa >= 2.5) return "#2563EB";
  if (cgpa >= 2.0) return "#D97706";
  return "#DC2626";
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  // Filter state
  const [filterDept, setFilterDept] = useState("");
  const [filterSem, setFilterSem] = useState("");
  const [appliedDept, setAppliedDept] = useState("");
  const [appliedSem, setAppliedSem] = useState("");

  // Export state
  const [isExporting, setIsExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Alert state
  const [isSendingAlert, setIsSendingAlert] = useState(false);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

  const filterParams = {
    department: appliedDept || undefined,
    semester: appliedSem ? Number(appliedSem) : undefined,
  };

  // ── API calls ──────────────────────────────────────────────────────────────
  const { data: kpi, isLoading: kpiLoading, error: kpiError, refetch: kpiRefetch } =
    useApi<KPIData>(() => analyticsApi.kpi(filterParams).then((r) => r.data), [appliedDept, appliedSem]);

  const { data: rawTrend, isLoading: trendLoading } =
    useApi<CGPATrendItem[] | { trend: CGPATrendItem[] }>(
      () => analyticsApi.cgpaTrend(filterParams).then((r) => r.data),
      [appliedDept, appliedSem]
    );

  const { data: rawGrade, isLoading: gradeLoading } =
    useApi<GradeDistributionItem[] | { distribution: GradeDistributionItem[] }>(
      () => analyticsApi.gradeDistribution(filterParams).then((r) => r.data),
      [appliedDept, appliedSem]
    );

  const { data: rawDept, isLoading: deptLoading } =
    useApi<DeptBreakdownItem[] | { departments: DeptBreakdownItem[] }>(
      () => analyticsApi.departmentBreakdown().then((r) => r.data),
      []
    );

  const { data: rawDifficulty, isLoading: difficultyLoading, error: difficultyError } =
    useApi<SubjectDifficultyItem[] | { subjects: SubjectDifficultyItem[] }>(
      () => analyticsApi.subjectDifficulty(filterParams).then((r) => r.data),
      [appliedDept, appliedSem]
    );

  const { data: rawMerit, isLoading: meritLoading } =
    useApi<MeritListItem[] | { merit_list: MeritListItem[] }>(
      () => analyticsApi.meritList({ top_n: 10, ...filterParams }).then((r) => r.data),
      [appliedDept, appliedSem]
    );

  const { data: rawAtRisk, isLoading: atRiskLoading, refetch: atRiskRefetch } =
    useApi<Student[] | AtRiskResponse>(
      () => studentsApi.atRisk().then((r) => r.data),
      []
    );

  // Normalise
  const trendData: CGPATrendItem[] = Array.isArray(rawTrend)
    ? rawTrend : (rawTrend as { trend?: CGPATrendItem[] })?.trend ?? [];

  const gradeData: GradeDistributionItem[] = Array.isArray(rawGrade)
    ? rawGrade : (rawGrade as { distribution?: GradeDistributionItem[] })?.distribution ?? [];

  const deptData: DeptBreakdownItem[] = Array.isArray(rawDept)
    ? rawDept : (rawDept as { departments?: DeptBreakdownItem[] })?.departments ?? [];

  const diffData: SubjectDifficultyItem[] = (Array.isArray(rawDifficulty)
    ? rawDifficulty : (rawDifficulty as { subjects?: SubjectDifficultyItem[] })?.subjects ?? [])
    .sort((a, b) => b.fail_rate - a.fail_rate);

  const meritList: MeritListItem[] = Array.isArray(rawMerit)
    ? rawMerit : (rawMerit as { merit_list?: MeritListItem[] })?.merit_list ?? [];

  const atRiskStudents: Student[] = Array.isArray(rawAtRisk)
    ? rawAtRisk : (rawAtRisk as AtRiskResponse)?.students ?? [];

  // Chart data
  const chartTrend = trendData.map((t) => ({ name: `${t.semester}`, gpa: t.average_gpa ?? 0 }));
  const chartDept = deptData.map((d) => ({
    name: d.department,
    cgpa: d.average_cgpa ?? d.avg_cgpa ?? 0,
  }));

  // ── Export ─────────────────────────────────────────────────────────────────
  const handleExport = async (type: string, filename: string) => {
    setIsExporting(type);
    setExportError(null);
    try {
      const res = await api.get("/api/v1/analytics/summary-report", {
        params: { type, ...filterParams },
        responseType: "blob",
      });
      downloadBlob(new Blob([res.data], { type: "application/pdf" }), filename);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setExportError(e?.response?.data?.detail ?? e?.message ?? "Export failed");
    } finally {
      setIsExporting(null);
    }
  };

  // ── Send HoD alert ─────────────────────────────────────────────────────────
  const sendHoDAlert = async () => {
    setIsSendingAlert(true);
    setAlertMsg(null);
    try {
      const res = await notificationsApi.sendGradesPublished({
        notification_type: "at_risk_alert",
        department: appliedDept || undefined,
      });
      setAlertMsg(res.data?.message ?? "Alert sent to HoD successfully");
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setAlertMsg(e?.response?.data?.detail ?? "Failed to send alert");
    } finally {
      setIsSendingAlert(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle
        title="Analytics"
        subtitle="Deep dive into academic performance metrics"
      />

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">Department</label>
            <select
              value={filterDept}
              onChange={(e) => setFilterDept(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white min-w-[180px] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">All Departments</option>
              <option value="CS">Computer Science</option>
              <option value="SE">Software Engineering</option>
              <option value="IT">Information Technology</option>
              <option value="EE">Electrical Engineering</option>
              <option value="ME">Mechanical Engineering</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">Semester</label>
            <select
              value={filterSem}
              onChange={(e) => setFilterSem(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white min-w-[160px] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">All Semesters</option>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={n}>Semester {n}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => { setAppliedDept(filterDept); setAppliedSem(filterSem); }}
            className="h-9 px-5 text-sm font-semibold text-white bg-[#2563EB] rounded-lg hover:bg-blue-700 transition-colors"
          >
            Apply Filters
          </button>
          {(appliedDept || appliedSem) && (
            <button
              onClick={() => {
                setFilterDept(""); setFilterSem("");
                setAppliedDept(""); setAppliedSem("");
              }}
              className="h-9 px-4 text-sm text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      {kpiError ? (
        <ErrorMessage message={`KPI load failed: ${kpiError}`} onRetry={kpiRefetch} />
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <StatCard title="Total Students" value={kpiLoading ? "—" : (kpi?.total_students ?? 0).toLocaleString()} icon={<Users className="w-5 h-5" />} color="blue" />
          <StatCard title="Avg CGPA" value={kpiLoading ? "—" : formatCGPA(kpi?.average_cgpa ?? null)} icon={<TrendingUp className="w-5 h-5" />} color="green" />
          <StatCard title="At Risk" value={kpiLoading ? "—" : (kpi?.at_risk_count ?? 0).toLocaleString()} subtitle="CGPA < 2.0" icon={<AlertTriangle className="w-5 h-5" />} color="red" />
          <StatCard title="Dean's List" value={kpiLoading ? "—" : (kpi?.excellent_count ?? 0).toLocaleString()} subtitle="CGPA ≥ 3.5" icon={<Award className="w-5 h-5" />} color="amber" />
          <StatCard title="Marks Recorded" value={kpiLoading ? "—" : (kpi?.total_marks_recorded ?? 0).toLocaleString()} icon={<BookOpen className="w-5 h-5" />} color="blue" />
          <StatCard title="Active Semesters" value={kpiLoading ? "—" : (kpi?.semesters_active ?? 0).toLocaleString()} icon={<Layers className="w-5 h-5" />} color="green" />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="CGPA Trend" subtitle="Average GPA by semester" isLoading={trendLoading}>
          {chartTrend.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-sm text-[#94A3B8]">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartTrend} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#64748B" }} tickFormatter={(v) => `S${v}`} />
                <YAxis domain={[0, 4]} tick={{ fontSize: 10, fill: "#64748B" }} tickCount={5} />
                <Tooltip />
                <Line type="monotone" dataKey="gpa" stroke="#2563EB" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Grade Distribution" subtitle="Students per grade letter" isLoading={gradeLoading}>
          {gradeData.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-sm text-[#94A3B8]">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={gradeData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="grade" tick={{ fontSize: 10, fill: "#64748B" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                <Tooltip formatter={(v, n) => [`${v} students`, "Count"]} />
                <Bar dataKey="count" fill="#2563EB" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Department Comparison" subtitle="Average CGPA per department" isLoading={deptLoading}>
          {chartDept.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-sm text-[#94A3B8]">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartDept} margin={{ top: 5, right: 5, left: -20, bottom: 5 }} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" horizontal={false} />
                <XAxis type="number" domain={[0, 4]} tick={{ fontSize: 10, fill: "#64748B" }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#64748B" }} width={35} />
                <Tooltip formatter={(v) => [Number(v).toFixed(2), "Avg CGPA"]} />
                <Bar dataKey="cgpa" radius={[0, 3, 3, 0]}>
                  {chartDept.map((entry, i) => (
                    <Cell key={i} fill={deptBarColor(entry.cgpa)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Subject Difficulty */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-[#0F172A]">
            Subject Difficulty Index
          </h3>
          <p className="text-xs text-[#64748B] mt-0.5">
            Subjects ranked by student failure rate (highest first)
          </p>
        </div>

        {difficultyLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="md" text="Loading subjects…" />
          </div>
        ) : difficultyError ? (
          <ErrorMessage message="Failed to load subject difficulty data" />
        ) : diffData.length === 0 ? (
          <p className="text-sm text-center text-[#94A3B8] py-8">No subject data available</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  {["Subject Name", "Department", "Avg Grade", "Avg %", "Fail Rate", "Difficulty"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {diffData.map((item, idx) => (
                  <tr key={idx} className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC]">
                    <td className="py-3 px-4 font-medium text-[#0F172A] max-w-[200px] truncate">{item.subject_name}</td>
                    <td className="py-3 px-4 text-[#64748B]">{item.department ?? "—"}</td>
                    <td className="py-3 px-4 text-[#64748B]">{item.average_grade ?? item.avg_grade ?? "—"}</td>
                    <td className="py-3 px-4 text-[#64748B]">
                      {(item.average_percentage ?? item.avg_percentage) != null
                        ? `${(item.average_percentage ?? item.avg_percentage)!.toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-[#64748B]">{item.fail_rate.toFixed(1)}%</td>
                    <td className="py-3 px-4">{failRateBadge(item.fail_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Merit List + At Risk */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Merit List */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <h3 className="text-sm font-semibold text-[#0F172A] mb-4">
            Merit List — Top 10 Students
          </h3>
          {meritLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="md" />
            </div>
          ) : meritList.length === 0 ? (
            <p className="text-sm text-center text-[#94A3B8] py-8">No merit list data</p>
          ) : (
            <div className="space-y-0">
              {meritList.map((item) => (
                <div
                  key={item.rank}
                  className="flex items-center gap-3 py-3 border-b border-[#F1F5F9] last:border-0"
                >
                  <div className="w-7 flex items-center justify-center shrink-0">
                    {rankIcon(item.rank)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#0F172A] truncate">{item.student_name}</p>
                    <p className="text-xs text-[#64748B] font-mono">{item.roll_no}</p>
                  </div>
                  <span className="text-sm font-bold text-[#16A34A]">
                    {formatCGPA(item.cgpa)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* At Risk */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[#0F172A]">
              At Risk Students
            </h3>
            <button
              onClick={sendHoDAlert}
              disabled={isSendingAlert}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#DC2626] border border-[#DC2626] rounded-lg hover:bg-[#FEF2F2] transition-colors disabled:opacity-50"
            >
              {isSendingAlert ? (
                <LoadingSpinner size="sm" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
              Send Alert to HoD
            </button>
          </div>

          {alertMsg && (
            <div className="mb-3 p-3 rounded-lg text-xs font-medium bg-[#DCFCE7] text-[#16A34A]">
              {alertMsg}
            </div>
          )}

          {atRiskLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="md" />
            </div>
          ) : atRiskStudents.length === 0 ? (
            <p className="text-sm text-center text-[#94A3B8] py-8">
              🎉 No students at risk
            </p>
          ) : (
            <div className="space-y-0">
              {atRiskStudents.map((s) => (
                <div key={s.roll_no} className="flex items-center gap-3 py-3 border-b border-[#FEE2E2] last:border-0">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#0F172A] truncate">{s.student_name}</p>
                    <p className="text-xs text-[#64748B] font-mono">{s.roll_no}</p>
                  </div>
                  <span className="text-sm font-bold text-[#DC2626]">
                    {formatCGPA(s.cgpa)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Export buttons */}
      {exportError && (
        <ErrorMessage message={exportError} onRetry={() => setExportError(null)} />
      )}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
        <h3 className="text-sm font-semibold text-[#0F172A] mb-4">Export Reports</h3>
        <div className="flex flex-wrap gap-3">
          {[
            { type: "merit_list", label: "Download Merit List PDF", file: "merit-list.pdf" },
            { type: "at_risk", label: "Download At Risk Report PDF", file: "at-risk-report.pdf" },
            { type: "full_analytics", label: "Download Full Analytics PDF", file: "full-analytics.pdf" },
          ].map((btn) => (
            <button
              key={btn.type}
              onClick={() => handleExport(btn.type, btn.file)}
              disabled={isExporting === btn.type}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors disabled:opacity-50"
            >
              {isExporting === btn.type ? (
                <LoadingSpinner size="sm" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              {btn.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
