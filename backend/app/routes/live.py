"""Live browser-camera frame analysis.

Reuses the exact same vision/risk/reasoning/database services as
routes/analysis.py -- this module only adds the policy layer specific
to a frame arriving every few seconds from a live feed: skip incident
creation for normal_activity, and cooldown-dedupe repeated meaningful
events per (camera, event type) so the same ongoing event doesn't spam
a new incident (and a new Groq call) every 3-5 seconds.
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.database import database
from app.models.schemas import AnalysisInfo, EventInfo, LiveFrameResponse, RecommendationInfo, RiskInfo
from app.services import dedup, llm, reasoning, recommendations, risk
from app.services import vision as vision_service
from app.services.vision import VisionUnavailableError

logger = logging.getLogger("edgepilot.live")

router = APIRouter()

_ALLOWED_PREFIXES = ("image/",)


@router.post("/analyze-frame", response_model=LiveFrameResponse, summary="Analyze one live camera frame")
async def analyze_frame(
    file: UploadFile = File(..., description="A single captured frame (image) from a live browser camera feed"),
    camera_id: str | None = Form(None),
    location: str | None = Form(None),
) -> LiveFrameResponse:
    if not file.content_type or not file.content_type.startswith(_ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail="Frame must be an image.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Frame is empty.")

    # Matches database.insert_incident's own default so the dedup key and
    # the persisted row always agree on which camera this is.
    resolved_camera_id = camera_id or "CAM-01"

    try:
        detection = vision_service.detect_event(contents, file.content_type)
    except VisionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        risk_assessment = risk.assess_risk(detection)
        event_info = EventInfo(type=detection.type, label=detection.label, confidence=detection.confidence)
        risk_info = RiskInfo(level=risk_assessment.level, score=risk_assessment.score)

        # Nothing worth reasoning about -- most frames land here. No Groq
        # call, no incident, no log spam.
        if detection.type == "normal_activity":
            logger.debug("Live frame: normal_activity on %s, no incident.", resolved_camera_id)
            return LiveFrameResponse(incidentCreated=False, status="NORMAL", event=event_info, risk=risk_info)

        # A meaningful event, but the same one is already being tracked for
        # this camera -- don't create a duplicate incident or call Groq again.
        if not dedup.should_create_incident(resolved_camera_id, detection.type):
            logger.debug(
                "Live frame: %s on %s within cooldown, skipping incident.", detection.type, resolved_camera_id
            )
            return LiveFrameResponse(incidentCreated=False, status="COOLDOWN", event=event_info, risk=risk_info)

        # Only this path -- a genuinely new, meaningful event -- calls Groq.
        llm_result = llm.generate_reasoning(detection, risk_assessment, location)
        if llm_result is not None:
            summary, explanation = llm_result.summary, llm_result.explanation
            action, priority = llm_result.action, llm_result.priority
        else:
            analysis = reasoning.generate_explanation(detection, location)
            recommendation = recommendations.recommend_action(risk_assessment)
            summary, explanation = analysis.summary, analysis.explanation
            action, priority = recommendation.action, recommendation.priority
    except HTTPException:
        raise
    except Exception:
        logger.exception("Live frame analysis pipeline failed")
        raise HTTPException(status_code=500, detail="Frame analysis pipeline failed.")

    incident = database.insert_incident(
        event=detection.label,
        risk=risk_assessment.level,
        confidence=round(detection.confidence * 100),
        explanation=explanation,
        recommendation=action,
        detection=detection.label,
        context=detection.context,
        location=location,
        camera_id=resolved_camera_id,
    )
    dedup.mark_incident_created(resolved_camera_id, detection.type)

    logger.info(
        "Live frame created incident %s on %s (risk=%s, score=%d)",
        incident["id"], resolved_camera_id, risk_assessment.level, risk_assessment.score,
    )

    return LiveFrameResponse(
        incidentCreated=True,
        status="CREATED",
        event=event_info,
        risk=risk_info,
        incidentId=incident["id"],
        analysis=AnalysisInfo(summary=summary, explanation=explanation),
        recommendation=RecommendationInfo(action=action, priority=priority),
    )
