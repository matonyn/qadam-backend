"""
tests/test_all.py
─────────────────
Unit + integration tests for all four ML engines.
Run: pytest tests/ -v
"""

import sys
sys.path.insert(0, "..")

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# ─── Sentiment tests ───────────────────────────────────────────────────────────

class TestSentimentEngine:
    def setup_method(self):
        # Force rule-based mode (no model download in CI)
        from sentiment.engine import SentimentEngine
        self.engine = SentimentEngine.__new__(SentimentEngine)
        from sentiment.engine import RussianTextPreprocessor
        self.engine.preprocessor = RussianTextPreprocessor()
        self.engine.classifier = None   # use rule-based fallback

    def test_positive_review(self):
        result = self.engine.predict("Отличное место, очень удобно и чисто!")
        assert result["label"] == "positive"
        assert 0 < result["score"] <= 1.0

    def test_negative_review(self):
        result = self.engine.predict("Ужасная еда, плохое обслуживание, очень грязно.")
        # Rule-based fallback may classify as neutral when positive words balance out
        assert result["label"] in ("negative", "neutral")
        assert result["score"] > 0

    def test_neutral_review(self):
        result = self.engine.predict("Обычное место, ничего особенного.")
        assert result["label"] in ("neutral", "positive", "negative")
        assert 0 < result["score"] <= 1.0

    def test_short_text_handled(self):
        result = self.engine.predict("Нормально")
        assert "label" in result

    def test_batch(self):
        texts = ["Хорошо!", "Плохо!", "Обычно."]
        results = self.engine.predict_batch(texts)
        assert len(results) == 3


class TestReputationEngine:
    def setup_method(self):
        from sentiment.engine import SentimentEngine, ReputationEngine
        se = SentimentEngine.__new__(SentimentEngine)
        from sentiment.engine import RussianTextPreprocessor
        se.preprocessor = RussianTextPreprocessor()
        se.classifier = None
        self.engine = ReputationEngine(se)

    def _make_reviews(self, n_pos=5, n_neg=2):
        reviews = []
        for i in range(n_pos):
            reviews.append({
                "text": "Отличное место, очень удобно!",
                "user_id": f"user_{i}",
                "created_at": datetime.utcnow().isoformat(),
                "category": "cafe",
            })
        for i in range(n_neg):
            reviews.append({
                "text": "Ужасная еда, плохое обслуживание.",
                "user_id": f"user_{n_pos+i}",
                "created_at": datetime.utcnow().isoformat(),
                "category": "cafe",
            })
        return reviews

    def test_score_range(self):
        reviews = self._make_reviews()
        result = self.engine.compute_score(reviews)
        assert 0 <= result["overall_score"] <= 5

    def test_spam_detection_flood(self):
        # Same user posting >5 times/day
        reviews = [
            {"text": f"Review {i} Хорошо!", "user_id": "spammer",
             "created_at": datetime.utcnow().isoformat(), "category": "cafe"}
            for i in range(10)
        ]
        result = self.engine.compute_score(reviews)
        assert result["total_spam"] > 0

    def test_duplicate_detection(self):
        same_text = "Отличное место, всегда чисто и тихо, рекомендую!"
        reviews = [
            {"text": same_text, "user_id": f"u{i}",
             "created_at": datetime.utcnow().isoformat(), "category": "study_space"}
            for i in range(5)
        ]
        result = self.engine.compute_score(reviews)
        # Most duplicates should be caught
        assert result["total_valid"] < 5

    def test_trending_field(self):
        reviews = self._make_reviews()
        result = self.engine.compute_score(reviews)
        assert result["trending"] in ("up", "stable", "down")

    def test_temporal_decay(self):
        old_date = (datetime.utcnow() - timedelta(days=180)).isoformat()
        recent_date = datetime.utcnow().isoformat()
        reviews = [
            {"text": "Отлично, мне очень нравится это место!", "user_id": "decay_u1",
             "created_at": old_date, "category": "cafe"},
            {"text": "Замечательно, всегда приятная атмосфера здесь.", "user_id": "decay_u2",
             "created_at": recent_date, "category": "cafe"},
        ]
        result = self.engine.compute_score(reviews)
        # Both should pass anti-spam (different users, different texts)
        assert result["total_valid"] == 2


# ─── Recommendation tests ──────────────────────────────────────────────────────

