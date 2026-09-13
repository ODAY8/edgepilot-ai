"""Deterministic risk-assessment service.

Maps a detected event type to a risk level and a numeric score via a
lookup table. The score is a pure function of (event type, confidence):
the event type picks a fixed score band, and Gemini's own confidence
for that detection places the score within that band -- higher
confidence pushes the score toward the top of the band, lower
confidence toward the bottom. Same detection type + same confidence
always yields the same level and score; nothing here is randomized.

This is the seam where a real rules-based or model-driven risk engine
will plug in later without changing `assess_risk`'s signature.
"""

from dataclasses import dataclass

from app.services.vision import Detection


@dataclass
class RiskAssessment:
    level: str
    score: int


# event type -> (risk level, score band)
_RISK_TABLE: dict[str, tuple[str, tuple[int, int]]] = {
    "restricted_area_entry": ("HIGH", (85, 96)),
    "forklift_near_miss": ("HIGH", (80, 92)),
    "ppe_violation": ("MEDIUM", (55, 72)),
    "unattended_object": ("MEDIUM", (45, 62)),
    "normal_activity": ("LOW", (2, 15)),
}

_DEFAULT: tuple[str, tuple[int, int]] = ("MEDIUM", (40, 60))


def assess_risk(detection: Detection) -> RiskAssessment:
    level, (low, high) = _RISK_TABLE.get(detection.type, _DEFAULT)
    confidence = max(0.0, min(1.0, detection.confidence))
    score = round(low + confidence * (high - low))
    score = max(low, min(high, score))
    return RiskAssessment(level=level, score=score)
