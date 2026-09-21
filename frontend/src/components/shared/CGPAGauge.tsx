"use client";

import { useEffect, useRef } from "react";

interface CGPAGaugeProps {
  cgpa: number | null;
  size?: "sm" | "md" | "lg";
}

const SIZE_CONFIG = {
  sm:  { dim: 88,  r: 32, sw: 6,  valuePx: 18, labelPx: 10 },
  md:  { dim: 128, r: 48, sw: 8,  valuePx: 26, labelPx: 12 },
  lg:  { dim: 168, r: 64, sw: 10, valuePx: 36, labelPx: 13 },
};

function gaugeColor(cgpa: number | null): string {
  if (cgpa === null) return "#94A3B8";
  if (cgpa >= 3.5) return "#16A34A";
  if (cgpa >= 2.5) return "#2563EB";
  if (cgpa >= 2.0) return "#D97706";
  return "#DC2626";
}

function gradeLabel(cgpa: number | null): string {
  if (cgpa === null) return "No Grades";
  if (cgpa >= 3.5) return "Excellent";
  if (cgpa >= 2.5) return "Good";
  if (cgpa >= 2.0) return "Satisfactory";
  return "At Risk";
}

export function CGPAGauge({ cgpa, size = "md" }: CGPAGaugeProps) {
  const circleRef = useRef<SVGCircleElement>(null);
  const { dim, r, sw, valuePx, labelPx } = SIZE_CONFIG[size];
  const cx = dim / 2;
  const cy = dim / 2;
  const circumference = 2 * Math.PI * r;
  const progress = cgpa !== null ? Math.min(Math.max(cgpa / 4.0, 0), 1) : 0;
  const color = gaugeColor(cgpa);

  useEffect(() => {
    const el = circleRef.current;
    if (!el) return;
    // Reset without transition
    el.style.transition = "none";
    el.style.strokeDashoffset = String(circumference);
    // Animate to target on next frame
    const raf = requestAnimationFrame(() => {
      el.style.transition = "stroke-dashoffset 1.1s cubic-bezier(0.4, 0, 0.2, 1)";
      el.style.strokeDashoffset = String(circumference - progress * circumference);
    });
    return () => cancelAnimationFrame(raf);
  }, [circumference, progress]);

  return (
    <div style={{ position: "relative", width: dim, height: dim }}>
      <svg
        width={dim}
        height={dim}
        viewBox={`0 0 ${dim} ${dim}`}
        style={{ transform: "rotate(-90deg)" }}
        aria-hidden="true"
      >
        {/* Track */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={sw}
        />
        {/* Progress arc */}
        <circle
          ref={circleRef}
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={color}
          strokeWidth={sw}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference}
        />
      </svg>

      {/* Center label */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
        aria-label={`CGPA ${cgpa !== null ? cgpa.toFixed(2) : "not available"}, ${gradeLabel(cgpa)}`}
      >
        <span
          style={{
            fontSize: valuePx,
            fontWeight: 700,
            color,
            lineHeight: 1,
          }}
        >
          {cgpa !== null ? cgpa.toFixed(2) : "—"}
        </span>
        <span
          style={{
            fontSize: labelPx,
            color: "#94A3B8",
            fontWeight: 500,
            marginTop: 3,
            lineHeight: 1,
          }}
        >
          {gradeLabel(cgpa)}
        </span>
      </div>
    </div>
  );
}
