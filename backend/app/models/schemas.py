"""Pydantic response/request schemas for the EdgePilot AI API.

Field names on the Incident/DashboardStats/Analytics models intentionally
use camelCase to mirror `src/data/types.ts` on the frontend, so that
swapping `src/services/api.ts` from mock data to real HTTP calls later
requires no field-mapping layer.
"""

from typing import Literal

from pydantic import BaseModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
IncidentStatus = Literal["ACTIVE", "ACKNOWLEDGED", "ESCALATED", "RESOLVED"]
Priority = Literal["IMMEDIATE", "HIGH", "MEDIUM", "LOW"]


class HealthResponse(BaseModel):
    status: str
    service: str


# --- /api/system/status --------------------------------------------------


class SystemStatusResponse(BaseModel):
    """Non-secret configuration status for the Settings page. Never
    includes key values -- only whether each provider is configured, the
    same booleans vision.is_configured()/llm.is_configured() already
    expose for the startup log."""

    version: str
    visionEnabled: bool
    reasoningEnabled: bool


# --- /api/analyze -----------------------------------------------------


class EventInfo(BaseModel):
    type: str
    label: str
    confidence: float


class RiskInfo(BaseModel):
    level: RiskLevel
    score: int


class AnalysisInfo(BaseModel):
    summary: str
    explanation: str


class RecommendationInfo(BaseModel):
    action: str
    priority: Priority


class DetectedObjectInfo(BaseModel):
    name: str
    confidence: float
    context: str


class AnalyzeResponse(BaseModel):
    id: str
    event: EventInfo
    risk: RiskInfo
    analysis: AnalysisInfo
    recommendation: RecommendationInfo
    # General scene understanding -- independent of the safety event above.
    objects: list[DetectedObjectInfo] = []
    sceneDescription: str = ""


# --- /api/analyze-frame (live browser camera) ----------------------------

FrameStatus = Literal["NORMAL", "COOLDOWN", "CREATED"]


class LiveFrameResponse(BaseModel):
    incidentCreated: bool
    status: FrameStatus
    event: EventInfo
    risk: RiskInfo
    incidentId: str | None = None
    analysis: AnalysisInfo | None = None
    recommendation: RecommendationInfo | None = None
    # Populated on every response regardless of status -- object recognition
    # runs on every frame independent of whether a safety event was found.
    objects: list[DetectedObjectInfo] = []
    sceneDescription: str = ""


# --- /api/incidents -----------------------------------------------------


class Incident(BaseModel):
    id: str
    event: str
    risk: RiskLevel
    confidence: int
    location: str
    cameraId: str
    edgeNode: str
    timestamp: str
    date: str
    explanation: str
    recommendation: str
    status: IncidentStatus
    detection: str
    context: str


# --- /api/dashboard/stats -----------------------------------------------


class StatBlock(BaseModel):
    value: float
    change: float


class DashboardStatsResponse(BaseModel):
    totalEvents: StatBlock
    highRisk: StatBlock
    activeInputs: StatBlock
    systemHealth: StatBlock


# --- /api/analytics -------------------------------------------------------


class TimelinePoint(BaseModel):
    time: str
    events: int


class RiskDistributionPoint(BaseModel):
    name: RiskLevel
    value: int


class EventCategoryPoint(BaseModel):
    name: str
    value: int


class SystemHealthInfo(BaseModel):
    uptime: str
    avgResponseTime: str
    edgeNodesOnline: int
    edgeNodesTotal: int


class AnalyticsResponse(BaseModel):
    eventsOverTime: list[TimelinePoint]
    riskDistribution: list[RiskDistributionPoint]
    eventCategories: list[EventCategoryPoint]
    systemHealth: SystemHealthInfo
