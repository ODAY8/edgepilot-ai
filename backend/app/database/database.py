"""SQLite/PostgreSQL persistence for incidents.

A thin wrapper -- no ORM -- around either the standard-library `sqlite3`
module or `psycopg` (PostgreSQL/Supabase), selected once at import time:

    DATABASE_URL set      -> PostgreSQL (e.g. a Supabase connection string)
    DATABASE_URL not set  -> SQLite at DATABASE_PATH (unchanged default)

Every public function below (`init_db`, `list_incidents`, `get_incident`,
`update_incident_status`, `insert_incident`, `compute_dashboard_stats`,
`compute_analytics`) keeps its exact existing signature and return shape
regardless of which backend is active -- callers in `app/routes/*.py`
never know or care which database is behind them. `get_connection()` is
the one seam that actually differs per backend; every query function
above it is backend-agnostic because:

  - SQLite's `sqlite3.Row` and PostgreSQL's `dict_row` factory both
    support `row["column_name"]` access, so `_row_to_incident()` never
    branches.
  - Both `sqlite3.Connection.execute()` and `psycopg.Connection.execute()`
    accept a query string plus a dict (named placeholders) or tuple
    (positional placeholders) and return a cursor with the same
    `fetchone()`/`fetchall()`/`rowcount` surface -- only the placeholder
    *syntax* differs (`:name`/`?` for SQLite vs `%(name)s`/`%s` for
    PostgreSQL), so only the SQL strings themselves are picked per
    backend, once, at module load.

Multi-user isolation: every incident-scoped function above now also
takes a `user_id` -- the verified id from app/services/auth.py, never a
value supplied by the client -- and every query filters or scopes by it,
so one user's incidents, stats, and analytics are never visible to
another. Rows created before multi-user isolation existed (the SQLite
seed data, and any pre-existing Supabase rows) have `user_id IS NULL`; a
`NULL` never matches any real user's id in a `WHERE user_id = ...`
comparison (true in both SQLite and PostgreSQL), so those legacy rows
are automatically invisible to every authenticated user without being
deleted. See scripts/assign_legacy_incidents_to_user.py for the explicit,
opt-in way to hand them to one chosen account (e.g. a demo login).
"""

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DB_PATH = os.path.abspath(
    os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "edgepilot.db"))
)

