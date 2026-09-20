import { PageTitle } from "@/components/shared/PageTitle";
import { BarChart3 } from "lucide-react";

export default function StubPage() {
  return (
    <div>
      <PageTitle
        title="Analytics"
        subtitle="Grade distributions, CGPA trends, and department breakdowns"
      />
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 flex flex-col items-center justify-center text-center gap-4">
        <div className="w-16 h-16 bg-[#DCFCE7] rounded-2xl flex items-center justify-center">
          <BarChart3 className="w-8 h-8 text-[#16A34A]" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[#0F172A]">Analytics</h3>
          <p className="text-sm text-[#64748B] mt-1">
            Grade distributions, CGPA trends, and department breakdowns — coming in Module 9
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-[#DBEAFE] text-[#2563EB] px-3 py-1 text-xs font-medium">
          Coming in Module 9
        </span>
      </div>
    </div>
  );
}
