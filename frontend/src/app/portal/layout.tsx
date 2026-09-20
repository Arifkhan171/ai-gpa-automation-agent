"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { StudentSidebar } from "@/components/layout/StudentSidebar";
import { Header } from "@/components/layout/Header";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { isLoggedIn, getUser, getDashboardPath } from "@/lib/auth";
import type { UserRole } from "@/types";

const PAGE_NAMES: Record<string, string> = {
  "/portal": "My Dashboard",
  "/portal/grades": "My Grades",
  "/portal/transcript": "My Transcript",
  "/portal/payments": "Payments",
};

function getPageName(pathname: string): string {
  return PAGE_NAMES[pathname] || "Student Portal";
}

export default function PortalLayout({
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
    if (user && user.role !== "student") {
      router.replace(getDashboardPath(user.role as UserRole));
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
      <StudentSidebar />
      <div className="ml-[260px] flex flex-col min-h-screen">
        <Header pageName={getPageName(pathname)} />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
