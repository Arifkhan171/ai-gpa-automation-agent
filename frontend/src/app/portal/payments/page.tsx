"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  CreditCard,
  FileText,
  Receipt,
  Award,
  Download,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  MapPin,
  Phone,
  Clock,
} from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { StatCard } from "@/components/shared/StatCard";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { studentsApi, paymentsApi } from "@/lib/api";
import { downloadBlob, formatDate } from "@/lib/utils";
import type { PaymentVoucher } from "@/types";

// ── Helpers ────────────────────────────────────────────────────────────────
function isExpiringSoon(expiresAt: string): boolean {
  if (!expiresAt) return false;
  const now = Date.now();
  const expiry = new Date(expiresAt).getTime();
  const twoDays = 2 * 24 * 60 * 60 * 1000;
  return expiry > now && expiry - now <= twoDays;
}

function purposeIcon(purpose: string) {
  const p = purpose?.toLowerCase() ?? "";
  if (p.includes("transcript")) return <FileText className="w-4 h-4" />;
  if (p.includes("attest")) return <Award className="w-4 h-4" />;
  return <Receipt className="w-4 h-4" />;
}

function purposeLabel(purpose: string): string {
  if (!purpose) return "Other";
  const p = purpose.toLowerCase();
  if (p.includes("transcript")) return "Transcript";
  if (p.includes("attest")) return "Attestation";
  return purpose.charAt(0).toUpperCase() + purpose.slice(1);
}

function statusBadge(status: PaymentVoucher["status"]) {
  switch (status) {
    case "pending":
      return (
        <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#FEF3C7] text-[#D97706]">
          Pending
        </span>
      );
    case "paid":
      return (
        <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#DCFCE7] text-[#16A34A]">
          <CheckCircle className="w-3 h-3" />
          Paid
        </span>
      );
    case "cancelled":
      return (
        <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#F1F5F9] text-[#64748B]">
          Cancelled
        </span>
      );
    case "expired":
      return (
        <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#FEE2E2] text-[#DC2626]">
          Expired
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#F1F5F9] text-[#64748B]">
          {status}
        </span>
      );
  }
}

// ── HOW-TO-PAY guide steps ─────────────────────────────────────────────────
const HOW_TO_PAY_STEPS = [
  {
    text: "Note your voucher number from the table above",
  },
  {
    text: "Visit the university cashier window during working hours (8 AM to 4 PM)",
  },
  {
    text: "Tell the cashier your voucher number and pay the required amount",
  },
  {
    text: "The cashier will confirm your payment in the system",
  },
  {
    text: "Return to this page to download your document once processed",
  },
];

