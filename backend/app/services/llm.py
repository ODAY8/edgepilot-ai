"""Groq-backed reasoning service.

Calls a Groq-hosted LLM to turn a detection + risk assessment into a
natural-language explanation and a recommended operator action. This
sits alongside -- not instead of -- the rule-based templates in
reasoning.py/recommendations.py: if no API key is configured, or the
call fails for any reason, `generate_reasoning` returns None and the
caller falls back to those templates, so the pipeline never breaks
because of a missing key or a third-party outage.
"""

import json
import logging
import os
from dataclasses import dataclass

from groq import Groq

from app.services.risk import RiskAssessment
from app.services.vision import Detection

logger = logging.getLogger("edgepilot.llm")

_GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Model availability on Groq changes over time -- if this 404s with
# "model_not_found", run `client.models.list()` to see what's currently
# available on your account and update GROQ_MODEL in .env.
_GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
_VALID_PRIORITIES = {"IMMEDIATE", "HIGH", "MEDIUM", "LOW"}

_client = Groq(api_key=_GROQ_API_KEY, timeout=15.0) if _GROQ_API_KEY else None

_SYSTEM_PROMPT = (
    "You are the reasoning engine inside EdgePilot AI, an industrial safety "
    "monitoring system. Given a detected event and its assessed risk level, "
    "write a concise, professional safety-incident summary, explanation, and "
    "recommended operator action. Respond with ONLY a JSON object with "
    "exactly these keys: "
    '"summary" (<=15 words), '
    '"explanation" (1-2 factual sentences, do not speculate beyond what is given), '
    '"action" (1 imperative sentence addressed to a human operator), '
    '"priority" -- must be exactly one of these four strings, uppercase, '
    "no other words: IMMEDIATE, HIGH, MEDIUM, LOW."
)


@dataclass
class LLMReasoning:
    summary: str
    explanation: str
    action: str
    priority: str


def is_configured() -> bool:
    return _client is not None


def generate_reasoning(detection: Detection, risk: RiskAssessment, location: str | None) -> LLMReasoning | None:
    """Never raises. Returns None if Groq isn't configured or the call fails,
    so callers can fall back to the rule-based templates."""
    if _client is None:
        return None

    user_prompt = (
        f"Event type: {detection.type}\n"
        f"Event label: {detection.label}\n"
        f"Detection confidence: {detection.confidence:.0%}\n"
        f"Context: {detection.context}\n"
        f"Location: {location or 'not specified'}\n"
        f"Assessed risk level: {risk.level}\n"
        f"Risk score: {risk.score}/100"
    )

    # gpt-oss (and other reasoning) models spend a chunk of the token
    # budget on an internal reasoning trace before the final JSON, and
    # Groq lets that budget be capped via reasoning_effort. Keeping it
    # low both speeds up the response and leaves more of max_tokens for
    # the actual answer.
    extra_kwargs = {"reasoning_effort": "low"} if "gpt-oss" in _GROQ_MODEL else {}

    try:
        response = _client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1024,
            response_format={"type": "json_object"},
            **extra_kwargs,
        )
        data = json.loads(response.choices[0].message.content)

        priority = str(data.get("priority", "")).upper()
        if priority not in _VALID_PRIORITIES:
            priority = risk.level  # LOW/MEDIUM/HIGH are valid priorities too

        return LLMReasoning(
            summary=str(data["summary"]),
            explanation=str(data["explanation"]),
            action=str(data["action"]),
            priority=priority,
        )
    except Exception:
        logger.exception("Groq reasoning call failed; falling back to template reasoning.")
        return None
