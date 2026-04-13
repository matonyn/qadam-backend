# Smart Campus ML Backend
### Nazarbayev University — Smart Campus Navigation App
**53 Kabanbay Batyr Ave, Nura District, Astana, Kazakhstan**

> ML/AI component of the NU Smart Campus mobile application.
> Provides sentiment analysis of campus reviews, personalised venue recommendations,
> real-time crowd prediction, and a live analytics dashboard —
> all served as a single FastAPI backend.

---

## File Structure

```
smart_campus/
│
├── config.py                        ← Single source of truth for all campus data
│                                      (buildings, rooms, elevators, escalators,
│                                       venues, ML constants)
│
├── main.py                          ← FastAPI app — all REST endpoints
├── requirements.txt
│
├── sentiment/
│   ├── scraper.py                   ← Selenium 2GIS scraper (+ mock mode)
│   └── engine.py                    ← RuBERT fine-tuning · inference · reputation
│
├── recommendation/
│   └── engine.py                    ← ALS collaborative + content-based hybrid
│
├── crowd_prediction/
│   └── engine.py                    ← LightGBM time-series · NU-schedule rule fallback
│
├── analytics/
│   └── dashboard.py                 ← Dash dashboard (4 tabs, auto-refresh)
│
└── tests/
    └── test_all.py                  ← 48 unit + topology tests (zero model downloads)
```

---

## Campus Data  (`config.py`)

All campus geography is defined in `CAMPUS_LOCATIONS` — a single dict consumed by
every engine. Each entry follows this 7-field schema:

```python
"location_id": (x, y, human_label, category, building_code, floors, capacity)
```

### Buildings modelled

| Code | Name | Key locations |
|------|------|---------------|
| **B1 / C1** | Main Building (5F) | 2 elevators, 3 escalator flights, seminar rooms 1101–3302 |
| **B12A** | New Atrium (glass spine) | 3 escalator flights (GF→1F→2F→3F), Atrium Coffee House |
| **C2 / BC2** | Auditorium Block | Main Aud (1460), Orange Hall (450), Blue Hall (230), Green Hall (230); 2 elevators, escalator |
| **B3** | SEDS wing A (4F) | Elevator, lobby escalator, rooms 3101–3401 |
| **B4** | Canteen Building | Main canteen (300 cap ground + 200 upper), elevator |
| **B5 / 5E** | Library + IT (5F) | 2 elevators, lobby escalator, Library Café, study spaces 2F–4F, 5 group rooms (≤6 persons, bookable) |
| **C3 / BC3** | GSB / GSPP / GSE | Elevator, seminar rooms C3-101 to C3-301 |
| **B7** | SEDS wing B / SSH | Elevator, seminar rooms, large lecture hall (120) |
| **B8** | SSH wing B | Elevator, Room 8502 (F5, near elevator) |
| **B9 / C4** | NURIS / student labs | Elevator, lab F1 |
| **B34** | Sports Center (6000 m²) | Elevator, Sports Complex Café |
| **B35** | Athletic Center | Elevator |
| **D1–D7** | Student dormitories (7/10/12-storey) | 2 elevators per block, ground-floor canteens |
| **B38-39 / B44-45** | Faculty residential (Skywalk → C2) | 2 elevators per block, Coffee House, Skywalk node |

### Location categories

| Category | Used for |
|----------|----------|
| `elevator` | Academic building lifts (weight = 2.5 × crowd) |
| `escalator` | Moving stairs in B1, Atrium, C2, B3, B5 (weight = 2.0 ×) |
| `atrium` | B12A through-traffic nodes (weight = 1.0 ×) |
| `cafe` | Coffee houses — Atrium, Library, Sports Complex, Res. B44 |
| `canteen` | B4 main, D1 (24/7), D2, D3 Corner Meal |
| `study_space` | Library floors 2–4, group rooms, Atrium 1F/2F |
| `lecture_hall` | C2 halls, B3/B7 lecture rooms |
| `seminar_room` | Numbered rooms (1101, 3302, 8502 …) |
| `dorm_elevator` | D1–D7 + B38/B44 lifts (weight = 2.5 ×) |
| `transition` | Skywalks, main corridors, campus entrance |
| `sports` | B34 / B35 |

### Room numbering convention
```
BFNN  →  B = block number · F = floor · NN = room on that floor
3302  →  Block 3, Floor 3, Room 02  (near stairs — confirmed from NU Researcher Links doc)
8502  →  Block 8, Floor 5, Room 02  (near elevator — confirmed from 2015 conference doc)
1101  →  Block 1, Floor 1, Room 01
```

---

## Component 1 · Sentiment Analysis Engine  (`sentiment/`)