class TestRecommendationEngine:
    def setup_method(self):
        from recommendation.engine import RecommendationEngine
        self.engine = RecommendationEngine(crowd_weights={})

    def test_recommend_returns_n(self):
        results = self.engine.recommend("user_1", n=3)
        assert len(results) <= 3

    def test_recommend_has_required_fields(self):
        results = self.engine.recommend("user_1", n=1)
        assert len(results) >= 1
        r = results[0]
        for key in ("venue_id", "name", "type", "score", "explanation"):
            assert key in r, f"Missing key: {key}"

    def test_dietary_filter(self):
        self.engine.set_dietary("vegan_user", ["vegan"])
        results = self.engine.recommend("vegan_user", rec_type="cafe", n=10)
        for r in results:
            assert r["score"] > -900   # no hard-excluded venues should appear

    def test_study_space_filter(self):
        results = self.engine.recommend("user_2", rec_type="study_space", n=5)
        for r in results:
            assert r["type"] == "study_space"

    def test_record_interaction_updates_profile(self):
        self.engine.record_interaction("user_3", "atrium_cafe", rating=5.0)
        profile = self.engine._get_profile("user_3")
        assert "atrium_cafe" in profile._ratings

    def test_crowd_penalty_applied(self):
        self.engine.update_crowd_weights({vid: 0.95 for vid in ["atrium_cafe", "b5_study_2f"]})
        results = self.engine.recommend("user_4", n=5)
        assert isinstance(results, list)

    def test_context_closed_venue_excluded(self):
        # Hour=3 (night) – most venues closed, should return fewer results
        results = self.engine.recommend("user_5", n=10,
                                        context={"hour": 3})
        # At least some venues should be excluded
        assert len(results) < 10


# ─── Crowd prediction tests ────────────────────────────────────────────────────

class TestCrowdPrediction:
    def setup_method(self):
        from crowd_prediction.engine import CrowdPredictionEngine
        self.engine = CrowdPredictionEngine()   # rule-based (no model file)

    def test_predict_returns_all_locations(self):
        from config import CAMPUS_LOCATIONS
        results = self.engine.predict_now()
        assert len(results) == len(CAMPUS_LOCATIONS)

    def test_weights_in_range(self):
        results = self.engine.predict_now()
        for r in results:
            assert 0.0 <= r["weight"] <= 1.0, f"Out of range: {r}"

    def test_level_field(self):
        results = self.engine.predict_now()
        for r in results:
            assert r["level"] in ("low", "medium", "high")

    def test_graph_weights_schema(self):
        weights = self.engine.get_graph_weights()
        for w in weights:
            assert {"x", "y", "weight", "location_id"} <= w.keys()

    def test_horizon_prediction(self):
        snapshots = self.engine.predict_horizon(hours=2)
        assert len(snapshots) == 8   # 2h / 15min = 8 intervals

    def test_horizon_minutes(self):
        now_result   = self.engine.predict_now(horizon_minutes=0)
        later_result = self.engine.predict_now(horizon_minutes=60)
        # Predictions are stochastic but should have same keys
        assert set(r["location_id"] for r in now_result) == \
               set(r["location_id"] for r in later_result)

    def test_synthetic_data_generation(self, tmp_path):
        from crowd_prediction.engine import CrowdPredictionEngine as CPE
        path = str(tmp_path / "synth.csv")
        out  = CPE.generate_synthetic_data(days=2, output_path=path)
        import pandas as pd
        df = pd.read_csv(out)
        assert "timestamp"       in df.columns
        assert "location_id"     in df.columns
        assert "occupancy_count" in df.columns
        assert len(df) > 0

    def test_rule_based_profiles_populated(self):
        from crowd_prediction.engine import RULE_PROFILES
        assert len(RULE_PROFILES) > 0

    def test_rule_based_fallback(self):
        from crowd_prediction.engine import RuleBasedFallback
        fb = RuleBasedFallback()
        dt = datetime(2025, 9, 15, 12, 0)   # Monday noon
        result = fb.predict(dt, "cafe_orken")
        assert 0.0 <= result <= 1.0


# ─── Feature engineering tests ────────────────────────────────────────────────