// ── Page ──────────────────────────────────────────────────────────────────
export default function PaymentsPage() {
  const {
    data: rawVouchers,
    isLoading,
    error,
    refetch,
  } = useApi<PaymentVoucher[]>(
    () => studentsApi.portalVouchers().then((r) => r.data),
    []
  );

  const [openHowToPayId, setOpenHowToPayId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  // ── Normalise ──────────────────────────────────────────────────────────
  const vouchers: PaymentVoucher[] = Array.isArray(rawVouchers)
    ? rawVouchers
    : [];

  const pendingCount = vouchers.filter((v) => v.status === "pending").length;
  const completedCount = vouchers.filter((v) => v.status === "paid").length;
  const totalPaid = vouchers
    .filter((v) => v.status === "paid")
    .reduce((sum, v) => sum + (v.amount ?? 0), 0);

  // ── Download transcript ────────────────────────────────────────────────
  const handleDownloadTranscript = async (voucherNumber: string) => {
    setDownloading(voucherNumber);
    try {
      const res = await paymentsApi.downloadTranscript(voucherNumber);
      downloadBlob(res.data as Blob, `transcript-${voucherNumber}.pdf`);
    } catch (err) {
      console.error("Transcript download failed:", err);
    } finally {
      setDownloading(null);
    }
  };

  // ── Loading / error ────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" text="Loading payment history…" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorMessage
        message={`Could not load payments: ${error}`}
        onRetry={refetch}
      />
    );
  }

  // ── Empty state ────────────────────────────────────────────────────────
  if (vouchers.length === 0) {
    return (
      <div className="space-y-6">
        <PageTitle
          title="My Payments"
          subtitle="Payment vouchers and transaction history"
        />
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-12 flex flex-col items-center justify-center text-center gap-4">
          <div className="w-16 h-16 bg-[#F1F5F9] rounded-2xl flex items-center justify-center">
            <CreditCard className="w-8 h-8 text-[#94A3B8]" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[#0F172A]">
              No payment history yet
            </h3>
            <p className="text-sm text-[#64748B] mt-1">
              When you request a transcript, a payment voucher will appear here
            </p>
          </div>
          <Link
            href="/portal/transcript"
            className="inline-flex items-center justify-center px-5 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] transition-colors"
          >
            Request Transcript →
          </Link>
        </div>
      </div>
    );
  }

  // ── Main render ────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <PageTitle
        title="My Payments"
        subtitle="Payment vouchers and transaction history"
      />

      {/* ── Summary cards ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Pending"
          value={pendingCount}
          subtitle="Awaiting payment"
          icon={<CreditCard className="w-5 h-5" />}
          color="amber"
        />
        <StatCard
          title="Completed"
          value={completedCount}
          subtitle="Payments confirmed"
          icon={<CheckCircle className="w-5 h-5" />}
          color="green"
        />
        <StatCard
          title="Total Paid"
          value={`Rs. ${totalPaid.toLocaleString()}`}
          subtitle="Across all transactions"
          icon={<Receipt className="w-5 h-5" />}
          color="blue"
        />
      </div>

      {/* ── Vouchers table ────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2E8F0]">
          <h2 className="text-base font-semibold text-[#0F172A]">
            All Vouchers
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[680px]">
            <thead className="bg-[#F8FAFC]">
              <tr>
                <th className="text-left px-5 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Voucher Number
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Purpose
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Amount
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Status
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Created
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Expires
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {vouchers.map((v) => {
                const expiringSoon =
                  v.status === "pending" && isExpiringSoon(v.expires_at);
                const isOpen = openHowToPayId === v.voucher_number;

                return (
                  <React.Fragment key={v.id}>
                    <tr className="border-t border-[#F1F5F9] hover:bg-[#FAFBFC] transition-colors">
                      {/* Voucher number */}
                      <td className="px-5 py-3.5">
                        <span className="font-mono text-sm font-bold text-[#0F172A]">
                          {v.voucher_number}
                        </span>
                      </td>

                      {/* Purpose */}
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center gap-1.5 text-[#64748B]">
                          {purposeIcon(v.purpose)}
                          {purposeLabel(v.purpose)}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="px-4 py-3.5 text-center text-[#0F172A] font-medium">
                        Rs. {v.amount}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5 text-center">
                        {statusBadge(v.status)}
                      </td>

                      {/* Created */}
                      <td className="px-4 py-3.5 text-center text-xs text-[#64748B]">
                        {formatDate(v.created_at)}
                      </td>

                      {/* Expires */}
                      <td
                        className={[
                          "px-4 py-3.5 text-center text-xs",
                          expiringSoon
                            ? "text-[#DC2626] font-semibold"
                            : "text-[#64748B]",
                        ].join(" ")}
                      >
                        {formatDate(v.expires_at)}
                        {expiringSoon && (
                          <p className="text-[10px] text-[#DC2626]">Soon!</p>
                        )}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3.5 text-center">
                        {v.status === "pending" && (
                          <button
                            onClick={() =>
                              setOpenHowToPayId(
                                isOpen ? null : v.voucher_number
                              )
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[#E2E8F0] text-[#64748B] hover:bg-[#F8FAFC] hover:text-[#0F172A] transition-colors"
                          >
                            How to Pay
                            {isOpen ? (
                              <ChevronUp className="w-3 h-3" />
                            ) : (
                              <ChevronDown className="w-3 h-3" />
                            )}
                          </button>
                        )}

                        {v.status === "paid" &&
                          v.purpose?.toLowerCase().includes("transcript") && (
                            <button
                              onClick={() =>
                                handleDownloadTranscript(v.voucher_number)
                              }
                              disabled={downloading === v.voucher_number}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#DBEAFE] text-[#2563EB] hover:bg-[#BFDBFE] disabled:opacity-60 transition-colors"
                            >
                              {downloading === v.voucher_number ? (
                                <span className="w-3 h-3 border border-[#2563EB]/30 border-t-[#2563EB] rounded-full animate-spin" />
                              ) : (
                                <Download className="w-3.5 h-3.5" />
                              )}
                              Download Transcript
                            </button>
                          )}
                      </td>
                    </tr>

                    {/* How to Pay expandable row */}
                    {isOpen && (
                      <tr className="border-t-0">
                        <td
                          colSpan={7}
                          className="px-5 pt-0 pb-4 bg-[#F8FAFC]"
                        >
                          <div className="border border-[#E2E8F0] rounded-xl p-4 text-sm text-[#1E40AF] bg-[#DBEAFE]">
                            <p className="font-semibold mb-1">How to pay:</p>
                            <p>
                              Take voucher number{" "}
                              <span className="font-mono font-bold">
                                {v.voucher_number}
                              </span>{" "}
                              to the university cashier window. Pay{" "}
                              <strong>Rs. {v.amount}</strong>. Reference:{" "}
                              <span className="font-mono">{v.voucher_number}</span>
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── How to Pay guide (permanent) ──────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <h2 className="text-base font-semibold text-[#0F172A] mb-5">
          How to Pay Your Fee
        </h2>

        <div className="space-y-4">
          {HOW_TO_PAY_STEPS.map((step, idx) => (
            <div key={idx} className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-[#DBEAFE] flex items-center justify-center shrink-0 mt-0.5">
                <span className="text-sm font-bold text-[#2563EB]">
                  {idx + 1}
                </span>
              </div>
              <p className="text-sm text-[#0F172A] pt-1.5">{step.text}</p>
            </div>
          ))}
        </div>

        {/* Info box */}
        <div className="mt-6 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2 text-sm text-[#64748B]">
            <Clock className="w-4 h-4 text-[#2563EB] shrink-0" />
            <span>
              Working Hours: Monday to Friday, 8:00 AM to 4:00 PM
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-[#64748B]">
            <MapPin className="w-4 h-4 text-[#2563EB] shrink-0" />
            <span>Cashier Location: Administration Block, Ground Floor</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-[#64748B]">
            <Phone className="w-4 h-4 text-[#2563EB] shrink-0" />
            <span>
              For urgent requests contact: +92-XXX-XXXXXXX
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
