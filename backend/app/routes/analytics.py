from fastapi import APIRouter

from app.database import database
from app.models.schemas import AnalyticsResponse

router = APIRouter()


@router.get("/insights", response_model=AnalyticsResponse, summary="Analytics data for charts")
def analytics() -> dict:
    # Route path is deliberately NOT "/api/analytics" -- ad-blocker/privacy
    # extension filter lists (e.g. EasyPrivacy) commonly block any request
    # path containing "analytics", which broke this endpoint for real users
    # even though the backend itself was never at fault. See also the
    # frontend's src/pages/Insights.tsx and src/components/insights/ for
    # the matching rename on the client side.
    return database.compute_analytics()
