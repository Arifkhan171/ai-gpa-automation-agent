"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { isLoggedIn, getUser } from "@/lib/auth";

const PAGE_NAMES: Record<string, string> = {
  "/dashboard/overview": "Overview",
  "/dashboard/upload": "Upload Files",
  "/dashboard/students": "Students",
  "/dashboard/analytics": "Analytics",
  "/dashboard/transcripts": "Transcripts",
  "/dashboard/payments": "Payments",
  "/dashboard/notifications": "Notifications",
  "/dashboard/audit": "Audit Log",
};

function getPageName(pathname: string): string {
  if (pathname.startsWith("/dashboard/students/")) return "Student Detail";
  return PAGE_NAMES[pathname] || "Dashboard";
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    const user = getUser();
    if (user?.role === "student") {
      router.replace("/portal");
      return;
    }
    setChecking(false);
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <LoadingSpinner size="lg" text="Loading..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Sidebar />
      <div className="ml-[260px] flex flex-col min-h-screen">
        <Header pageName={getPageName(pathname)} />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
