"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  GraduationCap,
  LayoutDashboard,
  Upload,
  Users,
  BarChart3,
  FileText,
  CreditCard,
  Bell,
  Shield,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import type { UserRole } from "@/types";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  roles: UserRole[];
}

const ALL_STAFF: UserRole[] = ["super_admin", "controller", "hod", "coordinator"];

const navItems: NavItem[] = [
  {
    label: "Overview",
    href: "/dashboard/overview",
    icon: <LayoutDashboard className="w-4.5 h-4.5" />,
    roles: ALL_STAFF,
  },
  {
    label: "Upload Files",
    href: "/dashboard/upload",
    icon: <Upload className="w-4.5 h-4.5" />,
    roles: ["coordinator", "super_admin"],
  },
  {
    label: "Students",
    href: "/dashboard/students",
    icon: <Users className="w-4.5 h-4.5" />,
    roles: ALL_STAFF,
  },
  {
    label: "Analytics",
    href: "/dashboard/analytics",
    icon: <BarChart3 className="w-4.5 h-4.5" />,
    roles: ["hod", "controller", "super_admin"],
  },
  {
    label: "Transcripts",
    href: "/dashboard/transcripts",
    icon: <FileText className="w-4.5 h-4.5" />,
    roles: ["coordinator", "controller", "super_admin"],
  },
  {
    label: "Payments",
    href: "/dashboard/payments",
    icon: <CreditCard className="w-4.5 h-4.5" />,
    roles: ["coordinator", "controller", "super_admin"],
  },
  {
    label: "Notifications",
    href: "/dashboard/notifications",
    icon: <Bell className="w-4.5 h-4.5" />,
    roles: ["coordinator", "controller", "super_admin"],
  },
  {
    label: "Audit Log",
    href: "/dashboard/audit",
    icon: <Shield className="w-4.5 h-4.5" />,
    roles: ["controller", "super_admin"],
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

function getRoleLabel(role: UserRole): string {
  const labels: Record<UserRole, string> = {
    super_admin: "Super Admin",
    controller: "Controller",
    hod: "Head of Department",
    coordinator: "Coordinator",
    student: "Student",
  };
  return labels[role] ?? role;
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const visibleItems = navItems.filter(
    (item) => user && item.roles.includes(user.role)
  );

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
              University of Loralai
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <div className="space-y-1">
          {visibleItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard/overview" &&
                pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
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
            <div className="w-9 h-9 rounded-full bg-[#2563EB] flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-semibold">
                {getInitials(user.full_name)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">
                {user.full_name}
              </p>
              <p className="text-slate-400 text-xs truncate">
                {getRoleLabel(user.role)}
              </p>
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