| | |
|---|---|
| **Base model** | `blanchefort/rubert-base-cased-sentiment-rusentiment` (Russian BERT) |
| **Data source** | 2GIS reviews scraped with Selenium — NU Astana venues (cafés, canteens, library, dorms) |
| **Fallback** | Russian lexicon rule-based classifier (no model download needed) |
| **Target metric** | 85 %+ precision / recall |
| **Anti-spam** | Character n-gram near-duplicate detection + per-user daily flood limit (5 reviews/day) |
| **Temporal weighting** | Exponential decay, 90-day half-life |
| **Trending** | Compares last 30 days vs. older reviews → "up" / "stable" / "down" |

### Data collection → training pipeline

```bash
# 1. Scrape campus reviews from 2GIS (requires Chrome installed)
python -m sentiment.scraper \
    --query "Назарбаев Университет кафе атриум Астана" \
    --category cafe \
    --max 500 \
    --out data/raw_reviews.json

# Run with --mock to generate synthetic data without a browser
python -m sentiment.scraper --mock --max 200 --out data/raw_reviews.json

# 2. Fine-tune (GPU recommended; CPU works but slow)
python - <<'EOF'
from sentiment.engine import SentimentTrainer
SentimentTrainer().train("data/raw_reviews.json", epochs=4)
EOF
# Saves model → models/sentiment_finetuned/
# Prints classification_report to stdout and models/sentiment_finetuned/eval_report.txt
```

### API

```
POST /sentiment/predict          { "text": "Отличный кофе!" }
POST /sentiment/reputation       { "reviews": [{text, user_id, created_at, category}, …] }
```

---

## Component 2 · Recommendation Engine  (`recommendation/`)

| | |
|---|---|
| **CF model** | ALS (Alternating Least Squares) — `implicit` library |
| **Content model** | Tag cosine similarity with user preference vector |
| **Blend** | 55 % CF + 45 % content-based |
| **Cold start** | Falls back to pure content when user has no interaction history |
| **Context** | Crowd levels · opening hours · time-of-day · dietary restrictions |
| **Preference learning** | Bayesian mean update on each recorded interaction |

All venues come from `config.VENUES` (single source of truth with `building` + `floor`).

Recommendation result includes:
```json
{
  "venue_id": "b5_study_3f",
  "name": "Library Study Space 3F",
  "type": "study_space",
  "building": "B5",
  "floor": "3",
  "score": 0.812,
  "crowd_level": 0.34,
  "open_hours": "07:00–23:00",
  "tags": ["quiet", "wifi", "outlets", "solo", "circulation_desk"],
  "dietary": [],
  "capacity": 80,
  "explanation": "matches your preference for quiet, wifi; currently quiet; B5, Floor 3"
}
```

### API

```
POST /recommend                  { "user_id": "u1", "type": "study_space", "n": 5 }
POST /recommend/interaction      { "user_id": "u1", "venue_id": "atrium_cafe", "rating": 4 }
POST /recommend/dietary          { "user_id": "u1", "dietary": ["halal", "vegetarian"] }
```

`type` options: `study_space` · `cafe` · `canteen` · `lecture_hall` · `sports` · `all`

---

## Component 3 · Crowd Prediction  (`crowd_prediction/`)

| | |
|---|---|
| **Primary model** | LightGBM regression (time-series features) |
| **Features** | Hour & weekday (cyclic sin/cos), semester week, NU class-start flags, event flags, lag values |
| **Fallback** | Expert rule-based profiles calibrated to NU's real timetable |
| **Output** | `{x, y, weight: 0–1, location_id}` table for navigation graph |
| **Horizon** | Up to 4 hours ahead, 15-min resolution |

### NU class schedule encoded in rule-based fallback

Real NU slots (75 min): `08:00 · 09:30 · 11:00 · 12:30 · 14:00 · 15:30 · 17:00`

Elevator/escalator profiles spike at class-transition hours; canteens peak at 12:00–13:00;
lecture halls are ~95 % full during slots and ~5 % between them; dorm elevators peak
07:00–09:00 (students leaving) and 17:00–20:00 (returning).

### Navigation backend integration

```
GET /crowd/graph-weights
→ [{"x": 8, "y": 20, "weight": 0.88, "location_id": "b1_escalator_1f_2f"}, …]
```

Use in your graph algorithm:
```python
edge_cost = base_distance * (1 + crowd_weight * CROWD_SENSITIVITY[category])
# CROWD_SENSITIVITY: elevator=2.5, escalator=2.0, transition=1.8, canteen=1.5, cafe=1.3
```

Poll this endpoint every **15 minutes** and update edge weights before routing.

### Generate data → train → predict

