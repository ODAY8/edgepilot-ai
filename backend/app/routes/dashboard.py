from fastapi import APIRouter, Depends

from app.database import database
from app.models.schemas import DashboardStatsResponse
from app.services.auth import get_current_user_id

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStatsResponse, summary="Dashboard overview stats")
def dashboard_stats(user_id: str = Depends(get_current_user_id)) -> dict:
    return database.compute_dashboard_stats(user_id=user_id)
