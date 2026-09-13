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

# Minimum reported confidence for a non-normal classification to be trusted
# even when the model claims evidence_visible=true. Guards against a model
# that's technically "confident" but for the wrong reasons.
_MIN_EVENT_CONFIDENCE = 0.6

_SYSTEM_PROMPT = (
    "You are the vision analysis engine inside EdgePilot AI, an industrial "
    "safety monitoring system. Analyze the provided image/frame from a "
    "security camera and determine whether it shows clear, unambiguous, "
    "directly visible evidence of a specific safety event.\n\n"
    "Default to normal_activity unless the image contains direct, "
    "unmistakable visual evidence of one of the other event types below. "
    "Do NOT infer, assume, or invent anything that is not actually visible "
    "in the image -- including restricted-area markings, hazard signage, "
    "PPE requirements, forklifts, or industrial/workplace context. An "
    "ordinary room, office, or a person sitting or standing with no visible "
    "signage, barrier, or hazard is normal_activity, even if the space "
    "could plausibly be a workplace. When in doubt, choose normal_activity.\n\n"
    "Event types and the evidence each one strictly requires:\n"
    "- restricted_area_entry: ONLY if you can clearly see BOTH (a) a "
    "marked or signed restricted/controlled area -- a barrier, sign, "
    "painted boundary line, or warning tape -- AND (b) a person inside or "
    "entering that specific marked area. A person in an ordinary, "
    "unmarked room or space is NOT this event, no matter how confident "
    "it might otherwise seem.\n"
    "- forklift_near_miss: ONLY if an actual forklift is visible in the "
    "image AND its position or movement relative to a person is clearly "
    "hazardous. No visible forklift means this can never apply.\n"
    "- ppe_violation: ONLY if the specific PPE requirement for that "
    "location is visually evident (e.g. a visible hard-hat-required sign, "
    "or visible active machinery that plainly calls for protection) AND a "
    "person is visibly missing that required PPE. Do not assume PPE is "
    "required just because a space looks industrial or work-related.\n"
    "- unattended_object: ONLY if an object is clearly isolated, visibly "
    "out of place, and left with no person nearby.\n"
    "- normal_activity: any ordinary scene, or any scene where the "
    "evidence required above is not clearly and directly visible.\n\n"
    "Respond with ONLY a JSON object with exactly these keys:\n"
    f'"event_type" -- must be exactly one of: {", ".join(_EVENT_TYPES)}\n'
    '"evidence_visible" -- true ONLY if you can point to the specific, '
    "directly visible evidence required above for a non-normal_activity "
    "classification; false if you are inferring, assuming, guessing, or "
    "the scene is ambiguous. Always true for normal_activity.\n"
    '"confidence" -- your confidence in this classification, a float '
    "between 0 and 1, reflecting only what is visibly evident -- never "
    "inflate this to express certainty about something assumed rather "
    "than seen.\n"
    '"context" -- a factual 1-2 sentence description of exactly what you '
    "observe in the image. Do not speculate beyond what is visibly in "
    "the image."
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
        context = str(data["context"])

        # Code-level backstop, not just prompt wording: a non-normal
        # classification is only trusted if the model itself confirms
        # clearly visible evidence AND reports meaningful confidence in it.
        # This is what actually prevents false positives (e.g. an ordinary
        # room misread as a restricted area) even if the model's own
        # judgment drifts on a given call.
        evidence_visible = bool(data.get("evidence_visible", True))
        if event_type != "normal_activity" and (not evidence_visible or confidence < _MIN_EVENT_CONFIDENCE):
            logger.info(
                "Downgrading %s to normal_activity: evidence_visible=%s confidence=%.2f",
                event_type, evidence_visible, confidence,
            )
            event_type = "normal_activity"

        return Detection(
            type=event_type,
            label=_LABELS[event_type],
            confidence=confidence,
            context=context,
        )
    except Exception as exc:
        logger.exception("Gemini vision call failed.")
        raise VisionUnavailableError(f"Vision analysis failed: {exc}") from exc
