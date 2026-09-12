"""Placeholder vision service.

Stands in for the real computer-vision model. Given an uploaded file's
metadata, returns a plausible detection result so the rest of the
pipeline (reasoning -> risk -> recommendation) can be built and tested
end-to-end before a real model is wired in. Swap the body of
`detect_event` for an actual inference call later; the return shape is
the contract the rest of the pipeline depends on.
"""

import random
from dataclasses import dataclass


@dataclass
class Detection:
    type: str
    label: str
    confidence: float
    context: str


_DETECTION_CATALOG: list[Detection] = [
    Detection("restricted_area_entry", "Restricted Area Entry", 0.94, "Restricted zone"),
    Detection("forklift_near_miss", "Forklift Near-Miss", 0.89, "Loading dock corridor"),
    Detection("ppe_violation", "PPE Violation", 0.85, "Active machinery zone"),
    Detection("unattended_object", "Unattended Object", 0.81, "Walkway obstruction"),
    Detection("normal_activity", "Normal Activity", 0.98, "Authorized zone"),
]

_WEIGHTS = [0.35, 0.15, 0.2, 0.15, 0.15]


def detect_event(filename: str | None, content_type: str | None) -> Detection:
    """Simulate running the uploaded media through a vision model."""
    return random.choices(_DETECTION_CATALOG, weights=_WEIGHTS, k=1)[0]
