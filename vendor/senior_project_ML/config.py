"""
config.py  –  Nazarbayev University Smart Campus
53 Kabanbay Batyr Ave, Nura District, Astana, Kazakhstan

Building codes (official NU campus security map + registrar):
  B1  / C1   – Main Building (admin, classrooms, 5 floors)
  B2         – Center for Preparatory Studies (NUFYP)
  B3         – School of Engineering and Digital Sciences (SEDS) wing A
  B4         – Dedicated Canteen / Dining building
  B5  / 5E   – Library + IT Services (5 floors; group study on 2-4F)
  B6         – School of Mining and Geosciences
  B7         – SEDS wing B / School of Sciences and Humanities (SSH)
  B8         – SSH wing B
  B9  / C4   – NURIS / Astana Business Campus / student labs
  B12A       – New Atrium (glass spine, escalators, skywalks)
  BC2 / C2   – Multifunctional Auditorium Block
               (1460-seat Main Aud; 500-seat; 2×230-seat Orange/Blue/Green halls)
  BC3 / C3   – Graduate School of Business / GSPP / GSE
  BC4        – Multidisciplinary Research Center
  BS1 / S1   – Life Sciences Center (labs)
  BS4 / S4   – Energy Research Center (labs)
  B13        – Technopark
  B34        – Sports Center (6000+ m², multi-sport)
  B35        – Athletic Center
  D1–D7      – Student dormitories (7-, 10-, 12-storey)
  B38-39     – Faculty residential blocks (Skywalk to C2 Atrium)
  B44-45     – Faculty residential blocks

Room numbering: BFNN  (block, floor, room on floor)
  e.g. 3302 = Block 3, Floor 3, Room 02
       8502 = Block 8, Floor 5, Room 02  (near elevator per 2015 conference doc)
       1101 = Block 1, Floor 1, Room 01

Grid (x, y) in metres from SW corner of main atrium entrance.
North = +y, East = +x.  Proportional to published campus map.
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
#  CAMPUS_LOCATIONS
#  Each entry: id → (x, y, human_label, category, building, floors, capacity)
#  category: elevator | escalator | cafe | canteen | atrium | study_space |
#            lecture_hall | seminar_room | library | sports | dorm_elevator |
#            transition
# ══════════════════════════════════════════════════════════════════════════════

CAMPUS_LOCATIONS: dict[str, tuple] = {

    # ── Main Building B1  (5 floors) ──────────────────────────────────────────
    "b1_elevator_main":        (0,   0,  "B1 Main Elevator",              "elevator",     "B1",  "1-5", 8),
    "b1_elevator_north":       (15,  40, "B1 North Elevator",             "elevator",     "B1",  "1-5", 8),
    "b1_escalator_1f_2f":      (8,   20, "B1 Escalator 1F→2F",           "escalator",    "B1",  "1-2", 20),
    "b1_escalator_2f_3f":      (8,   22, "B1 Escalator 2F→3F",           "escalator",    "B1",  "2-3", 20),
    "b1_escalator_3f_4f":      (8,   24, "B1 Escalator 3F→4F",           "escalator",    "B1",  "3-4", 20),
    "b1_room_1101":            (-10,  5, "Room 1101 (B1 F1)",             "seminar_room", "B1",  "1",   30),
    "b1_room_1102":            (-10, 10, "Room 1102 (B1 F1)",             "seminar_room", "B1",  "1",   30),
    "b1_room_2201":            (-10, 15, "Room 2201 (B1 F2)",             "seminar_room", "B1",  "2",   30),
    "b1_room_2202":            (-10, 20, "Room 2202 (B1 F2)",             "seminar_room", "B1",  "2",   30),
    "b1_room_3301":            (-10, 25, "Room 3301 (B1 F3)",             "seminar_room", "B1",  "3",   40),
    "b1_room_3302":            (-10, 30, "Room 3302 (B1 F3, near stairs)","seminar_room", "B1",  "3",   40),

    # ── New Atrium B12A  (glass spine, escalators, skywalks) ──────────────────
    "atrium_escalator_gf_1f":  (60,   0, "Atrium Escalator GF→1F",       "escalator",    "B12A","G-1",  25),
    "atrium_escalator_1f_2f":  (60,   5, "Atrium Escalator 1F→2F",       "escalator",    "B12A","1-2",  25),
    "atrium_escalator_2f_3f":  (60,  10, "Atrium Escalator 2F→3F",       "escalator",    "B12A","2-3",  25),
    "atrium_ground":           (60, -10, "Main Atrium Ground Floor",      "atrium",       "B12A","G",   300),
    "atrium_1f":               (60,   0, "Main Atrium 1st Floor",         "atrium",       "B12A","1",   200),
    "atrium_2f":               (60,  10, "Main Atrium 2nd Floor",         "atrium",       "B12A","2",   150),
    "atrium_cafe":             (55,  -8, "Atrium Coffee House (C2 side)", "cafe",         "B12A","G",    60),

    # ── Auditorium Block C2  (major lecture/conference halls) ─────────────────
    "c2_elevator_1":          (120,   0, "C2 Elevator 1",                 "elevator",     "C2",  "1-5", 10),
    "c2_elevator_2":          (135,   0, "C2 Elevator 2",                 "elevator",     "C2",  "1-5", 10),
    "c2_escalator_main":      (127,   8, "C2 Escalator (main lobby)",     "escalator",    "C2",  "1-2", 30),
    "c2_hall_orange":         (140,  -5, "Orange Hall C2 (cap. 450)",     "lecture_hall", "C2",  "1",  450),
    "c2_hall_main_1460":      (160,   0, "Main Auditorium C2 (cap. 1460)","lecture_hall", "C2",  "1", 1460),
    "c2_hall_blue":           (140,  15, "Blue Hall C2 (cap. 230)",       "lecture_hall", "C2",  "2",  230),
    "c2_hall_green":          (140,  30, "Green Hall C2 (cap. 230)",      "lecture_hall", "C2",  "3",  230),

    # ── Block B3  (SEDS wing A, 4 floors) ─────────────────────────────────────
    "b3_elevator":            (200,  80, "B3 Elevator",                   "elevator",     "B3",  "1-4",  8),
    "b3_escalator_lobby":     (195,  75, "B3 Lobby Escalator",            "escalator",    "B3",  "1-2", 20),
    "b3_room_3101":           (185,  85, "Room 3101 (B3 F1)",             "seminar_room", "B3",  "1",   35),
    "b3_room_3201":           (185,  90, "Room 3201 (B3 F2)",             "seminar_room", "B3",  "2",   35),
    "b3_room_3301":           (185,  95, "Room 3301 (B3 F3, near stairs)","seminar_room", "B3",  "3",   40),
    "b3_lecture_3401":        (175, 100, "Lecture Hall 3401 (B3 F4)",     "lecture_hall", "B3",  "4",  100),

    # ── Block B4  (Canteen building) ──────────────────────────────────────────
    "b4_canteen_main":         (80, -60, "Main Canteen B4 (ground)",      "canteen",      "B4",  "G",  300),
    "b4_canteen_upper":        (80, -55, "Main Canteen B4 (upper)",       "canteen",      "B4",  "1",  200),
    "b4_elevator":             (85, -50, "B4 Elevator",                   "elevator",     "B4",  "1-2",  8),

    # ── Block B5/5E  (Library + IT, 5 floors; group rooms 2–4F) ──────────────
    "b5_elevator_main":       (-60,  80, "Library Elevator (main)",       "elevator",     "B5",  "1-5", 10),
    "b5_elevator_service":    (-50,  85, "Library Service Elevator",      "elevator",     "B5",  "1-5",  8),
    "b5_escalator_lobby":     (-55,  75, "Library Lobby Escalator",       "escalator",    "B5",  "1-2", 20),
    "b5_cafe":                (-65,  70, "Library Café (ground)",         "cafe",         "B5",  "G",   50),
    "b5_study_2f":            (-60,  82, "Library Study Space 2F",        "study_space",  "B5",  "2",   80),
    "b5_study_3f":            (-60,  85, "Library Study Space 3F",        "study_space",  "B5",  "3",   80),
    "b5_study_4f":            (-60,  88, "Library Study Space 4F",        "study_space",  "B5",  "4",   80),
    "b5_group_room_2f_a":     (-70,  82, "Library Group Room 2F-A (≤6)",  "study_space",  "B5",  "2",    6),
    "b5_group_room_2f_b":     (-70,  83, "Library Group Room 2F-B (≤6)",  "study_space",  "B5",  "2",    6),
    "b5_group_room_3f_a":     (-70,  85, "Library Group Room 3F-A (≤6)",  "study_space",  "B5",  "3",    6),
    "b5_group_room_3f_b":     (-70,  86, "Library Group Room 3F-B (≤6)",  "study_space",  "B5",  "3",    6),
    "b5_group_room_4f_a":     (-70,  88, "Library Group Room 4F-A (≤6)",  "study_space",  "B5",  "4",    6),

    # ── Block C3  (GSB / GSPP / GSE) ──────────────────────────────────────────
    "c3_elevator":            (230,  10, "C3 Elevator",                   "elevator",     "C3",  "1-4",  8),
    "c3_room_c3101":          (220,  15, "Room C3-101 (F1)",              "seminar_room", "C3",  "1",   40),
    "c3_room_c3201":          (220,  20, "Room C3-201 (F2)",              "seminar_room", "C3",  "2",   40),
    "c3_room_c3301":          (220,  25, "Room C3-301 (F3)",              "seminar_room", "C3",  "3",   40),

    # ── Block B7  (SEDS wing B / SSH) ─────────────────────────────────────────
    "b7_elevator":            (260,  80, "B7 Elevator",                   "elevator",     "B7",  "1-5",  8),
    "b7_room_7101":           (250,  85, "Room 7101 (B7 F1)",             "seminar_room", "B7",  "1",   35),
    "b7_room_7201":           (250,  90, "Room 7201 (B7 F2)",             "seminar_room", "B7",  "2",   35),
    "b7_lecture_large":       (270,  90, "B7 Large Lecture Hall (F2)",    "lecture_hall", "B7",  "2",  120),

    # ── Block B8  (SSH wing B) ────────────────────────────────────────────────
    "b8_elevator":            (300,  60, "B8 Elevator",                   "elevator",     "B8",  "1-5",  8),
    "b8_room_8502":           (295,  50, "Room 8502 (B8 F5, near elev.)", "seminar_room", "B8",  "5",   30),

    # ── Block B9  (NURIS / student labs) ──────────────────────────────────────
    "b9_elevator":            (180, -40, "B9 Elevator",                   "elevator",     "B9",  "1-4", 10),
    "b9_lab_floor1":          (170, -45, "B9 Student Lab (F1)",           "seminar_room", "B9",  "1",   30),

    # ── Sports / Athletic ─────────────────────────────────────────────────────
    "b34_sports_elevator":   (-120, 120, "Sports Center B34 Elevator",    "elevator",     "B34", "1-3",  8),
    "b34_sports_cafe":       (-125, 110, "Sports Complex Café",           "cafe",         "B34", "1",   50),
    "b35_athletic_elevator": (-150, 130, "Athletic Center B35 Elevator",  "elevator",     "B35", "1-2",  8),

    # ── Dormitories D1–D7 ─────────────────────────────────────────────────────
    "dorm_d1_elevator_a":   (-200, -50, "Dorm D1 Elevator A",            "dorm_elevator","D1",  "1-12", 8),
    "dorm_d1_elevator_b":   (-190, -50, "Dorm D1 Elevator B",            "dorm_elevator","D1",  "1-12", 8),
    "dorm_d1_canteen":      (-195, -60, "Dorm D1 Canteen (24/7)",        "canteen",       "D1",  "G",  120),
    "dorm_d2_elevator_a":   (-230, -50, "Dorm D2 Elevator A",            "dorm_elevator","D2",  "1-10", 8),
    "dorm_d2_elevator_b":   (-220, -50, "Dorm D2 Elevator B",            "dorm_elevator","D2",  "1-10", 8),
    "dorm_d2_canteen":      (-225, -60, "Dorm D2 Canteen",               "canteen",       "D2",  "G",  100),
    "dorm_d3_elevator_a":   (-260, -50, "Dorm D3 Elevator A",            "dorm_elevator","D3",  "1-7",  8),
    "dorm_d3_elevator_b":   (-250, -50, "Dorm D3 Elevator B",            "dorm_elevator","D3",  "1-7",  8),
    "dorm_d3_canteen":      (-255, -60, "Dorm D3 Corner Meal Canteen",   "canteen",       "D3",  "G",   80),
    "dorm_d4_elevator_a":   (-200, -90, "Dorm D4 Elevator A",            "dorm_elevator","D4",  "1-12", 8),
    "dorm_d4_elevator_b":   (-190, -90, "Dorm D4 Elevator B",            "dorm_elevator","D4",  "1-12", 8),
    "dorm_d5_elevator_a":   (-230, -90, "Dorm D5 Elevator A",            "dorm_elevator","D5",  "1-10", 8),
    "dorm_d5_elevator_b":   (-220, -90, "Dorm D5 Elevator B",            "dorm_elevator","D5",  "1-10", 8),
    "dorm_d6_elevator_a":   (-260, -90, "Dorm D6 Elevator A",            "dorm_elevator","D6",  "1-7",  8),
    "dorm_d7_elevator_a":   (-290, -90, "Dorm D7 Elevator A",            "dorm_elevator","D7",  "1-7",  8),

    # ── Faculty residential blocks (Skywalk → C2) ─────────────────────────────
    "res_38_elevator_a":     (120,-100, "Res. Block 38 Elevator A",       "dorm_elevator","B38", "1-10",10),
    "res_38_elevator_b":     (130,-100, "Res. Block 38 Elevator B",       "dorm_elevator","B38", "1-10",10),
    "res_38_skywalk":        (125, -80, "Skywalk B38→C2 Atrium",          "transition",   "B38", "1",   50),
    "res_44_elevator_a":     (160,-100, "Res. Block 44 Elevator A",       "dorm_elevator","B44", "1-12",10),
    "res_44_elevator_b":     (170,-100, "Res. Block 44 Elevator B",       "dorm_elevator","B44", "1-12",10),
    "res_44_cafe":           (155, -95, "Res. Block 44 Coffee House",     "cafe",         "B44", "G",   30),

    # ── Transition / navigation nodes ─────────────────────────────────────────
    "skywalk_b1_atrium":      (30,   0, "Skywalk B1→Atrium",              "transition",   "B12A","1",   60),
    "skywalk_atrium_c2":      (90,   0, "Skywalk Atrium→C2",              "transition",   "B12A","1",   60),
    "skywalk_atrium_b3":      (60,  50, "Skywalk Atrium→B3",              "transition",   "B12A","1",   40),
    "skywalk_atrium_b5":      (0,   50, "Skywalk Atrium→B5",              "transition",   "B12A","1",   40),
    "main_entrance_north":    (60, -80, "Main Campus Entrance (North)",   "transition",   "EXT", "G",  200),
}

# ══════════════════════════════════════════════════════════════════════════════
#  VENUES  (recommendation engine catalogue)
# ══════════════════════════════════════════════════════════════════════════════

VENUES: list[dict] = [
    # Study spaces
    {"id":"b5_study_2f",        "name":"Library Study Space 2F",       "type":"study_space",
     "building":"B5","floor":"2","tags":["quiet","wifi","outlets","solo","light"],
     "capacity":80,  "open_hours":(7,23), "dietary":[]},
    {"id":"b5_study_3f",        "name":"Library Study Space 3F",       "type":"study_space",
     "building":"B5","floor":"3","tags":["quiet","wifi","outlets","solo","circulation_desk"],
     "capacity":80,  "open_hours":(7,23), "dietary":[]},
    {"id":"b5_study_4f",        "name":"Library Study Space 4F",       "type":"study_space",
     "building":"B5","floor":"4","tags":["quiet","wifi","solo","silent_zone"],
     "capacity":80,  "open_hours":(7,23), "dietary":[]},
    {"id":"b5_group_room_2f_a", "name":"Library Group Room 2F-A",      "type":"study_space",
     "building":"B5","floor":"2","tags":["group","whiteboard","wifi","bookable"],
     "capacity":6,   "open_hours":(8,22), "dietary":[]},
    {"id":"b5_group_room_3f_a", "name":"Library Group Room 3F-A",      "type":"study_space",
     "building":"B5","floor":"3","tags":["group","whiteboard","wifi","bookable"],
     "capacity":6,   "open_hours":(8,22), "dietary":[]},
    {"id":"b5_group_room_4f_a", "name":"Library Group Room 4F-A",      "type":"study_space",
     "building":"B5","floor":"4","tags":["group","whiteboard","wifi","bookable"],
     "capacity":6,   "open_hours":(8,22), "dietary":[]},
    {"id":"atrium_1f",          "name":"Main Atrium 1st Floor",        "type":"study_space",
     "building":"B12A","floor":"1","tags":["wifi","social","light","open_space"],
     "capacity":200, "open_hours":(7,22), "dietary":[]},
    {"id":"atrium_2f",          "name":"Main Atrium 2nd Floor",        "type":"study_space",
     "building":"B12A","floor":"2","tags":["wifi","quiet","light","outlets"],
     "capacity":150, "open_hours":(7,22), "dietary":[]},
    # Cafés
    {"id":"atrium_cafe",        "name":"Atrium Coffee House",          "type":"cafe",
     "building":"B12A","floor":"G","tags":["coffee","pastries","takeaway","seating","central"],
     "capacity":60,  "open_hours":(8,21), "dietary":["vegetarian"]},
    {"id":"b5_cafe",            "name":"Library Café",                 "type":"cafe",
     "building":"B5","floor":"G","tags":["coffee","tea","quiet","solo","snacks"],
     "capacity":50,  "open_hours":(8,20), "dietary":["vegetarian","vegan"]},
    {"id":"b34_sports_cafe",    "name":"Sports Complex Café",          "type":"cafe",
     "building":"B34","floor":"1","tags":["protein","smoothies","healthy","post_workout"],
     "capacity":50,  "open_hours":(9,21), "dietary":["vegetarian","halal"]},
    {"id":"res_44_cafe",        "name":"Res. Block 44 Coffee House",   "type":"cafe",
     "building":"B44","floor":"G","tags":["coffee","cozy","evening"],
     "capacity":30,  "open_hours":(9,22), "dietary":["vegetarian"]},
    # Canteens
    {"id":"b4_canteen_main",    "name":"Main Canteen B4",              "type":"canteen",
     "building":"B4","floor":"G","tags":["hot_meals","set_menu","affordable","large"],
     "capacity":300, "open_hours":(8,19), "dietary":["vegetarian","halal"]},
    {"id":"dorm_d1_canteen",    "name":"Dorm D1 Canteen (24/7)",       "type":"canteen",
     "building":"D1","floor":"G","tags":["hot_meals","24h","halal","homestyle"],
     "capacity":120, "open_hours":(0,24), "dietary":["halal","vegetarian"]},
    {"id":"dorm_d2_canteen",    "name":"Dorm D2 Canteen",              "type":"canteen",
     "building":"D2","floor":"G","tags":["hot_meals","set_menu","affordable"],
     "capacity":100, "open_hours":(7,22), "dietary":["halal","vegetarian"]},
    {"id":"dorm_d3_canteen",    "name":"Corner Meal Canteen D3",       "type":"canteen",
     "building":"D3","floor":"G","tags":["hot_meals","fast_food","variety","casual"],
     "capacity":80,  "open_hours":(7,22), "dietary":["halal","vegetarian"]},
    # Lecture halls (tracked for crowd, rarely recommended directly)
    {"id":"c2_hall_orange",     "name":"Orange Hall C2 (450)",         "type":"lecture_hall",
     "building":"C2","floor":"1","tags":["lecture","large","av_equipped","conference"],
     "capacity":450, "open_hours":(8,22), "dietary":[]},
    {"id":"c2_hall_main_1460",  "name":"Main Auditorium C2 (1460)",    "type":"lecture_hall",
     "building":"C2","floor":"1","tags":["lecture","flagship","av_equipped"],
     "capacity":1460,"open_hours":(8,22), "dietary":[]},
    {"id":"c2_hall_blue",       "name":"Blue Hall C2 (230)",           "type":"lecture_hall",
     "building":"C2","floor":"2","tags":["lecture","seminar","av_equipped"],
     "capacity":230, "open_hours":(8,22), "dietary":[]},
    {"id":"c2_hall_green",      "name":"Green Hall C2 (230)",          "type":"lecture_hall",
     "building":"C2","floor":"3","tags":["lecture","seminar","av_equipped"],
     "capacity":230, "open_hours":(8,22), "dietary":[]},
    # Sports
    {"id":"b34_sports",         "name":"Sports Center B34",            "type":"sports",
     "building":"B34","floor":"1-3","tags":["gym","courts","wellness","active"],
     "capacity":200, "open_hours":(7,22), "dietary":[]},
]

ALL_TAGS: list[str] = sorted({t for v in VENUES for t in v["tags"]})

# ══════════════════════════════════════════════════════════════════════════════
#  2GIS SCRAPING TARGETS
# ══════════════════════════════════════════════════════════════════════════════

TWOGIS_TARGETS: list[dict] = [
    {"query": "Назарбаев Университет кафе атриум Астана",        "category": "cafe"},
    {"query": "Nazarbayev University столовая корпус Астана",    "category": "canteen"},
    {"query": "Nazarbayev University библиотека кафе Астана",    "category": "cafe"},
    {"query": "НУ общежитие столовая кампус Астана",             "category": "canteen"},
    {"query": "Nazarbayev University спорткомплекс кафе Астана", "category": "cafe"},
    {"query": "Назарбаев Университет учебные пространства",      "category": "study_space"},
]

# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULE  (NU official: 75-min slots, class starts below)
# ══════════════════════════════════════════════════════════════════════════════

SEMESTER_STARTS      = ["2025-01-20", "2025-08-25", "2026-01-19"]
CLASS_START_HOURS    = [8, 9, 11, 12, 14, 15, 17]   # rush on vertical circulation
CLASS_END_HOURS      = [9, 10, 12, 13, 15, 16, 18]
LUNCH_HOURS          = [12, 13]
EVENING_HOURS        = [17, 18, 19]

# ══════════════════════════════════════════════════════════════════════════════
#  ML CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SENTIMENT_MODEL_NAME  = "blanchefort/rubert-base-cased-sentiment-rusentiment"
SENTIMENT_MODEL_PATH  = os.getenv("SENTIMENT_MODEL_PATH", "models/sentiment_finetuned")
SENTIMENT_CATEGORIES  = ["cafe", "canteen", "study_space", "lecture_hall",
                         "library", "sports", "dorm", "general"]
SENTIMENT_LABELS      = ["negative", "neutral", "positive"]

NUM_FACTORS     = 64
NUM_ITERATIONS  = 20
REGULARIZATION  = 0.01

CROWD_MODEL_PATH       = os.getenv("CROWD_MODEL_PATH", "models/crowd_lgbm.pkl")
CROWD_HORIZON_HOURS    = 4
CROWD_INTERVAL_MIN     = 15
HIGH_CROWD_THRESHOLD   = 0.70
MEDIUM_CROWD_THRESHOLD = 0.40

# Navigation graph: edge_cost = base_distance × (1 + weight × sensitivity)
CROWD_SENSITIVITY: dict[str, float] = {
    "elevator":      2.5,
    "escalator":     2.0,
    "atrium":        1.0,
    "cafe":          1.3,
    "canteen":       1.5,
    "study_space":   1.2,
    "lecture_hall":  1.0,
    "seminar_room":  1.0,
    "transition":    1.8,
    "dorm_elevator": 2.5,
    "sports":        1.0,
}

MIN_REVIEW_LENGTH            = 10
MAX_REVIEWS_PER_USER_PER_DAY = 5
SPAM_SIMILARITY_THRESHOLD    = 0.85

ANALYTICS_DB_URL = os.getenv("ANALYTICS_DB_URL", "sqlite+aiosqlite:///data/analytics.db")
