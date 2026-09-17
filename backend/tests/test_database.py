"""Tests for the SQLite/PostgreSQL dual-backend database layer.

The normal test suite must never touch a real Supabase/PostgreSQL
database (see conftest.py, which strips DATABASE_URL for the whole test
session) -- so every PostgreSQL-related test here mocks the psycopg
layer instead of opening a real network connection. The SQLite-backed
tests (insert/list/get/acknowledge/escalate/dashboard-stats/analytics)
exercise the real thing, since a local SQLite file is fast, free, and
requires no external dependency -- exactly the tradeoff the module
itself makes.

Every incident-scoped function now takes a user_id (see
app/database/database.py's module docstring for why) -- TEST_USER and
OTHER_USER below stand in for two different verified, authenticated
callers, the same way two real Supabase accounts would.
"""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

from app.database import database as db

TEST_USER = "test-user-1"
OTHER_USER = "test-user-2"


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """A fresh, empty (unseeded) SQLite-backed database at an isolated
    temp path -- never the real backend/edgepilot.db. Reloads the module
    so DB_PATH/_USE_POSTGRES are recomputed, and always reloads back to
    the environment's real state afterwards so later tests in the same
    session aren't affected."""
    db_path = tmp_path / "test_edgepilot.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)
    assert db.is_using_postgres() is False

    # Schema only -- deliberately skips init_db()'s seed-data insertion so
    # dashboard/analytics assertions below can use exact, known totals.
    with db.get_connection() as conn:
        conn.execute(db._SCHEMA)

    yield db

    importlib.reload(db)