```bash
# Generate 60 days of synthetic occupancy CSV
curl -X POST "http://localhost:8000/crowd/generate-synthetic?days=60"

# Train LightGBM on it (background task)
curl -X POST http://localhost:8000/crowd/train \
     -H "Content-Type: application/json" \
     -d '{"csv_path": "data/synthetic_occupancy.csv"}'

# Get current graph weights
curl http://localhost:8000/crowd/graph-weights

# Get 4-hour horizon (15-min intervals)
curl http://localhost:8000/crowd/horizon
```

---

## Component 4 · Analytics Dashboard  (`analytics/`)

Run standalone:
```bash
python -m analytics.dashboard
# → http://localhost:8050
```

| Tab | Content |
|-----|---------|
| **Overview** | DAU / MAU chart, feature usage (navigation, recommendations, reviews), review volume |
| **Sentiment** | Positive % trend by venue category (café, canteen, study space, …); sentiment mix bar chart |
| **Crowd Prediction** | Live campus heatmap (colour = occupancy %; auto-refreshes every 60 s); sorted legend |
| **Adoption Metrics** | DAU/MAU with stickiness overlay; 30-day feature funnel |

The dashboard reads from the same `config.CAMPUS_LOCATIONS` so the heatmap always
reflects the full NU topology. In production, swap `_gen_crowd_snapshot()` with a call
to `CrowdPredictionEngine().get_graph_weights()`.

---

## Running the API

```bash
# Install dependencies
pip install -r requirements.txt

# Start API (port 8000)
uvicorn main:app --reload --port 8000

# Interactive docs
open http://localhost:8000/docs
```

### All endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sentiment/predict` | Single review sentiment |
| `POST` | `/sentiment/reputation` | Batch venue reputation score |
| `POST` | `/recommend` | Personalised venue recommendations |
| `POST` | `/recommend/interaction` | Record user interaction |
| `POST` | `/recommend/dietary` | Set dietary restrictions |
| `POST` | `/crowd/predict` | Crowd predictions at given horizon |
| `GET`  | `/crowd/graph-weights` | Current weights for navigation graph |
| `GET`  | `/crowd/horizon` | 4-hour forecast (15-min steps) |
| `POST` | `/crowd/train` | Trigger background model training |
| `POST` | `/crowd/generate-synthetic` | Generate training CSV |
| `GET`  | `/health` | Engine status check |

---

## Running Tests

```bash
cd smart_campus
pytest tests/ -v

# 48 tests — all run without downloading any model or browser
# Covers: sentiment engine, reputation/anti-spam, recommendations,
#         crowd prediction, NU campus topology validation
```

### Test groups

| Class | Tests | What it checks |
|-------|-------|----------------|
| `TestSentimentEngine` | 5 | RU text classification, batch, edge cases |
| `TestReputationEngine` | 5 | Score range, spam flood, duplicate detection, trending, temporal decay |
| `TestRecommendationEngine` | 7 | Return count, required fields, dietary filter, study-space filter, interaction recording, crowd penalty, closed-venue exclusion |
| `TestCrowdPrediction` | 8 | All locations returned, weight range, levels, graph schema, horizon, synthetic data |
| `TestFeatureEngineering` | 2 | Cyclic features, NU-specific flags |
| `TestScraper` | 3 | Mock review count, star→label mapping, save/load roundtrip |
| `TestNUCampusConfig` | **18** | All buildings present, 7-field tuples, capacities, C2 hall sizes, library group rooms, escalator buildings, dorm elevators, NU class-hour crowd spikes, weekend quietness, canteen lunch peak, lecture-room empty-between-slots, graph weight completeness, sensitivity coverage |

---

## Environment Variables  (`.env`)

```env
SENTIMENT_MODEL_PATH=models/sentiment_finetuned
CROWD_MODEL_PATH=models/crowd_lgbm.pkl
ANALYTICS_DB_URL=sqlite+aiosqlite:///data/analytics.db
```

---

## Data Flow

```
2GIS (Selenium)
    │ scraped reviews (RU text + star rating)
    ▼
sentiment/scraper.py  ──►  data/raw_reviews.json
    │
    ▼
sentiment/engine.py   ──►  Fine-tuned RuBERT  ──►  POST /sentiment/predict
                      ──►  ReputationEngine   ──►  POST /sentiment/reputation
                                                        │ crowd_weights
crowd_prediction/     ──►  LightGBM / Rules   ──►  GET  /crowd/graph-weights ◄─────────┐
engine.py                                                │                               │
                                                         ▼                               │
recommendation/       ──►  ALS + content      ──►  POST /recommend ────────────────────►│
engine.py                                                                                │
                                                                                  Navigation Backend
analytics/            ──►  Dash (port 8050)   ──►  Live heatmap, sentiment trends,      │
dashboard.py                                        DAU/MAU, adoption funnel             │
                                                                                         │
Mobile App  ◄──  FastAPI (port 8000)  ◄─────────────────────────────────────────────────┘
```
