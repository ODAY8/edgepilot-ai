"""Non-secret system configuration status, for the frontend Settings page.

Read-only: reuses vision.is_configured()/llm.is_configured() (the same
checks the startup log already makes) rather than adding any new
detection logic. Never returns key values -- only whether each provider
is configured.
"""

from fastapi import APIRouter, Request

from app.models.schemas import SystemStatusResponse
from app.services import llm, vision

router = APIRouter()


@router.get("/system/status", response_model=SystemStatusResponse, summary="Non-secret system configuration status")
def system_status(request: Request) -> dict:
    return {
        "version": request.app.version,
        "visionEnabled": vision.is_configured(),
        "reasoningEnabled": llm.is_configured(),
    }
