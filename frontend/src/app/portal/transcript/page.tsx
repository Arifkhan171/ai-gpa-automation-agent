"use client";

import React, { useState } from "react";
import {
  FileText,
  CheckCircle,
  Eye,
  Download,
  Clipboard,
  Check,
  Info,
} from "lucide-react";
import { PageTitle } from "@/components/shared/PageTitle";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { useApi } from "@/hooks/useApi";
import { studentsApi, paymentsApi, transcriptsApi } from "@/lib/api";
import { downloadBlob, formatDate } from "@/lib/utils";
import type { TranscriptRecord, PaymentVoucher } from "@/types";

// ── Local types ────────────────────────────────────────────────────────────
interface VoucherResponse {
  voucher_number: string;
  amount?: number;
  expires_at?: string;
  message?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────
function parseUpToSemester(range: string | null): number | undefined {
  if (!range || range === "all") return undefined;
  const parts = range.split("-");
  const n = parseInt(parts[parts.length - 1]);
  return isNaN(n) ? undefined : n;
}

function shortToken(token: string): string {
  if (!token) return "—";
  return token.length > 12 ? token.slice(0, 8) + "…" : token;
}

function semesterRangeLabel(range: string | null): string {
  if (!range) return "—";
  if (range === "all") return "All Semesters";
  return `Semesters ${range}`;
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function TranscriptPage() {
  // ── API data ───────────────────────────────────────────────────────────
  const {
    data: rawTranscripts,
    isLoading: tLoading,
    error: tError,
    refetch: tRefetch,
  } = useApi<TranscriptRecord[]>(
    () => studentsApi.portalTranscripts().then((r) => r.data),
    []
  );

  const {
    data: rawVouchers,
    isLoading: vLoading,
    error: vError,
    refetch: vRefetch,
  } = useApi<PaymentVoucher[]>(
    () => studentsApi.portalVouchers().then((r) => r.data),
    []
  );

  // ── Form state ─────────────────────────────────────────────────────────
  const [transcriptType, setTranscriptType] = useState<"full" | "partial">(
    "full"
  );
  const [upToSemester, setUpToSemester] = useState(4);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successVoucher, setSuccessVoucher] = useState<VoucherResponse | null>(
    null
  );
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);

  // ── Normalise ──────────────────────────────────────────────────────────
  const transcripts: TranscriptRecord[] = Array.isArray(rawTranscripts)
    ? rawTranscripts
    : [];
  const vouchers: PaymentVoucher[] = Array.isArray(rawVouchers)
    ? rawVouchers
    : [];

  const pendingTranscriptVouchers = vouchers.filter(
    (v) =>
      v.status === "pending" &&
      v.purpose?.toLowerCase().includes("transcript")
  );
  const hasPaidWithNoTranscript =
    vouchers.some(
      (v) =>
        v.status === "paid" && v.purpose?.toLowerCase().includes("transcript")
    ) && transcripts.filter((t) => t.is_valid).length === 0;