# Read once at import time, exactly like GEMINI_API_KEY/GROQ_API_KEY in
# services/vision.py and services/llm.py. Never logged or printed --
# only whether it's set is ever surfaced (see backend_name() below).
DATABASE_URL = os.getenv("DATABASE_URL")
_USE_POSTGRES = bool(DATABASE_URL)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    event TEXT NOT NULL,
    risk TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    location TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    edge_node TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    date TEXT NOT NULL,
    explanation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    status TEXT NOT NULL,
    detection TEXT NOT NULL,
    context TEXT NOT NULL,
    created_at TEXT NOT NULL,
    user_id TEXT
);
"""

# Nullable and with no default: a row with user_id = NULL means "created
# before multi-user isolation existed" (or, in principle, an
# unauthenticated write, which the API no longer allows). It is never
# NOT NULL because every pre-existing row must remain exactly as it was
# -- this column is additive, not a rewrite of history.


def _ensure_user_id_column(conn) -> None:
    """Adds the `user_id` column to an EXISTING incidents table that
    predates multi-user isolation, without touching any other column or
    any existing row's data. A brand-new table already has the column
    from _SCHEMA above, so this is a no-op for it. Safe to call on every
    startup -- idempotent for both backends."""
    if _USE_POSTGRES:
        conn.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS user_id TEXT")
    else:
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}
        if "user_id" not in existing_columns:
            conn.execute("ALTER TABLE incidents ADD COLUMN user_id TEXT")


# Mirrors src/data/mockData.ts so the API feels alive from the first run,
# before any real analysis has been submitted. Only ever seeded into a
# fresh local SQLite fallback -- never auto-copied into PostgreSQL (a
# real database is never silently populated with demo rows; see
# init_db() below).
_SEED_INCIDENTS: list[dict] = [
    dict(
        id="INC-001", event="Restricted Area Entry", risk="HIGH", confidence=94,
        location="Zone A — Assembly Line", camera_id="CAM-01", edge_node="EDGE NODE 01",
        timestamp="14:32:18", date="2026-09-09",
        explanation="A worker entered the predefined restricted zone near industrial equipment without visible protective clearance.",
        recommendation="Notify the safety officer and verify the restricted area before resuming operations.",
        status="ACTIVE", detection="Person detected", context="Restricted zone",
    ),
    dict(
        id="INC-002", event="Unattended Object", risk="MEDIUM", confidence=81,
        location="Zone C — Loading Dock", camera_id="CAM-04", edge_node="EDGE NODE 02",
        timestamp="14:28:42", date="2026-09-09",
        explanation="An object was left stationary near the loading dock walkway for over 45 seconds.",
        recommendation="Dispatch floor staff to inspect and clear the walkway.",
        status="ACTIVE", detection="Static object", context="Walkway obstruction",
    ),
    dict(
        id="INC-003", event="Normal Activity", risk="LOW", confidence=99,
        location="Zone B — Packaging", camera_id="CAM-02", edge_node="EDGE NODE 01",
        timestamp="14:21:07", date="2026-09-09",
        explanation="Routine personnel movement with no anomaly detected.",
        recommendation="No action required.",
        status="RESOLVED", detection="Person detected", context="Authorized zone",
    ),
    dict(
        id="INC-004", event="PPE Violation", risk="MEDIUM", confidence=87,
        location="Zone A — Assembly Line", camera_id="CAM-01", edge_node="EDGE NODE 01",
        timestamp="13:58:51", date="2026-09-09",
        explanation="Worker detected without required hard hat near active machinery.",
        recommendation="Alert floor supervisor to enforce PPE compliance.",
        status="ACKNOWLEDGED", detection="PPE gap", context="Active machinery zone",
    ),
    dict(
        id="INC-005", event="Forklift Near-Miss", risk="HIGH", confidence=91,
        location="Zone C — Loading Dock", camera_id="CAM-04", edge_node="EDGE NODE 02",
        timestamp="13:44:12", date="2026-09-09",
        explanation="Forklift path intersected with pedestrian walkway at unsafe speed.",
        recommendation="Escalate to site manager and review dock traffic patterns.",
        status="ESCALATED", detection="Vehicle + person overlap", context="Loading dock corridor",
    ),
    dict(
        id="INC-006", event="Smoke / Haze Detected", risk="HIGH", confidence=76,
        location="Zone D — Warehouse Storage", camera_id="CAM-06", edge_node="EDGE NODE 03",
        timestamp="12:57:33", date="2026-09-09",
        explanation="Visual haze consistent with smoke detected near storage racking.",
        recommendation="Verify with on-site sensors and notify fire safety team immediately.",
        status="RESOLVED", detection="Haze pattern", context="Storage racking",
    ),
    dict(
        id="INC-007", event="Unauthorized Access", risk="MEDIUM", confidence=83,
        location="Zone E — Server Room", camera_id="CAM-08", edge_node="EDGE NODE 03",
        timestamp="11:32:05", date="2026-09-09",
        explanation="Badge-less entry attempt detected at the server room access point.",
        recommendation="Verify access logs and confirm identity with security desk.",
        status="RESOLVED", detection="Person detected", context="Restricted access point",
    ),
    dict(
        id="INC-008", event="Normal Activity", risk="LOW", confidence=97,
        location="Zone B — Packaging", camera_id="CAM-02", edge_node="EDGE NODE 01",
        timestamp="10:15:44", date="2026-09-09",
        explanation="Shift changeover with expected personnel flow.",
        recommendation="No action required.",
        status="RESOLVED", detection="Person detected", context="Authorized zone",
    ),
]

_INSERT_SQL_SQLITE = """
INSERT INTO incidents
    (id, event, risk, confidence, location, camera_id, edge_node,
     timestamp, date, explanation, recommendation, status, detection, context, created_at, user_id)
VALUES
    (:id, :event, :risk, :confidence, :location, :camera_id, :edge_node,
     :timestamp, :date, :explanation, :recommendation, :status, :detection, :context, :created_at, :user_id)
"""

_INSERT_SQL_POSTGRES = """
INSERT INTO incidents
    (id, event, risk, confidence, location, camera_id, edge_node,
     timestamp, date, explanation, recommendation, status, detection, context, created_at, user_id)
