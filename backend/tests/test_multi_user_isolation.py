"""End-to-end (HTTP, via TestClient) tests for multi-user data isolation.

Covers the actual security property this whole feature exists for: two
different authenticated Supabase users must never see, modify, or infer
the existence of each other's incidents, stats, or analytics -- and an
unauthenticated caller must be rejected outright, never served a default
or empty-but-successful response.

The real Supabase Auth API is never called here: every test overrides
the `get_current_user_id` FastAPI dependency to a fixed fake user id
(see `as_user` below), the same technique FastAPI's own docs recommend
for testing auth-protected routes. The one test that checks
*unauthenticated* behavior deliberately does NOT override it, so the
real dependency runs and rejects the request on its own -- no network
call happens even then, since a missing Authorization header is rejected
before any call to Supabase.

Vision/Groq are mocked (see `_fake_detection`/`_no_llm`) so the two
incident-creation tests (live camera, uploaded analysis) are fast,
deterministic, and never depend on real Gemini/Groq output or quota --
only on whether the resulting incident is stamped with the right user_id.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from app.database import database as db
from app.main import app
from app.services import llm
from app.services import vision as vision_service
from app.services.auth import get_current_user_id
from app.services.vision import Detection

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"
NEW_USER = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated, seeded SQLite database + a TestClient against the real
    app. Seeding matters here: it's the direct check that legacy/demo
    rows (user_id IS NULL) never leak to any authenticated user."""
    db_path = tmp_path / "test_edgepilot.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)
    db.init_db()

    yield TestClient(app)

    app.dependency_overrides.pop(get_current_user_id, None)
    importlib.reload(db)


def as_user(user_id: str) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def unauthenticated() -> None:
    app.dependency_overrides.pop(get_current_user_id, None)


def _fake_detection() -> Detection:
    """A meaningful (non-normal_activity) event -- deterministic, so the
    dedup/incident-creation path is always exercised the same way,
    without depending on real Gemini output."""
    return Detection(
        type="restricted_area_entry",
        label="Restricted Area Entry",
        confidence=0.93,
        context="Zone A",
    )


@pytest.fixture(autouse=True)
def _mock_ai_pipeline(monkeypatch):
    """Applies to every test in this file, even ones that never call
    /api/analyze or /api/analyze-frame -- harmless when unused, and means
    no test here can ever make a real Gemini/Groq call by accident."""
    monkeypatch.setattr(vision_service, "detect_event", lambda *a, **kw: _fake_detection())
    # None forces the local template-reasoning fallback (reasoning.py +
    # recommendations.py) -- pure local logic, no network, deterministic.
    monkeypatch.setattr(llm, "generate_reasoning", lambda *a, **kw: None)


