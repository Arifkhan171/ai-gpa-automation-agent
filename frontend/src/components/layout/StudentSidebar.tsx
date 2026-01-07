"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  GraduationCap,
  Home,
  BookOpen,
  FileText,
  CreditCard,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const navItems = [
  {
    label: "My Dashboard",
    href: "/portal",
    icon: <Home className="w-4.5 h-4.5" />,
    exact: true,
  },
  {
    label: "My Grades",
    href: "/portal/grades",
    icon: <BookOpen className="w-4.5 h-4.5" />,
    exact: false,
  },
  {
    label: "My Transcript",
    href: "/portal/transcript",
    icon: <FileText className="w-4.5 h-4.5" />,
    exact: false,
  },
  {
    label: "Payments",
    href: "/portal/payments",
    icon: <CreditCard className="w-4.5 h-4.5" />,
    exact: false,
  },
];

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function StudentSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-[260px] bg-[#0F2444] flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 pt-6 pb-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center shrink-0">
            <GraduationCap className="w-6 h-6 text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-[18px] leading-tight">
              AcadTrack
            </p>
            <p className="text-slate-400 text-[11px] leading-tight">
              Student Portal
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <p className="text-slate-500 text-[10px] uppercase tracking-wider font-medium px-3 mb-3">
          Menu
        </p>
        <div className="space-y-1">
          {navItems.map((item) => {
            const actualActive =
              item.exact
                ? pathname === item.href
                : pathname.startsWith(item.href) && pathname !== "/portal";

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  actualActive
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                )}
              >
                <span className="shrink-0">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* User section */}
      {user && (
        <div className="px-3 pb-5 border-t border-white/10 pt-4">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="w-9 h-9 rounded-full bg-[#16A34A] flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-semibold">
                {getInitials(user.full_name)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">
                {user.full_name}
              </p>
              <p className="text-slate-400 text-xs truncate">{user.username}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-slate-300 hover:bg-white/5 hover:text-white text-sm font-medium transition-colors"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}
