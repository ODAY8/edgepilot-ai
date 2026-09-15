"""Real vision analysis via Google Gemini.

Sends the actual image (a still, or a frame extracted from video by
frame_extraction.py) to a Gemini vision model and asks it to do two
independent things in one call: (1) general scene understanding --
list the important objects actually visible and describe the scene,
and (2) safety-event classification into one of a fixed set of event
types, with a confidence score and a factual description of what was
actually observed. Part (1) never influences part (2): recognizing a
person, a forklift, or a sign as an object is not itself a safety
event -- see the prompt for the (unchanged) strict evidence rules.

Unlike llm.py's Groq reasoning step, there is deliberately NO fallback
here: if Gemini isn't configured or the call fails, `detect_event`
raises VisionUnavailableError. Silently returning a fake detection
would mean claiming the system observed something it never analyzed --
this project's vision layer only ever reports what a real model saw.
"""

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field

import httpx
from google import genai
from google.genai import errors as genai_errors
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

# Cap on how many detected objects we ever trust from a single frame, even
# if the model returns more than the prompt asks for.
_MAX_OBJECTS = 15

_client = genai.Client(api_key=_GEMINI_API_KEY) if _GEMINI_API_KEY else None

# Minimum reported confidence for a non-normal classification to be trusted
# even when the model claims evidence_visible=true. Guards against a model
# that's technically "confident" but for the wrong reasons.
_MIN_EVENT_CONFIDENCE = 0.6

# --- Transient-failure resilience (503/5xx, per Gemini's own retry
# guidance: bounded exponential backoff with jitter) -------------------
#
# Two layers, both bounded and both automatic:
#
# 1. Per-call retry: a single detect_event() call retries a transient
#    5xx/connection error up to _MAX_RETRIES times with exponential
#    backoff + jitter, capped at a few seconds total -- enough to ride
#    out a brief blip without noticeably stalling the live camera's
#    4-second polling loop.
# 2. Circuit breaker: if _CONSECUTIVE_FAILURES_BEFORE_COOLDOWN calls in a
#    row still fail after their own retries, every call for the next
#    _COOLDOWN_SECONDS fails FAST with VisionUnavailableError -- no
#    network call is attempted at all -- so a sustained Gemini outage
#    doesn't turn every 4-second poll into 3 more retried Gemini calls.
#    The next call after cooldown is a real "trial": success resets the
#    breaker and resumes normal analysis automatically; failure re-enters
#    cooldown. Process-memory only, matching services/dedup.py's existing
#    single-process pattern -- resets on restart, not shared across
#    workers, which is fine for this project's deployment shape.
_MAX_RETRIES = 2
_BASE_BACKOFF_SECONDS = 0.5
_MAX_BACKOFF_SECONDS = 4.0

_CONSECUTIVE_FAILURES_BEFORE_COOLDOWN = 3
_COOLDOWN_SECONDS = 30.0

_consecutive_failures = 0
_cooldown_until = 0.0  # a time.monotonic() timestamp; 0.0 means "not in cooldown"

