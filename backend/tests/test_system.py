"""Tests for the read-only /api/system/status endpoint used by the
frontend Settings page. Must never leak key values -- only whether each
provider is configured."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_system_status_returns_expected_shape():
    response = client.get("/api/system/status")
    assert response.status_code == 200

    data = response.json()
    assert set(data.keys()) == {"version", "visionEnabled", "reasoningEnabled"}
    assert isinstance(data["version"], str) and data["version"]
    assert isinstance(data["visionEnabled"], bool)
    assert isinstance(data["reasoningEnabled"], bool)


def test_system_status_never_leaks_key_material(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "super-secret-groq-key")

    response = client.get("/api/system/status")

    body_text = response.text
    assert "super-secret-gemini-key" not in body_text
    assert "super-secret-groq-key" not in body_text
