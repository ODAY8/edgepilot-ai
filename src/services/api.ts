import type {
  DashboardStats,
  EventCategoryPoint,
  Incident,
  RiskDistributionPoint,
  RiskLevel,
  TimelinePoint,
} from "@/data/types";

// Real backend integration (see backend/). Every export here keeps the
// exact same signature and return shape it had as a mock, so this file
// is the only one that needed to change when the mock layer was
// replaced with the FastAPI backend.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new ApiError("Cannot reach the EdgePilot backend. Is it running on port 8000?", 0);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // no JSON body to read a message from -- fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

async function orUndefinedOn404<T>(fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return undefined;
    throw err;
  }
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>("/api/dashboard/stats");
}

export async function getIncidents(): Promise<Incident[]> {
  return apiFetch<Incident[]>("/api/incidents");
}

export async function getIncident(id: string): Promise<Incident | undefined> {
  return orUndefinedOn404(() => apiFetch<Incident>(`/api/incidents/${id}`));
}

export async function acknowledgeIncident(id: string): Promise<Incident | undefined> {
  return orUndefinedOn404(() => apiFetch<Incident>(`/api/incidents/${id}/acknowledge`, { method: "POST" }));
}

export async function escalateIncident(id: string): Promise<Incident | undefined> {
  return orUndefinedOn404(() => apiFetch<Incident>(`/api/incidents/${id}/escalate`, { method: "POST" }));
}

export interface AnalysisResult {
  id: string;
  event: string;
  risk: RiskLevel;
  confidence: number;
  explanation: string;
  recommendation: string;
  detection: string;
  context: string;
  timestamp: string;
}

interface BackendAnalyzeResponse {
  id: string;
  event: { type: string; label: string; confidence: number };
  risk: { level: RiskLevel; score: number };
  analysis: { summary: string; explanation: string };
  recommendation: { action: string; priority: string };
}

export async function analyzeInput(file: File): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", file);

  const analyzed = await apiFetch<BackendAnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: form,
  });

  // The backend's persisted incident record carries the full detail
  // (detection/context/timestamp) that the terse /api/analyze response
  // doesn't repeat -- fetch it once so the UI has everything it needs.
  const incident = await apiFetch<Incident>(`/api/incidents/${analyzed.id}`);

  return {
    id: incident.id,
    event: incident.event,
    risk: incident.risk,
    confidence: incident.confidence,
    explanation: incident.explanation,
    recommendation: incident.recommendation,
    detection: incident.detection,
    context: incident.context,
    timestamp: incident.timestamp,
  };
}

export interface DetectedObjectResult {
  name: string;
  confidence: number;
  context: string;
}

export interface LiveFrameResult {
  incidentCreated: boolean;
  status: "NORMAL" | "COOLDOWN" | "CREATED";
  event: { type: string; label: string; confidence: number };
  risk: { level: RiskLevel; score: number };
  incidentId: string | null;
  analysis: { summary: string; explanation: string } | null;
  recommendation: { action: string; priority: string } | null;
  // General scene understanding -- independent of the safety event above.
  // Populated on every frame regardless of status.
  objects: DetectedObjectResult[];
  sceneDescription: string;
}

// Sends one captured frame from a live browser camera to the backend.
// The backend itself decides whether this frame warrants an incident
// (see routes/live.py) -- normal frames and cooldown-deduped repeats
// come back with incidentCreated: false and no Groq call was made.
export async function analyzeFrame(frame: Blob, cameraId?: string, location?: string): Promise<LiveFrameResult> {
  const form = new FormData();
  form.append("file", frame, "frame.jpg");
  if (cameraId) form.append("camera_id", cameraId);
  if (location) form.append("location", location);

  return apiFetch<LiveFrameResult>("/api/analyze-frame", {
    method: "POST",
    body: form,
  });
}

export interface AnalyticsData {
  eventsOverTime: TimelinePoint[];
  riskDistribution: RiskDistributionPoint[];
  eventCategories: EventCategoryPoint[];
  systemHealth: { uptime: string; avgResponseTime: string; edgeNodesOnline: number; edgeNodesTotal: number };
}

export async function getAnalyticsData(): Promise<AnalyticsData> {
  return apiFetch<AnalyticsData>("/api/analytics");
}
