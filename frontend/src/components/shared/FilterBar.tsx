"use client";

import React from "react";
import { X } from "lucide-react";

export interface FilterOption {
  label: string;
  value: string;
}

export interface FilterConfig {
  key: string;
  label: string;
  type: "select" | "text" | "date";
  options?: FilterOption[];
  placeholder?: string;
  value: string;
}

interface FilterBarProps {
  filters: FilterConfig[];
  onFilterChange: (key: string, value: string) => void;
  onClear: () => void;
  hasActiveFilters?: boolean;
  children?: React.ReactNode;
}

export function FilterBar({
  filters,
  onFilterChange,
  onClear,
  hasActiveFilters = false,
  children,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {filters.map((filter) => (
        <div key={filter.key} className="min-w-[150px]">
          {filter.type === "select" ? (
            <select
              value={filter.value}
              onChange={(e) => onFilterChange(filter.key, e.target.value)}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent min-w-[150px]"
            >
              <option value="">{filter.label}: All</option>
              {filter.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={filter.type}
              value={filter.value}
              onChange={(e) => onFilterChange(filter.key, e.target.value)}
              placeholder={filter.placeholder ?? filter.label}
              className="h-9 px-3 text-sm border border-[#E2E8F0] rounded-lg bg-white text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent min-w-[150px]"
            />
          )}
        </div>
      ))}
      {children}
      {hasActiveFilters && (
        <button
          onClick={onClear}
          className="flex items-center gap-1.5 h-9 px-3 text-sm text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors whitespace-nowrap"
        >
          <X className="w-3.5 h-3.5" />
          Clear Filters
        </button>
      )}
    </div>
  );
}
