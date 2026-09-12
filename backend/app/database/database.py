"""SQLite persistence for incidents.

A thin wrapper around the standard-library `sqlite3` module -- no ORM.
Keeps schema, seed data, and queries in one place so the storage layer
can be swapped out (e.g. for Postgres) later without touching the
routes that call into it.
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.abspath(
    os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "edgepilot.db"))
)

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
    created_at TEXT NOT NULL
);
"""

# Mirrors src/data/mockData.ts so the API feels alive from the first run,
# before any real analysis has been submitted.
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

_INSERT_SQL = """
INSERT INTO incidents
    (id, event, risk, confidence, location, camera_id, edge_node,
     timestamp, date, explanation, recommendation, status, detection, context, created_at)
VALUES
    (:id, :event, :risk, :confidence, :location, :camera_id, :edge_node,
     :timestamp, :date, :explanation, :recommendation, :status, :detection, :context, :created_at)
"""


@contextmanager
def get_connection():
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
        count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc).isoformat()
            conn.executemany(_INSERT_SQL, [{**row, "created_at": now} for row in _SEED_INCIDENTS])


def _row_to_incident(row: sqlite3.Row) -> dict:
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


def list_incidents() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    return [_row_to_incident(r) for r in rows]


def get_incident(incident_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return _row_to_incident(row) if row else None


def update_incident_status(incident_id: str, status: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.execute("UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id))
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return _row_to_incident(row)


def insert_incident(
    *,
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
    }
    with get_connection() as conn:
        conn.execute(_INSERT_SQL, record)
    # _row_to_incident only ever indexes by column name, so the dict we
    # already built satisfies it without a round-trip read from the DB.
    return _row_to_incident(record)


def compute_dashboard_stats() -> dict:
    with get_connection() as conn:
        rows = conn.execute("SELECT risk, status, camera_id FROM incidents").fetchall()

    total = len(rows)
    high_risk = sum(1 for r in rows if r["risk"] == "HIGH")
    active_inputs = len({r["camera_id"] for r in rows}) or 1
    unresolved_high = sum(1 for r in rows if r["risk"] == "HIGH" and r["status"] in ("ACTIVE", "ESCALATED"))
    unresolved_medium = sum(1 for r in rows if r["risk"] == "MEDIUM" and r["status"] in ("ACTIVE", "ESCALATED"))
    system_health = max(90.0, min(100.0, round(100 - unresolved_high * 1.5 - unresolved_medium * 0.5, 1)))

    # NOTE: "change" is left at 0 until a stats-history table exists to
    # diff against -- better an honest flat trend than an invented one.
    return {
        "totalEvents": {"value": total, "change": 0},
        "highRisk": {"value": high_risk, "change": 0},
        "activeInputs": {"value": active_inputs, "change": 0},
        "systemHealth": {"value": system_health, "change": 0},
    }


def compute_analytics() -> dict:
    with get_connection() as conn:
        rows = conn.execute("SELECT event, risk, timestamp, camera_id FROM incidents").fetchall()

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

    edge_nodes_total = len({r["camera_id"] for r in rows}) or 1

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
