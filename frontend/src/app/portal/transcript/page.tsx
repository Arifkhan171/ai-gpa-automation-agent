import { PageTitle } from "@/components/shared/PageTitle";
import { FileText } from "lucide-react";

export default function StubPage() {
  return (
    <div>
      <PageTitle
        title="My Transcript"
        subtitle="Request and download your official academic transcript"
      />
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-10 flex flex-col items-center justify-center text-center gap-4">
        <div className="w-16 h-16 bg-[#FEF3C7] rounded-2xl flex items-center justify-center">
          <FileText className="w-8 h-8 text-[#D97706]" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[#0F172A]">My Transcript</h3>
          <p className="text-sm text-[#64748B] mt-1">
            Request and download your official academic transcript — coming in Module 9
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-[#DCFCE7] text-[#16A34A] px-3 py-1 text-xs font-medium">
          Coming in Module 9
        </span>
      </div>
    </div>
  );
}
