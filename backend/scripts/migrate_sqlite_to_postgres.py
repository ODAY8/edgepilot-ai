#!/usr/bin/env python
"""One-time migration: copy incidents from the local SQLite database
(backend/edgepilot.db) into PostgreSQL (Supabase).

Deliberately NOT run automatically by anything -- this is a standalone
script you run yourself, once, when you're ready.

Safety properties:
  - Never writes to, deletes, or alters edgepilot.db in any way -- it is
    opened strictly read-only (SQLite's `mode=ro` URI, enforced by SQLite
    itself, not just by convention).
  - Existing incident IDs are never duplicated or overwritten: each
    insert uses `ON CONFLICT (id) DO NOTHING`, so re-running this script
    against a partially- or fully-migrated PostgreSQL database is safe.
  - Every row is inserted in its own SAVEPOINT, so one bad row is
    recorded as "failed" and skipped without losing progress already
    made on the rows around it.
  - --dry-run performs every real insert attempt (so you see real
    conflict/error counts) inside a transaction that is always rolled
    back at the end -- nothing is ever actually persisted to PostgreSQL
    in dry-run mode.
  - Never prints DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY, or any other
    credential -- only counts and incident IDs are logged.

Usage (run from the backend/ directory, with the venv active):
    python scripts/migrate_sqlite_to_postgres.py             # perform the migration
    python scripts/migrate_sqlite_to_postgres.py --dry-run   # show what would happen, write nothing
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# stdout is fully block-buffered (not line-buffered) whenever it isn't an
# interactive terminal -- e.g. when piped or captured. Without this, every
# print() below would sit in a buffer and never actually appear until the
# process exits, which defeats "print clear progress" for anyone piping
# this script's output or watching it over a slow/flaky connection.
sys.stdout.reconfigure(line_buffering=True)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

# Same loading convention as app/main.py / tests/conftest.py: a real
# exported environment variable always wins over backend/.env.
load_dotenv(_BACKEND_DIR / ".env", override=False)

import psycopg  # noqa: E402

from app.database.database import DB_PATH, _SCHEMA  # noqa: E402

_COLUMNS = [
    "id", "event", "risk", "confidence", "location", "camera_id", "edge_node",
    "timestamp", "date", "explanation", "recommendation", "status", "detection",
    "context", "created_at",
]

_INSERT_SQL = f"""
INSERT INTO incidents ({", ".join(_COLUMNS)})
VALUES ({", ".join(f"%({c})s" for c in _COLUMNS)})
ON CONFLICT (id) DO NOTHING
"""


def read_sqlite_incidents() -> list[dict]:
    """Read-only: opens edgepilot.db via SQLite's own read-only URI mode,
    so it is not possible for this script to write to it even by mistake."""
    if not os.path.exists(DB_PATH):
        print(f"No SQLite database found at {DB_PATH} -- nothing to migrate.")
        return []

    uri = f"file:{Path(DB_PATH).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT {', '.join(_COLUMNS)} FROM incidents ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def migrate(dry_run: bool) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set -- nothing to migrate into. Aborting.")
        sys.exit(1)

    sqlite_rows = read_sqlite_incidents()
    total = len(sqlite_rows)
    print(f"SQLite records: {total}")
    if total == 0:
        print("Inserted: 0")
        print("Already existing/skipped: 0")
        print("Failed: 0")
        return

    inserted = 0
    skipped = 0
    failed = 0

    # Never logs database_url -- psycopg.connect() itself doesn't either.
    # An explicit timeout means an unreachable database fails predictably
    # instead of hanging on the OS's own (often much longer) TCP timeout.
    print("Connecting to PostgreSQL...")
    try:
        conn = psycopg.connect(database_url, connect_timeout=10)
    except Exception as exc:
        print(f"Could not connect to PostgreSQL: {exc}")
        sys.exit(1)

    with conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            # Idempotent and safe even if the table already exists (it
            # does, per Supabase already having it) -- a defensive no-op.
            cur.execute(_SCHEMA)

            for i, row in enumerate(sqlite_rows, start=1):
                incident_id = row["id"]
                try:
                    cur.execute("SAVEPOINT row_sp")
                    cur.execute(_INSERT_SQL, row)
                    if cur.rowcount == 1:
                        inserted += 1
                        print(f"[{i}/{total}] {incident_id} ... inserted")
                    else:
                        skipped += 1
                        print(f"[{i}/{total}] {incident_id} ... already exists, skipped")
                    cur.execute("RELEASE SAVEPOINT row_sp")
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                    failed += 1
                    print(f"[{i}/{total}] {incident_id} ... FAILED: {exc}")

            if dry_run:
                conn.rollback()
                print("\nDry run: no changes were committed to PostgreSQL.")
            else:
                conn.commit()
                print("\nChanges committed to PostgreSQL.")

            # Verification query -- reflects the real current count either
            # way (dry-run rolled back, so this shows the unchanged count).
            with conn.cursor() as verify_cur:
                verify_cur.execute("SELECT COUNT(*) FROM incidents")
                pg_count = verify_cur.fetchone()[0]

    print()
    print(f"SQLite records: {total}")
    print(f"Inserted: {inserted}")
    print(f"Already existing/skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"PostgreSQL incident count now: {pg_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Attempt every insert for real (to surface real conflicts/errors) but roll back at the end -- nothing is persisted.",
    )
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
