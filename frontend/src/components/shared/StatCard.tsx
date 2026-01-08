import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; label: string };
  color?: "blue" | "green" | "red" | "amber";
}

const colorClasses: Record<string, string> = {
  blue: "border-l-[#2563EB]",
  green: "border-l-[#16A34A]",
  red: "border-l-[#DC2626]",
  amber: "border-l-[#D97706]",
};

const iconBgClasses: Record<string, string> = {
  blue: "bg-[#DBEAFE] text-[#2563EB]",
  green: "bg-[#DCFCE7] text-[#16A34A]",
  red: "bg-[#FEE2E2] text-[#DC2626]",
  amber: "bg-[#FEF3C7] text-[#D97706]",
};

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  color = "blue",
}: StatCardProps) {
  return (
    <div
      className={cn(
        "bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 border-l-4",
        colorClasses[color]
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-medium uppercase tracking-wider text-[#94A3B8] mb-2">
            {title}
          </p>
          <p className="text-3xl font-bold text-[#0F172A]">{value}</p>
          {subtitle && (
            <p className="text-sm text-[#64748B] mt-1">{subtitle}</p>
          )}
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              {trend.value >= 0 ? (
                <TrendingUp className="w-3.5 h-3.5 text-[#16A34A]" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-[#DC2626]" />
              )}
              <span
                className={cn(
                  "text-xs font-medium",
                  trend.value >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"
                )}
              >
                {trend.value >= 0 ? "+" : ""}
                {trend.value}% {trend.label}
              </span>
            </div>
          )}
        </div>
        {icon && (
          <div
            className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
              iconBgClasses[color]
            )}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
