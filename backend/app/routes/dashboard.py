from fastapi import APIRouter

from app.database import database
from app.models.schemas import DashboardStatsResponse

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStatsResponse, summary="Dashboard overview stats")
def dashboard_stats() -> dict:
    return database.compute_dashboard_stats()
