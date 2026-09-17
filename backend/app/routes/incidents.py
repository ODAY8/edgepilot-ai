from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import database
from app.models.schemas import Incident
from app.services.auth import get_current_user_id

router = APIRouter()


@router.get("/incidents", response_model=list[Incident], summary="List incidents")
def list_incidents(
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Return only the N most recent incidents. Omit for full history (used by the Incidents page).",
    ),
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    return database.list_incidents(user_id=user_id, limit=limit)


@router.get("/incidents/{incident_id}", response_model=Incident, summary="Get a single incident")
def get_incident(incident_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    incident = database.get_incident(incident_id, user_id=user_id)
    if incident is None:
        # Deliberately the same 404 whether the id doesn't exist at all or
        # belongs to another user -- never confirm that a given id exists
        # for someone else.
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@router.post("/incidents/{incident_id}/acknowledge", response_model=Incident, summary="Acknowledge an incident")
def acknowledge_incident(incident_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    incident = database.update_incident_status(incident_id, "ACKNOWLEDGED", user_id=user_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@router.post("/incidents/{incident_id}/escalate", response_model=Incident, summary="Escalate an incident")
def escalate_incident(incident_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    incident = database.update_incident_status(incident_id, "ESCALATED", user_id=user_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident
