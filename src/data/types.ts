export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type IncidentStatus = "ACTIVE" | "ACKNOWLEDGED" | "ESCALATED" | "RESOLVED";

export interface Incident {
  id: string;
  event: string;
  risk: RiskLevel;
  confidence: number;
  location: string;
  cameraId: string;
  edgeNode: string;
  timestamp: string;
  date: string;
  explanation: string;
  recommendation: string;
  status: IncidentStatus;
  detection: string;
  context: string;
}

export interface DashboardStats {
  totalEvents: { value: number; change: number };
  highRisk: { value: number; change: number };
  activeInputs: { value: number; change: number };
  systemHealth: { value: number; change: number };
}

export interface TimelinePoint {
  time: string;
  events: number;
}

export interface RiskDistributionPoint {
  name: RiskLevel;
  value: number;
}

export interface EventCategoryPoint {
  name: string;
  value: number;
}