  // ── Handlers ───────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const semesterRange =
        transcriptType === "full" ? "all" : `1-${upToSemester}`;
      const res = await paymentsApi.requestVoucher({
        purpose: "transcript",
        semester_range: semesterRange,
      });
      setSuccessVoucher(res.data as VoucherResponse);
      vRefetch();
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      setSubmitError(
        e?.response?.data?.detail ||
          e?.message ||
          "Submission failed. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!successVoucher?.voucher_number) return;
    try {
      await navigator.clipboard.writeText(successVoucher.voucher_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* silently ignore clipboard errors */
    }
  };

  const handleDownload = async (record: TranscriptRecord, idx: number) => {
    setDownloading(idx);
    try {
      const upTo = parseUpToSemester(record.semester_range);
      const res = await transcriptsApi.generate({
        roll_no: record.roll_no,
        ...(upTo !== undefined ? { up_to_semester: upTo } : {}),
      });
      downloadBlob(res.data as Blob, `transcript-${record.roll_no}.pdf`);
    } catch (err) {
      console.error("Download failed:", err);
    } finally {
      setDownloading(null);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <PageTitle
        title="Official Transcript"
        subtitle="Request and download your authenticated academic transcript"
      />

      {/* ── Section 1: Request form ────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <h2 className="text-lg font-semibold text-[#0F172A] mb-1">
          Request Official Transcript
        </h2>
        <p className="text-sm text-[#64748B] mb-6 leading-relaxed">
          An official transcript is an authenticated record of your academic
          performance. It includes all your grades, GPA, and CGPA with a QR
          verification code that employers and universities can scan to verify
          it is genuine.
        </p>

        {successVoucher ? (
          /* ── Success state ─────────────────────────────────────── */
          <div className="flex flex-col items-center text-center gap-5 py-4">
            <div className="w-16 h-16 bg-[#DCFCE7] rounded-full flex items-center justify-center">
              <CheckCircle className="w-9 h-9 text-[#16A34A]" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#0F172A]">
                Request Submitted Successfully
              </h3>
              <p className="text-sm text-[#64748B] mt-1">
                Your transcript request has been received
              </p>
            </div>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl px-10 py-5 w-full max-w-sm">
              <p className="text-xs text-[#94A3B8] mb-2">Your Voucher Number</p>
              <p className="text-2xl font-bold font-mono text-[#0F172A] tracking-widest break-all">
                {successVoucher.voucher_number}
              </p>
            </div>

            <div className="bg-[#DBEAFE] border border-[#2563EB]/20 rounded-xl p-5 text-left text-sm text-[#1E40AF] w-full max-w-md">
              <p className="font-semibold mb-2">Next steps:</p>
              <ol className="list-decimal list-inside space-y-1.5">
                <li>
                  Take this voucher number to the university cashier window
                </li>
                <li>Pay Rs. 200</li>
                <li>
                  Your transcript will be available for download within 24
                  hours of payment confirmation
                </li>
                <li>This voucher expires in 7 days — act promptly</li>
              </ol>
            </div>

            <button
              onClick={handleCopy}
              className={[
                "inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium border transition-colors min-h-[44px]",
                copied
                  ? "bg-[#DCFCE7] border-[#16A34A] text-[#16A34A]"
                  : "bg-white border-[#E2E8F0] text-[#0F172A] hover:bg-[#F8FAFC]",
              ].join(" ")}
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Clipboard className="w-4 h-4" />
                  Copy Voucher Number
                </>
              )}
            </button>

            <button
              onClick={() => {
                setSuccessVoucher(null);
                setSubmitError(null);
              }}
              className="text-xs text-[#2563EB] hover:underline"
            >
              Request another transcript
            </button>
          </div>
        ) : (
          /* ── Request form ──────────────────────────────────────── */
          <div className="space-y-5 max-w-lg">
            {/* Transcript type */}
            <div>
              <p className="text-sm font-medium text-[#0F172A] mb-2">
                Transcript Type
              </p>
              <div className="space-y-2.5">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="transcriptType"
                    value="full"
                    checked={transcriptType === "full"}
                    onChange={() => setTranscriptType("full")}
                    className="accent-[#2563EB] w-4 h-4 cursor-pointer"
                  />
                  <span className="text-sm text-[#0F172A]">
                    Full Transcript (All Semesters)
                  </span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="transcriptType"
                    value="partial"
                    checked={transcriptType === "partial"}
                    onChange={() => setTranscriptType("partial")}
                    className="accent-[#2563EB] w-4 h-4 cursor-pointer"
                  />
                  <span className="text-sm text-[#0F172A]">
                    Partial Transcript (Up to a specific semester)
                  </span>
                </label>
              </div>

              {transcriptType === "partial" && (
                <div className="mt-3 ml-7">
                  <label className="text-xs font-medium text-[#64748B] block mb-1.5">
                    Include semesters up to:
                  </label>
                  <select
                    value={upToSemester}
                    onChange={(e) => setUpToSemester(Number(e.target.value))}
                    className="border border-[#E2E8F0] rounded-lg px-3 py-2 text-sm text-[#0F172A] bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 min-h-[40px]"
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                      <option key={n} value={n}>
                        Semester {n}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Purpose */}
            <div>
              <label className="text-sm font-medium text-[#0F172A] block mb-1.5">
                Purpose
              </label>
              <select className="w-full border border-[#E2E8F0] rounded-lg px-3 py-2.5 text-sm text-[#0F172A] bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 min-h-[44px]">
                <option>Employment Application</option>
                <option>Higher Education Admission</option>
                <option>Bank or Financial Institution</option>
                <option>Government Application</option>
                <option>Personal Record</option>
                <option>Other</option>
              </select>
            </div>

            {/* Fee info */}
            <div className="bg-[#DBEAFE] border border-[#2563EB]/20 rounded-xl p-4">
              <p className="text-sm text-[#1E40AF] font-semibold mb-1.5">
                Transcript Fee: Rs. 200
              </p>
              <p className="text-xs text-[#1E40AF]">
                Payment Method: University Cashier Window
              </p>
              <p className="text-xs text-[#1E40AF] mt-0.5">
                Processing Time: Within 24 hours of payment
              </p>
            </div>

            {submitError && (
              <div className="bg-[#FEE2E2] border border-[#DC2626]/20 rounded-lg p-3 text-sm text-[#DC2626]">
                {submitError}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-[#2563EB] text-white text-sm font-semibold rounded-lg hover:bg-[#1D4ED8] disabled:opacity-60 disabled:cursor-not-allowed transition-colors min-h-[48px]"
            >
              {submitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Submitting…
                </>
              ) : (
                "Request Transcript"
              )}
            </button>
          </div>
        )}
      </div>

      {/* ── Section 2: Transcript history ─────────────────────────── */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <h2 className="text-lg font-semibold text-[#0F172A] mb-4">
          My Transcripts
        </h2>

        {tLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="md" text="Loading transcripts…" />
          </div>
        ) : tError ? (
          <ErrorMessage
            message={`Could not load transcripts: ${tError}`}
            onRetry={tRefetch}
          />
        ) : transcripts.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center gap-3 py-10">
            <div className="w-14 h-14 bg-[#F1F5F9] rounded-xl flex items-center justify-center">
              <FileText className="w-7 h-7 text-[#94A3B8]" />
            </div>
            <div>
              <p className="text-base font-semibold text-[#0F172A]">
                No transcripts issued yet
              </p>
              <p className="text-sm text-[#64748B] mt-1">
                Submit a request above to get started
              </p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-[#E2E8F0]">
            <table className="w-full text-sm min-w-[620px]">
              <thead className="bg-[#F8FAFC]">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Semesters Covered
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    CGPA at Issue
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Issue Date
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Scans
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {transcripts.map((rec, idx) => (
                  <tr
                    key={rec.id}
                    className="border-t border-[#F1F5F9] hover:bg-[#FAFBFC] transition-colors"
                  >
                    <td className="px-4 py-3 text-[#0F172A] font-medium">
                      {semesterRangeLabel(rec.semester_range)}
                    </td>
                    <td className="px-4 py-3 text-center font-semibold text-[#0F172A]">
                      {rec.cgpa_at_issue !== null
                        ? rec.cgpa_at_issue.toFixed(2)
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-center text-[#64748B]">
                      {formatDate(rec.issued_at)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex items-center gap-1 text-[#64748B]">
                        <Eye className="w-3.5 h-3.5" />
                        {rec.scan_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span
                          className={[
                            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                            rec.is_valid
                              ? "bg-[#DCFCE7] text-[#16A34A]"
                              : "bg-[#FEE2E2] text-[#DC2626]",
                          ].join(" ")}
                        >
                          {rec.is_valid ? "Valid" : "Revoked"}
                        </span>
                        <span className="text-[10px] font-mono text-[#94A3B8]">
                          {shortToken(rec.verification_token)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {rec.is_valid && (
                        <button
                          onClick={() => handleDownload(rec, idx)}
                          disabled={downloading === idx}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#DBEAFE] text-[#2563EB] hover:bg-[#BFDBFE] disabled:opacity-60 transition-colors"
                        >
                          {downloading === idx ? (
                            <span className="w-3.5 h-3.5 border border-[#2563EB]/30 border-t-[#2563EB] rounded-full animate-spin" />
                          ) : (
                            <Download className="w-3.5 h-3.5" />
                          )}
                          Download PDF
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hasPaidWithNoTranscript && (
          <div className="mt-4 flex items-start gap-3 bg-[#DBEAFE] border border-[#2563EB]/20 rounded-xl p-4">
            <Info className="w-4 h-4 text-[#2563EB] shrink-0 mt-0.5" />
            <p className="text-sm text-[#1E40AF]">
              Payment received. Your transcript is being processed. Check back
              soon.
            </p>
          </div>
        )}
      </div>

      {/* ── Previous vouchers ─────────────────────────────────────── */}
      {!vLoading && !vError && pendingTranscriptVouchers.length > 0 && (
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
          <h2 className="text-base font-semibold text-[#0F172A] mb-4">
            Pending Payment Vouchers
          </h2>
          <div className="overflow-x-auto rounded-lg border border-[#E2E8F0]">
            <table className="w-full text-sm min-w-[440px]">
              <thead className="bg-[#F8FAFC]">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Voucher Number
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                    Expires
                  </th>
                </tr>
              </thead>
              <tbody>
                {pendingTranscriptVouchers.map((v) => (
                  <tr key={v.id} className="border-t border-[#F1F5F9]">
                    <td className="px-4 py-3 font-mono text-sm font-bold text-[#0F172A]">
                      {v.voucher_number}
                    </td>
                    <td className="px-4 py-3 text-center text-[#64748B]">
                      Rs. {v.amount}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-[#FEF3C7] text-[#D97706]">
                        Pending
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-[#64748B] text-xs">
                      {formatDate(v.expires_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
