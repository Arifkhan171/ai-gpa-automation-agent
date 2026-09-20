"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  GraduationCap,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  Loader2,
  BrainCircuit,
  QrCode,
  BarChart3,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { isLoggedIn, getUser, getDashboardPath } from "@/lib/auth";

const features = [
  {
    icon: <BrainCircuit className="w-5 h-5 text-blue-300" />,
    text: "AI-Powered Grade Validation",
  },
  {
    icon: <QrCode className="w-5 h-5 text-blue-300" />,
    text: "QR-Verified Transcripts",
  },
  {
    icon: <BarChart3 className="w-5 h-5 text-blue-300" />,
    text: "Real-Time Analytics Dashboard",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if already logged in
  useEffect(() => {
    if (isLoggedIn()) {
      const user = getUser();
      if (user) {
        router.replace(getDashboardPath(user.role));
      }
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Please enter both username and password.");
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      await login(username.trim(), password);
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Login failed. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* ── LEFT: Navy panel ── */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0F2444] flex-col justify-between p-12">
        <div>
          {/* University branding */}
          <div className="flex items-center gap-4 mb-12">
            <div className="w-20 h-20 bg-white/10 rounded-2xl flex items-center justify-center">
              <GraduationCap className="w-12 h-12 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold text-white tracking-tight">
                AcadTrack
              </h1>
              <p className="text-slate-300 text-base mt-1">
                University of Loralai
              </p>
            </div>
          </div>

          {/* Tagline */}
          <div className="mb-12">
            <h2 className="text-2xl font-semibold text-white mb-3">
              Enterprise GPA Management
            </h2>
            <p className="text-slate-400 text-base leading-relaxed max-w-sm">
              A unified platform for managing student grades, generating
              verified transcripts, and tracking academic performance across
              all departments.
            </p>
          </div>

          {/* Divider */}
          <div className="border-t border-white/10 mb-8" />

          {/* Feature highlights */}
          <div className="space-y-4">
            {features.map((f) => (
              <div key={f.text} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center shrink-0">
                  {f.icon}
                </div>
                <span className="text-white text-sm font-medium">{f.text}</span>
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] ml-auto shrink-0" />
              </div>
            ))}
          </div>
        </div>

        {/* Bottom attribution */}
        <p className="text-slate-500 text-xs">
          © {new Date().getFullYear()} University of Loralai — AcadTrack v1.0
        </p>
      </div>

      {/* ── RIGHT: Login form ── */}
      <div className="flex-1 flex items-center justify-center bg-[#F8FAFC] p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-10 h-10 bg-[#0F2444] rounded-xl flex items-center justify-center">
              <GraduationCap className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-[#0F2444] font-bold text-lg">AcadTrack</p>
              <p className="text-[#64748B] text-xs">University of Loralai</p>
            </div>
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-8">
            <h2 className="text-2xl font-bold text-[#0F172A] mb-1">
              Welcome back
            </h2>
            <p className="text-sm text-[#64748B] mb-8">
              Sign in to your account to continue
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Username */}
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Roll number or username"
                  autoComplete="username"
                  disabled={isLoading}
                  className="w-full px-4 py-2.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] disabled:opacity-50 transition"
                />
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    disabled={isLoading}
                    className="w-full px-4 py-2.5 pr-11 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] disabled:opacity-50 transition"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#64748B] transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="w-4.5 h-4.5" />
                    ) : (
                      <Eye className="w-4.5 h-4.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Error message */}
              {error && (
                <div className="flex items-start gap-2.5 bg-[#FEE2E2] border border-[#DC2626]/20 rounded-lg px-4 py-3">
                  <AlertCircle className="w-4.5 h-4.5 text-[#DC2626] shrink-0 mt-0.5" />
                  <p className="text-sm text-[#DC2626]">{error}</p>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#2563EB] text-white rounded-lg py-2.5 px-4 font-medium text-sm hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <p className="text-xs text-[#94A3B8] text-center mt-6">
              Contact your system administrator if you cannot log in.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
