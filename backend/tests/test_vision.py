"""Tests for the Gemini vision service: object/scene recognition and the
existing false-positive guardrails for safety-event detection.

Three layers are tested:
1. Mocked unit tests (fast, no network) proving the evidence-based
   backstop in detect_event() still downgrades ungrounded or
   low-confidence classifications to normal_activity, unaffected by the
   new nested JSON shape.
2. Mocked unit tests proving general object/scene recognition is parsed
   correctly and stays independent of safety-event detection (an object
   like a person or a sign never implies an incident by itself).
3. Real Gemini integration tests (skipped automatically without a
   GEMINI_API_KEY): the two pre-existing safety-detection cases, plus one
   new test for general object recognition against the real model.
"""

import io
import json
import os

import pytest

from app.services import vision

_HAS_REAL_KEY = bool(os.getenv("GEMINI_API_KEY"))


# --- mocked unit tests: safety-event backstop (unchanged behavior) -------


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


def _event_payload(event_type: str, confidence: float, context: str, evidence_visible: bool | None = True) -> dict:
    """Builds a full mocked Gemini response in the current nested shape.
    evidence_visible=None omits the key entirely (tests the compatibility
    default)."""
    event: dict = {"type": event_type, "confidence": confidence, "context": context}
    if evidence_visible is not None:
        event["evidence_visible"] = evidence_visible
    return {"objects": [], "scene_description": "", "event": event}


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
    _mock_gemini_response(monkeypatch, _event_payload(
        "restricted_area_entry", 0.95,
        "A person stands inside a red-marked restricted zone with hazard stripes.",
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "restricted_area_entry"
    assert result.confidence == 0.95


def test_no_visible_evidence_is_downgraded_to_normal_activity(monkeypatch):
    """Reproduces the reported bug at the code level: the model picks a
    safety event but itself admits there's no clear visual evidence for
    it -- this must never reach the rest of the pipeline as a real event."""
    _mock_gemini_response(monkeypatch, _event_payload(
        "restricted_area_entry", 0.9,
        "A person is sitting in a chair in an ordinary room; no signage or barrier is visible.",
        evidence_visible=False,
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


def test_low_confidence_is_downgraded_even_if_evidence_flag_is_true(monkeypatch):
    """A backstop independent of the evidence flag: weak confidence in a
    non-normal classification is never trusted, in case the model marks
    evidence_visible=true too liberally."""
    _mock_gemini_response(monkeypatch, _event_payload(
        "ppe_violation", 0.4, "Possibly missing a hard hat, hard to tell from this angle.",
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


def test_normal_activity_is_never_downgraded_or_altered(monkeypatch):
    _mock_gemini_response(monkeypatch, _event_payload(
        "normal_activity", 0.98, "Routine personnel movement with no anomaly.",
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"
    assert result.confidence == 0.98


def test_missing_evidence_visible_key_defaults_to_true_for_compatibility(monkeypatch):
    """Older/alternate model responses might omit the field entirely --
    should not crash, and should fall back to the confidence-only check."""
    _mock_gemini_response(monkeypatch, _event_payload(
        "forklift_near_miss", 0.9, "A forklift passes close to a worker in the loading dock.",
        evidence_visible=None,
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "forklift_near_miss"


def test_unrecognized_event_type_falls_back_to_normal_activity(monkeypatch):
    _mock_gemini_response(monkeypatch, _event_payload(
        "something_the_model_made_up", 0.9, "Unclear scene.",
    ))
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"


# --- mocked unit tests: object/scene recognition --------------------------


def test_objects_and_scene_are_parsed_for_a_normal_frame(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "objects": [
            {"name": "person", "confidence": 0.98, "context": "seated at a desk"},
            {"name": "laptop", "confidence": 0.97, "context": "on the desk"},
        ],
        "scene_description": "A person is seated at a desk using a laptop.",
        "event": {"type": "normal_activity", "confidence": 0.95, "context": "No anomaly.", "evidence_visible": True},
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"
    assert [o.name for o in result.objects] == ["person", "laptop"]
    assert result.objects[0].confidence == 0.98
    assert result.scene_description == "A person is seated at a desk using a laptop."


def test_restricted_area_sign_as_an_object_alone_stays_normal_activity(monkeypatch):
    """A sign can be listed as a recognized object without that alone
    triggering restricted_area_entry -- object recognition and safety
    detection are independent, exactly as required."""
    _mock_gemini_response(monkeypatch, {
        "objects": [
            {"name": "restricted area sign", "confidence": 0.96, "context": "mounted on the wall"},
        ],
        "scene_description": "A restricted-area warning sign is visible on the wall; no one is present.",
        "event": {
            "type": "normal_activity", "confidence": 0.97,
            "context": "Only a sign is visible; no person is present in or entering the area.",
            "evidence_visible": True,
        },
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"
    assert any(o.name == "restricted area sign" for o in result.objects)


def test_person_in_marked_zone_still_detected_alongside_objects(monkeypatch):
    """Objects and the safety event coexist correctly: the event can still
    be restricted_area_entry while objects are also reported."""
    _mock_gemini_response(monkeypatch, {
        "objects": [
            {"name": "person", "confidence": 0.98, "context": "standing near the marked area"},
            {"name": "restricted area sign", "confidence": 0.96, "context": "visible in the background"},
        ],
        "scene_description": "A person is standing near a restricted-area warning sign.",
        "event": {
            "type": "restricted_area_entry", "confidence": 0.95,
            "context": "The person is visibly inside the marked restricted zone.",
            "evidence_visible": True,
        },
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "restricted_area_entry"
    assert {o.name for o in result.objects} == {"person", "restricted area sign"}


def test_multiple_objects_are_all_returned_up_to_the_cap(monkeypatch):
    objects_payload = [{"name": f"object-{i}", "confidence": 0.8, "context": "visible"} for i in range(20)]
    _mock_gemini_response(monkeypatch, {
        "objects": objects_payload,
        "scene_description": "A cluttered scene with many items.",
        "event": {"type": "normal_activity", "confidence": 0.9, "context": "No anomaly.", "evidence_visible": True},
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    # The model was asked for at most 10-15; we defensively cap at 15
    # regardless of how many it actually returns.
    assert len(result.objects) == 15


def test_ambiguous_scene_yields_conservative_objects_and_normal_activity(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "objects": [{"name": "person", "confidence": 0.7, "context": "partially visible, backlit"}],
        "scene_description": "A dimly lit, partially obscured scene with a person barely visible.",
        "event": {
            "type": "normal_activity", "confidence": 0.9,
            "context": "The scene is too ambiguous to identify any specific safety concern.",
            "evidence_visible": True,
        },
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.type == "normal_activity"
    assert len(result.objects) == 1


def test_malformed_object_entries_are_skipped_not_fatal(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "objects": [
            {"name": "person", "confidence": 0.9, "context": "standing"},
            {"confidence": 0.5, "context": "missing a name entirely"},
            {"name": "", "confidence": 0.5, "context": "empty name"},
            "not even an object dict",
        ],
        "scene_description": "A person is standing.",
        "event": {"type": "normal_activity", "confidence": 0.9, "context": "No anomaly.", "evidence_visible": True},
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert [o.name for o in result.objects] == ["person"]


def test_missing_objects_key_defaults_to_empty_list(monkeypatch):
    _mock_gemini_response(monkeypatch, {
        "scene_description": "",
        "event": {"type": "normal_activity", "confidence": 0.9, "context": "No anomaly.", "evidence_visible": True},
    })
    result = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result.objects == []
    assert result.scene_description == ""


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


def _desk_with_laptop_image() -> bytes:
    """A person seated at a desk with a laptop -- a normal scene with
    multiple clearly identifiable everyday objects."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 480), color=(45, 45, 48))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 300, 640, 480], fill=(65, 65, 68))
    # desk
    draw.rectangle([150, 300, 500, 340], fill=(120, 90, 60))
    draw.rectangle([170, 340, 190, 420], fill=(90, 65, 45))
    draw.rectangle([460, 340, 480, 420], fill=(90, 65, 45))
    # laptop on the desk
    draw.rectangle([260, 250, 390, 300], fill=(30, 30, 32))
    draw.rectangle([270, 260, 380, 295], fill=(80, 140, 200))
    # person seated behind the desk
    draw.ellipse([290, 150, 330, 190], fill=(230, 200, 180))
    draw.rectangle([280, 190, 340, 260], fill=(70, 90, 140))
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


@pytest.mark.skipif(not _HAS_REAL_KEY, reason="requires a real GEMINI_API_KEY")
def test_real_gemini_recognizes_general_objects_in_a_normal_scene():
    """The one real-model test for the new general object recognition
    capability: a desk scene with a person and a laptop should come back
    as normal_activity while still reporting at least one real object."""
    result = vision.detect_event(_desk_with_laptop_image(), "image/jpeg")
    assert result.type == "normal_activity", (
        f"Expected normal_activity for a desk scene, got {result.type!r} (context={result.context!r})"
    )
    assert len(result.objects) >= 1, "Expected at least one recognized object for a desk-with-laptop scene"
    object_names = " ".join(o.name.lower() for o in result.objects)
    assert "person" in object_names or "laptop" in object_names, (
        f"Expected 'person' or 'laptop' among recognized objects, got: {[o.name for o in result.objects]}"
    )
    assert result.scene_description, "Expected a non-empty scene description"