_SYSTEM_PROMPT = (
    "You are the vision analysis engine inside EdgePilot AI, an industrial "
    "safety monitoring system. Analyze the provided image/frame from a "
    "security camera and do TWO independent things.\n\n"
    "PART 1 -- GENERAL SCENE UNDERSTANDING (always performed, independent "
    "of the safety event decided in PART 2):\n"
    "List the important objects actually visible in the frame -- people, "
    "furniture, devices, equipment, vehicles, signage, anything relevant "
    "to understanding the scene. Return at most 10-15 objects, the most "
    "important/relevant ones only; ignore tiny or unimportant background "
    "clutter unless it's relevant to the scene or to safety. Do NOT "
    "hallucinate: only list an object if you can actually see it clearly; "
    "if you are uncertain whether something is present, omit it rather "
    "than guess. Also write one concise sentence describing the overall "
    "scene.\n"
    "Recognizing an object -- including a person, a forklift, or a "
    "warning sign -- is NOT by itself a safety event and must NOT "
    "influence your answer in PART 2. Listing a sign or a forklift among "
    "the objects does not mean the corresponding safety event is "
    "occurring; that is decided separately below, using its own, "
    "stricter evidence requirements.\n\n"
    "PART 2 -- SAFETY EVENT DETECTION:\n"
    "Determine whether the image shows clear, unambiguous, directly "
    "visible evidence of a specific safety event. Default to "
    "normal_activity unless the image contains direct, unmistakable "
    "visual evidence of one of the other event types below. Do NOT infer, "
    "assume, or invent anything that is not actually visible in the image "
    "-- including restricted-area markings, hazard signage, PPE "
    "requirements, forklifts, or industrial/workplace context. An "
    "ordinary room, office, or a person sitting or standing with no "
    "visible signage, barrier, or hazard is normal_activity, even if the "
    "space could plausibly be a workplace. When in doubt, choose "
    "normal_activity.\n\n"
    "Event types and the evidence each one strictly requires:\n"
    "- restricted_area_entry: ONLY if you can clearly see BOTH (a) a "
    "marked or signed restricted/controlled area -- a barrier, sign, "
    "painted boundary line, or warning tape -- AND (b) a person inside or "
    "entering that specific marked area. A person in an ordinary, "
    "unmarked room or space is NOT this event, no matter how confident "
    "it might otherwise seem. Merely seeing a restricted-area sign as an "
    "object, with no person actually in the marked area, does not "
    "satisfy this on its own.\n"
    "- forklift_near_miss: ONLY if an actual forklift is visible in the "
    "image AND its position or movement relative to a person is clearly "
    "hazardous. No visible forklift means this can never apply. Seeing a "
    "forklift with no unsafe proximity to a person does not qualify.\n"
    "- ppe_violation: ONLY if the specific PPE requirement for that "
    "location is visually evident (e.g. a visible hard-hat-required sign, "
    "or visible active machinery that plainly calls for protection) AND a "
    "person is visibly missing that required PPE. Do not assume PPE is "
    "required just because a space looks industrial or work-related.\n"
    "- unattended_object: ONLY if an object is clearly isolated, visibly "
    "out of place, and left with no person nearby.\n"
    "- normal_activity: any ordinary scene, or any scene where the "
    "evidence required above is not clearly and directly visible.\n\n"
    "Respond with ONLY a JSON object with exactly this shape:\n"
    "{\n"
    '  "objects": [ { "name": string, "confidence": number 0-1, "context": string }, ... ],\n'
    '  "scene_description": string,\n'
    '  "event": {\n'
    f'    "type": one of {", ".join(_EVENT_TYPES)},\n'
    '    "confidence": number 0-1 -- reflecting only what is visibly '
    "evident, never inflated to express certainty about something "
    "assumed rather than seen,\n"
    '    "context": a factual 1-2 sentence description of exactly what '
    "you observe that led to this classification. Do not speculate "
    "beyond what is visibly in the image,\n"
    '    "evidence_visible": true ONLY if you can point to the specific, '
    "directly visible evidence required above for a non-normal_activity "
    "classification; false if you are inferring, assuming, guessing, or "
    "the scene is ambiguous. Always true for normal_activity.\n"
    "  }\n"
    "}"
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
class DetectedObject:
    name: str
    confidence: float
    context: str


@dataclass
class Detection:
    type: str
    label: str
    confidence: float
    context: str
    # General scene understanding -- independent of the safety event above.
    # Defaulted so every existing call site that builds a Detection with
    # only the original four fields keeps working unchanged.
    objects: list[DetectedObject] = field(default_factory=list)
    scene_description: str = ""


def is_configured() -> bool:
    return _client is not None


def _parse_objects(raw: object) -> list[DetectedObject]:
    """Defensive parsing: skips malformed entries instead of failing the
    whole request over one bad object -- object recognition is a bonus on
    top of safety detection, not something that should ever block it."""
    if not isinstance(raw, list):
        return []

    objects: list[DetectedObject] = []
    for entry in raw[:_MAX_OBJECTS]:
        try:
            name = str(entry["name"]).strip()
            if not name:
                continue
            confidence = max(0.0, min(1.0, float(entry.get("confidence", 0.0))))
            context = str(entry.get("context", ""))
            objects.append(DetectedObject(name=name, confidence=confidence, context=context))
        except (KeyError, TypeError, ValueError):
            continue
    return objects


def _is_retryable(exc: Exception) -> bool:
    """True for transient errors worth retrying: any 5xx from Gemini
    (google.genai.errors.ServerError is raised specifically for 500-599
    responses -- verified directly against the SDK, not guessed), plus
    lower-level connection/timeout errors from the underlying HTTP
    transport. Never retries a 4xx (ClientError) -- a bad request or an
    auth problem will never succeed just by trying again, so retrying it
    would only add latency to a guaranteed failure."""
    return isinstance(exc, (genai_errors.ServerError, httpx.TransportError))


def _call_gemini(image_bytes: bytes, mime_type: str):
    return _client.models.generate_content(
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


def _call_gemini_with_retry(image_bytes: bytes, mime_type: str):
    """Up to _MAX_RETRIES retries (so _MAX_RETRIES + 1 attempts total) for
    a transient 5xx/connection error, with exponential backoff + jitter --
    per Gemini's own retry guidance, and bounded so this never turns into
    an indefinite retry loop or a long stall of the live camera's polling
    loop. A non-retryable error (4xx, or the final attempt) raises
    immediately."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return _call_gemini(image_bytes, mime_type)
        except Exception as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES or not _is_retryable(exc):
                raise
            # Exponential backoff (0.5s, 1s, 2s, ... capped) with jitter
            # (uniformly 50-100% of the computed delay) so many concurrent
            # callers don't all retry in lockstep.
            delay = min(_BASE_BACKOFF_SECONDS * (2**attempt), _MAX_BACKOFF_SECONDS)
            delay *= 0.5 + random.random() * 0.5
            logger.warning(
                "Gemini call failed (attempt %d/%d, retryable): %s -- retrying in %.2fs",
                attempt + 1, _MAX_RETRIES + 1, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # pragma: no cover -- loop above always returns or raises


def detect_event(image_bytes: bytes, mime_type: str) -> Detection:
    """Analyzes a real image with Gemini. Raises VisionUnavailableError if
    Gemini isn't configured, is in a post-outage cooldown (see the module
    docstring above), or the call still fails after retries -- never
    returns a guess."""
    global _consecutive_failures, _cooldown_until

    if _client is None:
        raise VisionUnavailableError("Vision analysis is not configured (GEMINI_API_KEY is not set).")

    now = time.monotonic()
    if _cooldown_until > now:
        remaining = _cooldown_until - now
        raise VisionUnavailableError(
            f"Vision analysis is temporarily unavailable after repeated errors; "
            f"retrying automatically in {remaining:.0f}s."
        )

    try:
        response = _call_gemini_with_retry(image_bytes, mime_type)
    except Exception as exc:
        if _is_retryable(exc):
            # Only a genuinely transient/service-level failure counts
            # toward the breaker -- a malformed request or bad image
            # (never retryable, see _is_retryable) doesn't mean Gemini
            # itself is degraded, so it shouldn't trigger a cooldown.
            _consecutive_failures += 1
            if _consecutive_failures >= _CONSECUTIVE_FAILURES_BEFORE_COOLDOWN:
                _cooldown_until = time.monotonic() + _COOLDOWN_SECONDS
                logger.warning(
                    "Gemini failed %d times in a row -- backing off for %.0fs before trying again.",
                    _consecutive_failures, _COOLDOWN_SECONDS,
                )
        logger.exception("Gemini vision call failed.")
        raise VisionUnavailableError(f"Vision analysis failed: {exc}") from exc

    # A real response came back -- Gemini is healthy again. Resume normal
    # analysis immediately, regardless of how many failures preceded this.
    _consecutive_failures = 0
    _cooldown_until = 0.0

    try:
        data = json.loads(response.text)
        event_data = data["event"]

        event_type = str(event_data["type"])
        if event_type not in _EVENT_TYPES:
            event_type = "normal_activity"

        confidence = max(0.0, min(1.0, float(event_data["confidence"])))
        context = str(event_data["context"])

        # Code-level backstop, not just prompt wording: a non-normal
        # classification is only trusted if the model itself confirms
        # clearly visible evidence AND reports meaningful confidence in it.
        # This is what actually prevents false positives (e.g. an ordinary
        # room misread as a restricted area) even if the model's own
        # judgment drifts on a given call. Unchanged from before objects
        # were added -- object recognition never factors into this check.
        evidence_visible = bool(event_data.get("evidence_visible", True))
        if event_type != "normal_activity" and (not evidence_visible or confidence < _MIN_EVENT_CONFIDENCE):
            logger.info(
                "Downgrading %s to normal_activity: evidence_visible=%s confidence=%.2f",
                event_type, evidence_visible, confidence,
            )
            event_type = "normal_activity"

        objects = _parse_objects(data.get("objects"))
        scene_description = str(data.get("scene_description", ""))

        return Detection(
            type=event_type,
            label=_LABELS[event_type],
            confidence=confidence,
            context=context,
            objects=objects,
            scene_description=scene_description,
        )
    except Exception as exc:
        logger.exception("Gemini vision call failed.")
        raise VisionUnavailableError(f"Vision analysis failed: {exc}") from exc
