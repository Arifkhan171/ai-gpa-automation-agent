import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div className="bg-[#FEE2E2] border border-[#DC2626]/20 rounded-xl p-4 flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-[#DC2626] shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-[#DC2626] font-medium">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 text-xs text-[#DC2626] hover:text-red-800 font-medium shrink-0"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      )}
    </div>
  );
}