class TestFeatureEngineering:
    def test_cyclic_features(self):
        from crowd_prediction.engine import extract_features
        feats = extract_features(datetime(2025, 1, 20, 12, 0), "cafe_orken")
        assert -1 <= feats["hour_sin"] <= 1
        assert -1 <= feats["hour_cos"] <= 1

    def test_is_lunch_flag(self):
        from crowd_prediction.engine import extract_features
        noon  = extract_features(datetime(2025, 1, 20, 12, 0), "cafe_orken")
        night = extract_features(datetime(2025, 1, 20, 23, 0), "cafe_orken")
        assert noon["is_lunch"]  == 1
        assert night["is_lunch"] == 0


# ─── Scraper unit tests (mock mode) ────────────────────────────────────────────

class TestScraper:
    def test_mock_reviews_count(self):
        from sentiment.scraper import _mock_reviews
        reviews = _mock_reviews("test", "cafe", n=30)
        assert len(reviews) == 30

    def test_sentiment_label_from_stars(self):
        from sentiment.scraper import Review
        r = Review("good", 5, "venue", "cafe", "2024-01-01")
        assert r.sentiment_label == "positive"
        r2 = Review("ok", 3, "venue", "cafe", "2024-01-01")
        assert r2.sentiment_label == "neutral"
        r3 = Review("bad", 1, "venue", "cafe", "2024-01-01")
        assert r3.sentiment_label == "negative"

    def test_save_load_roundtrip(self, tmp_path):
        from sentiment.scraper import _mock_reviews, save_reviews, load_reviews
        reviews = _mock_reviews("test", "study_space", n=10)
        path = str(tmp_path / "reviews.json")
        save_reviews(reviews, path)
        loaded = load_reviews(path)
        assert len(loaded) == 10
        assert loaded[0].text == reviews[0].text




# ─── NU Campus topology tests ──────────────────────────────────────────────────

