import { PageTitle } from "@/components/shared/PageTitle";
import { LayoutDashboard } from "lucide-react";

export default function OverviewPage() {
  return (
    <div>
      <PageTitle
        title="Overview"
        subtitle="University-wide academic performance at a glance"
      />
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 flex flex-col items-center justify-center text-center gap-4">
        <div className="w-16 h-16 bg-[#DBEAFE] rounded-2xl flex items-center justify-center">
          <LayoutDashboard className="w-8 h-8 text-[#2563EB]" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[#0F172A]">
            Overview Dashboard
          </h3>
          <p className="text-sm text-[#64748B] mt-1">
            KPI cards, CGPA trends, and department summaries — coming in Module 9
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-[#DBEAFE] text-[#2563EB] px-3 py-1 text-xs font-medium">
          Coming in Module 9
        </span>
      </div>
    </div>
  );
}
