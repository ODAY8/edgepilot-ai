"""Tests for app/services/auth.py -- the backend's Supabase token
verification. Includes a regression test for the exact production
incident this file was added to diagnose: SUPABASE_URL/SUPABASE_ANON_KEY
missing on the deployed backend, which made every request fail with 401
regardless of whether the frontend sent a perfectly valid token.

httpx.get is monkeypatched in every test that reaches _verify_token, so
none of these ever make a real network call to Supabase.
"""

import importlib

import httpx
import pytest
from fastapi import HTTPException

from app.services import auth


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake-project.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
    importlib.reload(auth)
    yield auth
    importlib.reload(auth)


@pytest.fixture
def not_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    importlib.reload(auth)
    yield auth
    importlib.reload(auth)


class _FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


def test_is_configured_true_when_both_env_vars_are_set(configured):
    assert configured.is_configured() is True


def test_is_configured_false_when_env_vars_are_missing(not_configured):
    assert not_configured.is_configured() is False


def test_missing_authorization_header_is_rejected_without_any_network_call(not_configured, monkeypatch):
    # Must reject before ever touching Supabase -- a real request that
    # doesn't even try to authenticate shouldn't cost a network round trip.
    called = False

    def _unexpected_get(*a, **kw):
        nonlocal called
        called = True
        raise AssertionError("should never call Supabase when there's no Authorization header")

    monkeypatch.setattr(httpx, "get", _unexpected_get)

    with pytest.raises(HTTPException) as exc_info:
        not_configured.get_current_user_id(authorization=None)

    assert exc_info.value.status_code == 401
    assert called is False


@pytest.mark.parametrize("header", ["", "Token abc123", "Bearer", "Bearer   "])
def test_malformed_authorization_header_is_rejected(not_configured, header):
    with pytest.raises(HTTPException) as exc_info:
        not_configured.get_current_user_id(authorization=header)
    assert exc_info.value.status_code == 401


def test_a_present_token_is_rejected_with_a_clear_message_when_backend_is_not_configured(not_configured):
    """Regression test for the production incident this module exists to
    diagnose: the Render deployment never had SUPABASE_URL/SUPABASE_ANON_KEY
    set, so is_configured() was False and *every* request -- including
    ones with a perfectly valid frontend-supplied token -- was rejected.
    The 401 detail must say so clearly rather than looking identical to a
    genuinely bad/expired token, so this exact failure mode is
    diagnosable from the response alone next time."""
    with pytest.raises(HTTPException) as exc_info:
        not_configured.get_current_user_id(authorization="Bearer some-otherwise-perfectly-valid-token")

    assert exc_info.value.status_code == 401
    assert "not configured" in exc_info.value.detail.lower()
    assert "SUPABASE_URL" in exc_info.value.detail
    assert "SUPABASE_ANON_KEY" in exc_info.value.detail


def test_valid_token_returns_the_verified_user_id(configured, monkeypatch):
    def _fake_get(url, headers, timeout):
        assert url == "https://fake-project.supabase.co/auth/v1/user"
        assert headers["Authorization"] == "Bearer real-token"
        assert headers["apikey"] == "fake-anon-key"
        return _FakeResponse(200, {"id": "user-abc-123"})

    monkeypatch.setattr(httpx, "get", _fake_get)

    user_id = configured.get_current_user_id(authorization="Bearer real-token")

    assert user_id == "user-abc-123"


def test_token_rejected_by_supabase_is_rejected_here_too(configured, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(401, {"msg": "invalid JWT"}))

    with pytest.raises(HTTPException) as exc_info:
        configured.get_current_user_id(authorization="Bearer expired-or-bad-token")

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower() or "invalid" in exc_info.value.detail.lower()


def test_response_with_no_user_id_is_treated_as_invalid(configured, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, {}))

    with pytest.raises(HTTPException) as exc_info:
        configured.get_current_user_id(authorization="Bearer weird-token")

    assert exc_info.value.status_code == 401


def test_unreachable_supabase_is_a_401_not_a_500(configured, monkeypatch):
    def _raise_transport_error(*a, **kw):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(httpx, "get", _raise_transport_error)

    with pytest.raises(HTTPException) as exc_info:
        configured.get_current_user_id(authorization="Bearer some-token")

    # A network hiccup talking to Supabase must not be a 500 -- from the
    # caller's point of view it's simply "not authenticated right now".
    assert exc_info.value.status_code == 401


def test_bearer_prefix_is_case_insensitive(configured, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, {"id": "user-xyz"}))

    assert configured.get_current_user_id(authorization="bearer real-token") == "user-xyz"
    assert configured.get_current_user_id(authorization="BEARER real-token") == "user-xyz"
