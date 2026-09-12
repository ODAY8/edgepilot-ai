"""Placeholder reasoning service.

Turns a detection into a human-readable summary and explanation.
Templated today; will be replaced by an LLM-backed reasoning step later
without changing `generate_explanation`'s signature.
"""

from dataclasses import dataclass

from app.services.vision import Detection


@dataclass
class Analysis:
    summary: str
    explanation: str


_EXPLANATIONS: dict[str, str] = {
    "restricted_area_entry": (
        "A worker entered the predefined restricted zone near industrial "
        "equipment without visible protective clearance."
    ),
    "forklift_near_miss": "A forklift path intersected with a pedestrian walkway at unsafe speed.",
    "ppe_violation": "A worker was detected without required personal protective equipment near active machinery.",
    "unattended_object": "An object was left stationary in a monitored walkway for an extended period.",
    "normal_activity": "Routine personnel movement was observed with no anomaly detected.",
}


def generate_explanation(detection: Detection, location: str | None) -> Analysis:
    explanation = _EXPLANATIONS.get(
        detection.type,
        f"{detection.label} was detected with {detection.confidence:.0%} confidence.",
    )
    where = f" in {location}" if location else ""
    summary = f"{detection.label} detected{where}."
    return Analysis(summary=summary, explanation=explanation)