VALUES
    (%(id)s, %(event)s, %(risk)s, %(confidence)s, %(location)s, %(camera_id)s, %(edge_node)s,
     %(timestamp)s, %(date)s, %(explanation)s, %(recommendation)s, %(status)s, %(detection)s, %(context)s, %(created_at)s, %(user_id)s)
"""

# Both variants take a dict of named params either way -- callers below
# never need to know which one is active.
_INSERT_SQL = _INSERT_SQL_POSTGRES if _USE_POSTGRES else _INSERT_SQL_SQLITE
# Scoped by user_id, not just id: a row that exists but belongs to a
# different user must be indistinguishable from a row that doesn't exist
# at all -- both come back as no row found, which routes turn into a 404,
# never another user's data.
_SELECT_BY_ID_SQL = (
    "SELECT * FROM incidents WHERE id = %s AND user_id = %s"
    if _USE_POSTGRES
    else "SELECT * FROM incidents WHERE id = ? AND user_id = ?"
)
_UPDATE_STATUS_SQL = (
    "UPDATE incidents SET status = %s WHERE id = %s AND user_id = %s"
    if _USE_POSTGRES
    else "UPDATE incidents SET status = ? WHERE id = ? AND user_id = ?"
)

# The pool is created once, during FastAPI's lifespan startup (see
# init_pool()/close_pool() and app/main.py), and reused for every
# request -- never opened per-call. None until init_pool() runs, and
# only ever used when _USE_POSTGRES is True.
_pool: ConnectionPool | None = None


def is_using_postgres() -> bool:
    return _USE_POSTGRES


def backend_name() -> str:
    """Safe for logging -- never includes DATABASE_URL or any credential."""
    return "PostgreSQL" if _USE_POSTGRES else "SQLite"


def init_pool() -> None:
    """Opens the PostgreSQL connection pool. Called once from the FastAPI
    lifespan on startup; a no-op when DATABASE_URL isn't set (SQLite needs
    no pool -- each call already opens/closes its own lightweight
    local-file connection, as it always has).

    Deliberately opens eagerly (`open=False` then an explicit `.open()`)
    and lets a failed connection raise here, at startup, rather than on
    the first request -- a misconfigured DATABASE_URL should fail loudly
    and immediately, the same way a missing GEMINI_API_KEY does.

    min_size=2 (not 1): the dashboard always requests stats and incidents
    concurrently (see src/pages/Dashboard.tsx's Promise.all). With only
    one warm connection, the second of those two concurrent requests had
    to open a brand-new connection on demand -- a full TCP+TLS+auth round
    trip to Supabase -- on every single dashboard load. Keeping 2
    connections warm means both requests can reuse an already-authenticated
    connection from the pool instead of paying that handshake cost.
    """
    global _pool
    if not _USE_POSTGRES or _pool is not None:
        return
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=2, max_size=5, open=False)
    _pool.open(wait=True, timeout=10)


def close_pool() -> None:
    """Closes the PostgreSQL connection pool. Called once from the
    FastAPI lifespan on shutdown; a no-op for SQLite or if never opened."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_connection():
    if _USE_POSTGRES:
        if _pool is None:
            raise RuntimeError("PostgreSQL pool is not initialized -- call init_pool() during app startup first.")
        with _pool.connection() as conn:
            conn.row_factory = dict_row
            yield conn
        # psycopg_pool's connection() context manager already commits on
        # clean exit / rolls back on exception (see its docstring) and
        # returns the connection to the pool -- nothing more to do here.
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(_SCHEMA)
        _ensure_user_id_column(conn)

        if _USE_POSTGRES:
            # Confirm the database can actually initialize correctly
            # first; demo/seed rows are only ever written into a fresh
            # local SQLite fallback, never auto-copied into a real
            # database. Migrating real historical data (if ever wanted)
            # is a deliberate, separate, explicit step -- not this one.
            return

        count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc).isoformat()
            # user_id=None (not any particular account) -- demo/seed data
            # is legacy by construction and stays invisible to every real
            # user, exactly like a pre-existing Supabase row (see
            # _ensure_user_id_column above).
            conn.executemany(_INSERT_SQL, [{**row, "created_at": now, "user_id": None} for row in _SEED_INCIDENTS])


