import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.database import database
from app.models.schemas import AnalysisInfo, AnalyzeResponse, EventInfo, RecommendationInfo, RiskInfo
from app.services import llm, reasoning, recommendations, risk
from app.services import vision as vision_service
from app.services.frame_extraction import FrameExtractionError, extract_frame
from app.services.vision import VisionUnavailableError

logger = logging.getLogger("edgepilot.analysis")

router = APIRouter()

_ALLOWED_PREFIXES = ("image/", "video/")


@router.post("/analyze", response_model=AnalyzeResponse, summary="Analyze an uploaded image or video")
async def analyze(
    file: UploadFile = File(..., description="Image or video captured from a camera / edge node"),
    location: str | None = Form(None),
    camera_id: str | None = Form(None),
) -> AnalyzeResponse:
    if not file.content_type or not file.content_type.startswith(_ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail="File must be an image or video.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info("Analyzing upload: %s (%s, %d bytes)", file.filename, file.content_type, len(contents))

    # Vision models take a still image, so a video upload first gets reduced
    # to one representative frame; images are analyzed as-is.
    if file.content_type.startswith("video/"):
        try:
            image_bytes = extract_frame(contents)
        except FrameExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        image_mime = "image/jpeg"
    else:
        image_bytes = contents
        image_mime = file.content_type

    try:
        detection = vision_service.detect_event(image_bytes, image_mime)
    except VisionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        risk_assessment = risk.assess_risk(detection)

        llm_result = llm.generate_reasoning(detection, risk_assessment, location)
        if llm_result is not None:
            summary, explanation = llm_result.summary, llm_result.explanation
            action, priority = llm_result.action, llm_result.priority
        else:
            analysis = reasoning.generate_explanation(detection, location)
            recommendation = recommendations.recommend_action(risk_assessment)
            summary, explanation = analysis.summary, analysis.explanation
            action, priority = recommendation.action, recommendation.priority
    except Exception:
        logger.exception("Analysis pipeline failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Analysis pipeline failed.")

    incident = database.insert_incident(
        event=detection.label,
        risk=risk_assessment.level,
        confidence=round(detection.confidence * 100),
        explanation=explanation,
        recommendation=action,
        detection=detection.label,
        context=detection.context,
        location=location,
        camera_id=camera_id,
    )

    logger.info(
        "Created incident %s (risk=%s, score=%d, llm=%s)",
        incident["id"], risk_assessment.level, risk_assessment.score, llm_result is not None,
    )

    return AnalyzeResponse(
        id=incident["id"],
        event=EventInfo(type=detection.type, label=detection.label, confidence=detection.confidence),
        risk=RiskInfo(level=risk_assessment.level, score=risk_assessment.score),
        analysis=AnalysisInfo(summary=summary, explanation=explanation),
        recommendation=RecommendationInfo(action=action, priority=priority),
    )
