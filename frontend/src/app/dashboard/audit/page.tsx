"use client";

import React, { useState } from "react";
import { Shield, Download, ChevronDown, ChevronRight } from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { notificationsApi } from "@/lib/api";
import { cn, downloadBlob } from "@/lib/utils";

// ── Local types ─────────────────────────────────────────────────────────────
interface AuditEntry {
  id: number;
  timestamp: string;
  created_at?: string;
  username?: string;
  user?: string;
  role?: string;
  action: string;
  entity?: string;
  resource?: string;
  details?: Record<string, unknown> | string | null;
  ip_address?: string;
  ip?: string;
}

interface AuditResponse {
  items?: AuditEntry[];
  logs?: AuditEntry[];
  total?: number;
}

// ── Action colour ─────────────────────────────────────────────────────────────
function actionColor(action: string): string {
  const a = action?.toLowerCase() ?? "";
  if (["login", "logout"].some((k) => a.includes(k)))
    return "bg-[#DBEAFE] text-[#2563EB]";
  if (["upload", "approve", "create", "add"].some((k) => a.includes(k)))
    return "bg-[#DCFCE7] text-[#16A34A]";
  if (["revoke", "cancel", "delete", "remove"].some((k) => a.includes(k)))
    return "bg-[#FEE2E2] text-[#DC2626]";
  return "bg-[#F1F5F9] text-[#64748B]";
}

// ── Format timestamp ──────────────────────────────────────────────────────────
function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

