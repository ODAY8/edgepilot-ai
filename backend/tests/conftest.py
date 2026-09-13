"""Loads backend/.env (if present) before tests run, the same way
`uvicorn --env-file .env` does for the app itself. This lets tests that
need a real GEMINI_API_KEY/GROQ_API_KEY find them locally without
requiring the shell to export them first. Never overwrites a variable
that's already set in the environment.
"""

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _value = _line.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip())
