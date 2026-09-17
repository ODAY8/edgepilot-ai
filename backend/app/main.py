import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load backend/.env, if present, before any app module below reads
# GEMINI_API_KEY / GROQ_API_KEY / etc. at import time -- vision.py and
# llm.py each read their key once at module load, so this has to run
# before the `app.routes`/`app.services` imports just below it. This
# makes `python -m uvicorn app.main:app` work on its own; explicit
# environment variables (a real shell export, `--env-file`, a production
# secrets manager) still take priority, since override=False never lets
# .env replace a value that's already set. Never logs key values -- only
# whether each provider ends up configured (see the startup log below).
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from app.database import database  # noqa: E402
from app.routes import analysis, analytics, dashboard, health, incidents, live, system  # noqa: E402
from app.services import llm, vision  # noqa: E402
from app.services import auth as auth_service  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("edgepilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # For PostgreSQL, opens the connection pool once here (and only here --
    # never per-request); a no-op for the SQLite fallback. A misconfigured
    # DATABASE_URL fails loudly at startup rather than on the first
    # request. Never logs DATABASE_URL or any credential -- only which
    # backend ended up active.
    database.init_pool()
    database.init_db()
    logger.info("EdgePilot AI API starting up")
    logger.info("Database backend: %s", database.backend_name())
    logger.info(
        "Vision analysis (Gemini): %s",
        "enabled" if vision.is_configured() else "DISABLED -- /api/analyze will return 503 until GEMINI_API_KEY is set",
    )
    logger.info(
        "Groq reasoning: %s",
        "enabled" if llm.is_configured() else "disabled (falling back to template reasoning) -- set GROQ_API_KEY to enable",
    )
    logger.info(
        "Supabase auth verification: %s",
        "enabled"
        if auth_service.is_configured()
        else "DISABLED -- every user-scoped endpoint will return 401 until SUPABASE_URL/SUPABASE_ANON_KEY are set",
    )
    yield
    database.close_pool()
    logger.info("EdgePilot AI API shutting down")


app = FastAPI(title="EdgePilot AI API", version="1.0.0", lifespan=lifespan)

_frontend_origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(live.router, prefix="/api", tags=["Live"])
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(system.router, prefix="/api", tags=["System"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

@app.get("/", tags=["Health"], summary="API root")
def root() -> dict:
    return {"service": "EdgePilot AI API", "version": "1.0.0", "docs": "/docs"}
