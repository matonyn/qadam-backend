"""
recommendation/engine.py
────────────────────────
AI-Driven Recommendation Engine for Smart Campus

Provides:
1. Study spot recommendations  (collaborative + content-based hybrid)
2. Dining suggestions          (dietary-aware + preference learning)
3. Event / activity recommendations (social + location-aware)
4. Context-aware suggestions   (time of day, location, crowd level)

Architecture:
- Collaborative filtering via Alternating Least Squares (ALS / implicit)
- Content-based fallback with cosine similarity
- Context vector fused at scoring time
- Preference profile updates via online learning (Bayesian mean update)
"""

from __future__ import annotations

import json
import math
import pickle
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from sklearn.preprocessing import normalize

try:
    import implicit
    IMPLICIT_AVAILABLE = True
except ImportError:
    IMPLICIT_AVAILABLE = False
    logger.warning("implicit library not available – using pure cosine fallback")

try:
    from scipy.sparse import csr_matrix
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from config import (
    NUM_FACTORS, NUM_ITERATIONS, REGULARIZATION, CAMPUS_LOCATIONS,
    VENUES, ALL_TAGS,
)


# ─── Data models ───────────────────────────────────────────────────────────────

class UserProfile:
    """Running preference model for a single user."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        # Dietary restrictions: set of strings, e.g. {"vegetarian", "halal"}
        self.dietary: set[str] = set()
        # Liked / disliked tags
        self.liked_tags:    defaultdict[str, float] = defaultdict(float)
        self.disliked_tags: defaultdict[str, float] = defaultdict(float)
        # Bayesian mean: (sum, count) per venue_id
        self._ratings: dict[str, list[float]] = defaultdict(list)
        # Visit history: [(venue_id, timestamp)]
        self.history: list[tuple[str, datetime]] = []

    def record_interaction(self, venue_id: str, rating: float, tags: list[str]):
        """Update preference model with a new explicit or implicit signal."""
        self._ratings[venue_id].append(rating)
        for tag in tags:
            if rating >= 4:
                self.liked_tags[tag] += 1
            elif rating <= 2:
                self.disliked_tags[tag] += 1
        self.history.append((venue_id, datetime.utcnow()))

    def mean_rating(self, venue_id: str) -> Optional[float]:
        ratings = self._ratings.get(venue_id)
        if not ratings:
            return None
        return float(np.mean(ratings))

    def preference_vector(self, all_tags: list[str]) -> np.ndarray:
        """Build a tag-preference vector (positive–negative)."""
        vec = np.array([
            self.liked_tags.get(t, 0) - self.disliked_tags.get(t, 0)
            for t in all_tags
        ], dtype=float)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec


# ─── Collaborative Filtering ───────────────────────────────────────────────────

class CollaborativeFilter:
    """ALS model over user×venue implicit feedback matrix."""

    def __init__(self):
        self.model = None
        self.user_index:  dict[str, int] = {}
        self.venue_index: dict[str, int] = {}
        self._item_factors: Optional[np.ndarray] = None
        self._user_factors: Optional[np.ndarray] = None

    def fit(self, interactions: list[tuple[str, str, float]]):
        """
        interactions: [(user_id, venue_id, confidence_score)]
        confidence_score = 1 + alpha * rating  (standard ALS implicit formulation)
        """
        if not IMPLICIT_AVAILABLE or not SCIPY_AVAILABLE:
            logger.warning("implicit/scipy not available – CF skipped")
            return

        users  = sorted({u for u, _, _ in interactions})
        venues = sorted({v for _, v, _ in interactions})
        self.user_index  = {u: i for i, u in enumerate(users)}
        self.venue_index = {v: i for i, v in enumerate(venues)}

        rows = [self.user_index[u] for u, _, _ in interactions]
        cols = [self.venue_index[v] for _, v, _ in interactions]
        data = [c for _, _, c in interactions]

        matrix = csr_matrix((data, (rows, cols)),
                             shape=(len(users), len(venues)),
                             dtype=np.float32)

        self.model = implicit.als.AlternatingLeastSquares(
            factors=NUM_FACTORS,
            iterations=NUM_ITERATIONS,
            regularization=REGULARIZATION,
            random_state=42,
        )
        self.model.fit(matrix)
        self._item_factors = self.model.item_factors
        self._user_factors = self.model.user_factors
        logger.info("ALS model fitted")

    def recommend(self, user_id: str, n: int = 5) -> list[tuple[str, float]]:
        if not self.model or user_id not in self.user_index:
            return []
        uid = self.user_index[user_id]
        # Build user-item matrix row (dummy – model.recommend handles this)
        ids, scores = self.model.recommend(
            uid,
            filter_already_liked_items=True,
            N=n,
        )
        venue_ids = list(self.venue_index.keys())
        return [(venue_ids[i], float(s)) for i, s in zip(ids, scores)]

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str) -> "CollaborativeFilter":
        with open(path, "rb") as f:
            return pickle.load(f)


# ─── Content-based Filter ──────────────────────────────────────────────────────

class ContentFilter:
    """Cosine similarity between user preference vector and venue tag vectors."""

    def __init__(self):
        self.venue_matrix = self._build_matrix()

    def _build_matrix(self) -> np.ndarray:
        """(num_venues × num_tags) binary matrix."""
        mat = np.zeros((len(VENUES), len(ALL_TAGS)), dtype=float)
        for i, venue in enumerate(VENUES):
            for tag in venue["tags"]:
                if tag in ALL_TAGS:
                    j = ALL_TAGS.index(tag)
                    mat[i, j] = 1.0
        return normalize(mat, norm="l2")

    def recommend(self, profile: UserProfile, n: int = 5) -> list[tuple[str, float]]:
        pref_vec = profile.preference_vector(ALL_TAGS).reshape(1, -1)
        norm = np.linalg.norm(pref_vec)
        if norm == 0:
            return [(v["id"], 0.5) for v in VENUES[:n]]
        pref_vec_norm = normalize(pref_vec, norm="l2")
        scores = (self.venue_matrix @ pref_vec_norm.T).flatten()
        top_idx = np.argsort(scores)[::-1][:n]
        return [(VENUES[i]["id"], float(scores[i])) for i in top_idx]


# ─── Context module ────────────────────────────────────────────────────────────

class ContextualScorer:
    """Adjust scores based on real-time context signals."""

    def __init__(self, crowd_weights: Optional[dict[str, float]] = None):
        # crowd_weights: {venue_id: 0.0–1.0} from crowd prediction engine
        self.crowd_weights = crowd_weights or {}

    def score(self, venue_id: str, base_score: float, context: dict) -> float:
        """
        context keys:
            hour         (int 0–23)
            user_lat     (float)
            user_lon     (float)
            dietary      (set[str])
        """
        venue = next((v for v in VENUES if v["id"] == venue_id), None)
        if not venue:
            return base_score

        boost = 0.0

        # ── Opening hours ──────────────────────────────────────────────────
        hour = context.get("hour", datetime.utcnow().hour)
        open_h, close_h = venue["open_hours"]
        if not (open_h <= hour < close_h):
            return -999.0   # closed – exclude

        # ── Dietary filter ─────────────────────────────────────────────────
        user_dietary = set(context.get("dietary", []))
        if user_dietary:
            venue_dietary = set(venue.get("dietary", []))
            missing = user_dietary - venue_dietary
            if missing and venue["type"] in ("cafe", "canteen"):
                return -999.0  # dietary hard constraint

        # ── Crowd penalty ──────────────────────────────────────────────────
        crowd = self.crowd_weights.get(venue_id, 0.3)
        boost -= crowd * 0.3   # heavier penalty for crowded venues

        # ── Time-of-day preference for study spots ─────────────────────────
        if venue["type"] == "study_space":
            if 9 <= hour <= 12 or 14 <= hour <= 17:
                boost += 0.1   # peak study hours

        return base_score + boost


# ─── Master Recommendation Engine ──────────────────────────────────────────────

class RecommendationEngine:
    """
    Hybrid recommender combining:
    - Collaborative filtering (ALS)
    - Content-based filtering (tag cosine)
    - Contextual re-ranking
    """

    CF_WEIGHT      = 0.55
    CONTENT_WEIGHT = 0.45

    def __init__(
        self,
        cf_model_path: Optional[str] = None,
        crowd_weights: Optional[dict[str, float]] = None,
    ):
        self.content_filter  = ContentFilter()
        self.contextual      = ContextualScorer(crowd_weights)
        self.profiles:       dict[str, UserProfile] = {}
        self.cf: Optional[CollaborativeFilter] = None

        if cf_model_path and Path(cf_model_path).exists():
            try:
                self.cf = CollaborativeFilter.load(cf_model_path)
                logger.info("Loaded CF model")
            except Exception as e:
                logger.warning(f"Could not load CF model: {e}")

    def _get_profile(self, user_id: str) -> UserProfile:
        if user_id not in self.profiles:
            self.profiles[user_id] = UserProfile(user_id)
        return self.profiles[user_id]

    def update_crowd_weights(self, weights: dict[str, float]):
        self.contextual.crowd_weights = weights

    # ── Interaction recording ──────────────────────────────────────────────────

    def record_interaction(self, user_id: str, venue_id: str,
                           rating: float, tags: Optional[list[str]] = None):
        profile = self._get_profile(user_id)
        venue = next((v for v in VENUES if v["id"] == venue_id), None)
        tags = tags or (venue["tags"] if venue else [])
        profile.record_interaction(venue_id, rating, tags)

    def set_dietary(self, user_id: str, dietary: list[str]):
        self._get_profile(user_id).dietary = set(dietary)

    # ── Recommendation ────────────────────────────────────────────────────────

    def recommend(
        self,
        user_id: str,
        rec_type: str = "all",   # "study_space" | "cafe" | "event" | "all"
        n: int = 5,
        context: Optional[dict] = None,
    ) -> list[dict]:
        """
        Returns list of venue dicts with recommendation scores and explanations.
        """
        context = context or {}
        profile = self._get_profile(user_id)

        # Merge dietary into context for contextual scorer
        context.setdefault("dietary", list(profile.dietary))
        context.setdefault("hour", datetime.utcnow().hour)

        # ── Content scores ──────────────────────────────────────────────────
        content_scores: dict[str, float] = dict(self.content_filter.recommend(profile, n=len(VENUES)))

        # ── CF scores ──────────────────────────────────────────────────────
        cf_raw = self.cf.recommend(user_id, n=len(VENUES)) if self.cf else []
        cf_scores: dict[str, float] = dict(cf_raw)

        # ── Blend ──────────────────────────────────────────────────────────
        all_ids = {v["id"] for v in VENUES}
        blended: dict[str, float] = {}
        for vid in all_ids:
            c_score = content_scores.get(vid, 0.0)
            f_score = cf_scores.get(vid, c_score)   # fallback to content
            blended[vid] = self.CF_WEIGHT * f_score + self.CONTENT_WEIGHT * c_score

        # ── Context re-rank ────────────────────────────────────────────────
        contextual_scores: dict[str, float] = {
            vid: self.contextual.score(vid, score, context)
            for vid, score in blended.items()
        }

        # ── Filter by type ─────────────────────────────────────────────────
        venue_map = {v["id"]: v for v in VENUES}
        filtered = {
            vid: score for vid, score in contextual_scores.items()
            if score > -900
            and (rec_type == "all" or venue_map[vid]["type"] == rec_type)
        }

        # ── Sort and format ────────────────────────────────────────────────
        top = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:n]
        results = []
        for vid, score in top:
            venue = venue_map[vid]
            crowd = self.contextual.crowd_weights.get(vid, 0.3)
            results.append({
                "venue_id":    vid,
                "name":        venue["name"],
                "type":        venue["type"],
                "building":    venue.get("building", ""),
                "floor":       venue.get("floor", ""),
                "score":       round(score, 4),
                "crowd_level": round(crowd, 2),
                "open_hours":  f"{venue['open_hours'][0]:02d}:00–{venue['open_hours'][1]:02d}:00",
                "tags":        venue["tags"],
                "dietary":     venue.get("dietary", []),
                "capacity":    venue.get("capacity", 0),
                "explanation": _explain(venue, profile, crowd, context),
            })
        return results


def _explain(venue: dict, profile: UserProfile, crowd: float, context: dict) -> str:
    """Generate a short human-readable reason for the recommendation."""
    parts = []
    shared_tags = set(venue["tags"]) & set(profile.liked_tags.keys())
    if shared_tags:
        parts.append(f"matches your preference for {', '.join(list(shared_tags)[:2])}")
    if crowd < 0.35:
        parts.append("currently quiet")
    elif crowd > 0.70:
        parts.append("heads up: busy right now")
    hour = context.get("hour", datetime.utcnow().hour)
    if hour in (12, 13) and venue["type"] in ("cafe", "canteen"):
        parts.append("good for lunch hour")
    if venue["type"] == "study_space" and 9 <= hour <= 22:
        parts.append("open for studying now")
    building = venue.get("building", "")
    floor = venue.get("floor", "")
    if building and floor:
        parts.append(f"{building}, Floor {floor}")
    return "; ".join(parts) if parts else "suggested based on campus activity"
