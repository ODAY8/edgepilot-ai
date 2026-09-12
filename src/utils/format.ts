import type { IncidentStatus, RiskLevel } from "@/data/types";

export function formatChange(change: number, suffix = ""): string {
  if (change === 0) return `No change`;
  const sign = change > 0 ? "+" : "";
  return `${sign}${change}${suffix} vs last shift`;
}

export const RISK_ORDER: RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  ACTIVE: "Active",
  ACKNOWLEDGED: "Acknowledged",
  ESCALATED: "Escalated",
  RESOLVED: "Resolved",
};
