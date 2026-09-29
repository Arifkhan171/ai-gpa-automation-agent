"use client";

import React, { useState, useMemo } from "react";
import { Search, CreditCard, CheckCircle, Download } from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatCard } from "@/components/shared/StatCard";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useApi } from "@/hooks/useApi";
import { paymentsApi, api } from "@/lib/api";
import { formatDate, formatCurrency, downloadBlob } from "@/lib/utils";
import type { PaymentVoucher } from "@/types";

// ── Local types ─────────────────────────────────────────────────────────────
interface VoucherListResponse {
  items?: PaymentVoucher[];
  vouchers?: PaymentVoucher[];
}

interface DailyReportItem {
  purpose: string;
  count: number;
  total_amount?: number;
  amount?: number;
}

interface DailyReportResponse {
  items?: DailyReportItem[];
  breakdown?: DailyReportItem[];
  total_amount?: number;
  total?: number;
}

// ── Status badge ──────────────────────────────────────────────────────────────
function VoucherStatusBadge({ status }: { status: PaymentVoucher["status"] }) {
  const styles: Record<PaymentVoucher["status"], string> = {
    pending: "bg-[#FEF3C7] text-[#D97706]",
    paid: "bg-[#DCFCE7] text-[#16A34A]",
    cancelled: "bg-[#F1F5F9] text-[#64748B]",
    expired: "bg-[#FEE2E2] text-[#DC2626]",
  };
  const labels: Record<PaymentVoucher["status"], string> = {
    pending: "Pending",
    paid: "Paid",
    cancelled: "Cancelled",
    expired: "Expired",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function PaymentsPage() {
  // Local vouchers (to update after mark-paid)
  const [localVouchers, setLocalVouchers] = useState<PaymentVoucher[] | null>(null);

  // Filters
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFilter, setDateFilter] = useState("");

  // Mark paid confirm
  const [payTarget, setPayTarget] = useState<PaymentVoucher | null>(null);
  const [isPaying, setIsPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  // Daily report
  const [reportDate, setReportDate] = useState(
    () => new Date().toISOString().split("T")[0]
  );

  // Fetch vouchers
  const {
    data: rawVouchers,
    isLoading,
    error,
    refetch,
  } = useApi<PaymentVoucher[] | VoucherListResponse>(
    () =>
      paymentsApi
        .vouchers({ status: statusFilter || undefined, date: dateFilter || undefined })
        .then((r) => r.data),
    [statusFilter, dateFilter]
  );

  // Fetch daily report
  const {
    data: dailyReport,
    isLoading: reportLoading,
    error: reportError,
  } = useApi<DailyReportResponse>(
    () => paymentsApi.dailyReport(reportDate).then((r) => r.data),
    [reportDate]
  );

  // Normalise
  const apiVouchers: PaymentVoucher[] = Array.isArray(rawVouchers)
    ? rawVouchers
    : (rawVouchers as VoucherListResponse)?.items ??
      (rawVouchers as VoucherListResponse)?.vouchers ?? [];

  const vouchers = localVouchers ?? apiVouchers;

  // Client-side search filter
  const displayed = useMemo(() => {
    const q = searchInput.toLowerCase();
    return vouchers.filter((v) => {
      if (q && !v.voucher_number.toLowerCase().includes(q) && !v.student_name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [vouchers, searchInput]);

  // ── Stats ──────────────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    // BUG 12 FIX: Use toDateString() comparison so timezone differences
    // (UTC vs local) never cause today's amount to show Rs. 0
    const today = new Date().toDateString();
    const pending = vouchers.filter((v) => v.status === "pending").length;
    const paidToday = vouchers.filter(
      (v) => v.status === "paid" && v.paid_at != null &&
             new Date(v.paid_at).toDateString() === today
    ).length;
    const paidTodayAmount = vouchers
      .filter((v) => v.status === "paid" && v.paid_at != null &&
                     new Date(v.paid_at).toDateString() === today)
      .reduce((sum, v) => sum + v.amount, 0);
    const thisMonth = new Date().toISOString().slice(0, 7);
    const totalMonth = vouchers
      .filter((v) => v.status === "paid" && v.paid_at?.startsWith(thisMonth))
      .reduce((sum, v) => sum + v.amount, 0);
    return { pending, paidToday, paidTodayAmount, totalMonth };
  }, [vouchers]);

  // ── Mark paid ──────────────────────────────────────────────────────────────
  const handleMarkPaid = async () => {
    if (!payTarget) return;
    setIsPaying(true);
    setPayError(null);
    try {
      await paymentsApi.markPaid(payTarget.voucher_number, {
        payment_method: "cash",
      });
      setLocalVouchers((prev) => {
        const list = prev ?? apiVouchers;
        return list.map((v) =>
          v.voucher_number === payTarget.voucher_number
            ? { ...v, status: "paid" as const, paid_at: new Date().toISOString() }
            : v
        );
      });
      setPayTarget(null);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setPayError(e?.response?.data?.detail ?? e?.message ?? "Payment failed");
    } finally {
      setIsPaying(false);
    }
  };

  // ── Download daily report PDF ──────────────────────────────────────────────
  const handleDownloadReport = async () => {
    try {
      const res = await api.get("/api/v1/payments/daily-report", {
        params: { date: reportDate, format: "pdf" },
        responseType: "blob",
      });
      downloadBlob(new Blob([res.data], { type: "application/pdf" }), `daily-report-${reportDate}.pdf`);
    } catch {
      window.print();
    }
  };

  const reportItems: DailyReportItem[] =
    dailyReport?.items ?? dailyReport?.breakdown ?? [];
  const reportTotal = dailyReport?.total_amount ?? dailyReport?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* Header with today's total */}
      <PageTitle
        title="Payment Vouchers"
        subtitle="Track and manage student payment vouchers"
        action={
          <div className="flex items-center gap-2 px-4 py-2 bg-[#DCFCE7] border border-[#16A34A]/30 rounded-lg">
            <CheckCircle className="w-4 h-4 text-[#16A34A]" />
            <span className="text-sm font-semibold text-[#16A34A]">
              Today: {formatCurrency(stats.paidTodayAmount)}
            </span>
          </div>
        }
      />

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Pending Vouchers"
          value={isLoading ? "—" : stats.pending.toLocaleString()}
          icon={<CreditCard className="w-5 h-5" />}
          color="amber"
        />
        <StatCard
          title="Paid Today"
          value={isLoading ? "—" : stats.paidToday.toLocaleString()}
          subtitle={formatCurrency(stats.paidTodayAmount)}
          icon={<CheckCircle className="w-5 h-5" />}
          color="green"
        />
        <StatCard
          title="Total This Month"
          value={isLoading ? "—" : formatCurrency(stats.totalMonth)}
          icon={<CreditCard className="w-5 h-5" />}
          color="blue"
        />
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search voucher or student…"
            className="pl-9 pr-4 h-9 w-60 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        >
          <option value="">Status: All</option>
          <option value="pending">Pending</option>
          <option value="paid">Paid</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
        </select>
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        />
        {(statusFilter || dateFilter || searchInput) && (
          <button
            onClick={() => { setStatusFilter(""); setDateFilter(""); setSearchInput(""); }}
            className="h-9 px-3 text-sm text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Vouchers table */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
        {error ? (
          <div className="p-6">
            <ErrorMessage message={`Failed to load vouchers: ${error}`} onRetry={refetch} />
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-20">
            <LoadingSpinner size="md" text="Loading vouchers…" />
          </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <CreditCard className="w-10 h-10 text-[#94A3B8]" />
            <p className="text-sm text-[#64748B]">No vouchers found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  {[
                    "Voucher No",
                    "Student",
                    "Purpose",
                    "Amount",
                    "Status",
                    "Created",
                    "Expires",
                    "Actions",
                  ].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayed.map((v) => (
                  <tr key={v.voucher_number} className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-[#0F172A]">
                      {v.voucher_number}
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-medium text-[#0F172A] truncate max-w-[140px]">{v.student_name}</p>
                      <p className="text-xs text-[#64748B] font-mono">{v.roll_no}</p>
                    </td>
                    <td className="py-3 px-4 text-[#64748B] max-w-[120px] truncate">{v.purpose}</td>
                    <td className="py-3 px-4 font-semibold text-[#0F172A]">
                      {formatCurrency(v.amount)}
                    </td>
                    <td className="py-3 px-4">
                      <VoucherStatusBadge status={v.status} />
                    </td>
                    <td className="py-3 px-4 text-[#64748B] whitespace-nowrap text-xs">
                      {formatDate(v.created_at)}
                    </td>
                    <td className="py-3 px-4 text-[#64748B] whitespace-nowrap text-xs">
                      {formatDate(v.expires_at)}
                    </td>
                    <td className="py-3 px-4">
                      {v.status === "pending" ? (
                        <button
                          onClick={() => setPayTarget(v)}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#16A34A] rounded-lg hover:bg-green-700 transition-colors"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          Mark Paid
                        </button>
                      ) : v.status === "paid" ? (
                        <span className="text-xs text-[#64748B]">
                          Paid {v.paid_at ? formatDate(v.paid_at) : ""}
                          {v.action_taken && (
                            <span className="ml-1 text-[#16A34A]">✓ Transcript</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-[#94A3B8]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Daily Collection Report */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[#0F172A]">
            Daily Collection Report
          </h3>
          <div className="flex items-center gap-3">
            <input
              type="date"
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors"
            >
              <Download className="w-4 h-4" />
              Download PDF
            </button>
          </div>
        </div>

        {reportError ? (
          <ErrorMessage message="Failed to load daily report" />
        ) : reportLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="sm" text="Loading report…" />
          </div>
        ) : reportItems.length === 0 ? (
          <p className="text-sm text-center text-[#94A3B8] py-6">
            No collections for {reportDate}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="text-left py-2 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Purpose</th>
                  <th className="text-right py-2 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Count</th>
                  <th className="text-right py-2 px-4 text-xs font-semibold text-[#64748B] uppercase tracking-wider">Amount</th>
                </tr>
              </thead>
              <tbody>
                {reportItems.map((item, i) => (
                  <tr key={i} className="border-b border-[#E2E8F0] last:border-0">
                    <td className="py-2.5 px-4 text-[#0F172A]">{item.purpose}</td>
                    <td className="py-2.5 px-4 text-right text-[#64748B]">{item.count}</td>
                    <td className="py-2.5 px-4 text-right font-medium text-[#0F172A]">
                      {formatCurrency(item.total_amount ?? item.amount ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-[#F8FAFC] border-t-2 border-[#E2E8F0] font-bold">
                  <td className="py-3 px-4 text-[#0F172A]">Total</td>
                  <td className="py-3 px-4 text-right text-[#0F172A]">
                    {reportItems.reduce((s, i) => s + i.count, 0)}
                  </td>
                  <td className="py-3 px-4 text-right text-[#16A34A]">
                    {formatCurrency(reportTotal)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* ── Mark Paid Confirm ────────────────────────────────────────────────── */}
      <ConfirmDialog
        isOpen={!!payTarget}
        title="Confirm Payment"
        message={`Confirm payment of ${payTarget ? formatCurrency(payTarget.amount) : ""} from ${payTarget?.student_name ?? ""}?\n\nVoucher: ${payTarget?.voucher_number ?? ""}`}
        confirmLabel="Confirm Payment"
        confirmVariant="default"
        onConfirm={handleMarkPaid}
        onCancel={() => { setPayTarget(null); setPayError(null); }}
        isLoading={isPaying}
      />

      {payError && (
        <ErrorMessage message={payError} onRetry={() => setPayError(null)} />
      )}
    </div>
  );
}
