"use client";

import React, { useState } from "react";
import { FileText, Eye, Download, XCircle, Search } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageTitle } from "@/components/shared/PageTitle";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useApi } from "@/hooks/useApi";
import { transcriptsApi } from "@/lib/api";
import { formatDate, downloadBlob } from "@/lib/utils";
import type { TranscriptRecord } from "@/types";

// ── Local types ─────────────────────────────────────────────────────────────
interface TranscriptsResponse {
  items?: TranscriptRecord[];
  records?: TranscriptRecord[];
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function TranscriptsPage() {
  // Generate modal
  const [genOpen, setGenOpen] = useState(false);
  const [genRollNo, setGenRollNo] = useState("");
  const [genUpTo, setGenUpTo] = useState<string>("all");
  const [genIsUnofficial, setGenIsUnofficial] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // Revoke confirm
  const [revokeTarget, setRevokeTarget] = useState<TranscriptRecord | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  // Filters
  const [searchRoll, setSearchRoll] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Bulk generate
  const [bulkRolls, setBulkRolls] = useState("");
  const [bulkUpTo, setBulkUpTo] = useState<string>("all");
  const [isBulking, setIsBulking] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

  // Local records state (to update on revoke)
  const [localRecords, setLocalRecords] = useState<TranscriptRecord[] | null>(null);

  // Fetch records — pass is_valid filter to backend
  const {
    data: rawRecords,
    isLoading,
    error,
    refetch,
  } = useApi<TranscriptRecord[] | TranscriptsResponse>(
    () =>
      transcriptsApi
        .records({
          roll_no: searchRoll || undefined,
          // BUG FIX: is_valid filter was computed but never properly sent when empty
          ...(statusFilter === "valid" ? { is_valid: true } : statusFilter === "revoked" ? { is_valid: false } : {}),
        })
        .then((r) => r.data),
    [searchRoll, statusFilter]
  );

  const apiRecords: TranscriptRecord[] = Array.isArray(rawRecords)
    ? rawRecords
    : (rawRecords as TranscriptsResponse)?.items ??
      (rawRecords as TranscriptsResponse)?.records ?? [];

  const records = localRecords ?? apiRecords;

  // ── Generate single transcript ──────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!genRollNo.trim()) { setGenError("Roll number is required"); return; }
    setIsGenerating(true);
    setGenError(null);
    try {
      const res = await transcriptsApi.generate({
        roll_no: genRollNo.trim(),
        up_to_semester: genUpTo === "all" ? null : Number(genUpTo),
        is_unofficial: genIsUnofficial,
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      downloadBlob(blob, `transcript-${genRollNo}.pdf`);
      setGenOpen(false);
      setGenRollNo("");
      setGenUpTo("all");
      setGenIsUnofficial(false);
      // Refresh table
      setLocalRecords(null);
      setTimeout(refetch, 500);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setGenError(e?.response?.data?.detail ?? e?.message ?? "Failed to generate");
    } finally {
      setIsGenerating(false);
    }
  };

  // ── Download existing record ────────────────────────────────────────────────
  const handleDownload = async (record: TranscriptRecord) => {
    try {
      // BUG FIX: was always sending up_to_semester: null (all semesters).
      // Now parse semester_range from the stored record (e.g. "1-4" → up_to_semester 4).
      let upTo: number | null = null;
      if (record.semester_range && record.semester_range !== "all") {
        // Range format is "1-N" — extract the last number
        const match = record.semester_range.match(/(\d+)$/);
        if (match) upTo = parseInt(match[1], 10);
      }
      const res = await transcriptsApi.generate({
        roll_no: record.roll_no,
        up_to_semester: upTo,
        is_unofficial: record.is_unofficial,
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      downloadBlob(blob, `transcript-${record.roll_no}.pdf`);
    } catch {
      // silently handle
    }
  };

  // ── Revoke ─────────────────────────────────────────────────────────────────
  const handleRevoke = async () => {
    if (!revokeTarget) return;
    setIsRevoking(true);
    setRevokeError(null);
    try {
      await transcriptsApi.revoke(revokeTarget.verification_token);
      // Update local records
      setLocalRecords((prev) => {
        const list = prev ?? apiRecords;
        return list.map((r) =>
          r.verification_token === revokeTarget.verification_token
            ? { ...r, is_valid: false }
            : r
        );
      });
      setRevokeTarget(null);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setRevokeError(e?.response?.data?.detail ?? e?.message ?? "Revoke failed");
    } finally {
      setIsRevoking(false);
    }
  };

  // ── Bulk generate ──────────────────────────────────────────────────────────
  const handleBulk = async () => {
    const rolls = bulkRolls
      .split("\n")
      .map((r) => r.trim())
      .filter(Boolean);
    if (!rolls.length) { setBulkError("Enter at least one roll number"); return; }
    setIsBulking(true);
    setBulkError(null);
    try {
      const res = await transcriptsApi.generateBulk({
        roll_numbers: rolls,
        up_to_semester: bulkUpTo === "all" ? null : Number(bulkUpTo),
      });
      const blob = new Blob([res.data], { type: "application/zip" });
      downloadBlob(blob, "transcripts-bulk.zip");
      setBulkRolls("");
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setBulkError(e?.response?.data?.detail ?? e?.message ?? "Bulk generation failed");
    } finally {
      setIsBulking(false);
    }
  };

  // ── Apply search filter client-side (for a smoother UX) ────────────────────
  const displayed = records.filter((r) => {
    const matchesRoll = !searchRoll || r.roll_no.toLowerCase().includes(searchRoll.toLowerCase());
    const matchesStatus =
      !statusFilter ||
      (statusFilter === "valid" ? r.is_valid : !r.is_valid);
    return matchesRoll && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <PageTitle
        title="Transcripts"
        subtitle="Generate, manage, and revoke student transcripts"
        action={
          <button
            onClick={() => setGenOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
          >
            <FileText className="w-4 h-4" />
            Generate Transcript
          </button>
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
          <input
            value={searchRoll}
            onChange={(e) => setSearchRoll(e.target.value)}
            placeholder="Search by roll number…"
            className="pl-9 pr-4 h-9 w-56 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
        >
          <option value="">Status: All</option>
          <option value="valid">Valid</option>
          <option value="revoked">Revoked</option>
        </select>
      </div>

      {/* Records table */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
        {error ? (
          <div className="p-6">
            <ErrorMessage message={`Failed to load records: ${error}`} onRetry={refetch} />
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-20">
            <LoadingSpinner size="md" text="Loading transcripts…" />
          </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <FileText className="w-10 h-10 text-[#94A3B8]" />
            <p className="text-sm text-[#64748B]">No transcript records found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  {[
                    "Student Name",
                    "Roll No",
                    "Semesters",
                    "CGPA",
                    "Issued By",
                    "Issue Date",
                    "Scans",
                    "Status",
                    "Actions",
                  ].map((h) => (
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
                {displayed.map((rec) => (
                  <tr
                    key={rec.verification_token}
                    className="border-b border-[#E2E8F0] last:border-0 hover:bg-[#F8FAFC] transition-colors"
                  >
                    <td className="py-3 px-4 font-medium text-[#0F172A] max-w-[160px] truncate">
                      {rec.student_name}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-[#64748B]">
                      {rec.roll_no}
                    </td>
                    <td className="py-3 px-4 text-[#64748B]">{rec.semester_range}</td>
                    <td className="py-3 px-4 font-semibold text-[#0F172A]">
                      {rec.cgpa_at_issue != null
                        ? rec.cgpa_at_issue.toFixed(2)
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-[#64748B]">{rec.issued_by}</td>
                    <td className="py-3 px-4 text-[#64748B] whitespace-nowrap">
                      {formatDate(rec.issued_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1 text-[#64748B]">
                        <Eye className="w-3.5 h-3.5" />
                        <span>{rec.scan_count}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {rec.is_valid ? (
                        <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold bg-[#DCFCE7] text-[#16A34A]">
                          Valid
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold bg-[#FEE2E2] text-[#DC2626]">
                          Revoked
                        </span>
                      )}
                      {rec.is_unofficial && (
                        <span className="ml-1.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-[#F1F5F9] text-[#64748B]">
                          Unofficial
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDownload(rec)}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-[#2563EB] border border-[#2563EB] rounded-lg hover:bg-[#EFF6FF] transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download
                        </button>
                        {rec.is_valid && (
                          <button
                            onClick={() => setRevokeTarget(rec)}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-[#DC2626] border border-[#DC2626] rounded-lg hover:bg-[#FEF2F2] transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Revoke
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bulk Generate */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6">
        <h3 className="text-sm font-semibold text-[#0F172A] mb-1">Bulk Generate</h3>
        <p className="text-xs text-[#64748B] mb-4">
          Generate transcripts for multiple students at once — downloads as a ZIP archive
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <label className="block text-xs font-medium text-[#64748B] mb-1.5">
              Roll Numbers (one per line)
            </label>
            <textarea
              value={bulkRolls}
              onChange={(e) => setBulkRolls(e.target.value)}
              rows={5}
              placeholder={"21CS-001\n21CS-002\n21CS-003"}
              className="w-full px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB] font-mono resize-none"
            />
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#64748B] mb-1.5">
                Up to Semester
              </label>
              <select
                value={bulkUpTo}
                onChange={(e) => setBulkUpTo(e.target.value)}
                className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              >
                <option value="all">All Semesters</option>
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>Up to Semester {n}</option>
                ))}
              </select>
            </div>
            {bulkError && (
              <p className="text-xs text-[#DC2626]">{bulkError}</p>
            )}
            <button
              onClick={handleBulk}
              disabled={isBulking}
              className="w-full flex items-center justify-center gap-2 h-10 bg-[#0F172A] text-white text-sm font-semibold rounded-lg hover:bg-slate-800 transition-colors disabled:opacity-50"
            >
              {isBulking ? (
                <>
                  <LoadingSpinner size="sm" />
                  Generating…
                </>
              ) : (
                "Generate ZIP"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Generate Transcript Modal ────────────────────────────────────────── */}
      <Dialog open={genOpen} onOpenChange={(o) => { setGenOpen(o); if (!o) setGenError(null); }}>
        <DialogContent className="bg-white border border-[#E2E8F0] max-w-md sm:rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-[#0F172A] font-semibold">
              Generate Transcript
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="block text-sm font-medium text-[#0F172A] mb-1.5">
                Roll Number
              </label>
              <input
                value={genRollNo}
                onChange={(e) => setGenRollNo(e.target.value)}
                placeholder="e.g. 21CS-001"
                className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#0F172A] mb-1.5">
                Up to Semester
              </label>
              <select
                value={genUpTo}
                onChange={(e) => setGenUpTo(e.target.value)}
                className="w-full h-10 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              >
                <option value="all">All Semesters</option>
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>Up to Semester {n}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setGenIsUnofficial(false)}
                className={`flex-1 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  !genIsUnofficial
                    ? "bg-[#2563EB] text-white border-[#2563EB]"
                    : "text-[#64748B] border-[#E2E8F0] hover:bg-[#F8FAFC]"
                }`}
              >
                Official
              </button>
              <button
                onClick={() => setGenIsUnofficial(true)}
                className={`flex-1 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  genIsUnofficial
                    ? "bg-[#2563EB] text-white border-[#2563EB]"
                    : "text-[#64748B] border-[#E2E8F0] hover:bg-[#F8FAFC]"
                }`}
              >
                Unofficial
              </button>
            </div>

            {genError && (
              <div className="bg-[#FEE2E2] border border-[#DC2626]/20 rounded-lg p-3 text-sm text-[#DC2626]">
                {genError}
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="w-full flex items-center justify-center gap-2 h-11 bg-[#2563EB] text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50"
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

      {/* ── Revoke Confirm Dialog ────────────────────────────────────────────── */}
      <ConfirmDialog
        isOpen={!!revokeTarget}
        title="Revoke Transcript"
        message={`Are you sure? This transcript for ${revokeTarget?.student_name ?? "this student"} will become invalid and the QR code will stop working. This action cannot be undone.`}
        confirmLabel="Yes, Revoke"
        confirmVariant="destructive"
        onConfirm={handleRevoke}
        onCancel={() => { setRevokeTarget(null); setRevokeError(null); }}
        isLoading={isRevoking}
      />

      {revokeError && (
        <ErrorMessage message={revokeError} onRetry={() => setRevokeError(null)} />
      )}
    </div>
  );
}
