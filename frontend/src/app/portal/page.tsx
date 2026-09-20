import { PageTitle } from "@/components/shared/PageTitle";
import { Home } from "lucide-react";

export default function PortalHomePage() {
  return (
    <div>
      <PageTitle
        title="My Dashboard"
        subtitle="Your academic snapshot at a glance"
      />
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 flex flex-col items-center justify-center text-center gap-4">
        <div className="w-16 h-16 bg-[#DCFCE7] rounded-2xl flex items-center justify-center">
          <Home className="w-8 h-8 text-[#16A34A]" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[#0F172A]">Student Portal</h3>
          <p className="text-sm text-[#64748B] mt-1">
            Your CGPA, latest grades, and quick actions — coming in Module 9
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-[#DCFCE7] text-[#16A34A] px-3 py-1 text-xs font-medium">
          Coming in Module 9
        </span>
      </div>
    </div>
  );
}
