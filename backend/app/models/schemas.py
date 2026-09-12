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


class AnalyzeResponse(BaseModel):
    id: str
    event: EventInfo
    risk: RiskInfo
    analysis: AnalysisInfo
    recommendation: RecommendationInfo


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
