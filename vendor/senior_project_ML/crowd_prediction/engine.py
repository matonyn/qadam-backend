"""
crowd_prediction/engine.py
──────────────────────────
ML-Based Crowd Prediction for Smart Campus

Outputs a weight table:
  [(location_id, x, y, predicted_crowd_weight: 0.0–1.0)]

These weights feed directly into the navigation backend's graph algorithm
so that crowded corridors receive higher traversal costs.

Architecture:
- Primary:  LightGBM regression on time-series features (hour, weekday,
            semester week, weather, known events)
- Fallback: Rule-based statistical model using historical mean profiles
- Scheduler: predictions refresh every 15 minutes via APScheduler

Training data format (CSV):
  timestamp,location_id,occupancy_count,capacity
"""

from __future__ import annotations

import json
import pickle
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import lightgbm as lgb
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False
    logger.warning("LightGBM not available – falling back to statistical model")

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import TimeSeriesSplit
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from config import (
    CAMPUS_LOCATIONS,
    CROWD_HORIZON_HOURS,
    CROWD_INTERVAL_MIN,
    HIGH_CROWD_THRESHOLD,
    MEDIUM_CROWD_THRESHOLD,
    CROWD_MODEL_PATH,
)

warnings.filterwarnings("ignore")


# ─── Feature engineering ───────────────────────────────────────────────────────

SEMESTER_START = datetime(2025, 1, 20)   # spring 2025; see config.SEMESTER_STARTS for all

# Real NU class-start hours (75-min slots): 08:00 09:30 11:00 12:30 14:00 15:30 17:00
NU_CLASS_START_HOURS = [8, 9, 11, 12, 14, 15, 17]
NU_CLASS_END_HOURS   = [9, 10, 12, 13, 15, 16, 18]
NU_LUNCH_HOURS       = [12, 13]

