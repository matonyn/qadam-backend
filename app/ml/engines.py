from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ml_root: Path | None = None
_engines_ready = False
_init_error: str | None = None

sentiment_engine = None
reputation_engine = None
recommendation_engine = None
crowd_engine = None


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "vendor" / "senior_project_ML"


def configure_ml_path() -> Path:
    """Put the ML repo on sys.path and default model env vars to vendor paths."""
    global _ml_root
    root = _package_root()
    if not root.is_dir():
        raise FileNotFoundError(
            "ML package missing. Clone into vendor/senior_project_ML:\n"
            "  git clone https://github.com/aruryss/senior_project_ML.git vendor/senior_project_ML"
        )
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)

    models_dir = root / "models"
    os.environ.setdefault("SENTIMENT_MODEL_PATH", str(models_dir / "sentiment_finetuned"))
    os.environ.setdefault("CROWD_MODEL_PATH", str(models_dir / "crowd_lgbm.pkl"))

    _ml_root = root
    return root


def init_ml_engines() -> None:
    """Load sentiment, crowd, and recommendation engines (rule-based fallbacks if no model files)."""
    global sentiment_engine, reputation_engine, recommendation_engine, crowd_engine
    global _engines_ready, _init_error

    try:
        configure_ml_path()
        # Imports resolve against vendor/senior_project_ML (config, sentiment, …).
        from sentiment.engine import ReputationEngine, SentimentEngine
        from recommendation.engine import RecommendationEngine
        from crowd_prediction.engine import CrowdPredictionEngine

        sentiment_engine = SentimentEngine()
        reputation_engine = ReputationEngine(sentiment_engine)
        crowd_engine = CrowdPredictionEngine()
        crowd_weights = {r["location_id"]: r["weight"] for r in crowd_engine.predict_now()}
        recommendation_engine = RecommendationEngine(crowd_weights=crowd_weights)

        _engines_ready = True
        _init_error = None
        logger.info("Smart Campus ML engines initialized")
    except Exception as e:
        _init_error = repr(e)
        logger.warning("ML engines not initialized: %s", e)
        _engines_ready = False


def ml_health() -> dict:
    return {
        "ready": _engines_ready,
        "package_path": str(_ml_root) if _ml_root else None,
        "engines": {
            "sentiment": sentiment_engine is not None,
            "reputation": reputation_engine is not None,
            "recommendation": recommendation_engine is not None,
            "crowd": crowd_engine is not None,
        },
    }
