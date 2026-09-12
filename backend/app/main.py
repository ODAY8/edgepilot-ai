import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database.database import init_db
from app.routes import analysis, analytics, dashboard, health, incidents
from app.services import llm

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("edgepilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("EdgePilot AI API starting up (db=%s)", os.getenv("DATABASE_PATH", "<default>"))
    logger.info(
        "Groq reasoning: %s",
        "enabled" if llm.is_configured() else "disabled (falling back to template reasoning) -- set GROQ_API_KEY to enable",
    )
    yield
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
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

@app.get("/", tags=["Health"], summary="API root")
def root() -> dict:
    return {"service": "EdgePilot AI API", "version": "1.0.0", "docs": "/docs"}