def extract_features(dt: datetime, location_id: str, event_flag: int = 0) -> dict:
    """
    Build feature dict for a single (timestamp, location) pair.
    All features are static/time-derivable so they can be used for inference
    without live sensor data.
    """
    week_of_semester = max(0, (dt - SEMESTER_START).days // 7)
    loc_data = CAMPUS_LOCATIONS.get(location_id, (0, 0, "", "general", "UNK", "1", 30))
    cat = loc_data[3]

    return {
        "hour":             dt.hour,
        "minute":           dt.minute,
        "weekday":          dt.weekday(),          # 0=Mon, 6=Sun
        "is_weekend":       int(dt.weekday() >= 5),
        "week_of_semester": week_of_semester,
        "month":            dt.month,
        # Cyclic encoding of hour (avoids discontinuity at midnight)
        "hour_sin":         np.sin(2 * np.pi * dt.hour / 24),
        "hour_cos":         np.cos(2 * np.pi * dt.hour / 24),
        "dow_sin":          np.sin(2 * np.pi * dt.weekday() / 7),
        "dow_cos":          np.cos(2 * np.pi * dt.weekday() / 7),
        # Location identity (one-hot via categoricals in LightGBM)
        "location_id":      location_id,
        "location_cat":     cat,
        "loc_x":            loc_data[0],
        "loc_y":            loc_data[1],
        # Event flag (injected from event calendar)
        "event_flag":       event_flag,
        # Derived
        # NU-specific time flags
        "is_class_start":   int(dt.hour in NU_CLASS_START_HOURS),
        "is_class_end":     int(dt.hour in NU_CLASS_END_HOURS),
        "is_lunch":         int(dt.hour in NU_LUNCH_HOURS),
        "is_morning_rush":  int(8 <= dt.hour <= 9),
        "is_evening":       int(17 <= dt.hour <= 19),
    }


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Build full feature matrix from raw occupancy dataframe."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["occupancy_rate"] = df["occupancy_count"] / df["capacity"].clip(lower=1)
    df["occupancy_rate"] = df["occupancy_rate"].clip(0, 1)

    rows = []
    for _, row in df.iterrows():
        feats = extract_features(row["timestamp"], row["location_id"],
                                 event_flag=row.get("event_flag", 0))
        feats["target"] = row["occupancy_rate"]
        rows.append(feats)

    feat_df = pd.DataFrame(rows)

    # Lag features (previous 1-4 intervals per location)
    feat_df = feat_df.sort_values(["location_id", "timestamp"] if "timestamp" in feat_df.columns else "location_id")
    for loc_id, group in feat_df.groupby("location_id"):
        for lag in [1, 2, 4]:
            feat_df.loc[group.index, f"lag_{lag}"] = group["target"].shift(lag).values

    feat_df.fillna(method="bfill", inplace=True)
    return feat_df


# ─── LightGBM Model ────────────────────────────────────────────────────────────

class CrowdLGBM:
    CAT_FEATURES = ["location_id", "location_cat"]
    DROP_COLS    = ["target"]

    def __init__(self):
        self.model:  Optional[lgb.Booster]  = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_cols: list[str] = []

    def fit(self, df: pd.DataFrame):
        if not LGBM_AVAILABLE:
            logger.error("LightGBM not installed")
            return

        feat_df = build_feature_matrix(df)
        X = feat_df.drop(columns=self.DROP_COLS + (["timestamp"] if "timestamp" in feat_df.columns else []))
        y = feat_df["target"]
        self.feature_cols = list(X.columns)

        # Encode categoricals
        for col in self.CAT_FEATURES:
            if col in X.columns:
                X[col] = X[col].astype("category")

        tscv = TimeSeriesSplit(n_splits=5)
        params = {
            "objective":     "regression",
            "metric":        "mae",
            "num_leaves":    63,
            "learning_rate": 0.05,
            "n_estimators":  500,
            "min_child_samples": 20,
            "subsample":     0.8,
            "colsample_bytree": 0.8,
            "random_state":  42,
            "verbose":       -1,
        }

        maes, r2s = [], []
        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(50, verbose=False)],
                categorical_feature=self.CAT_FEATURES,
            )
            preds = model.predict(X_val)
            maes.append(mean_absolute_error(y_val, preds))
            r2s.append(r2_score(y_val, preds))

        logger.info(f"CV MAE: {np.mean(maes):.4f} ± {np.std(maes):.4f}")
        logger.info(f"CV R²:  {np.mean(r2s):.4f}")

        # Final model on all data
        self.model = lgb.LGBMRegressor(**params)
        self.model.fit(X, y, categorical_feature=self.CAT_FEATURES)

    def predict_single(self, dt: datetime, location_id: str,
                       event_flag: int = 0, lag_values: Optional[list[float]] = None) -> float:
        if not self.model:
            return 0.5   # unknown

        feats = extract_features(dt, location_id, event_flag)
        if lag_values:
            for i, lag in enumerate([1, 2, 4]):
                feats[f"lag_{lag}"] = lag_values[i] if i < len(lag_values) else 0.3

        row = pd.DataFrame([feats])
        for col in self.CAT_FEATURES:
            if col in row.columns:
                row[col] = row[col].astype("category")

        # Align columns
        for col in self.feature_cols:
            if col not in row.columns:
                row[col] = 0.0
        row = row[self.feature_cols]

        pred = float(self.model.predict(row)[0])
        return float(np.clip(pred, 0.0, 1.0))

    def save(self, path: str = CROWD_MODEL_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Saved crowd model → {path}")

    @staticmethod
    def load(path: str = CROWD_MODEL_PATH) -> "CrowdLGBM":
        with open(path, "rb") as f:
            return pickle.load(f)


# ─── Rule-based Fallback ───────────────────────────────────────────────────────

# Mean occupancy profiles per (category, weekday, hour) based on domain knowledge
# Format: {(category, weekday 0-6, hour 0-23): mean_occupancy_rate}
RULE_PROFILES: dict[tuple, float] = {}

def _populate_rule_profiles():
    """
    Encode crowd patterns calibrated to the real NU Astana schedule.

    NU class slots (75 min):  08:00  09:30  11:00  12:30  14:00  15:30  17:00
    Class-transition rush windows (elevators/escalators): each class-start/end hour.
    Lunch peak: 12:00–13:00.
    """
    # ── helpers ───────────────────────────────────────────────────────────────
    def pat(base: float, peaks: dict) -> dict:
        p = {h: base for h in range(24)}
        p.update(peaks)
        return p

    # ── Elevators & escalators  ───────────────────────────────────────────────
    # Heavy rush exactly at NU class transitions: 8,9,11,12,14,15,17,18
    elevator_pattern = pat(0.15, {
        8: 0.70, 9: 0.88, 10: 0.30,
        11: 0.82, 12: 0.75, 13: 0.40,
        14: 0.80, 15: 0.85, 16: 0.35,
        17: 0.88, 18: 0.70, 19: 0.35,
        7: 0.30,
    })

    # ── Escalators  (slightly lower than elevators – students spread across) ──
    escalator_pattern = {h: elevator_pattern[h] * 0.85 for h in range(24)}

    # ── Atrium  (B12A – through-traffic + social) ──────────────────────────────
    # Busy at every inter-class window AND lunch
    atrium_pattern = pat(0.20, {
        8: 0.55, 9: 0.80, 10: 0.40,
        11: 0.72, 12: 0.85, 13: 0.75,
        14: 0.65, 15: 0.78, 16: 0.45,
        17: 0.82, 18: 0.65, 19: 0.35,
    })

    # ── Cafés  (Atrium coffee house, Library café, Sports café) ───────────────
    cafe_pattern = pat(0.10, {
        8: 0.50, 9: 0.60, 10: 0.35,
        11: 0.40, 12: 0.88, 13: 0.82,
        14: 0.35, 15: 0.45, 16: 0.50,
        17: 0.40, 18: 0.35, 19: 0.25,
    })

    # ── Canteens  (B4 main, dorm canteens) ────────────────────────────────────
    # B4 main closes 19:00, dorm D1 open 24h
    canteen_pattern = pat(0.10, {
        8: 0.65, 9: 0.55, 10: 0.25,
        11: 0.35, 12: 0.95, 13: 0.90,
        14: 0.30, 15: 0.20, 16: 0.20,
        17: 0.50, 18: 0.65, 19: 0.45,
        20: 0.30, 21: 0.20,
    })

    # ── Library study spaces  ─────────────────────────────────────────────────
    # NU library: 07:00–23:00; peaks during study hours between classes
    study_pattern = pat(0.15, {
        8: 0.30, 9: 0.40, 10: 0.65,
        11: 0.60, 12: 0.35,   # most go to lunch
        13: 0.55, 14: 0.70,
        15: 0.65, 16: 0.75,
        17: 0.68, 18: 0.72,
        19: 0.70, 20: 0.65,
        21: 0.50, 22: 0.30,
    })

    # ── Seminar / lecture rooms ────────────────────────────────────────────────
    # Occupancy during class hours only; empty between slots
    lecture_pattern = pat(0.05, {
        8: 0.95, 9: 0.10, 10: 0.05,
        11: 0.92, 12: 0.10, 13: 0.05,
        14: 0.95, 15: 0.10, 16: 0.05,
        17: 0.92, 18: 0.10,
    })

    # ── Dorm elevators ────────────────────────────────────────────────────────
    # Peak: morning 07–09 (leaving for class) + evening 17–20 (returning)
    dorm_elev_pattern = pat(0.15, {
        7: 0.70, 8: 0.85, 9: 0.55, 10: 0.20,
        12: 0.30, 13: 0.35,
        17: 0.60, 18: 0.80, 19: 0.75, 20: 0.55,
        22: 0.30, 23: 0.25,
    })

    # ── Transition nodes (skywalks, corridors) ─────────────────────────────────
    transition_pattern = {h: atrium_pattern[h] * 0.75 for h in range(24)}

    # ── Sports / Athletic ─────────────────────────────────────────────────────
    sports_pattern = pat(0.05, {
        7: 0.35, 8: 0.25, 9: 0.20,
        12: 0.40, 13: 0.50,
        17: 0.65, 18: 0.80, 19: 0.75, 20: 0.55, 21: 0.30,
    })

    # ── Fill RULE_PROFILES ────────────────────────────────────────────────────
    category_patterns = {
        "elevator":      elevator_pattern,
        "escalator":     escalator_pattern,
        "atrium":        atrium_pattern,
        "cafe":          cafe_pattern,
        "canteen":       canteen_pattern,
        "study_space":   study_pattern,
        "lecture_hall":  lecture_pattern,
        "seminar_room":  lecture_pattern,
        "dorm_elevator": dorm_elev_pattern,
        "transition":    transition_pattern,
        "sports":        sports_pattern,
    }

    for weekday in range(5):   # Mon–Fri (full academic day)
        for cat, pattern in category_patterns.items():
            for h in range(24):
                RULE_PROFILES[(cat, weekday, h)] = pattern[h]

    for weekday in range(5, 7):  # Sat–Sun
        # Saturday: library + sports active, classes mostly absent
        # Sunday: very quiet everywhere
        sat_factor = 0.45 if weekday == 5 else 0.20
        for cat, pattern in category_patterns.items():
            for h in range(24):
                base = pattern[h]
                if cat in ("study_space", "sports", "cafe"):
                    RULE_PROFILES[(cat, weekday, h)] = base * sat_factor
                elif cat in ("lecture_hall", "seminar_room", "elevator", "escalator"):
                    RULE_PROFILES[(cat, weekday, h)] = base * (sat_factor * 0.3)
                elif cat == "canteen":
                    RULE_PROFILES[(cat, weekday, h)] = base * sat_factor * 0.6
                else:
                    RULE_PROFILES[(cat, weekday, h)] = base * sat_factor * 0.5

_populate_rule_profiles()


class RuleBasedFallback:
    """Statistical rule model for when ML is unavailable or under-performs."""

    def predict(self, dt: datetime, location_id: str) -> float:
        loc_data = CAMPUS_LOCATIONS.get(location_id)
        if not loc_data:
            return 0.3
        cat     = loc_data[3]
        weekday = dt.weekday()
        hour    = dt.hour
        base    = RULE_PROFILES.get((cat, weekday, hour), 0.3)
        # Add small gaussian noise to avoid perfectly flat predictions
        noise   = np.random.normal(0, 0.03)
        return float(np.clip(base + noise, 0.0, 1.0))


# ─── Master Crowd Engine ───────────────────────────────────────────────────────

class CrowdPredictionEngine:
    """
    Combines ML and rule-based models.
    Exposes predict_weights() → list[dict] consumed by navigation backend.
    """

    MAE_THRESHOLD = 0.15   # fallback to rule-based if MAE exceeds this

    def __init__(self, model_path: str = CROWD_MODEL_PATH):
        self.lgbm     = None
        self.fallback = RuleBasedFallback()
        self._use_ml  = False

        if Path(model_path).exists():
            try:
                self.lgbm    = CrowdLGBM.load(model_path)
                self._use_ml = True
                logger.info("ML crowd model loaded")
            except Exception as e:
                logger.warning(f"Could not load ML model: {e} – using rule-based")

    def train(self, csv_path: str, save_path: str = CROWD_MODEL_PATH):
        """Train the LightGBM model from historical occupancy CSV."""
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        self.lgbm = CrowdLGBM()
        self.lgbm.fit(df)
        self.lgbm.save(save_path)
        self._use_ml = True

    def predict_now(
        self,
        horizon_minutes: int = 0,
        event_flags: Optional[dict[str, int]] = None,
    ) -> list[dict]:
        """
        Predict crowd weights for all campus locations.

        Args:
            horizon_minutes: 0 = now, 15 = 15 min ahead, etc.
            event_flags:     {location_id: 1} for locations near active events

        Returns:
            [{"location_id", "x", "y", "label", "category",
              "weight", "level", "predicted_at"}]
        """
        target_dt   = datetime.utcnow() + timedelta(minutes=horizon_minutes)
        event_flags = event_flags or {}
        results     = []

        for loc_id, loc_data in CAMPUS_LOCATIONS.items():
            x, y, label, category, building, floors, capacity = loc_data
            if self._use_ml and self.lgbm:
                weight = self.lgbm.predict_single(
                    target_dt, loc_id,
                    event_flag=event_flags.get(loc_id, 0),
                )
            else:
                weight = self.fallback.predict(target_dt, loc_id)

            level = (
                "high"   if weight >= HIGH_CROWD_THRESHOLD else
                "medium" if weight >= MEDIUM_CROWD_THRESHOLD else
                "low"
            )
            results.append({
                "location_id":   loc_id,
                "x":             x,
                "y":             y,
                "label":         label,
                "category":      category,
                "building":      building,
                "floors":        floors,
                "capacity":      capacity,
                "weight":        round(weight, 4),
                "level":         level,
                "predicted_at":  target_dt.isoformat(),
                "horizon_min":   horizon_minutes,
            })

        return results

    def predict_horizon(self, hours: int = CROWD_HORIZON_HOURS) -> list[list[dict]]:
        """
        Return predictions for every CROWD_INTERVAL_MIN interval
        up to `hours` ahead.
        """
        snapshots = []
        for minute in range(0, hours * 60, CROWD_INTERVAL_MIN):
            snapshots.append(self.predict_now(horizon_minutes=minute))
        return snapshots

    def get_graph_weights(self) -> list[dict]:
        """
        Thin wrapper: returns the current weight table in the format
        expected by the navigation backend graph algorithm.

        Schema: {x, y, weight}  where weight ∈ [0, 1]
        """
        current = self.predict_now(horizon_minutes=0)
        return [
            {"x": r["x"], "y": r["y"], "weight": r["weight"],
             "location_id": r["location_id"]}
            for r in current
        ]

    # ── Synthetic data generator for testing ──────────────────────────────────

    @staticmethod
    def generate_synthetic_data(
        days: int = 60,
        output_path: str = "data/synthetic_occupancy.csv",
    ):
        """
        Generate realistic synthetic occupancy data for model training.
        Uses the rule profiles + noise to simulate sensor readings.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        rows = []
        base_dt = datetime.utcnow() - timedelta(days=days)
        fb = RuleBasedFallback()

        for day in range(days):
            dt = base_dt + timedelta(days=day)
            for hour in range(7, 23):
                for minute in range(0, 60, CROWD_INTERVAL_MIN):
                    ts = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    for loc_id, loc_data in CAMPUS_LOCATIONS.items():
                        x, y, label, cat, building, floors, capacity = loc_data
                        rate = fb.predict(ts, loc_id)
                        rows.append({
                            "timestamp":       ts.isoformat(),
                            "location_id":     loc_id,
                            "occupancy_count": int(rate * capacity),
                            "capacity":        capacity,
                            "event_flag":      0,
                        })

        pd.DataFrame(rows).to_csv(output_path, index=False)
        logger.info(f"Synthetic data saved → {output_path} ({len(rows)} rows)")
        return output_path
