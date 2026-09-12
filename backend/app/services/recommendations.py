"""Placeholder recommendation service.

Maps a risk level to a recommended operator action and priority. Kept
as an explicit, inspectable step -- separate from reasoning -- so "what
happened" and "what a human should do about it" can evolve
independently.
"""

from dataclasses import dataclass

from app.services.risk import RiskAssessment


@dataclass
class Recommendation:
    action: str
    priority: str


# risk level -> (recommended action, priority)
_ACTIONS: dict[str, tuple[str, str]] = {
    "HIGH": ("Notify the safety officer and verify the area immediately.", "IMMEDIATE"),
    "MEDIUM": ("Dispatch floor staff to inspect the area shortly.", "HIGH"),
    "LOW": ("No immediate action required; continue routine monitoring.", "LOW"),
}

_DEFAULT: tuple[str, str] = _ACTIONS["MEDIUM"]


def recommend_action(risk: RiskAssessment) -> Recommendation:
    action, priority = _ACTIONS.get(risk.level, _DEFAULT)
    return Recommendation(action=action, priority=priority)
