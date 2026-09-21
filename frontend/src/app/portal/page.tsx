"use client";

import React from "react";
import Link from "next/link";
import {
  TrendingUp,
  BookOpen,
  Award,
  FileText,
  CreditCard,
  AlertTriangle,
  Info,
} from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorMessage } from "@/components/shared/ErrorMessage";
import { CGPAGauge } from "@/components/shared/CGPAGauge";
import { useApi } from "@/hooks/useApi";
import { studentsApi } from "@/lib/api";
import { getStatusLabel } from "@/lib/utils";

// ── Local type for student portal response ─────────────────────────────────
interface StudentPortalData {
  student_name: string;
  roll_no: string;
  father_name: string | null;
  department: string | null;
  session: string | null;
  cgpa: number | null;
  total_credit_hours: number;
  semesters_completed: number;
  status: "excellent" | "good" | "satisfactory" | "at_risk" | "no_grades";
  pending_vouchers: number;
  total_transcripts_issued: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────
function todayLabel(): string {
  return new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function PortalHomePage() {
  const {
    data: me,
    isLoading,
    error,
    refetch,
  } = useApi<StudentPortalData>(
    () => studentsApi.portalMe().then((r) => r.data),
    []
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" text="Loading your dashboard…" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorMessage
        message={`Could not load dashboard: ${error}`}
        onRetry={refetch}
      />
    );
  }

  const statusLabel =
    me?.status && me.status !== "no_grades"
      ? getStatusLabel(me.status)
      : null;

  return (
    <div className="space-y-6">
      {/* ── Welcome header ─────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">
            Welcome back,{" "}
            <span className="text-[#2563EB]">
              {me?.student_name ?? "Student"}
            </span>
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            {me?.roll_no}
            {me?.department ? ` · ${me.department}` : ""}
          </p>
        </div>
        <p className="text-sm text-[#94A3B8] shrink-0 pt-1">{todayLabel()}</p>
      </div>

      {/* ── Quick stats ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* CGPA — custom card with CGPAGauge */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 border-l-4 border-l-[#2563EB] flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-[#94A3B8] uppercase tracking-wider">
              My CGPA
            </p>
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-[#DBEAFE]">
              <TrendingUp className="w-4 h-4 text-[#2563EB]" />
            </div>
          </div>
          <div className="flex justify-center">
            <CGPAGauge cgpa={me?.cgpa ?? null} size="sm" />
          </div>
          {statusLabel && (
            <p className="text-xs text-center text-[#64748B]">{statusLabel}</p>
          )}
        </div>

        <StatCard
          title="Semesters Completed"
          value={me?.semesters_completed ?? 0}
          icon={<BookOpen className="w-5 h-5" />}
          color="blue"
        />

        <StatCard
          title="Credit Hours"
          value={me?.total_credit_hours ?? 0}
          subtitle="Total Earned"
          icon={<Award className="w-5 h-5" />}
          color="amber"
        />

        <StatCard
          title="Transcripts Issued"
          value={me?.total_transcripts_issued ?? 0}
          icon={<FileText className="w-5 h-5" />}
          color="green"
        />
      </div>

      {/* ── Alerts ─────────────────────────────────────────────────────── */}
      {me && (
        <div className="space-y-3">
          {me.cgpa !== null && me.cgpa < 2.0 && (
            <div className="flex items-start gap-3 bg-[#FEE2E2] border border-[#DC2626]/20 rounded-xl p-4">
              <AlertTriangle className="w-5 h-5 text-[#DC2626] shrink-0 mt-0.5" />
              <p className="text-sm text-[#DC2626] font-medium">
                Academic Warning: Your CGPA is below 2.0. Please meet with your
                academic advisor immediately to discuss your options.
              </p>
            </div>
          )}
          {me.pending_vouchers > 0 && (
            <div className="flex items-start gap-3 bg-[#DBEAFE] border border-[#2563EB]/20 rounded-xl p-4">
              <Info className="w-5 h-5 text-[#2563EB] shrink-0 mt-0.5" />
              <p className="text-sm text-[#2563EB] font-medium">
                You have {me.pending_vouchers} pending payment voucher
                {me.pending_vouchers !== 1 ? "s" : ""}. Visit the Payments page
                to check status.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Quick actions ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Grades */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col gap-4">
          <div className="w-12 h-12 bg-[#DBEAFE] rounded-xl flex items-center justify-center">
            <BookOpen className="w-6 h-6 text-[#2563EB]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#0F172A]">
              My Academic Record
            </h3>
            <p className="text-sm text-[#64748B] mt-1">
              View all your semester results and grade details
            </p>
          </div>
          <Link
            href="/portal/grades"
            className="mt-auto inline-flex items-center justify-center w-full px-4 py-3 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] transition-colors"
          >
            View Grades →
          </Link>
        </div>

        {/* Transcript */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col gap-4">
          <div className="w-12 h-12 bg-[#DCFCE7] rounded-xl flex items-center justify-center">
            <FileText className="w-6 h-6 text-[#16A34A]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#0F172A]">
              Get Official Transcript
            </h3>
            <p className="text-sm text-[#64748B] mt-1">
              Request an official transcript for employment or admission
            </p>
          </div>
          <Link
            href="/portal/transcript"
            className="mt-auto inline-flex items-center justify-center w-full px-4 py-3 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] transition-colors"
          >
            Request Transcript →
          </Link>
        </div>

        {/* Payments */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col gap-4">
          <div className="w-12 h-12 bg-[#FEF3C7] rounded-xl flex items-center justify-center">
            <CreditCard className="w-6 h-6 text-[#D97706]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#0F172A]">
              Payment Vouchers
            </h3>
            <p className="text-sm text-[#64748B] mt-1">
              View your payment history and pending vouchers
            </p>
          </div>
          <Link
            href="/portal/payments"
            className="mt-auto inline-flex items-center justify-center w-full px-4 py-3 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] transition-colors"
          >
            View Payments →
          </Link>
        </div>
      </div>
    </div>
  );
}
