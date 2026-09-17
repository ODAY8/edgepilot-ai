"""Backend verification of Supabase access tokens.

The frontend already authenticates against Supabase (see
src/context/AuthContext.tsx) and sends the resulting access token on
every API request as `Authorization: Bearer <token>` (see
src/services/api.ts). This module is the backend half of that: it never
trusts a user id the client claims to be -- every user-scoped route
depends on `get_current_user_id`, which asks Supabase's own Auth API to
validate the token and tells us who it actually belongs to. There is no
`?user_id=...` query parameter anywhere; the user id always comes from a
verified token.

Verification is done by calling Supabase's `GET /auth/v1/user` endpoint
rather than decoding the JWT locally. This is deliberately
algorithm-agnostic (works whether the project signs tokens with a shared
HS256 secret or an asymmetric key) and requires no additional secret
beyond the same project URL and anon/publishable key the frontend already
uses -- both safe to expose, never a service_role key. The tradeoff is
one extra network round trip to Supabase per authenticated request; if
that ever matters at a scale beyond this project, switching to local JWT
verification via SUPABASE_JWT_SECRET (see Supabase's own docs) is the
documented next step.

Never logs the access token itself, or any other credential.
"""

import os

import httpx
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

_SESSION_EXPIRED_DETAIL = "Your session has expired or is invalid. Please sign in again."


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


class AuthError(Exception):
    """Raised for any bearer token that doesn't verify -- missing config,
    unreachable auth service, expired/invalid/malformed token."""


def _verify_token(token: str) -> str:
    """Returns the verified caller's Supabase user id, or raises AuthError."""
    if not is_configured():
        raise AuthError(
            "Backend authentication is not configured -- set SUPABASE_URL and SUPABASE_ANON_KEY."
        )
    try:
        response = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
            timeout=10.0,
        )
    except httpx.TransportError as exc:
        raise AuthError("Could not reach the authentication service.") from exc

    if response.status_code != 200:
        raise AuthError(_SESSION_EXPIRED_DETAIL)

    user_id = response.json().get("id")
    if not user_id:
        raise AuthError(_SESSION_EXPIRED_DETAIL)
    return user_id


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency -- every user-scoped route takes this as a
    parameter. A plain (sync) function so FastAPI runs it in the same
    threadpool a sync route handler would use, rather than blocking the
    event loop with the network call inside _verify_token.

    Raises 401 for a missing/malformed header or a token that doesn't
    verify -- never falls back to a default/global user id.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization[len("bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    try:
        return _verify_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
