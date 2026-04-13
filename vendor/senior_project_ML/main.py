"""
main.py
───────
FastAPI application exposing all four Smart Campus ML engines as REST endpoints.

Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from sentiment.engine   import SentimentEngine, ReputationEngine
from recommendation.engine import RecommendationEngine
from crowd_prediction.engine import CrowdPredictionEngine

# ─── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Campus ML API",
    description="NLP Sentiment · AI Recommendations · Crowd Prediction · Analytics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Engine singletons (initialised at startup) ────────────────────────────────

sentiment_engine:     SentimentEngine     = None
reputation_engine:    ReputationEngine    = None
recommendation_engine: RecommendationEngine = None
crowd_engine:         CrowdPredictionEngine = None

@app.on_event("startup")
async def startup():
    global sentiment_engine, reputation_engine, recommendation_engine, crowd_engine
    logger.info("Initialising ML engines …")
    sentiment_engine      = SentimentEngine()
    reputation_engine     = ReputationEngine(sentiment_engine)
    crowd_engine          = CrowdPredictionEngine()
    crowd_weights         = {r["location_id"]: r["weight"]
                             for r in crowd_engine.predict_now()}
    recommendation_engine = RecommendationEngine(crowd_weights=crowd_weights)
    logger.info("All engines ready ✓")


# ─── Schemas ───────────────────────────────────────────────────────────────────

class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)

class ReviewBatch(BaseModel):
    reviews: list[dict]   # {text, user_id, created_at, category}

class RecommendRequest(BaseModel):
    user_id:  str
    type:     str = "all"   # study_space | cafe | event | all
    n:        int = Field(5, ge=1, le=20)
    context:  Optional[dict] = None

class InteractionRequest(BaseModel):
    user_id:  str
    venue_id: str
    rating:   float = Field(..., ge=1, le=5)
    tags:     list[str] = []

class DietaryRequest(BaseModel):
    user_id:  str
    dietary:  list[str]

class CrowdRequest(BaseModel):
    horizon_minutes: int = Field(0, ge=0, le=240)
    event_flags:     Optional[dict[str, int]] = None

class TrainRequest(BaseModel):
    csv_path: str


# ─── Sentiment endpoints ────────────────────────────────────────────────────────

@app.post("/sentiment/predict", tags=["Sentiment"])
async def predict_sentiment(req: SentimentRequest):
    """Predict sentiment label + confidence for a single review."""
    return sentiment_engine.predict(req.text)


@app.post("/sentiment/reputation", tags=["Sentiment"])
async def compute_reputation(batch: ReviewBatch):
    """
    Compute weighted reputation score for a venue from a batch of reviews.
    Includes anti-spam, temporal weighting, and trending analysis.
    """
    return reputation_engine.compute_score(batch.reviews)


# ─── Recommendation endpoints ──────────────────────────────────────────────────

@app.post("/recommend", tags=["Recommendations"])
async def get_recommendations(req: RecommendRequest):
    """Return personalised venue recommendations."""
    # Refresh crowd weights before every recommendation call
    crowd_weights = {r["location_id"]: r["weight"]
                     for r in crowd_engine.predict_now()}
    recommendation_engine.update_crowd_weights(crowd_weights)

    results = recommendation_engine.recommend(
        user_id=req.user_id,
        rec_type=req.type,
        n=req.n,
        context=req.context,
    )
    return {"recommendations": results, "generated_at": datetime.utcnow().isoformat()}


@app.post("/recommend/interaction", tags=["Recommendations"])
async def record_interaction(req: InteractionRequest):
    """Record a user interaction to update their preference model."""
    recommendation_engine.record_interaction(
        req.user_id, req.venue_id, req.rating, req.tags
    )
    return {"status": "ok"}


@app.post("/recommend/dietary", tags=["Recommendations"])
async def set_dietary(req: DietaryRequest):
    """Set dietary restrictions for a user."""
    recommendation_engine.set_dietary(req.user_id, req.dietary)
    return {"status": "ok", "dietary": req.dietary}


# ─── Crowd prediction endpoints ────────────────────────────────────────────────

@app.post("/crowd/predict", tags=["Crowd Prediction"])
async def predict_crowd(req: CrowdRequest):
    """Predict crowd levels for all campus locations at a given horizon."""
    results = crowd_engine.predict_now(
        horizon_minutes=req.horizon_minutes,
        event_flags=req.event_flags,
    )
    return {"predictions": results, "generated_at": datetime.utcnow().isoformat()}


@app.get("/crowd/graph-weights", tags=["Crowd Prediction"])
async def get_graph_weights():
    """
    Return current crowd weights formatted for the navigation graph algorithm.
    Schema: [{x, y, weight, location_id}]
    """
    return {"weights": crowd_engine.get_graph_weights(),
            "generated_at": datetime.utcnow().isoformat()}


@app.get("/crowd/horizon", tags=["Crowd Prediction"])
async def get_crowd_horizon():
    """Return crowd predictions for the next 4 hours (15-min intervals)."""
    snapshots = crowd_engine.predict_horizon()
    return {"snapshots": snapshots, "interval_minutes": 15}


@app.post("/crowd/train", tags=["Crowd Prediction"])
async def train_crowd_model(req: TrainRequest, background_tasks: BackgroundTasks):
    """Trigger background re-training of the crowd prediction model."""
    def _train():
        crowd_engine.train(req.csv_path)
        logger.info("Crowd model re-trained ✓")
    background_tasks.add_task(_train)
    return {"status": "training started", "csv_path": req.csv_path}


@app.post("/crowd/generate-synthetic", tags=["Crowd Prediction"])
async def generate_synthetic(days: int = 60):
    """Generate synthetic training data for crowd model testing."""
    path = CrowdPredictionEngine.generate_synthetic_data(days=days)
    return {"status": "ok", "path": path, "days": days}


# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "engines": {
            "sentiment":      sentiment_engine is not None,
            "recommendation": recommendation_engine is not None,
            "crowd":          crowd_engine is not None,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
