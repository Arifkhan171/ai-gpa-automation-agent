"use client";

import { useState } from "react";
import { Search, Bell, ChevronDown, KeyRound, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import type { UserRole } from "@/types";

interface HeaderProps {
  pageName: string;
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

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function Header({ pageName }: HeaderProps) {
  const { user, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <header className="h-16 bg-white border-b border-[#E2E8F0] flex items-center px-6 gap-4 sticky top-0 z-20">
      {/* Page name */}
      <div className="flex-1">
        <h2 className="text-[15px] font-semibold text-[#0F172A]">{pageName}</h2>
      </div>

      {/* Search */}
      <div className="relative hidden md:block">
        <Search className="w-4 h-4 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          placeholder="Search..."
          className="pl-9 pr-4 py-2 text-sm border border-[#E2E8F0] rounded-lg bg-[#F8FAFC] text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] w-56 transition"
        />
      </div>

      {/* Notification bell */}
      <button className="relative w-9 h-9 rounded-lg hover:bg-[#F8FAFC] flex items-center justify-center transition-colors">
        <Bell className="w-4.5 h-4.5 text-[#64748B]" />
        <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#DC2626]" />
      </button>

      {/* User dropdown */}
      {user && (
        <div className="relative">
          <button
            onClick={() => setDropdownOpen((v) => !v)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-[#F8FAFC] transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-[#2563EB] flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-semibold">
                {getInitials(user.full_name)}
              </span>
            </div>
            <div className="hidden md:block text-left">
              <p className="text-sm font-medium text-[#0F172A] leading-none">
                {user.full_name}
              </p>
              <p className="text-[11px] text-[#64748B] leading-none mt-0.5">
                {getRoleLabel(user.role)}
              </p>
            </div>
            <ChevronDown className="w-4 h-4 text-[#94A3B8]" />
          </button>

          {dropdownOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setDropdownOpen(false)}
              />
              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-2 w-52 bg-white rounded-xl border border-[#E2E8F0] shadow-lg z-20 overflow-hidden">
                <div className="px-4 py-3 border-b border-[#E2E8F0]">
                  <p className="text-sm font-semibold text-[#0F172A]">
                    {user.full_name}
                  </p>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {user.email || user.username}
                  </p>
                  <span className="inline-flex mt-2 items-center rounded-full bg-[#DBEAFE] text-[#2563EB] px-2 py-0.5 text-[10px] font-medium">
                    {getRoleLabel(user.role)}
                  </span>
                </div>
                <div className="py-1">
                  <button
                    className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-[#64748B] hover:bg-[#F8FAFC] hover:text-[#0F172A] transition-colors"
                    onClick={() => {
                      setDropdownOpen(false);
                      // Module 9 will add change-password modal
                    }}
                  >
                    <KeyRound className="w-4 h-4" />
                    Change Password
                  </button>
                  <button
                    className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-[#DC2626] hover:bg-[#FEE2E2] transition-colors"
                    onClick={() => {
                      setDropdownOpen(false);
                      logout();
                    }}
                  >
                    <LogOut className="w-4 h-4" />
                    Sign Out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </header>
  );
}