def _row_to_incident(row) -> dict:
    return {
        "id": row["id"],
        "event": row["event"],
        "risk": row["risk"],
        "confidence": row["confidence"],
        "location": row["location"],
        "cameraId": row["camera_id"],
        "edgeNode": row["edge_node"],
        "timestamp": row["timestamp"],
        "date": row["date"],
        "explanation": row["explanation"],
        "recommendation": row["recommendation"],
        "status": row["status"],
        "detection": row["detection"],
        "context": row["context"],
    }


def list_incidents(user_id: str, limit: int | None = None) -> list[dict]:
    """Only ever returns incidents owned by `user_id` -- the verified id
    from app/services/auth.py, never a client-supplied value. A legacy
    row with user_id IS NULL can never match a real user_id, so it's
    naturally excluded here without any extra logic.

    `limit=None` (the default) returns full history, unchanged --
    required by the Incidents page, which computes its own summary counts
    and filters across every incident, not just a recent slice. Callers
    that only ever display a handful of recent incidents (the dashboard)
    can pass a small limit to avoid transferring rows they'll never show."""
    query = "SELECT * FROM incidents WHERE user_id = %s ORDER BY created_at DESC" if _USE_POSTGRES else \
        "SELECT * FROM incidents WHERE user_id = ? ORDER BY created_at DESC"
    params: tuple = (user_id,)
    if limit is not None:
        query += " LIMIT %s" if _USE_POSTGRES else " LIMIT ?"
        params = (user_id, limit)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_incident(r) for r in rows]


def get_incident(incident_id: str, user_id: str) -> dict | None:
    """Returns None both when the incident doesn't exist AND when it
    belongs to a different user -- the two cases are indistinguishable on
    purpose, so a route can never leak "that id exists, just not yours"
    to the caller."""
    with get_connection() as conn:
        row = conn.execute(_SELECT_BY_ID_SQL, (incident_id, user_id)).fetchone()
    return _row_to_incident(row) if row else None


def update_incident_status(incident_id: str, status: str, user_id: str) -> dict | None:
    """None if the incident doesn't exist OR belongs to another user --
    the UPDATE's own WHERE clause already prevents it from ever touching
    another user's row; the rowcount check just reports that back."""
    with get_connection() as conn:
        cur = conn.execute(_UPDATE_STATUS_SQL, (status, incident_id, user_id))
        if cur.rowcount == 0:
            return None
        row = conn.execute(_SELECT_BY_ID_SQL, (incident_id, user_id)).fetchone()
    _invalidate_stats_cache(user_id)
    return _row_to_incident(row)


def insert_incident(
    *,
    user_id: str,
    event: str,
    risk: str,
    confidence: int,
    explanation: str,
    recommendation: str,
    detection: str,
    context: str,
    location: str | None = None,
    camera_id: str | None = None,
    edge_node: str | None = None,
) -> dict:
    """`user_id` is required, with no default -- every incident is always
    created for a specific, verified, authenticated user. There is no
    global/fallback user id here on purpose: a caller that hasn't
    verified who's asking has no business creating an incident at all."""
    now = datetime.now(timezone.utc)
    record = {
        "id": f"INC-{uuid.uuid4().hex[:6].upper()}",
        "event": event,
        "risk": risk,
        "confidence": confidence,
        "location": location or "Unspecified Zone",
        "camera_id": camera_id or "CAM-01",
        "edge_node": edge_node or "EDGE NODE 01",
        "timestamp": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "explanation": explanation,
        "recommendation": recommendation,
        "status": "ACTIVE",
        "detection": detection,
        "context": context,
        "created_at": now.isoformat(),
        "user_id": user_id,
    }
    with get_connection() as conn:
        conn.execute(_INSERT_SQL, record)
    # _row_to_incident only ever indexes by column name, so the dict we
    # already built satisfies it without a round-trip read from the DB.
    _invalidate_stats_cache(user_id)
    return _row_to_incident(record)


