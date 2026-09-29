"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, Users } from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { studentsApi } from "@/lib/api";
import { formatCGPA, cn } from "@/lib/utils";
import type { Student } from "@/types";

// ── Local types ────────────────────────────────────────────────────────────
interface StudentsListResponse {
  items?: Student[];
  students?: Student[];
  data?: Student[];
  total?: number;
  pages?: number;
  page?: number;
}

// ── Inner component (uses useSearchParams) ────────────────────────────────
function StudentsListInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read initial status filter from URL
  const initialStatus = searchParams.get("status") ?? "";

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState(initialStatus);
  const [semester, setSemester] = useState("");
  const [page, setPage] = useState(1);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const { data: rawData, isLoading, error, refetch } = useApi<StudentsListResponse>(
    () =>
      studentsApi
        .list({
          page,
          search: search || undefined,
          department: department || undefined,
          status: status || undefined,
          semester: semester ? Number(semester) : undefined,
          page_size: 20,
        })
        .then((r) => r.data),
    [page, search, department, status, semester]
  );

  // Normalise response — backend sends { total, page, page_size, total_pages, students: [...] }
  const students: Student[] = rawData?.items ?? rawData?.students ?? rawData?.data ?? [];
  const total: number = rawData?.total ?? students.length;
  // BUG FIX: backend field is total_pages, not pages
  const totalPages: number = (rawData as { total_pages?: number })?.total_pages ?? Math.ceil(total / 20);

  const clearFilters = useCallback(() => {
    setSearchInput("");
    setSearch("");
    setDepartment("");
    setStatus("");
    setSemester("");
    setPage(1);
  }, []);

  const hasFilters = !!(search || department || status || semester);

  const handleRowClick = (s: Student) => {
    // BUG 13 FIX: encode roll_no so slashes like "UoL/CS-F-22/001-BS" don't break routing
    router.push(`/dashboard/students/${encodeURIComponent(s.roll_no)}`);
  };

  if (error) {
    return (
      <div>
        <PageTitle title="Students" />
        <ErrorMessage message={`Failed to load students: ${error}`} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      {/* Header row */}
      <PageTitle
        title="Students"
        subtitle={`${total.toLocaleString()} students registered`}
        action={
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by name or roll no…"
              className="pl-9 pr-4 h-9 w-64 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
          </div>
        }
      />

      {/* Filter row */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={department}
          onChange={(e) => { setDepartment(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        >
          <option value="">Department: All</option>
          <option value="CS">Computer Science</option>
          <option value="SE">Software Engineering</option>
          <option value="IT">Information Technology</option>
          <option value="EE">Electrical Engineering</option>
          <option value="ME">Mechanical Engineering</option>
          <option value="BBA">Business Administration</option>
        </select>

        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        >
          <option value="">Status: All</option>
          <option value="at_risk">At Risk</option>
          <option value="satisfactory">Satisfactory</option>
          <option value="good">Good</option>
          <option value="excellent">Excellent</option>
          <option value="no_grades">No Grades</option>
        </select>

        <select
          value={semester}
          onChange={(e) => { setSemester(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        >
          <option value="">Semester: All</option>
          {/* University of Loralai has max 8 semesters — cap to 8 */}
          {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
            <option key={n} value={n}>Semester {n}</option>
          ))}
        </select>

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="h-9 px-3 text-sm text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <LoadingSpinner size="md" text="Loading students…" />
          </div>
        ) : students.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-14 h-14 rounded-full bg-[#F1F5F9] flex items-center justify-center">
              <Users className="w-7 h-7 text-[#94A3B8]" />
            </div>
            <p className="text-[#0F172A] font-medium">No students found</p>
            <p className="text-sm text-[#64748B]">
              {hasFilters ? "Try adjusting your filters" : "No students have been added yet"}
            </p>
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="mt-1 px-4 py-2 text-sm text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Roll No</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Student Name</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Department</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Semesters Completed</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">CGPA</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Status</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr
                      key={s.roll_no}
                      onClick={() => handleRowClick(s)}
                      className={cn(
                        "border-b border-[#E2E8F0] last:border-0 cursor-pointer transition-colors hover:bg-[#F8FAFC]",
                        (s.cgpa ?? 0) < 2.0 && s.status !== "no_grades"
                          ? "border-l-4 border-l-[#DC2626]"
                          : ""
                      )}
                    >
                      <td className="py-3 px-4 font-mono text-xs text-[#64748B]">
                        {s.roll_no}
                      </td>
                      <td className="py-3 px-4 font-medium text-[#0F172A]">
                        {s.student_name}
                      </td>
                      <td className="py-3 px-4 text-[#64748B]">
                        {s.department ?? "—"}
                      </td>
                      <td className="py-3 px-4 text-[#64748B]">
                        {s.semesters_completed ?? 0}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span
                          className={cn(
                            "font-semibold",
                            s.cgpa == null
                              ? "text-[#94A3B8]"
                              : s.cgpa < 2.0
                              ? "text-[#DC2626]"
                              : s.cgpa >= 2.5
                              ? "text-[#16A34A]"
                              : "text-[#D97706]"
                          )}
                        >
                          {formatCGPA(s.cgpa)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/dashboard/students/${encodeURIComponent(s.roll_no)}`);
                          }}
                          className="px-3 py-1.5 text-xs font-medium text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors"
                        >
                          View →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination — only shown when there are results */}
            {total > 0 && <div className="flex items-center justify-between px-4 py-4 border-t border-[#E2E8F0]">
              <p className="text-sm text-[#64748B]">
                Showing{" "}
                <span className="font-medium text-[#0F172A]">
                  {Math.min((page - 1) * 20 + 1, total)}–
                  {Math.min(page * 20, total)}
                </span>{" "}
                of{" "}
                <span className="font-medium text-[#0F172A]">{total.toLocaleString()}</span>{" "}
                students
              </p>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-xs font-medium text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  ← Previous
                </button>

                {totalPages <= 7 &&
                  [...Array(totalPages)].map((_, i) => (
                    <button
                      key={i + 1}
                      onClick={() => setPage(i + 1)}
                      className={cn(
                        "w-8 h-8 text-xs font-medium rounded-lg transition-colors",
                        page === i + 1
                          ? "bg-[#2563EB] text-white"
                          : "text-[#64748B] border border-[#E2E8F0] hover:bg-[#F8FAFC]"
                      )}
                    >
                      {i + 1}
                    </button>
                  ))}

                {totalPages > 7 && (
                  <span className="px-2 text-sm text-[#64748B]">
                    Page {page} of {totalPages}
                  </span>
                )}

                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 text-xs font-medium text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>}
          </>
        )}
      </div>
    </div>
  );
}

// ── Page export ─────────────────────────────────────────────────────────────
export default function StudentsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <LoadingSpinner size="lg" text="Loading…" />
        </div>
      }
    >
      <StudentsListInner />
    </Suspense>
  );
}
