from fastapi import APIRouter, HTTPException

from app.database import database
from app.models.schemas import Incident

router = APIRouter()


@router.get("/incidents", response_model=list[Incident], summary="List all incidents")
def list_incidents() -> list[dict]:
    return database.list_incidents()


@router.get("/incidents/{incident_id}", response_model=Incident, summary="Get a single incident")
def get_incident(incident_id: str) -> dict:
    incident = database.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@router.post("/incidents/{incident_id}/acknowledge", response_model=Incident, summary="Acknowledge an incident")
def acknowledge_incident(incident_id: str) -> dict:
    incident = database.update_incident_status(incident_id, "ACKNOWLEDGED")
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@router.post("/incidents/{incident_id}/escalate", response_model=Incident, summary="Escalate an incident")
def escalate_incident(incident_id: str) -> dict:
    incident = database.update_incident_status(incident_id, "ESCALATED")
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident
