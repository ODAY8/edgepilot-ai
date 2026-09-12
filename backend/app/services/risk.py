"""Placeholder risk-assessment service.

Maps a detected event type to a risk level and numeric score via a
lookup table. This is the seam where a real rules-based or model-driven
risk engine will plug in later without changing `assess_risk`'s
signature.
"""

import random
from dataclasses import dataclass

from app.services.vision import Detection


@dataclass
class RiskAssessment:
    level: str
    score: int


# event type -> (risk level, score range)
_RISK_TABLE: dict[str, tuple[str, tuple[int, int]]] = {
    "restricted_area_entry": ("HIGH", (85, 96)),
    "forklift_near_miss": ("HIGH", (80, 92)),
    "ppe_violation": ("MEDIUM", (55, 72)),
    "unattended_object": ("MEDIUM", (45, 62)),
    "normal_activity": ("LOW", (2, 15)),
}

_DEFAULT: tuple[str, tuple[int, int]] = ("MEDIUM", (40, 60))


def assess_risk(detection: Detection) -> RiskAssessment:
    level, score_range = _RISK_TABLE.get(detection.type, _DEFAULT)
    return RiskAssessment(level=level, score=random.randint(*score_range))
