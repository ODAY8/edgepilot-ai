"""Real vision analysis via Google Gemini.

Sends the actual image (a still, or a frame extracted from video by
frame_extraction.py) to a Gemini vision model and asks it to classify
what it sees into one of a fixed set of event types, with a confidence
score and a factual description of what was actually observed.

Unlike llm.py's Groq reasoning step, there is deliberately NO fallback
here: if Gemini isn't configured or the call fails, `detect_event`
raises VisionUnavailableError. Silently returning a fake detection
would mean claiming the system observed something it never analyzed --
this project's vision layer only ever reports what a real model saw.
"""

import json
import logging
import os
from dataclasses import dataclass

from google import genai
from google.genai import types

logger = logging.getLogger("edgepilot.vision")

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# "-latest" aliases auto-track Google's current model for this tier, which
# matters in practice: during development, both gemini-2.0-flash and
# gemini-2.5-flash-lite were deprecated/removed out from under us. Pin to
# a dated model (e.g. "gemini-3.5-flash-lite") instead if you want fully
# reproducible behavior over silently-updated behavior. If this 404s with
# "model_not_found", list what's currently available on your account:
#   python -c "from google import genai; import os; [print(m.name) for m in genai.Client(api_key=os.environ['GEMINI_API_KEY']).models.list()]"
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

_EVENT_TYPES = (
    "restricted_area_entry",
    "forklift_near_miss",
    "ppe_violation",
    "unattended_object",
    "normal_activity",
)

_client = genai.Client(api_key=_GEMINI_API_KEY) if _GEMINI_API_KEY else None

_SYSTEM_PROMPT = (
    "You are the vision analysis engine inside EdgePilot AI, an industrial "
    "safety monitoring system. Analyze the provided image/frame from a "
    "security camera and identify any safety-relevant event.\n\n"
    "Respond with ONLY a JSON object with exactly these keys:\n"
    f'"event_type" -- must be exactly one of: {", ".join(_EVENT_TYPES)}\n'
    '"confidence" -- your confidence in this classification, a float between 0 and 1\n'
    '"context" -- a factual 1-2 sentence description of exactly what you observe '
    "in the image that led to this classification. Do not speculate beyond what "
    "is visibly in the image."
)

_LABELS: dict[str, str] = {
    "restricted_area_entry": "Restricted Area Entry",
    "forklift_near_miss": "Forklift Near-Miss",
    "ppe_violation": "PPE Violation",
    "unattended_object": "Unattended Object",
    "normal_activity": "Normal Activity",
}


class VisionUnavailableError(Exception):
    """Raised when real vision analysis cannot be performed. Never caught to
    fabricate a detection -- callers must surface this as a clear failure."""


@dataclass
class Detection:
    type: str
    label: str
    confidence: float
    context: str


def is_configured() -> bool:
    return _client is not None


def detect_event(image_bytes: bytes, mime_type: str) -> Detection:
    """Analyzes a real image with Gemini. Raises VisionUnavailableError if
    Gemini isn't configured or the call fails -- never returns a guess."""
    if _client is None:
        raise VisionUnavailableError("Vision analysis is not configured (GEMINI_API_KEY is not set).")

    try:
        response = _client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _SYSTEM_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(response.text)

        event_type = str(data["event_type"])
        if event_type not in _EVENT_TYPES:
            event_type = "normal_activity"

        confidence = max(0.0, min(1.0, float(data["confidence"])))

        return Detection(
            type=event_type,
            label=_LABELS[event_type],
            confidence=confidence,
            context=str(data["context"]),
        )
    except Exception as exc:
        logger.exception("Gemini vision call failed.")
        raise VisionUnavailableError(f"Vision analysis failed: {exc}") from exc
