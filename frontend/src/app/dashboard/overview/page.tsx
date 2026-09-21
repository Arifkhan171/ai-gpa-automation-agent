"use client";

import React from "react";
import Link from "next/link";
import { Users, TrendingUp, AlertTriangle, Award, ArrowRight, Clock } from "lucide-react";
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
} from "recharts";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatCard } from "@/components/shared/StatCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { ChartCard } from "@/components/shared/ChartCard";
import { useApi } from "@/hooks/useApi";
import { analyticsApi, studentsApi, gradesApi } from "@/lib/api";
import { formatCGPA } from "@/lib/utils";
import type { KPIData, CGPATrendItem, GradeDistributionItem, Student } from "@/types";

// ── Local types ────────────────────────────────────────────────────────────
interface UploadJob {
  job_id: string;
  id?: string;
  filename?: string;
  file_name?: string;
  original_filename?: string;
  status: string;
  created_at: string;
  department?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────
function timeAgo(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return dateStr;
  }
}

function jobStatusColor(status: string): string {
  const s = status?.toUpperCase();
  if (s === "CLEAN" || s === "APPROVED") return "bg-[#DCFCE7] text-[#16A34A]";
  if (s === "FLAGGED") return "bg-[#FEF3C7] text-[#D97706]";
  if (s === "BLOCKED" || s === "FAILED") return "bg-[#FEE2E2] text-[#DC2626]";
  return "bg-[#F1F5F9] text-[#64748B]";
}

function getJobFilename(job: UploadJob): string {
  return job.filename ?? job.file_name ?? job.original_filename ?? `Job ${job.job_id ?? job.id ?? ""}`;
}

// ── Custom tooltip for charts ──────────────────────────────────────────────
function CGPATooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg shadow-lg px-3 py-2">
      <p className="text-xs text-[#64748B]">Semester {label}</p>
      <p className="text-sm font-semibold text-[#0F172A]">
        Avg GPA: {payload[0].value?.toFixed(2)}
      </p>
    </div>
  );
}

function GradeTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg shadow-lg px-3 py-2">
      <p className="text-xs text-[#64748B]">Grade {label}</p>
      <p className="text-sm font-semibold text-[#0F172A]">
        {payload[0].value?.toLocaleString()} students
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  // KPI
  const {
    data: kpi,
    isLoading: kpiLoading,
    error: kpiError,
    refetch: kpiRefetch,
  } = useApi<KPIData>(() => analyticsApi.kpi().then((r) => r.data), []);

  // CGPA Trend
  const {
    data: rawTrend,
    isLoading: trendLoading,
    error: trendError,
    refetch: trendRefetch,
  } = useApi<CGPATrendItem[] | { trend: CGPATrendItem[] }>(
    () => analyticsApi.cgpaTrend().then((r) => r.data),
    []
  );

  // Grade Distribution
  const {
    data: rawGradeDist,
    isLoading: gradeLoading,
    error: gradeError,
    refetch: gradeRefetch,
  } = useApi<GradeDistributionItem[] | { distribution: GradeDistributionItem[] }>(
    () => analyticsApi.gradeDistribution().then((r) => r.data),
    []
  );

  // At-Risk Students
  const {
    data: rawAtRisk,
    isLoading: atRiskLoading,
    error: atRiskError,
    refetch: atRiskRefetch,
  } = useApi<Student[] | { students: Student[] }>(
    () => studentsApi.atRisk().then((r) => r.data),
    []
  );

  // Recent Jobs
  const {
    data: rawJobs,
    isLoading: jobsLoading,
    error: jobsError,
    refetch: jobsRefetch,
  } = useApi<UploadJob[] | { jobs: UploadJob[] } | { items: UploadJob[] }>(
    () => gradesApi.jobs({ limit: 5, page_size: 5 }).then((r) => r.data),
    []
  );

  // Normalise data shapes
  const trendData: CGPATrendItem[] = Array.isArray(rawTrend)
    ? rawTrend
    : (rawTrend as { trend?: CGPATrendItem[] })?.trend ?? [];

  const gradeDist: GradeDistributionItem[] = Array.isArray(rawGradeDist)
    ? rawGradeDist
    : (rawGradeDist as { distribution?: GradeDistributionItem[] })?.distribution ?? [];

  const atRiskStudents: Student[] = Array.isArray(rawAtRisk)
    ? rawAtRisk
    : (rawAtRisk as { students?: Student[] })?.students ?? [];

  const recentJobs: UploadJob[] = Array.isArray(rawJobs)
    ? rawJobs
    : (rawJobs as { jobs?: UploadJob[]; items?: UploadJob[] })?.jobs ??
      (rawJobs as { items?: UploadJob[] })?.items ?? [];

  // Chart data
  const chartTrendData = trendData.map((item) => ({
    name: `${item.semester}`,
    gpa: item.average_gpa ?? 0,
  }));

  return (
    <div className="space-y-6">
      <PageTitle
        title="Overview"
        subtitle="University-wide academic performance at a glance"
      />

      {/* ── KPI Cards ─────────────────────────────────────────────────── */}
      {kpiError ? (
        <ErrorMessage
          message={`Failed to load KPI data: ${kpiError}`}
          onRetry={kpiRefetch}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title="Total Students"
            value={kpiLoading ? "—" : (kpi?.total_students ?? 0).toLocaleString()}
            icon={<Users className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            title="Average CGPA"
            value={kpiLoading ? "—" : formatCGPA(kpi?.average_cgpa ?? null)}
            icon={<TrendingUp className="w-5 h-5" />}
            color="green"
          />
          <StatCard
            title="At Risk Students"
            value={kpiLoading ? "—" : (kpi?.at_risk_count ?? 0).toLocaleString()}
            subtitle="CGPA below 2.0"
            icon={<AlertTriangle className="w-5 h-5" />}
            color="red"
          />
          <StatCard
            title="Dean's List"
            value={kpiLoading ? "—" : (kpi?.excellent_count ?? 0).toLocaleString()}
            subtitle="CGPA 3.5 and above"
            icon={<Award className="w-5 h-5" />}
            color="amber"
          />
        </div>
      )}

      {/* ── Charts Row ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* CGPA Trend — 60% width */}
        <div className="xl:col-span-3">
          <ChartCard
            title="CGPA Trend by Semester"
            subtitle="Average GPA across all active semesters"
            isLoading={trendLoading}
          >
            {trendError ? (
              <ErrorMessage
                message="Failed to load trend data"
                onRetry={trendRefetch}
              />
            ) : chartTrendData.length === 0 ? (
              <div className="h-52 flex items-center justify-center text-sm text-[#94A3B8]">
                No trend data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartTrendData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
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
                  <Line
                    type="monotone"
                    dataKey="gpa"
                    stroke="#2563EB"
                    strokeWidth={2.5}
                    dot={{ fill: "#2563EB", r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: "#2563EB" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>

        {/* Grade Distribution — 40% width */}
        <div className="xl:col-span-2">
          <ChartCard
            title="Grade Distribution"
            subtitle="Student count per grade letter"
            isLoading={gradeLoading}
          >
            {gradeError ? (
              <ErrorMessage
                message="Failed to load grade data"
                onRetry={gradeRefetch}
              />
            ) : gradeDist.length === 0 ? (
              <div className="h-52 flex items-center justify-center text-sm text-[#94A3B8]">
                No grade data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={gradeDist}
                  margin={{ top: 5, right: 5, left: -20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                  <XAxis
                    dataKey="grade"
                    tick={{ fontSize: 11, fill: "#64748B" }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#64748B" }} />
                  <Tooltip content={<GradeTooltip />} />
                  <Bar dataKey="count" fill="#2563EB" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      </div>

      {/* ── At Risk + Recent Jobs ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* At Risk Students */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-[#0F172A]">
                At Risk Students
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">CGPA below 2.0</p>
            </div>
            <Link
              href="/dashboard/students?status=at_risk"
              className="flex items-center gap-1 text-xs text-[#2563EB] font-medium hover:underline"
            >
              View All <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {atRiskError ? (
            <ErrorMessage
              message="Failed to load at-risk students"
              onRetry={atRiskRefetch}
            />
          ) : atRiskLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse flex gap-3 items-center py-2">
                  <div className="h-3 bg-[#F1F5F9] rounded w-24" />
                  <div className="h-3 bg-[#F1F5F9] rounded w-32" />
                  <div className="h-3 bg-[#F1F5F9] rounded w-12 ml-auto" />
                </div>
              ))}
            </div>
          ) : atRiskStudents.length === 0 ? (
            <div className="py-8 text-center text-sm text-[#64748B]">
              🎉 No students at risk right now
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="text-left py-2 px-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Name</th>
                    <th className="text-left py-2 px-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Roll No</th>
                    <th className="text-right py-2 px-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">CGPA</th>
                    <th className="text-right py-2 px-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {atRiskStudents.slice(0, 5).map((s) => (
                    <tr
                      key={s.roll_no}
                      className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#FFF5F5] transition-colors"
                    >
                      <td className="py-2.5 px-2 font-medium text-[#0F172A] truncate max-w-[120px]">
                        {s.student_name}
                      </td>
                      <td className="py-2.5 px-2 font-mono text-xs text-[#64748B]">
                        {s.roll_no}
                      </td>
                      <td className="py-2.5 px-2 text-right font-semibold text-[#DC2626]">
                        {formatCGPA(s.cgpa)}
                      </td>
                      <td className="py-2.5 px-2 text-right">
                        <StatusBadge status={s.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent Upload Jobs */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-[#0F172A]">
                Recent Upload Jobs
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Latest grade file uploads
              </p>
            </div>
            <Link
              href="/dashboard/upload"
              className="flex items-center gap-1 text-xs text-[#2563EB] font-medium hover:underline"
            >
              View All <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {jobsError ? (
            <ErrorMessage
              message="Failed to load upload jobs"
              onRetry={jobsRefetch}
            />
          ) : jobsLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="animate-pulse flex gap-3 items-center py-2">
                  <div className="h-3 bg-[#F1F5F9] rounded flex-1" />
                  <div className="h-5 bg-[#F1F5F9] rounded w-16" />
                  <div className="h-3 bg-[#F1F5F9] rounded w-12" />
                </div>
              ))}
            </div>
          ) : recentJobs.length === 0 ? (
            <div className="py-8 text-center text-sm text-[#64748B]">
              No upload jobs yet
            </div>
          ) : (
            <div className="space-y-1">
              {recentJobs.map((job, idx) => (
                <div
                  key={job.job_id ?? idx}
                  className="flex items-center gap-3 py-2.5 border-b border-[#F1F5F9] last:border-0"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#0F172A] truncate">
                      {getJobFilename(job)}
                    </p>
                    {job.department && (
                      <p className="text-xs text-[#64748B]">{job.department}</p>
                    )}
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${jobStatusColor(job.status)}`}
                  >
                    {job.status}
                  </span>
                  <div className="flex items-center gap-1 text-xs text-[#94A3B8] shrink-0">
                    <Clock className="w-3 h-3" />
                    {timeAgo(job.created_at)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