def _create_incident_for(client: TestClient, user_id: str, event: str = "Restricted Area Entry") -> dict:
    as_user(user_id)
    response = client.post(
        "/api/analyze",
        files={"file": ("frame.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- 1 & 2: basic ownership -------------------------------------------


def test_user_a_can_see_user_a_incidents(client):
    _create_incident_for(client, USER_A)

    as_user(USER_A)
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_user_b_cannot_see_user_a_incidents(client):
    _create_incident_for(client, USER_A)

    as_user(USER_B)
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == []


# --- 3: fresh user -------------------------------------------------------


def test_new_user_with_no_incidents_gets_an_empty_list(client):
    as_user(NEW_USER)
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == []


def test_legacy_seed_incidents_never_appear_for_any_user(client):
    # The seeded demo incidents (user_id IS NULL) must be invisible to
    # every real account, not just a brand-new one.
    for user_id in (USER_A, USER_B, NEW_USER):
        as_user(user_id)
        response = client.get("/api/incidents")
        assert response.json() == []


# --- 4: dashboard stats ---------------------------------------------------


def test_dashboard_stats_are_user_specific(client):
    _create_incident_for(client, USER_A)
    _create_incident_for(client, USER_A)
    _create_incident_for(client, USER_A)

    as_user(USER_A)
    stats_a = client.get("/api/dashboard/stats").json()

    as_user(NEW_USER)
    stats_b = client.get("/api/dashboard/stats").json()

    assert stats_a["totalEvents"]["value"] == 3
    assert stats_b["totalEvents"]["value"] == 0
    assert stats_b["highRisk"]["value"] == 0
    assert stats_b["activeInputs"]["value"] == 0


# --- 5: analytics/insights ------------------------------------------------


def test_analytics_insights_are_user_specific(client):
    _create_incident_for(client, USER_A)

    as_user(USER_A)
    insights_a = client.get("/api/insights").json()

    as_user(NEW_USER)
    insights_b = client.get("/api/insights").json()

    assert len(insights_a["eventCategories"]) == 1
    assert insights_b["eventCategories"] == []
    assert insights_b["systemHealth"]["edgeNodesTotal"] == 0


# --- 6: cannot update another user's incident ----------------------------


def test_user_a_cannot_acknowledge_user_bs_incident(client):
    incident_b = _create_incident_for(client, USER_B)

    as_user(USER_A)
    response = client.post(f"/api/incidents/{incident_b['id']}/acknowledge")

    assert response.status_code == 404

    # And it must remain untouched from User B's own point of view.
    as_user(USER_B)
    still_active = client.get(f"/api/incidents/{incident_b['id']}").json()
    assert still_active["status"] == "ACTIVE"


def test_user_a_cannot_escalate_user_bs_incident(client):
    incident_b = _create_incident_for(client, USER_B)

    as_user(USER_A)
    response = client.post(f"/api/incidents/{incident_b['id']}/escalate")

    assert response.status_code == 404


# --- 7: cannot retrieve another user's incident by id ---------------------


def test_user_a_cannot_retrieve_user_bs_incident_by_id(client):
    incident_b = _create_incident_for(client, USER_B)

    as_user(USER_A)
    response = client.get(f"/api/incidents/{incident_b['id']}")

    assert response.status_code == 404
    # Never leaks the other user's data in the error body either.
    assert incident_b["event"]["label"] not in response.text


# --- 8: live camera incidents are stamped with the real caller -----------


def test_live_created_incident_uses_the_authenticated_users_id(client):
    as_user(USER_A)
    response = client.post(
        "/api/analyze-frame",
        files={"file": ("frame.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"camera_id": "CAM-TEST-LIVE"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["incidentCreated"] is True

    # Only User A can see it -- proves it was actually persisted with
    # user_id=USER_A, not a global/default id.
    as_user(USER_A)
    assert client.get(f"/api/incidents/{body['incidentId']}").status_code == 200

    as_user(USER_B)
    assert client.get(f"/api/incidents/{body['incidentId']}").status_code == 404


# --- 9: uploaded-analysis incidents are stamped with the real caller -----


def test_uploaded_analysis_incident_uses_the_authenticated_users_id(client):
    incident = _create_incident_for(client, USER_A)

    as_user(USER_A)
    assert client.get(f"/api/incidents/{incident['id']}").status_code == 200

    as_user(USER_B)
    assert client.get(f"/api/incidents/{incident['id']}").status_code == 404


# --- 10: unauthenticated requests are rejected ----------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/incidents"),
        ("GET", "/api/incidents/INC-000001"),
        ("POST", "/api/incidents/INC-000001/acknowledge"),
        ("POST", "/api/incidents/INC-000001/escalate"),
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/insights"),
    ],
)
def test_unauthenticated_requests_are_rejected(client, method, path):
    unauthenticated()
    response = client.request(method, path)
    assert response.status_code == 401


def test_unauthenticated_analyze_upload_is_rejected(client):
    unauthenticated()
    response = client.post(
        "/api/analyze",
        files={"file": ("frame.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 401


def test_unauthenticated_analyze_frame_is_rejected(client):
    unauthenticated()
    response = client.post(
        "/api/analyze-frame",
        files={"file": ("frame.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 401
