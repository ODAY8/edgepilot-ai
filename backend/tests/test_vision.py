"""Tests for the Gemini vision service's false-positive guardrails.

Two layers are tested:
1. Mocked unit tests (fast, no network) proving the evidence-based
   backstop in detect_event() actually downgrades ungrounded or
   low-confidence classifications to normal_activity.
2. Real Gemini integration tests (skipped automatically without a
   GEMINI_API_KEY) proving the fix against the real model: an ordinary
   scene must not be misclassified, and a genuinely marked hazard scene
   must still be correctly detected.
"""

import io
import json
import os

import pytest

from app.services import vision

_HAS_REAL_KEY = bool(os.getenv("GEMINI_API_KEY"))


# --- mocked unit tests ----------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: dict):
        self.text = json.dumps(payload)


class _FakeModels:
    def __init__(self, payload: dict):
        self._payload = payload

    def generate_content(self, **kwargs):
        return _FakeResponse(self._payload)


class _FakeClient:
    def __init__(self, payload: dict):
        self.models = _FakeModels(payload)


class _RaisingModels:
    def generate_content(self, **kwargs):
        raise RuntimeError("simulated network failure")


def _mock_gemini_response(monkeypatch, payload: dict):
    monkeypatch.setattr(vision, "_client", _FakeClient(payload))


def test_is_configured_false_when_no_client(monkeypatch):
    monkeypatch.setattr(vision, "_client", None)
    assert vision.is_configured() is False


def test_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(vision, "_client", None)
    with pytest.raises(vision.VisionUnavailableError):
        vision.detect_event(b"fake-bytes", "image/jpeg")


def test_call_failure_raises_vision_unavailable_not_a_guess(monkeypatch):
    fake_client = _FakeClient({})
    fake_client.models = _RaisingModels()
    monkeypatch.setattr(vision, "_client", fake_client)
    with pytest.raises(vision.VisionUnavailableError):
        vision.detect_event(b"fake-bytes", "image/jpeg")


def test_confident_classification_with_clear_evidence_is_trusted(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "event_type": "restricted_area_entry",
        "evidence_visible": True,
        "confidence": 0.95,
        "context": "A person stands inside a red-marked restricted zone with hazard stripes.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "restricted_area_entry"
    assert result.confidence == 0.95


def test_no_visible_evidence_is_downgraded_to_normal_activity(monkeypatch):
    """Reproduces the reported bug at the code level: the model picks a
    safety event but itself admits there's no clear visual evidence for
    it -- this must never reach the rest of the pipeline as a real event."""
    _mock_gemini_response(monkeypatch, {
        "event_type": "restricted_area_entry",
        "evidence_visible": False,
        "confidence": 0.9,
        "context": "A person is sitting in a chair in an ordinary room; no signage or barrier is visible.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


def test_low_confidence_is_downgraded_even_if_evidence_flag_is_true(monkeypatch):
    """A backstop independent of the evidence flag: weak confidence in a
    non-normal classification is never trusted, in case the model marks
    evidence_visible=true too liberally."""
    _mock_gemini_response(monkeypatch, {
        "event_type": "ppe_violation",
        "evidence_visible": True,
        "confidence": 0.4,
        "context": "Possibly missing a hard hat, hard to tell from this angle.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


def test_normal_activity_is_never_downgraded_or_altered(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "event_type": "normal_activity",
        "evidence_visible": True,
        "confidence": 0.98,
        "context": "Routine personnel movement with no anomaly.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"
    assert result.confidence == 0.98


def test_missing_evidence_visible_key_defaults_to_true_for_compatibility(monkeypatch):
    """Older/alternate model responses might omit the field entirely --
    should not crash, and should fall back to the confidence-only check."""
    _mock_gemini_response(monkeypatch, {
        "event_type": "forklift_near_miss",
        "confidence": 0.9,
        "context": "A forklift passes close to a worker in the loading dock.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "forklift_near_miss"


def test_unrecognized_event_type_falls_back_to_normal_activity(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "event_type": "something_the_model_made_up",
        "evidence_visible": True,
        "confidence": 0.9,
        "context": "Unclear scene.",
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


# --- real Gemini integration tests (require GEMINI_API_KEY) ---------------


def _ordinary_room_image() -> bytes:
    """A plain room: a chair and a seated person, no signage, no barriers,
    no hazard markings anywhere. This is the exact scenario previously
    misclassified as restricted_area_entry."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), color=(60, 58, 55))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 320, 640, 480], fill=(90, 85, 78))
    draw.rectangle([260, 260, 380, 320], fill=(120, 90, 60))
    draw.rectangle([260, 180, 280, 260], fill=(120, 90, 60))
    draw.rectangle([360, 180, 380, 260], fill=(120, 90, 60))
    draw.rectangle([260, 180, 380, 200], fill=(120, 90, 60))
    draw.ellipse([300, 150, 335, 185], fill=(230, 200, 180))
    draw.rectangle([295, 185, 345, 260], fill=(70, 90, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _marked_restricted_zone_image() -> bytes:
    """A clearly marked restricted zone (red boundary, hazard stripes, text
    label) with a person standing inside it."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), color=(40, 40, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 300, 640, 480], fill=(60, 60, 65))
    for x in range(100, 400, 30):
        draw.polygon([(x, 300), (x + 15, 300), (x - 15, 380), (x - 30, 380)], fill=(230, 180, 20))
    draw.rectangle([100, 150, 400, 300], outline=(220, 30, 30), width=6)
    draw.text((110, 155), "RESTRICTED ZONE", fill=(220, 30, 30))
    draw.ellipse([230, 190, 260, 220], fill=(230, 200, 180))
    draw.line([245, 220, 245, 280], fill=(230, 200, 180), width=6)
    draw.line([245, 235, 220, 260], fill=(230, 200, 180), width=5)
    draw.line([245, 235, 270, 260], fill=(230, 200, 180), width=5)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.mark.skipif(not _HAS_REAL_KEY, reason="requires a real GEMINI_API_KEY")
def test_real_gemini_ordinary_room_is_normal_activity():
    """Reproduces the exact reported bug against the real model: a plain
    room with a seated person and no signage must not be classified as a
    safety event."""
    result = vision.detect_event(_ordinary_room_image(), "image/jpeg")
    assert result.type == "normal_activity", (
        f"Expected normal_activity for an ordinary room, got {result.type!r} "
        f"(confidence={result.confidence}, context={result.context!r})"
    )


@pytest.mark.skipif(not _HAS_REAL_KEY, reason="requires a real GEMINI_API_KEY")
def test_real_gemini_marked_restricted_zone_is_still_detected():
    """The stricter prompt must not create false negatives on real,
    unambiguous evidence."""
    result = vision.detect_event(_marked_restricted_zone_image(), "image/jpeg")
    assert result.type == "restricted_area_entry", (
        f"Expected restricted_area_entry for a clearly marked zone, got "
        f"{result.type!r} (confidence={result.confidence}, context={result.context!r})"
    )
