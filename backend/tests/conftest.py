"""Loads backend/.env (if present) before tests run -- the same
load_dotenv call app/main.py makes, since pytest imports app.services
modules directly and never goes through main.py's own startup. This lets
tests that need a real GEMINI_API_KEY/GROQ_API_KEY find them locally
without requiring the shell to export them first. override=False, so a
variable already set in the real environment is never replaced by .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

# The normal test suite must never depend on live external infrastructure
# (a real Supabase/PostgreSQL database), even though a developer's real
# .env may legitimately have DATABASE_URL set for actually running the
# app. Unset it here, for the test session only, so app.database.database
# always picks the SQLite fallback by default -- exactly as it did before
# PostgreSQL support existed. Tests that specifically want to exercise the
# PostgreSQL branch-selection logic set a fake DATABASE_URL themselves and
# mock the psycopg layer (see test_database.py); they never need a real
# database to do that.
os.environ.pop("DATABASE_URL", None)
