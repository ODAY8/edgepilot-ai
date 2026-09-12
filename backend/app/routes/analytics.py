from fastapi import APIRouter

from app.database import database
from app.models.schemas import AnalyticsResponse

router = APIRouter()


@router.get("/analytics", response_model=AnalyticsResponse, summary="Analytics data for charts")
def analytics() -> dict:
    return database.compute_analytics()
