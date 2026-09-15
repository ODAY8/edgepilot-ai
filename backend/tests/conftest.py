"""Loads backend/.env (if present) before tests run -- the same
load_dotenv call app/main.py makes, since pytest imports app.services
modules directly and never goes through main.py's own startup. This lets
tests that need a real GEMINI_API_KEY/GROQ_API_KEY find them locally
without requiring the shell to export them first. override=False, so a
variable already set in the real environment is never replaced by .env.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
