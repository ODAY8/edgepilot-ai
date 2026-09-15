"""Locks in how app/main.py loads backend/.env, so a future edit can't
silently stop `python -m uvicorn app.main:app` (with no --env-file flag)
from picking up GEMINI_API_KEY/GROQ_API_KEY, and can't silently start
letting .env override real environment variables.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import dotenv

_EXPECTED_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def test_main_loads_backend_env_with_override_false_on_import():
    with patch.object(dotenv, "load_dotenv") as mock_load_dotenv:
        if "app.main" in sys.modules:
            importlib.reload(sys.modules["app.main"])
        else:
            import app.main  # noqa: F401

    assert mock_load_dotenv.called
    args, kwargs = mock_load_dotenv.call_args
    loaded_path = Path(args[0]) if args else Path(kwargs["dotenv_path"])

    assert loaded_path == _EXPECTED_ENV_PATH
    # override=False is the whole point: a real exported environment
    # variable (CI, a production secrets manager, --env-file) must always
    # win over whatever is sitting in the .env file.
    assert kwargs.get("override") is False