@pytest.fixture
def postgres_selected(monkeypatch):
    """Selects the PostgreSQL branch with a fake connection string --
    never a real one, and init_pool() is never called in these tests, so
    no real network connection is ever attempted. Always reloads back to
    the environment's real state afterwards."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@fake-host:5432/fakedb")
    importlib.reload(db)
    assert db.is_using_postgres() is True

    yield db

    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)


def test_sqlite_is_the_default_backend_when_database_url_is_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)
    try:
        assert db.is_using_postgres() is False
        assert db.backend_name() == "SQLite"
    finally:
        importlib.reload(db)


def test_postgres_branch_is_selected_when_database_url_is_set(postgres_selected):
    assert postgres_selected.is_using_postgres() is True
    assert postgres_selected.backend_name() == "PostgreSQL"
    # Placeholder syntax must actually be PostgreSQL-flavored, not SQLite's.
    assert "%(id)s" in postgres_selected._INSERT_SQL
    assert ":id" not in postgres_selected._INSERT_SQL
    # Both scoped by user_id -- a row belonging to another user must never
    # be selectable or updatable by id alone.
    assert postgres_selected._SELECT_BY_ID_SQL == "SELECT * FROM incidents WHERE id = %s AND user_id = %s"
    assert postgres_selected._UPDATE_STATUS_SQL == "UPDATE incidents SET status = %s WHERE id = %s AND user_id = %s"


def test_get_connection_raises_clearly_if_pool_was_never_initialized(postgres_selected):
    # A misconfigured/never-started pool must fail loudly and specifically,
    # never silently fall back to SQLite or hang trying to connect.
    with pytest.raises(RuntimeError, match="init_pool"):
        postgres_selected.list_incidents(user_id=TEST_USER)


def test_init_pool_opens_a_pool_without_a_real_connection(postgres_selected):
    with patch("app.database.database.ConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool

        postgres_selected.init_pool()

        mock_pool_cls.assert_called_once()
        _, kwargs = mock_pool_cls.call_args
        assert kwargs["conninfo"] == os.environ["DATABASE_URL"]
        assert kwargs["open"] is False
        mock_pool.open.assert_called_once()

        postgres_selected.close_pool()
        mock_pool.close.assert_called_once()


def test_init_pool_is_a_no_op_for_sqlite(sqlite_db):
    # Must not raise, must not try to construct a ConnectionPool at all.
    with patch("app.database.database.ConnectionPool") as mock_pool_cls:
        sqlite_db.init_pool()
        mock_pool_cls.assert_not_called()
    sqlite_db.close_pool()


def test_insert_incident_persists_and_returns_the_expected_fields(sqlite_db):
    incident = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry",
        risk="HIGH",
        confidence=91,
        explanation="A person entered the marked zone.",
        recommendation="Notify the safety officer.",
        detection="Restricted Area Entry",
        context="Zone A",
        location="Zone A",
        camera_id="CAM-01",
    )

    assert incident["id"].startswith("INC-")
    assert incident["event"] == "Restricted Area Entry"
    assert incident["risk"] == "HIGH"
    assert incident["confidence"] == 91
    assert incident["cameraId"] == "CAM-01"
    assert incident["status"] == "ACTIVE"
    # user_id is an internal ownership column, never part of the API
    # response shape -- see _row_to_incident, which never includes it.
    assert "user_id" not in incident


def test_insert_incident_applies_defaults_for_optional_fields(sqlite_db):
    incident = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Normal Activity", risk="LOW", confidence=10,
        explanation="Nothing happened.", recommendation="No action required.",
        detection="Normal Activity", context="",
    )
    assert incident["location"] == "Unspecified Zone"
    assert incident["cameraId"] == "CAM-01"
    assert incident["edgeNode"] == "EDGE NODE 01"


def test_list_incidents_returns_newest_first(sqlite_db):
    first = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Normal Activity", risk="LOW", confidence=50,
        explanation="e", recommendation="r", detection="d", context="c",
    )
    second = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=60,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    incidents = sqlite_db.list_incidents(user_id=TEST_USER)

    assert [i["id"] for i in incidents] == [second["id"], first["id"]]


def test_list_incidents_only_returns_the_requesting_users_incidents(sqlite_db):
    mine = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=90,
        explanation="e", recommendation="r", detection="d", context="c",
    )
    sqlite_db.insert_incident(
        user_id=OTHER_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    mine_only = sqlite_db.list_incidents(user_id=TEST_USER)
    theirs_only = sqlite_db.list_incidents(user_id=OTHER_USER)

    assert [i["id"] for i in mine_only] == [mine["id"]]
    assert len(theirs_only) == 1
    assert theirs_only[0]["id"] != mine["id"]


def test_get_incident_returns_the_matching_record(sqlite_db):
    created = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Forklift Near-Miss", risk="HIGH", confidence=88,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    found = sqlite_db.get_incident(created["id"], user_id=TEST_USER)

    assert found is not None
    assert found["id"] == created["id"]
    assert found["event"] == "Forklift Near-Miss"


def test_get_incident_returns_none_for_an_unknown_id(sqlite_db):
    assert sqlite_db.get_incident("INC-DOESNOTEXIST", user_id=TEST_USER) is None


def test_get_incident_returns_none_for_another_users_incident(sqlite_db):
    created = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Forklift Near-Miss", risk="HIGH", confidence=88,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    # Same id, wrong user -- must be indistinguishable from "doesn't exist".
    assert sqlite_db.get_incident(created["id"], user_id=OTHER_USER) is None
    # And the real owner can still fetch it just fine.
    assert sqlite_db.get_incident(created["id"], user_id=TEST_USER) is not None


def test_acknowledge_sets_status_to_acknowledged(sqlite_db):
    created = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    updated = sqlite_db.update_incident_status(created["id"], "ACKNOWLEDGED", user_id=TEST_USER)

    assert updated["status"] == "ACKNOWLEDGED"
    assert sqlite_db.get_incident(created["id"], user_id=TEST_USER)["status"] == "ACKNOWLEDGED"


def test_escalate_sets_status_to_escalated(sqlite_db):
    created = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Forklift Near-Miss", risk="HIGH", confidence=90,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    updated = sqlite_db.update_incident_status(created["id"], "ESCALATED", user_id=TEST_USER)

    assert updated["status"] == "ESCALATED"
    assert sqlite_db.get_incident(created["id"], user_id=TEST_USER)["status"] == "ESCALATED"


def test_update_incident_status_returns_none_for_an_unknown_id(sqlite_db):
    assert sqlite_db.update_incident_status("INC-DOESNOTEXIST", "ACKNOWLEDGED", user_id=TEST_USER) is None


def test_update_incident_status_returns_none_for_another_users_incident(sqlite_db):
    created = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c",
    )

    # OTHER_USER must not be able to acknowledge TEST_USER's incident.
    result = sqlite_db.update_incident_status(created["id"], "ACKNOWLEDGED", user_id=OTHER_USER)

    assert result is None
    # And it must remain untouched, still ACTIVE, still TEST_USER's.
    assert sqlite_db.get_incident(created["id"], user_id=TEST_USER)["status"] == "ACTIVE"


def test_list_incidents_limit_returns_only_the_most_recent(sqlite_db):
    for i in range(3):
        sqlite_db.insert_incident(
            user_id=TEST_USER,
            event=f"Event {i}", risk="LOW", confidence=50,
            explanation="e", recommendation="r", detection="d", context="c",
        )

    limited = sqlite_db.list_incidents(user_id=TEST_USER, limit=2)
    full = sqlite_db.list_incidents(user_id=TEST_USER)

    assert len(limited) == 2
    assert len(full) == 3
    assert limited == full[:2]


def test_dashboard_stats_are_served_from_cache_within_the_ttl_window(sqlite_db):
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=90,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    first = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert first["totalEvents"]["value"] == 1

    # Insert directly, bypassing insert_incident() (and its cache
    # invalidation), to prove the *next* call is served from the in-memory
    # cache rather than re-querying the database.
    with sqlite_db.get_connection() as conn:
        conn.execute(
            sqlite_db._INSERT_SQL,
            {
                "id": "INC-DIRECT", "event": "Normal Activity", "risk": "LOW", "confidence": 10,
                "location": "Zone A", "camera_id": "CAM-01", "edge_node": "EDGE NODE 01",
                "timestamp": "00:00:00", "date": "2026-01-01", "explanation": "e",
                "recommendation": "r", "status": "ACTIVE", "detection": "d", "context": "c",
                "created_at": "2026-01-01T00:00:00+00:00", "user_id": TEST_USER,
            },
        )

    cached = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert cached["totalEvents"]["value"] == 1  # still the cached value, not 2


def test_dashboard_stats_cache_is_invalidated_by_insert_incident(sqlite_db):
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=90,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    first = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert first["totalEvents"]["value"] == 1

    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-02",
    )
    second = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert second["totalEvents"]["value"] == 2  # never served stale after a real incident is created


def test_dashboard_stats_cache_is_invalidated_by_status_update(sqlite_db):
    incident = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    before = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert before["systemHealth"]["value"] == 99.5  # one unresolved MEDIUM

    sqlite_db.update_incident_status(incident["id"], "RESOLVED", user_id=TEST_USER)
    after = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    assert after["systemHealth"]["value"] == 100.0  # not served stale after resolving


def test_dashboard_stats_reflect_real_inserted_rows(sqlite_db):
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=95,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-02",
    )
    incident = sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Normal Activity", risk="LOW", confidence=10,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    sqlite_db.update_incident_status(incident["id"], "ACKNOWLEDGED", user_id=TEST_USER)

    stats = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)

    assert stats["totalEvents"]["value"] == 3
    assert stats["highRisk"]["value"] == 1
    assert stats["activeInputs"]["value"] == 2  # distinct camera_id: CAM-01, CAM-02
    assert stats["totalEvents"]["change"] == 0  # documented placeholder, not invented


def test_dashboard_stats_are_isolated_per_user(sqlite_db):
    for _ in range(3):
        sqlite_db.insert_incident(
            user_id=TEST_USER,
            event="Restricted Area Entry", risk="HIGH", confidence=90,
            explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
        )
    sqlite_db.insert_incident(
        user_id=OTHER_USER,
        event="Normal Activity", risk="LOW", confidence=10,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-02",
    )

    mine = sqlite_db.compute_dashboard_stats(user_id=TEST_USER)
    theirs = sqlite_db.compute_dashboard_stats(user_id=OTHER_USER)

    assert mine["totalEvents"]["value"] == 3
    assert mine["highRisk"]["value"] == 3
    assert theirs["totalEvents"]["value"] == 1
    assert theirs["highRisk"]["value"] == 0


def test_dashboard_stats_for_a_brand_new_user_are_all_zero(sqlite_db):
    # A user who has never created an incident must see honest zeros --
    # never a fabricated non-zero "at least 1" floor (see the `or 1`
    # removal in compute_dashboard_stats).
    stats = sqlite_db.compute_dashboard_stats(user_id="brand-new-user")

    assert stats == {
        "totalEvents": {"value": 0, "change": 0},
        "highRisk": {"value": 0, "change": 0},
        "activeInputs": {"value": 0, "change": 0},
        "systemHealth": {"value": 100.0, "change": 0},
    }


def test_analytics_reflect_real_inserted_rows(sqlite_db):
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=95,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=92,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-02",
    )
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )

    analytics = sqlite_db.compute_analytics(user_id=TEST_USER)

    risk_dist = {p["name"]: p["value"] for p in analytics["riskDistribution"]}
    assert risk_dist == {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    categories = {p["name"]: p["value"] for p in analytics["eventCategories"]}
    assert categories["Restricted Area Entry"] == 2
    assert categories["PPE Violation"] == 1

    assert analytics["systemHealth"]["edgeNodesOnline"] == 2
    assert analytics["systemHealth"]["edgeNodesTotal"] == 2


def test_analytics_are_isolated_per_user(sqlite_db):
    sqlite_db.insert_incident(
        user_id=TEST_USER,
        event="Restricted Area Entry", risk="HIGH", confidence=95,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-01",
    )
    sqlite_db.insert_incident(
        user_id=OTHER_USER,
        event="PPE Violation", risk="MEDIUM", confidence=70,
        explanation="e", recommendation="r", detection="d", context="c", camera_id="CAM-02",
    )

    mine = sqlite_db.compute_analytics(user_id=TEST_USER)
    theirs = sqlite_db.compute_analytics(user_id=OTHER_USER)

    mine_categories = {p["name"]: p["value"] for p in mine["eventCategories"]}
    theirs_categories = {p["name"]: p["value"] for p in theirs["eventCategories"]}

    assert mine_categories == {"Restricted Area Entry": 1}
    assert theirs_categories == {"PPE Violation": 1}


def test_analytics_for_a_brand_new_user_are_empty(sqlite_db):
    analytics = sqlite_db.compute_analytics(user_id="brand-new-user")

    assert analytics["eventsOverTime"] == []
    assert analytics["eventCategories"] == []
    assert {p["value"] for p in analytics["riskDistribution"]} == {0}
    assert analytics["systemHealth"]["edgeNodesOnline"] == 0
    assert analytics["systemHealth"]["edgeNodesTotal"] == 0


def test_init_db_creates_the_schema_and_seeds_only_for_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)
    try:
        db.init_db()
        # Seed rows are legacy/unowned (user_id IS NULL) on purpose -- see
        # init_db()'s own comment -- so they're verified with a raw,
        # unscoped query here rather than the now user-scoped
        # list_incidents(), which would correctly show none of them.
        with db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM incidents").fetchall()
        assert len(rows) == len(db._SEED_INCIDENTS)
        assert all(r["user_id"] is None for r in rows)
    finally:
        importlib.reload(db)


def test_seed_incidents_are_invisible_to_every_user(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db)
    try:
        db.init_db()

        assert db.list_incidents(user_id=TEST_USER) == []
        assert db.list_incidents(user_id=OTHER_USER) == []
        stats = db.compute_dashboard_stats(user_id=TEST_USER)
        assert stats["totalEvents"]["value"] == 0
    finally:
        importlib.reload(db)


def test_init_db_does_not_seed_demo_data_for_postgres(postgres_selected):
    with patch("app.database.database.ConnectionPool") as mock_pool_cls:
        mock_conn = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_pool = MagicMock()
        mock_pool.connection.return_value = mock_cm
        mock_pool_cls.return_value = mock_pool

        postgres_selected.init_pool()
        postgres_selected.init_db()

        # Only the schema DDL and the additive user_id migration are
        # executed -- never the seed INSERTs, and never a "how many rows
        # are there" COUNT check either (that check itself doesn't make
        # sense before deciding to seed).
        executed = [call.args[0] for call in mock_conn.execute.call_args_list]
        assert any("CREATE TABLE" in sql for sql in executed)
        assert any("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS user_id" in sql for sql in executed)
        assert not any("INSERT INTO incidents" in sql for sql in executed)
        assert not any("COUNT" in sql for sql in executed)

        postgres_selected.close_pool()


def test_ensure_user_id_column_is_idempotent_for_sqlite(sqlite_db):
    # Calling it again (e.g. on every startup, as init_db() does) must not
    # raise "duplicate column name" or otherwise fail.
    with sqlite_db.get_connection() as conn:
        sqlite_db._ensure_user_id_column(conn)
        sqlite_db._ensure_user_id_column(conn)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}
    assert "user_id" in columns
