"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  isLoading: boolean;
  className?: string;
  action?: React.ReactNode;
}

export function ChartCard({
  title,
  subtitle,
  children,
  isLoading,
  className,
  action,
}: ChartCardProps) {
  return (
    <div
      className={cn(
        "bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6",
        className
      )}
    >
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-[#0F172A]">{title}</h3>
          {subtitle && (
            <p className="text-xs text-[#64748B] mt-0.5">{subtitle}</p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      {isLoading ? (
        <div className="animate-pulse">
          <div className="h-48 bg-[#F1F5F9] rounded-lg" />
          <div className="flex gap-2 mt-3 justify-center">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-2 bg-[#F1F5F9] rounded w-12" />
            ))}
          </div>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
