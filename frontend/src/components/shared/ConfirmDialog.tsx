"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "default" | "destructive";
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "default",
  onConfirm,
  onCancel,
  isLoading = false,
}: ConfirmDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="bg-white border border-[#E2E8F0] max-w-md sm:rounded-xl">
        <DialogHeader>
          <DialogTitle className="text-[#0F172A] text-lg font-semibold">
            {title}
          </DialogTitle>
          <DialogDescription className="text-[#64748B] text-sm leading-relaxed mt-2">
            {message}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 mt-4 flex-row justify-end">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-[#64748B] border border-[#E2E8F0] rounded-lg hover:bg-[#F8FAFC] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
              confirmVariant === "destructive"
                ? "bg-[#DC2626] hover:bg-red-700"
                : "bg-[#2563EB] hover:bg-blue-700"
            )}
          >
            {isLoading && <LoadingSpinner size="sm" />}
            {confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
