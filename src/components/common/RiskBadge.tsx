import type { RiskLevel } from "@/data/types";

const STYLES: Record<RiskLevel, string> = {
  LOW: "bg-safe/10 text-safe border-safe/30",
  MEDIUM: "bg-warn/10 text-warn border-warn/30",
  HIGH: "bg-critical/10 text-critical border-critical/30",
};

interface RiskBadgeProps {
  risk: RiskLevel;
  className?: string;
}

export default function RiskBadge({ risk, className = "" }: RiskBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${STYLES[risk]} ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {risk}
    </span>
  );
}
