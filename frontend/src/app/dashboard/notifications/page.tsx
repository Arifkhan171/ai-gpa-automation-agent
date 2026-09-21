"use client";

import React, { useState } from "react";
import { Bell, Send, Play, RefreshCw } from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatCard } from "@/components/shared/StatCard";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { notificationsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

// ── Local types ─────────────────────────────────────────────────────────────
interface NotifStats {
  pending?: number;
  sent?: number;
  failed?: number;
  total?: number;
}

interface QueueItem {
  id: number;
  type?: string;
  notification_type?: string;
  channel?: string;
  recipient?: string;
  recipient_email?: string;
  recipient_phone?: string;
  status: "pending" | "sent" | "failed";
  created_at: string;
  sent_at?: string | null;
}

interface QueueResponse {
  items?: QueueItem[];
  queue?: QueueItem[];
}

// ── Status badge ──────────────────────────────────────────────────────────────
function QueueStatusBadge({ status }: { status: QueueItem["status"] }) {
  const styles: Record<QueueItem["status"], string> = {
    pending: "bg-[#FEF3C7] text-[#D97706]",
    sent: "bg-[#DCFCE7] text-[#16A34A]",
    failed: "bg-[#FEE2E2] text-[#DC2626]",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function NotificationsPage() {
  // Send notification form
  const [semester, setSemester] = useState("");
  const [academicYear, setAcademicYear] = useState("2024-2025");
  const [department, setDepartment] = useState("");
  const [channel, setChannel] = useState<"email" | "sms">("email");
  const [isSending, setIsSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  // Process queue
  const [isProcessing, setIsProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<string | null>(null);

  // Queue filter
  const [statusFilter, setStatusFilter] = useState("");

  // Local queue state (to refresh after process)
  const [queueKey, setQueueKey] = useState(0);

  // ── Fetch stats ──────────────────────────────────────────────────────────
  const { data: stats, isLoading: statsLoading, refetch: statsRefetch } =
    useApi<NotifStats>(
      () => notificationsApi.stats().then((r) => r.data),
      []
    );

  // ── Fetch queue ──────────────────────────────────────────────────────────
  const {
    data: rawQueue,
    isLoading: queueLoading,
    error: queueError,
    refetch: queueRefetch,
  } = useApi<QueueItem[] | QueueResponse>(
    () =>
      notificationsApi
        .queue({ status: statusFilter || undefined })
        .then((r) => r.data),
    [statusFilter, queueKey]
  );

  const queueItems: QueueItem[] = Array.isArray(rawQueue)
    ? rawQueue
    : (rawQueue as QueueResponse)?.items ?? (rawQueue as QueueResponse)?.queue ?? [];

  // ── Send notification ─────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!semester) { setSendError("Please select a semester"); return; }
    setIsSending(true);
    setSendResult(null);
    setSendError(null);
    try {
      const res = await notificationsApi.sendGradesPublished({
        semester_number: Number(semester),
        academic_year: academicYear,
        department: department || undefined,
        channel,
      });
      const data = res.data;
      setSendResult(
        data?.message ??
          `Notification queued for ${data?.queued ?? data?.count ?? "all"} students`
      );
      // Refresh queue and stats
      setQueueKey((k) => k + 1);
      statsRefetch();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setSendError(e?.response?.data?.detail ?? e?.message ?? "Send failed");
    } finally {
      setIsSending(false);
    }
  };

  // ── Process queue ─────────────────────────────────────────────────────────
  const handleProcessQueue = async () => {
    setIsProcessing(true);
    setProcessResult(null);
    try {
      const res = await notificationsApi.processQueue();
      const data = res.data;
      setProcessResult(
        data?.message ??
          `Sent: ${data?.sent ?? 0}, Failed: ${data?.failed ?? 0}`
      );
      setQueueKey((k) => k + 1);
      statsRefetch();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setProcessResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? "Processing failed"}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // ── Get recipient display ─────────────────────────────────────────────────
  const getRecipient = (item: QueueItem): string =>
    item.recipient ?? item.recipient_email ?? item.recipient_phone ?? "—";

  const getType = (item: QueueItem): string =>
    item.type ?? item.notification_type ?? "notification";

  return (
    <div className="space-y-6">
      <PageTitle
        title="Notifications"
        subtitle="Send grade notifications and manage the delivery queue"
      />

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Pending"
          value={statsLoading ? "—" : (stats?.pending ?? 0).toLocaleString()}
          color="amber"
          icon={<Bell className="w-5 h-5" />}
        />
        <StatCard
          title="Sent"
          value={statsLoading ? "—" : (stats?.sent ?? 0).toLocaleString()}
          color="green"
          icon={<Send className="w-5 h-5" />}
        />
        <StatCard
          title="Failed"
          value={statsLoading ? "—" : (stats?.failed ?? 0).toLocaleString()}
          color="red"
          icon={<Bell className="w-5 h-5" />}
        />
        <StatCard
          title="Total"
          value={statsLoading ? "—" : (stats?.total ?? 0).toLocaleString()}
          color="blue"
          icon={<Bell className="w-5 h-5" />}
        />
      </div>

      {/* Send notification card */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <h3 className="text-sm font-semibold text-[#0F172A] mb-1">
          Send Grade Results Notification
        </h3>
        <p className="text-xs text-[#64748B] mb-5">
          Notify students that their grade results have been published
        </p>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1.5">
              Semester
            </label>
            <select
              value={semester}
              onChange={(e) => setSemester(e.target.value)}
              className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">Select Semester</option>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={n}>Semester {n}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1.5">
              Academic Year
            </label>
            <input
              value={academicYear}
              onChange={(e) => setAcademicYear(e.target.value)}
              placeholder="e.g. 2024-2025"
              className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1.5">
              Department (optional)
            </label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">All Departments</option>
              <option value="CS">Computer Science</option>
              <option value="SE">Software Engineering</option>
              <option value="IT">Information Technology</option>
              <option value="EE">Electrical Engineering</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#64748B] mb-1.5">
              Channel
            </label>
            <div className="flex h-10 rounded-lg border border-[#E2E8F0] overflow-hidden">
              <button
                onClick={() => setChannel("email")}
                className={`flex-1 text-sm font-medium transition-colors ${
                  channel === "email"
                    ? "bg-[#2563EB] text-white"
                    : "text-[#64748B] hover:bg-[#F8FAFC]"
                }`}
              >
                Email
              </button>
              <button
                onClick={() => setChannel("sms")}
                className={`flex-1 text-sm font-medium transition-colors border-l border-[#E2E8F0] ${
                  channel === "sms"
                    ? "bg-[#2563EB] text-white"
                    : "text-[#64748B] hover:bg-[#F8FAFC]"
                }`}
              >
                SMS
              </button>
            </div>
          </div>
        </div>

        {sendError && (
          <ErrorMessage message={sendError} onRetry={() => setSendError(null)} />
        )}
        {sendResult && (
          <div className="mb-4 p-3 bg-[#DCFCE7] border border-[#16A34A]/20 rounded-lg text-sm text-[#16A34A] font-medium">
            ✓ {sendResult}
          </div>
        )}

        <button
          onClick={handleSend}
          disabled={isSending}
          className="flex items-center gap-2 px-6 py-2.5 bg-[#2563EB] text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {isSending ? (
            <>
              <LoadingSpinner size="sm" />
              Sending…
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Send to All Students
            </>
          )}
        </button>
      </div>

      {/* Queue table */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
        <div className="flex items-center justify-between p-5 border-b border-[#E2E8F0]">
          <div>
            <h3 className="text-sm font-semibold text-[#0F172A]">
              Notification Queue
            </h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Pending and recent notifications
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="sent">Sent</option>
              <option value="failed">Failed</option>
            </select>

            {processResult && (
              <span className="text-xs text-[#16A34A] font-medium">{processResult}</span>
            )}

            <button
              onClick={handleProcessQueue}
              disabled={isProcessing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-[#16A34A] rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <LoadingSpinner size="sm" />
                  Processing…
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Process Queue Now
                </>
              )}
            </button>

            <button
              onClick={queueRefetch}
              className="p-2 text-[#64748B] hover:text-[#0F172A] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {queueError ? (
          <div className="p-6">
            <ErrorMessage message={`Failed to load queue: ${queueError}`} onRetry={queueRefetch} />
          </div>
        ) : queueLoading ? (
          <div className="flex items-center justify-center py-16">
            <LoadingSpinner size="md" text="Loading queue…" />
          </div>
        ) : queueItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <Bell className="w-10 h-10 text-[#94A3B8]" />
            <p className="text-sm text-[#64748B]">
              {statusFilter ? `No ${statusFilter} notifications` : "Queue is empty"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  {["Type", "Channel", "Recipient", "Status", "Created", "Sent At"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queueItems.map((item) => (
                  <tr key={item.id} className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-3 px-4 text-[#0F172A] capitalize">{getType(item).replace(/_/g, " ")}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                        (item.channel ?? "").toLowerCase() === "email"
                          ? "bg-[#DBEAFE] text-[#2563EB]"
                          : "bg-[#F3E8FF] text-[#7C3AED]"
                      }`}>
                        {(item.channel ?? "—").toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#64748B] max-w-[200px] truncate">
                      {getRecipient(item)}
                    </td>
                    <td className="py-3 px-4">
                      <QueueStatusBadge status={item.status} />
                    </td>
                    <td className="py-3 px-4 text-[#64748B] whitespace-nowrap text-xs">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="py-3 px-4 text-[#64748B] whitespace-nowrap text-xs">
                      {item.sent_at ? formatDate(item.sent_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