# compute_dashboard_stats() is a non-critical aggregate (counts/percentages
# for the stat cards) -- NOT the incident list itself, which is never
# cached anywhere and always reflects the database immediately. Caching
# this aggregate for a few seconds means repeat dashboard loads (e.g.
# navigating back to /dashboard) within the window are served from memory
# instead of paying a round trip to Supabase, without ever risking a
# hidden incident: a new/updated incident invalidates the cache
# immediately (see insert_incident/update_incident_status above), so the
# very next stats fetch after any incident change is always fresh.
#
# Keyed by user_id -- a single shared cache entry would leak one user's
# stats to the next user who happens to load the dashboard within the
# same 5-second window, which is exactly the bug this whole change exists
# to fix. Each user gets their own independent cache slot instead.
_STATS_CACHE_TTL_SECONDS = 5.0
_stats_cache: dict[str, dict] = {}
_stats_cache_at: dict[str, float] = {}


def _invalidate_stats_cache(user_id: str) -> None:
    _stats_cache.pop(user_id, None)
    _stats_cache_at.pop(user_id, None)


def compute_dashboard_stats(user_id: str) -> dict:
    now = time.monotonic()
    cached_at = _stats_cache_at.get(user_id)
    if cached_at is not None and (now - cached_at) < _STATS_CACHE_TTL_SECONDS:
        return _stats_cache[user_id]

    query = (
        "SELECT risk, status, camera_id FROM incidents WHERE user_id = %s"
        if _USE_POSTGRES
        else "SELECT risk, status, camera_id FROM incidents WHERE user_id = ?"
    )
    with get_connection() as conn:
        rows = conn.execute(query, (user_id,)).fetchall()

    total = len(rows)
    high_risk = sum(1 for r in rows if r["risk"] == "HIGH")
    # No `or 1` floor: a user with zero incidents genuinely has zero
    # observed active inputs -- flooring this to 1 would show a fabricated
    # non-zero value on an otherwise all-zero fresh-user dashboard.
    active_inputs = len({r["camera_id"] for r in rows})
    unresolved_high = sum(1 for r in rows if r["risk"] == "HIGH" and r["status"] in ("ACTIVE", "ESCALATED"))
    unresolved_medium = sum(1 for r in rows if r["risk"] == "MEDIUM" and r["status"] in ("ACTIVE", "ESCALATED"))
    system_health = max(90.0, min(100.0, round(100 - unresolved_high * 1.5 - unresolved_medium * 0.5, 1)))

    # NOTE: "change" is left at 0 until a stats-history table exists to
    # diff against -- better an honest flat trend than an invented one.
    result = {
        "totalEvents": {"value": total, "change": 0},
        "highRisk": {"value": high_risk, "change": 0},
        "activeInputs": {"value": active_inputs, "change": 0},
        "systemHealth": {"value": system_health, "change": 0},
    }
    _stats_cache[user_id] = result
    _stats_cache_at[user_id] = now
    return result


def compute_analytics(user_id: str) -> dict:
    query = (
        "SELECT event, risk, timestamp, camera_id FROM incidents WHERE user_id = %s"
        if _USE_POSTGRES
        else "SELECT event, risk, timestamp, camera_id FROM incidents WHERE user_id = ?"
    )
    with get_connection() as conn:
        rows = conn.execute(query, (user_id,)).fetchall()

    hour_counts: dict[str, int] = {}
    for r in rows:
        hour = f"{r['timestamp'].split(':')[0]}:00"
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    events_over_time = [{"time": h, "events": c} for h, c in sorted(hour_counts.items())]

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for r in rows:
        risk_counts[r["risk"]] = risk_counts.get(r["risk"], 0) + 1
    risk_distribution = [{"name": k, "value": v} for k, v in risk_counts.items()]

    category_counts: dict[str, int] = {}
    for r in rows:
        category_counts[r["event"]] = category_counts.get(r["event"], 0) + 1
    event_categories = sorted(
        ({"name": k, "value": v} for k, v in category_counts.items()),
        key=lambda item: item["value"],
        reverse=True,
    )[:5]

    # Same reasoning as active_inputs in compute_dashboard_stats above --
    # no `or 1` floor, so a user with no incidents sees genuine zeros.
    edge_nodes_total = len({r["camera_id"] for r in rows})

    return {
        "eventsOverTime": events_over_time,
        "riskDistribution": risk_distribution,
        "eventCategories": event_categories,
        # Uptime/response-time are static placeholders until real
        # infrastructure telemetry is wired in.
        "systemHealth": {
            "uptime": "99.98%",
            "avgResponseTime": "1.4s",
            "edgeNodesOnline": edge_nodes_total,
            "edgeNodesTotal": edge_nodes_total,
        },
    }
