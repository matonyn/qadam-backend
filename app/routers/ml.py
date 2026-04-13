"""
REST surface for Smart Campus ML (vendor/senior_project_ML).
Paths are under /api/v1/ml/… — same behaviour as the upstream ML API, wrapped in ApiResponse.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app import models
from app.dependencies import get_current_user
from app.ml import engines as ml
from app.schemas import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])


def _require_ml():
    if not ml._engines_ready or not all(
        (ml.sentiment_engine, ml.reputation_engine, ml.recommendation_engine, ml.crowd_engine)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML service unavailable. Install optional deps (requirements-ml.txt) and ensure vendor/senior_project_ML exists.",
        )


# ─── Schemas (aligned with senior_project_ML/main.py) ──────────────────────────


class MlSentimentRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)


class MlReviewBatch(BaseModel):
    reviews: list[dict]


class MlRecommendRequest(BaseModel):
    user_id: str
    type: str = "all"
    n: int = Field(5, ge=1, le=20)
    context: Optional[dict] = None


class MlInteractionRequest(BaseModel):
    user_id: str
    venue_id: str
    rating: float = Field(..., ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


class MlDietaryRequest(BaseModel):
    user_id: str
    dietary: list[str]


class MlCrowdRequest(BaseModel):
    horizon_minutes: int = Field(0, ge=0, le=240)
    event_flags: Optional[dict[str, int]] = None


class MlTrainRequest(BaseModel):
    csv_path: str


# ─── Sentiment ─────────────────────────────────────────────────────────────────


@router.post("/sentiment/predict", response_model=ApiResponse[dict[str, Any]])
def ml_sentiment_predict(
    body: MlSentimentRequest,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    out = ml.sentiment_engine.predict(body.text)
    return ApiResponse(success=True, data=out)


@router.post("/sentiment/reputation", response_model=ApiResponse[dict[str, Any]])
def ml_sentiment_reputation(
    body: MlReviewBatch,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    out = ml.reputation_engine.compute_score(body.reviews)
    return ApiResponse(success=True, data=out)


# ─── Recommendations ───────────────────────────────────────────────────────────


@router.post("/recommend", response_model=ApiResponse[dict[str, Any]])
def ml_recommend(
    body: MlRecommendRequest,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    crowd_weights = {r["location_id"]: r["weight"] for r in ml.crowd_engine.predict_now()}
    ml.recommendation_engine.update_crowd_weights(crowd_weights)
    results = ml.recommendation_engine.recommend(
        user_id=body.user_id,
        rec_type=body.type,
        n=body.n,
        context=body.context,
    )
    return ApiResponse(
        success=True,
        data={"recommendations": results, "generated_at": datetime.utcnow().isoformat()},
    )


@router.post("/recommend/interaction", response_model=ApiResponse[dict[str, str]])
def ml_recommend_interaction(
    body: MlInteractionRequest,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    ml.recommendation_engine.record_interaction(
        body.user_id, body.venue_id, body.rating, body.tags
    )
    return ApiResponse(success=True, data={"status": "ok"})


@router.post("/recommend/dietary", response_model=ApiResponse[dict[str, Any]])
def ml_recommend_dietary(
    body: MlDietaryRequest,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    ml.recommendation_engine.set_dietary(body.user_id, body.dietary)
    return ApiResponse(success=True, data={"status": "ok", "dietary": body.dietary})


# ─── Crowd ─────────────────────────────────────────────────────────────────────


@router.post("/crowd/predict", response_model=ApiResponse[dict[str, Any]])
def ml_crowd_predict(
    body: MlCrowdRequest,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    results = ml.crowd_engine.predict_now(
        horizon_minutes=body.horizon_minutes,
        event_flags=body.event_flags,
    )
    return ApiResponse(
        success=True,
        data={"predictions": results, "generated_at": datetime.utcnow().isoformat()},
    )


@router.get("/crowd/graph-weights", response_model=ApiResponse[dict[str, Any]])
def ml_crowd_graph_weights(current_user: models.User = Depends(get_current_user)):
    _require_ml()
    return ApiResponse(
        success=True,
        data={
            "weights": ml.crowd_engine.get_graph_weights(),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )


@router.get("/crowd/horizon", response_model=ApiResponse[dict[str, Any]])
def ml_crowd_horizon(current_user: models.User = Depends(get_current_user)):
    _require_ml()
    snapshots = ml.crowd_engine.predict_horizon()
    return ApiResponse(
        success=True,
        data={"snapshots": snapshots, "interval_minutes": 15},
    )


@router.post("/crowd/train", response_model=ApiResponse[dict[str, Any]])
def ml_crowd_train(
    body: MlTrainRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()

    def _train():
        try:
            ml.crowd_engine.train(body.csv_path)
            logger.info("Crowd model re-trained")
        except Exception as e:
            logger.exception("Crowd train failed: %s", e)

    background_tasks.add_task(_train)
    return ApiResponse(success=True, data={"status": "training started", "csv_path": body.csv_path})


@router.post("/crowd/generate-synthetic", response_model=ApiResponse[dict[str, Any]])
def ml_crowd_generate_synthetic(
    days: int = 60,
    current_user: models.User = Depends(get_current_user),
):
    _require_ml()
    path = type(ml.crowd_engine).generate_synthetic_data(days=days)
    return ApiResponse(success=True, data={"status": "ok", "path": path, "days": days})


# ─── Health (no sensitive details) ─────────────────────────────────────────────


@router.get("/health", response_model=ApiResponse[dict[str, Any]])
def ml_health_check(current_user: models.User = Depends(get_current_user)):
    h = ml.ml_health()
    return ApiResponse(success=True, data=h)
