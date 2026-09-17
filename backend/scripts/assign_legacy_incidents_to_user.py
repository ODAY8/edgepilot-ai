#!/usr/bin/env python
"""One-time, manual, OPT-IN migration: assigns every incident that has no
owner (user_id IS NULL) to one specific Supabase user id you choose --
typically your own demo account, so you can still see the historical
demo incidents after logging in with multi-user isolation in place.

Deliberately NOT automatic. Rows with no user_id are already safe on
their own: every user-scoped query (list_incidents, get_incident,
compute_dashboard_stats, compute_analytics -- see
app/database/database.py) filters by `user_id = <the authenticated
caller>`, and a NULL column value never matches any real id, in either
SQLite or PostgreSQL. So an unowned row is already invisible to every
account and stays that way forever unless you explicitly run this
script. Nothing is ever deleted -- an incident with no owner keeps
existing, just unseen, until claimed.

Safety properties (same design as scripts/migrate_sqlite_to_postgres.py):
  - Only ever touches rows where user_id IS NULL -- never reassigns a
    row that already belongs to a real user.
  - --dry-run lists exactly which incident ids would be updated and
    changes nothing.
  - Never prints DATABASE_URL, SUPABASE_ANON_KEY, or any other
    credential -- only incident ids and the user id you pass on the
    command line.

Usage (run from the backend/ directory, with the venv active):
    python scripts/assign_legacy_incidents_to_user.py --user-id <supabase-user-uuid> --dry-run
    python scripts/assign_legacy_incidents_to_user.py --user-id <supabase-user-uuid>

Find your Supabase user id in the Supabase Dashboard -> Authentication ->
Users -> (your account) -> User UID. That UUID is not a secret in the
same sense as an API key, but it does identify a specific account --
treat it with the same care you'd give any other user identifier.
"""

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_BACKEND_DIR / ".env", override=False)

from app.database import database as db  # noqa: E402


def migrate(user_id: str, dry_run: bool) -> None:
    select_sql = "SELECT id FROM incidents WHERE user_id IS NULL ORDER BY created_at"
    update_sql = (
        "UPDATE incidents SET user_id = %s WHERE id = %s"
        if db.is_using_postgres()
        else "UPDATE incidents SET user_id = ? WHERE id = ?"
    )

    print(f"Backend: {db.backend_name()}")

    with db.get_connection() as conn:
        rows = conn.execute(select_sql).fetchall()
        ids = [r["id"] for r in rows]
        print(f"Unowned (legacy) incidents found: {len(ids)}")

        if not ids:
            print("Nothing to do.")
            return

        if dry_run:
            print("\nDry run -- would assign these incidents, nothing was changed:")
            for incident_id in ids:
                print(f"  {incident_id}")
            return

        for incident_id in ids:
            conn.execute(update_sql, (user_id, incident_id))
            print(f"  {incident_id} ... assigned")

    # get_connection()'s own context manager commits on clean exit for
    # both backends -- see its docstring in app/database/database.py.
    print(f"\nAssigned {len(ids)} incident(s) to user_id={user_id}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True, help="Supabase user UUID to assign unowned incidents to.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List which incidents would be assigned without changing anything.",
    )
    args = parser.parse_args()

    if db.is_using_postgres():
        db.init_pool()
    try:
        migrate(args.user_id, args.dry_run)
    finally:
        if db.is_using_postgres():
            db.close_pool()
