"""Tests for Gemini 503/5xx resilience in the vision service: bounded
retry with backoff for a single call, and a circuit breaker that stops
hammering Gemini during a sustained outage and resumes automatically once
it recovers.

All of these are mocked -- no real Gemini call, no real delay (time.sleep
is patched to a no-op so retry/backoff logic is exercised without
actually waiting). The module-level circuit breaker state is reset before
and after every test so tests never leak state into each other.
"""

import json

import pytest
from google.genai import errors as genai_errors

from app.services import vision


class _FakeResponse:
    def __init__(self, payload: dict):
        self.text = json.dumps(payload)


class _FlakyModels:
    """Fails with the given exception for the first `fail_times` calls,
    then succeeds. Tracks exactly how many times it was actually called,
    so tests can assert retries/cooldowns happened -- or didn't."""

    def __init__(self, make_exc, fail_times: int, payload: dict | None = None):
        self.make_exc = make_exc
        self.fail_times = fail_times
        self.payload = payload or _normal_payload()
        self.call_count = 0

    def generate_content(self, **kwargs):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise self.make_exc()
        return _FakeResponse(self.payload)


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _normal_payload() -> dict:
    return {
        "objects": [],
        "scene_description": "An empty room.",
        "event": {"type": "normal_activity", "confidence": 0.95, "context": "Nothing notable.", "evidence_visible": True},
    }


def _server_error() -> genai_errors.ServerError:
    return genai_errors.ServerError(503, {"message": "high demand", "status": "UNAVAILABLE"})


def _client_error() -> genai_errors.ClientError:
    return genai_errors.ClientError(400, {"message": "bad request", "status": "INVALID_ARGUMENT"})


@pytest.fixture(autouse=True)
def _reset_circuit_breaker(monkeypatch):
    """The breaker is module-level state shared across every call --
    reset it before and after each test so no test starts mid-cooldown or
    leaves the next one starting mid-cooldown."""
    monkeypatch.setattr(vision, "_consecutive_failures", 0)
    monkeypatch.setattr(vision, "_cooldown_until", 0.0)
    # Never actually sleep during tests -- only that backoff was attempted
    # (via call counts) matters, not real wall-clock time.
    monkeypatch.setattr(vision.time, "sleep", lambda seconds: None)
    yield
    monkeypatch.setattr(vision, "_consecutive_failures", 0)
    monkeypatch.setattr(vision, "_cooldown_until", 0.0)


def _install(monkeypatch, models) -> _FlakyModels:
    monkeypatch.setattr(vision, "_client", _FakeClient(models))
    return models


def test_successful_frame_needs_no_retry(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=0))

    result = vision.detect_event(b"fake-bytes", "image/jpeg")

    assert result.type == "normal_activity"
    assert models.call_count == 1
    assert vision._consecutive_failures == 0


def test_temporary_503_then_success_retries_and_recovers(monkeypatch):
    # Fails twice, succeeds on the 3rd attempt -- within _MAX_RETRIES + 1.
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=2))

    result = vision.detect_event(b"fake-bytes", "image/jpeg")

    assert result.type == "normal_activity"
    assert models.call_count == 3
    # A call that ultimately succeeded must not count as a failure.
    assert vision._consecutive_failures == 0


def test_repeated_503_exhausts_bounded_retries_then_raises(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=999))

    with pytest.raises(vision.VisionUnavailableError):
        vision.detect_event(b"fake-bytes", "image/jpeg")

    # Exactly _MAX_RETRIES + 1 attempts -- bounded, never indefinite.
    assert models.call_count == vision._MAX_RETRIES + 1
    assert vision._consecutive_failures == 1


def test_non_retryable_error_is_never_retried(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_client_error, fail_times=999))

    with pytest.raises(vision.VisionUnavailableError):
        vision.detect_event(b"fake-bytes", "image/jpeg")

    # A 4xx fails once, immediately -- retrying a bad request can never
    # succeed, so it would only add latency.
    assert models.call_count == 1
    # And it doesn't count toward the breaker either -- a bad request
    # doesn't mean Gemini's service itself is degraded.
    assert vision._consecutive_failures == 0


def test_backend_enters_cooldown_after_repeated_full_failures(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=999))

    for _ in range(vision._CONSECUTIVE_FAILURES_BEFORE_COOLDOWN):
        with pytest.raises(vision.VisionUnavailableError):
            vision.detect_event(b"fake-bytes", "image/jpeg")

    assert vision._cooldown_until > vision.time.monotonic()

    calls_before = models.call_count
    with pytest.raises(vision.VisionUnavailableError, match="temporarily unavailable"):
        vision.detect_event(b"fake-bytes", "image/jpeg")

    # The whole point of the breaker: no real call was attempted at all.
    assert models.call_count == calls_before


def test_live_polling_does_not_hammer_gemini_during_cooldown(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=999))

    for _ in range(vision._CONSECUTIVE_FAILURES_BEFORE_COOLDOWN):
        with pytest.raises(vision.VisionUnavailableError):
            vision.detect_event(b"fake-bytes", "image/jpeg")
    calls_after_breaker_trips = models.call_count

    # Simulate several more 4-second camera poll ticks while Gemini is
    # still down -- none of them should reach the network at all.
    for _ in range(10):
        with pytest.raises(vision.VisionUnavailableError, match="temporarily unavailable"):
            vision.detect_event(b"fake-bytes", "image/jpeg")

    assert models.call_count == calls_after_breaker_trips


def test_backend_resumes_automatically_once_cooldown_expires_and_gemini_recovers(monkeypatch):
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=999))

    for _ in range(vision._CONSECUTIVE_FAILURES_BEFORE_COOLDOWN):
        with pytest.raises(vision.VisionUnavailableError):
            vision.detect_event(b"fake-bytes", "image/jpeg")
    assert vision._cooldown_until > vision.time.monotonic()

    # Cooldown window has elapsed, and Gemini has recovered.
    monkeypatch.setattr(vision, "_cooldown_until", vision.time.monotonic() - 1)
    models.fail_times = 0  # the next real attempt now succeeds

    result = vision.detect_event(b"fake-bytes", "image/jpeg")

    assert result.type == "normal_activity"
    assert vision._consecutive_failures == 0
    assert vision._cooldown_until == 0.0

    # And normal polling resumes -- no more fail-fast short-circuiting.
    result2 = vision.detect_event(b"fake-bytes", "image/jpeg")
    assert result2.type == "normal_activity"


def test_a_single_failure_does_not_trip_the_breaker(monkeypatch):
    # One bad frame during otherwise-normal operation must not degrade
    # the whole live feed -- only sustained, repeated failure should.
    models = _install(monkeypatch, _FlakyModels(_server_error, fail_times=999))

    with pytest.raises(vision.VisionUnavailableError):
        vision.detect_event(b"fake-bytes", "image/jpeg")

    assert vision._cooldown_until == 0.0
    assert vision._consecutive_failures == 1

    # A subsequent success clears it back to a clean state.
    models.fail_times = 0
    vision.detect_event(b"fake-bytes", "image/jpeg")
    assert vision._consecutive_failures == 0
