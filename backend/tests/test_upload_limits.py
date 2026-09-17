"""Tests for the upload size limits added to /api/analyze and
/api/analyze-frame. Previously neither endpoint enforced any limit at
all, despite the frontend upload UI advertising "Up to 500MB" -- an
unbounded request body was read fully into memory. The real limits
(500MB / 10MB) are patched down to a few bytes here so the tests stay
fast and don't need to allocate huge buffers; the enforcement logic
being tested is identical regardless of the configured limit. These
tests don't require GEMINI_API_KEY -- the size check runs before any
vision call.

Both routes now also require authentication (see app/services/auth.py);
the auth dependency is overridden here to a fixed fake user so these
tests keep testing exactly one thing -- size enforcement -- independent
of the auth layer (which has its own tests in test_multi_user_isolation.py).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import analysis, live
from app.services.auth import get_current_user_id

client = TestClient(app)


@pytest.fixture(autouse=True)
def _authenticated():
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-upload-limits"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


def test_analyze_rejects_a_file_over_the_configured_limit(monkeypatch):
    monkeypatch.setattr(analysis, "_MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/analyze",
        files={"file": ("clip.mp4", b"x" * 11, "video/mp4")},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"].lower()


def test_analyze_accepts_a_file_at_or_under_the_configured_limit(monkeypatch):
    monkeypatch.setattr(analysis, "_MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/analyze",
        files={"file": ("photo.jpg", b"x" * 10, "image/jpeg")},
    )
    # Passes the size check; a tiny fake JPEG fails later in the real
    # pipeline (vision/frame decode), never with 413.
    assert response.status_code != 413


def test_analyze_frame_rejects_a_frame_over_the_configured_limit(monkeypatch):
    monkeypatch.setattr(live, "_MAX_FRAME_BYTES", 10)
    response = client.post(
        "/api/analyze-frame",
        files={"file": ("frame.jpg", b"x" * 11, "image/jpeg")},
    )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"].lower()


def test_analyze_frame_accepts_a_frame_at_or_under_the_configured_limit(monkeypatch):
    monkeypatch.setattr(live, "_MAX_FRAME_BYTES", 10)
    response = client.post(
        "/api/analyze-frame",
        files={"file": ("frame.jpg", b"x" * 10, "image/jpeg")},
    )
    assert response.status_code != 413
    assert response.status_code != 400


def test_analyze_rejects_an_unauthenticated_request_regardless_of_size(monkeypatch):
    # With no override in effect, the real get_current_user_id runs and
    # must reject a request with no Authorization header at all -- size
    # is irrelevant here, a tiny valid-looking file must still be rejected.
    app.dependency_overrides.pop(get_current_user_id, None)
    monkeypatch.setattr(analysis, "_MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/analyze",
        files={"file": ("photo.jpg", b"x" * 5, "image/jpeg")},
    )
    assert response.status_code == 401
