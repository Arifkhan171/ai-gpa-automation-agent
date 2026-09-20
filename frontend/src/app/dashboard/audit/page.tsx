import { PageTitle } from "@/components/shared/PageTitle";
import { Shield } from "lucide-react";

export default function StubPage() {
  return (
    <div>
      <PageTitle
        title="Audit Log"
        subtitle="Full audit trail of all system events and actions"
      />
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 flex flex-col items-center justify-center text-center gap-4">
        <div className="w-16 h-16 bg-[#F1F5F9] rounded-2xl flex items-center justify-center">
          <Shield className="w-8 h-8 text-[#64748B]" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[#0F172A]">Audit Log</h3>
          <p className="text-sm text-[#64748B] mt-1">
            Full audit trail of all system events and actions — coming in Module 9
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-[#DBEAFE] text-[#2563EB] px-3 py-1 text-xs font-medium">
          Coming in Module 9
        </span>
      </div>
    </div>
  );
}