// ── Collapsible JSON cell ─────────────────────────────────────────────────────
function DetailsCell({ details }: { details?: Record<string, unknown> | string | null }) {
  const [open, setOpen] = useState(false);
  if (!details) return <span className="text-[#94A3B8]">—</span>;

  const text =
    typeof details === "string"
      ? details
      : JSON.stringify(details, null, 2);

  const preview =
    typeof details === "string"
      ? details.slice(0, 40)
      : Object.keys(details)
          .slice(0, 2)
          .map((k) => `${k}: ${JSON.stringify((details as Record<string, unknown>)[k])}`)
          .join(", ");

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-xs text-[#64748B] hover:text-[#0F172A] transition-colors"
      >
        {open ? (
          <ChevronDown className="w-3 h-3 shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 shrink-0" />
        )}
        <span className="truncate max-w-[120px]">{preview || "details"}</span>
      </button>
      {open && (
        <pre className="mt-2 p-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs text-[#64748B] overflow-auto max-h-32 max-w-xs">
          {text}
        </pre>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function AuditPage() {
  // Filters
  const [username, setUsername] = useState("");
  const [actionType, setActionType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Applied filters (set on Apply click)
  const [applied, setApplied] = useState({
    username: "",
    action: "",
    date_from: "",
    date_to: "",
  });

  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const [isExporting, setIsExporting] = useState(false);

  // ── Fetch audit log ───────────────────────────────────────────────────────
  const {
    data: rawAudit,
    isLoading,
    error,
    refetch,
  } = useApi<AuditEntry[] | AuditResponse>(
    () =>
      notificationsApi
        .auditLog({
          username: applied.username || undefined,
          action: applied.action || undefined,
          date_from: applied.date_from || undefined,
          date_to: applied.date_to || undefined,
          page,
          page_size: PAGE_SIZE,
        })
        .then((r) => r.data),
    [applied.username, applied.action, applied.date_from, applied.date_to, page]
  );

  const entries: AuditEntry[] = Array.isArray(rawAudit)
    ? rawAudit
    : (rawAudit as AuditResponse)?.items ??
      (rawAudit as AuditResponse)?.logs ?? [];

  const total: number = Array.isArray(rawAudit)
    ? rawAudit.length
    : (rawAudit as AuditResponse)?.total ?? entries.length;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // ── Apply filters ──────────────────────────────────────────────────────────
  const applyFilters = () => {
    setApplied({
      username,
      action: actionType,
      date_from: dateFrom,
      date_to: dateTo,
    });
    setPage(1);
  };

  const clearFilters = () => {
    setUsername(""); setActionType(""); setDateFrom(""); setDateTo("");
    setApplied({ username: "", action: "", date_from: "", date_to: "" });
    setPage(1);
  };

  const hasFilters = !!(applied.username || applied.action || applied.date_from || applied.date_to);

  // ── Export CSV ─────────────────────────────────────────────────────────────
  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await notificationsApi.auditExport({
        username: applied.username || undefined,
        action: applied.action || undefined,
        date_from: applied.date_from || undefined,
        date_to: applied.date_to || undefined,
      });
      const blob = new Blob([res.data], { type: "text/csv" });
      downloadBlob(blob, `audit-log-${new Date().toISOString().split("T")[0]}.csv`);
    } catch (err: unknown) {
      const e = err as { message?: string };
      console.error("Export failed:", e?.message);
    } finally {
      setIsExporting(false);
    }
  };

  // ── Helpers ────────────────────────────────────────────────────────────────
  const getUsername = (e: AuditEntry) => e.username ?? e.user ?? "—";
  const getEntity = (e: AuditEntry) => e.entity ?? e.resource ?? "—";
  const getTimestamp = (e: AuditEntry) =>
    formatTimestamp(e.timestamp ?? e.created_at ?? "");
  const getIp = (e: AuditEntry) => e.ip_address ?? e.ip ?? "—";

  return (
    <div className="space-y-5">
      <PageTitle
        title="Audit Log"
        subtitle="Track all system actions for compliance and security"
        action={
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors disabled:opacity-50"
          >
            {isExporting ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Export CSV
          </button>
        }
      />

      {/* Filter row */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">
              Username
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Filter by user…"
              onKeyDown={(e) => e.key === "Enter" && applyFilters()}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white min-w-[160px] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">
              Action Type
            </label>
            <select
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white min-w-[160px] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">All Actions</option>
              <option value="login">Login</option>
              <option value="logout">Logout</option>
              <option value="upload">Upload</option>
              <option value="approve">Approve</option>
              <option value="generate">Generate Transcript</option>
              <option value="revoke">Revoke</option>
              <option value="view">View</option>
              <option value="mark_paid">Mark Paid</option>
              <option value="cancel">Cancel</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">
              Date From
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1">
              Date To
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
          </div>

          <button
            onClick={applyFilters}
            className="h-9 px-5 text-sm font-semibold text-white bg-[#2563EB] rounded-lg hover:bg-blue-700 transition-colors"
          >
            Apply
          </button>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="h-9 px-4 text-sm text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Total count */}
      {!isLoading && !error && (
        <p className="text-sm text-[#64748B]">
          Showing {entries.length.toLocaleString()} of{" "}
          <span className="font-medium text-[#0F172A]">{total.toLocaleString()}</span>{" "}
          entries (page {page} of {totalPages})
        </p>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
        {error ? (
          <div className="p-6">
            <ErrorMessage message={`Failed to load audit log: ${error}`} onRetry={refetch} />
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-20">
            <LoadingSpinner size="md" text="Loading audit log…" />
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <Shield className="w-10 h-10 text-[#94A3B8]" />
            <p className="text-sm text-[#64748B]">
              {hasFilters ? "No entries match your filters" : "No audit entries yet"}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    {["Timestamp", "User", "Role", "Action", "Entity", "Details", "IP"].map((h) => (
                      <th
                        key={h}
                        className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC] transition-colors"
                    >
                      <td className="py-3 px-4 text-[#64748B] whitespace-nowrap text-xs">
                        {getTimestamp(entry)}
                      </td>
                      <td className="py-3 px-4 font-medium text-[#0F172A]">
                        {getUsername(entry)}
                      </td>
                      <td className="py-3 px-4 text-[#64748B] capitalize text-xs">
                        {(entry.role ?? "—").replace(/_/g, " ")}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
                            actionColor(entry.action)
                          )}
                        >
                          {entry.action.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#64748B] text-xs">
                        {getEntity(entry)}
                      </td>
                      <td className="py-3 px-4">
                        <DetailsCell details={entry.details} />
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-[#94A3B8]">
                        {getIp(entry)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-4 border-t border-[#E2E8F0]">
                <p className="text-sm text-[#64748B]">
                  Page <span className="font-medium text-[#0F172A]">{page}</span> of{" "}
                  <span className="font-medium text-[#0F172A]">{totalPages}</span>
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-xs font-medium text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] disabled:opacity-40 transition-colors"
                  >
                    ← Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="px-3 py-1.5 text-xs font-medium text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] disabled:opacity-40 transition-colors"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
