interface StatusIndicatorProps {
  label: string;
  tone?: "safe" | "warn" | "critical";
  pulse?: boolean;
  className?: string;
}

const DOT_COLOR: Record<NonNullable<StatusIndicatorProps["tone"]>, string> = {
  safe: "bg-safe",
  warn: "bg-warn",
  critical: "bg-critical",
};

export default function StatusIndicator({
  label,
  tone = "safe",
  pulse = true,
  className = "",
}: StatusIndicatorProps) {
  return (
    <div className={`inline-flex items-center gap-2 text-xs font-medium text-ink-dim ${className}`}>
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-pulse-slow rounded-full ${DOT_COLOR[tone]} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${DOT_COLOR[tone]}`} />
      </span>
      <span className="uppercase tracking-wider">{label}</span>
    </div>
  );
}
