import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCGPA(cgpa: number | null): string {
  if (cgpa === null || cgpa === undefined) return "—";
  return cgpa.toFixed(2);
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "excellent":
      return "bg-[#DCFCE7] text-[#16A34A]";
    case "good":
      return "bg-[#DCFCE7] text-[#16A34A]";
    case "satisfactory":
      return "bg-[#FEF3C7] text-[#D97706]";
    case "at_risk":
      return "bg-[#FEE2E2] text-[#DC2626]";
    case "no_grades":
    default:
      return "bg-[#F1F5F9] text-[#64748B]";
  }
}

export function getStatusLabel(status: string): string {
  switch (status) {
    case "excellent":
      return "Excellent";
    case "good":
      return "Good";
    case "satisfactory":
      return "Satisfactory";
    case "at_risk":
      return "At Risk";
    case "no_grades":
      return "No Grades";
    default:
      return status;
  }
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function formatCurrency(amount: number): string {
  return `Rs. ${amount.toLocaleString()}`;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