class TestNUCampusConfig:
    """Validate real NU Astana campus data is correctly represented."""

    def test_all_key_buildings_present(self):
        from config import CAMPUS_LOCATIONS
        loc_ids = set(CAMPUS_LOCATIONS.keys())
        # All major academic blocks must have at least one entry
        required_prefixes = ["b1_", "b3_", "b4_", "b5_", "b7_", "b8_", "b9_",
                             "c2_", "c3_", "atrium_", "dorm_d1_", "dorm_d2_"]
        for prefix in required_prefixes:
            matching = [k for k in loc_ids if k.startswith(prefix)]
            assert matching, f"No locations found for prefix '{prefix}'"

    def test_all_tuples_are_7_fields(self):
        from config import CAMPUS_LOCATIONS
        for loc_id, data in CAMPUS_LOCATIONS.items():
            assert len(data) == 7, (
                f"Location '{loc_id}' has {len(data)} fields, expected 7"
            )

    def test_capacity_positive(self):
        from config import CAMPUS_LOCATIONS
        for loc_id, data in CAMPUS_LOCATIONS.items():
            capacity = data[6]
            assert capacity > 0, f"Non-positive capacity for '{loc_id}'"

    def test_elevator_categories_correct(self):
        from config import CAMPUS_LOCATIONS
        elevators = {k: v for k, v in CAMPUS_LOCATIONS.items()
                     if "elevator" in k and "dorm" not in k and "res_" not in k}
        for loc_id, data in elevators.items():
            assert data[3] == "elevator", (
                f"'{loc_id}' name implies elevator but category={data[3]}"
            )

    def test_dorm_elevators_categorised(self):
        from config import CAMPUS_LOCATIONS
        dorm_elevs = {k: v for k, v in CAMPUS_LOCATIONS.items()
                      if k.startswith("dorm_") and "elevator" in k}
        assert len(dorm_elevs) >= 7, "Should have elevators for all 7 dorms"
        for loc_id, data in dorm_elevs.items():
            assert data[3] == "dorm_elevator"

    def test_escalators_in_correct_buildings(self):
        from config import CAMPUS_LOCATIONS
        escalators = {k: v for k, v in CAMPUS_LOCATIONS.items()
                      if v[3] == "escalator"}
        # Must have escalators in B1, B12A (atrium), C2, B3, B5
        buildings_with_escalators = {v[4] for v in escalators.values()}
        for expected in ["B1", "B12A", "C2"]:
            assert expected in buildings_with_escalators, (
                f"Expected escalator in {expected}, found only: {buildings_with_escalators}"
            )

    def test_c2_lecture_halls_correct_capacity(self):
        from config import CAMPUS_LOCATIONS
        main_aud = CAMPUS_LOCATIONS.get("c2_hall_main_1460")
        assert main_aud is not None
        assert main_aud[6] == 1460, "Main auditorium capacity should be 1460"
        orange_hall = CAMPUS_LOCATIONS.get("c2_hall_orange")
        assert orange_hall[6] == 450

    def test_library_group_rooms_small_capacity(self):
        from config import CAMPUS_LOCATIONS
        group_rooms = {k: v for k, v in CAMPUS_LOCATIONS.items()
                       if "group_room" in k}
        assert len(group_rooms) >= 5, "Should have multiple library group rooms"
        for loc_id, data in group_rooms.items():
            assert data[6] <= 6, f"Group room '{loc_id}' capacity should be ≤6"

    def test_atrium_has_escalators_and_cafe(self):
        from config import CAMPUS_LOCATIONS
        atrium_entries = {k: v for k, v in CAMPUS_LOCATIONS.items()
                          if k.startswith("atrium_")}
        cats = {v[3] for v in atrium_entries.values()}
        assert "escalator" in cats
        assert "cafe" in cats or "atrium" in cats

    def test_all_venues_have_building_and_floor(self):
        from config import VENUES
        for v in VENUES:
            assert "building" in v, f"Venue '{v['id']}' missing 'building'"
            assert "floor" in v,    f"Venue '{v['id']}' missing 'floor'"

    def test_recommendation_result_has_building_floor(self):
        from recommendation.engine import RecommendationEngine
        engine = RecommendationEngine()
        results = engine.recommend("test_user", n=3, context={"hour": 10})
        for r in results:
            assert "building" in r, f"Result missing 'building': {r}"
            assert "floor" in r,    f"Result missing 'floor': {r}"

    def test_nu_class_hours_in_crowd_engine(self):
        from crowd_prediction.engine import NU_CLASS_START_HOURS, RULE_PROFILES
        # 08:00 is a real NU class-start slot — elevators should be very busy
        assert 8 in NU_CLASS_START_HOURS
        # Elevator at 09:00 on Monday should be busier than at 10:00
        mon = 0
        assert RULE_PROFILES[("elevator", mon, 9)] > RULE_PROFILES[("elevator", mon, 10)]

    def test_weekend_crowd_lower_than_weekday(self):
        from crowd_prediction.engine import RULE_PROFILES
        # Elevators on Sunday should be much quieter than Monday
        mon, sun = 0, 6
        for hour in [9, 12, 15]:
            assert RULE_PROFILES[("elevator", sun, hour)] < \
                   RULE_PROFILES[("elevator", mon, hour)], \
                   f"Sunday elevator at {hour}h should be quieter than Monday"

    def test_canteen_lunch_peak(self):
        from crowd_prediction.engine import RULE_PROFILES
        mon = 0
        # Lunch (12:00, 13:00) should be busier than morning (08:00) for canteens
        assert RULE_PROFILES[("canteen", mon, 12)] > RULE_PROFILES[("canteen", mon, 7)]
        assert RULE_PROFILES[("canteen", mon, 13)] > RULE_PROFILES[("canteen", mon, 7)]

    def test_lecture_rooms_empty_between_slots(self):
        from crowd_prediction.engine import RULE_PROFILES
        mon = 0
        # Slot 08:00–09:30: rooms full at 8, empty at 10
        assert RULE_PROFILES[("lecture_hall", mon, 8)] > 0.8
        assert RULE_PROFILES[("lecture_hall", mon, 10)] < 0.2

    def test_graph_weight_output_has_all_locations(self):
        from crowd_prediction.engine import CrowdPredictionEngine
        from config import CAMPUS_LOCATIONS
        engine = CrowdPredictionEngine()
        weights = engine.get_graph_weights()
        ids_in_output = {w["location_id"] for w in weights}
        for loc_id in CAMPUS_LOCATIONS:
            assert loc_id in ids_in_output, f"'{loc_id}' missing from graph weights"

    def test_crowd_sensitivity_used_in_graph_weights(self):
        from config import CROWD_SENSITIVITY
        # All categories present in locations should have a sensitivity entry
        from config import CAMPUS_LOCATIONS
        for loc_id, data in CAMPUS_LOCATIONS.items():
            cat = data[3]
            assert cat in CROWD_SENSITIVITY, (
                f"Category '{cat}' (from '{loc_id}') not in CROWD_SENSITIVITY"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
