"""In-memory cooldown tracker for live-camera frame analysis.

Prevents the same event type on the same camera from creating a new
incident every 3-5 seconds while it's still ongoing. Intentionally
simple -- a process-memory dict, not persisted or shared across
workers -- which is sufficient for a single-process hackathon
deployment. A multi-worker production deployment would move this to
Redis or a database table keyed the same way.

Keyed by (user_id, camera_id, event_type) -- not just (camera_id,
event_type). Camera ids are client-supplied and default to the same
"CAM-01" for everyone (see routes/live.py), so without the user_id two
different users' browsers would share one cooldown: a genuinely new
event for User B could get silently suppressed just because User A
recently triggered the same event type on their own (identically-named)
default camera.
"""

import os
import time

_COOLDOWN_SECONDS = float(os.getenv("LIVE_EVENT_COOLDOWN_SECONDS", "60"))

_last_incident_at: dict[tuple[str, str, str], float] = {}


def should_create_incident(user_id: str, camera_id: str, event_type: str) -> bool:
    """True if this (user, camera, event type) triple hasn't created an
    incident within the cooldown window."""
    last = _last_incident_at.get((user_id, camera_id, event_type))
    return last is None or (time.monotonic() - last) >= _COOLDOWN_SECONDS


def mark_incident_created(user_id: str, camera_id: str, event_type: str) -> None:
    _last_incident_at[(user_id, camera_id, event_type)] = time.monotonic()
