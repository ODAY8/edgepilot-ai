import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { useCountUp } from "@/hooks/useCountUp";

interface StatCardProps {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  change: number;
  changeSuffix?: string;
  icon: LucideIcon;
  tone?: "accent" | "safe" | "warn" | "critical";
  index?: number;
}

const TONE_STYLES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  accent: "text-accent bg-accent-soft",
  safe: "text-safe bg-safe/10",
  warn: "text-warn bg-warn/10",
  critical: "text-critical bg-critical/10",
};

export default function StatCard({
  label,
  value,
  decimals = 0,
  suffix = "",
  change,
  changeSuffix = "%",
  icon: Icon,
  tone = "accent",
  index = 0,
}: StatCardProps) {
  const animated = useCountUp(value, 1000, decimals);
  const isPositive = change >= 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: "easeOut" }}
      whileHover={{ y: -3 }}
      className="group rounded-2xl border border-border bg-surface p-5 transition-colors duration-200 hover:border-accent/30"
    >
      <div className="flex items-start justify-between">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${TONE_STYLES[tone]}`}>
          <Icon size={17} />
        </div>
        {change !== 0 && (
          <span
            className={`flex items-center gap-1 text-xs font-semibold ${
              isPositive ? "text-safe" : "text-critical"
            }`}
          >
            {isPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {Math.abs(change)}
            {changeSuffix}
          </span>
        )}
      </div>
      <p className="mt-4 text-2xl font-bold tabular-nums text-ink">
        {animated}
        {suffix}
      </p>
      <p className="mt-1 text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</p>
    </motion.div>
  );
}
