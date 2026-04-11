"""Seed the database with mock data on first run."""
from sqlalchemy.orm import Session
from app import models


BUILDINGS = [
    {"id": "bldg-001", "name": "Block 1 - Sciences", "short_name": "Block 1", "description": "Main science building with laboratories and lecture halls", "latitude": 51.0906, "longitude": 71.3989, "floors": 4, "has_elevator": True, "has_ramp": True, "category": "academic"},
    {"id": "bldg-002", "name": "Block 2 - Engineering", "short_name": "Block 2", "description": "Engineering and technology building", "latitude": 51.0912, "longitude": 71.3995, "floors": 4, "has_elevator": True, "has_ramp": True, "category": "academic"},
    {"id": "bldg-003", "name": "Block 3 - Business School", "short_name": "Block 3", "description": "Graduate School of Business", "latitude": 51.0898, "longitude": 71.3982, "floors": 3, "has_elevator": True, "has_ramp": True, "category": "academic"},
    {"id": "bldg-004", "name": "Library", "short_name": "Library", "description": "Main university library with study spaces", "latitude": 51.0904, "longitude": 71.4001, "floors": 3, "has_elevator": True, "has_ramp": True, "category": "library"},
    {"id": "bldg-005", "name": "Student Center", "short_name": "Student Center", "description": "Student services, cafeterias, and recreation", "latitude": 51.0910, "longitude": 71.4008, "floors": 2, "has_elevator": True, "has_ramp": True, "category": "dining"},
    {"id": "bldg-006", "name": "Dormitory A", "short_name": "Dorm A", "description": "Student residential building", "latitude": 51.0920, "longitude": 71.4015, "floors": 8, "has_elevator": True, "has_ramp": True, "category": "residential"},
    {"id": "bldg-007", "name": "Sports Complex", "short_name": "Sports", "description": "Gymnasium, pool, and sports facilities", "latitude": 51.0895, "longitude": 71.4020, "floors": 2, "has_elevator": False, "has_ramp": True, "category": "sports"},
    {"id": "bldg-008", "name": "Administration Building", "short_name": "Admin", "description": "University administration offices", "latitude": 51.0900, "longitude": 71.3975, "floors": 3, "has_elevator": True, "has_ramp": True, "category": "admin"},
]

ROOMS = [
    {"id": "room-001", "building_id": "bldg-001", "name": "101", "floor": 1, "type": "classroom", "capacity": 50, "accessible": True},
    {"id": "room-002", "building_id": "bldg-001", "name": "102", "floor": 1, "type": "lab", "capacity": 30, "accessible": True},
    {"id": "room-003", "building_id": "bldg-001", "name": "201", "floor": 2, "type": "classroom", "capacity": 80, "accessible": True},
    {"id": "room-004", "building_id": "bldg-001", "name": "301", "floor": 3, "type": "lab", "capacity": 25, "accessible": True},
    {"id": "room-005", "building_id": "bldg-002", "name": "105", "floor": 1, "type": "classroom", "capacity": 60, "accessible": True},
    {"id": "room-006", "building_id": "bldg-002", "name": "210", "floor": 2, "type": "lab", "capacity": 20, "accessible": True},
    {"id": "room-007", "building_id": "bldg-003", "name": "101", "floor": 1, "type": "classroom", "capacity": 100, "accessible": True},
    {"id": "room-008", "building_id": "bldg-004", "name": "Study Hall A", "floor": 1, "type": "study_room", "capacity": 40, "accessible": True},
    {"id": "room-009", "building_id": "bldg-004", "name": "Study Hall B", "floor": 2, "type": "study_room", "capacity": 30, "accessible": True},
    {"id": "room-010", "building_id": "bldg-004", "name": "Group Study 1", "floor": 2, "type": "study_room", "capacity": 8, "accessible": True},
]

CAMPUS_EVENTS = [
    {"id": "evt-001", "title": "Spring Career Fair 2026", "description": "Annual career fair featuring top employers from Kazakhstan and international companies.", "location": "Student Center, Main Hall", "building_id": "bldg-005", "start_date": "2026-04-15T10:00:00Z", "end_date": "2026-04-15T17:00:00Z", "category": "career", "organizer": "Career Center", "is_registration_required": True, "registration_url": "https://nu.edu.kz/career-fair"},
    {"id": "evt-002", "title": "AI & Machine Learning Workshop", "description": "Hands-on workshop on the latest AI technologies and their applications.", "location": "Block 2, Room 210", "building_id": "bldg-002", "start_date": "2026-04-10T14:00:00Z", "end_date": "2026-04-10T17:00:00Z", "category": "academic", "organizer": "Computer Science Department", "is_registration_required": True},
    {"id": "evt-003", "title": "Nauryz Celebration", "description": "Traditional Kazakh New Year celebration with music, food, and cultural performances.", "location": "Campus Main Square", "start_date": "2026-03-22T12:00:00Z", "end_date": "2026-03-22T20:00:00Z", "category": "cultural", "organizer": "Student Government", "is_registration_required": False},
    {"id": "evt-004", "title": "Basketball Tournament", "description": "Inter-department basketball competition. Come support your team!", "location": "Sports Complex, Main Gym", "building_id": "bldg-007", "start_date": "2026-04-05T18:00:00Z", "end_date": "2026-04-05T21:00:00Z", "category": "sports", "organizer": "Sports Club", "is_registration_required": False},
    {"id": "evt-005", "title": "Guest Lecture: Future of Renewable Energy", "description": "Distinguished lecture by Dr. Sarah Chen on sustainable energy solutions.", "location": "Block 3, Auditorium", "building_id": "bldg-003", "start_date": "2026-04-08T15:00:00Z", "end_date": "2026-04-08T17:00:00Z", "category": "academic", "organizer": "School of Engineering", "is_registration_required": False},
    {"id": "evt-006", "title": "Movie Night: Interstellar", "description": "Free outdoor movie screening. Bring your blankets!", "location": "Campus Amphitheater", "start_date": "2026-04-12T20:00:00Z", "end_date": "2026-04-12T23:00:00Z", "category": "social", "organizer": "Film Club", "is_registration_required": False},
]

DISCOUNTS = [
    {"id": "disc-001", "vendor_name": "Starbucks", "title": "15% Off All Beverages", "description": "Show your student ID to get 15% off any drink at Starbucks campus location.", "discount_percentage": 15, "category": "food", "valid_until": "2026-12-31", "terms": "Valid only at campus location. Cannot be combined with other offers.", "is_verified": True},
    {"id": "disc-002", "vendor_name": "Cinema City", "title": "Student Movie Tickets - 50% Off", "description": "Half price movie tickets for students on weekdays.", "discount_percentage": 50, "category": "entertainment", "valid_until": "2026-06-30", "code": "STUDENT50", "terms": "Valid Monday-Thursday. Not valid on holidays or special screenings.", "is_verified": True},
    {"id": "disc-003", "vendor_name": "TechZone", "title": "10% Off Electronics", "description": "Student discount on laptops, tablets, and accessories.", "discount_percentage": 10, "category": "shopping", "valid_until": "2026-08-31", "code": "NUSTUDENT10", "terms": "Valid with student ID. Some exclusions apply.", "is_verified": True},
    {"id": "disc-004", "vendor_name": "Fit Life Gym", "title": "Student Membership - 30% Off", "description": "Discounted monthly gym membership for NU students.", "discount_percentage": 30, "category": "services", "valid_until": "2026-12-31", "terms": "Valid student ID required. 6-month minimum commitment.", "is_verified": True},
    {"id": "disc-005", "vendor_name": "Pizza House", "title": "20% Off Large Pizzas", "description": "Student special on all large pizzas.", "discount_percentage": 20, "category": "food", "valid_until": "2026-05-31", "code": "NUPIZZA20", "terms": "Delivery and takeout only. Valid after 6 PM.", "is_verified": True},
    {"id": "disc-006", "vendor_name": "Kazakh Railways", "title": "Student Travel Discount - 25% Off", "description": "Discounted train tickets for students traveling within Kazakhstan.", "discount_percentage": 25, "category": "travel", "valid_until": "2026-12-31", "terms": "Valid with student ID. Economy class only.", "is_verified": True},
    {"id": "disc-007", "vendor_name": "Campus Cafe", "title": "Free Coffee Upgrade", "description": "Get a free size upgrade on any coffee drink.", "discount_percentage": 0, "category": "food", "valid_until": "2026-04-30", "terms": "Show Qadam app for discount.", "is_verified": True},
]

REVIEWS = [
    {"id": "rev-001", "user_id": "user-002", "target_id": "bldg-004", "target_type": "building", "target_name": "Library", "rating": 5, "comment": "Great study environment! The 3rd floor is perfect for quiet studying. Plenty of outlets and natural light.", "sentiment": "positive", "helpful": 24, "created_at": "2026-03-28T14:30:00Z"},
    {"id": "rev-002", "user_id": "user-003", "target_id": "bldg-005", "target_type": "cafe", "target_name": "Student Center Cafe", "rating": 4, "comment": "Good food options and reasonable prices. Can get crowded during lunch hours though.", "sentiment": "positive", "helpful": 15, "created_at": "2026-03-25T12:15:00Z"},
    {"id": "rev-003", "user_id": "user-004", "target_id": "room-010", "target_type": "room", "target_name": "Group Study Room 1", "rating": 3, "comment": "Room is nice but booking system is confusing. Wish it was easier to reserve.", "sentiment": "neutral", "helpful": 8, "created_at": "2026-03-20T16:45:00Z"},
    {"id": "rev-004", "user_id": "user-005", "target_id": "bldg-007", "target_type": "building", "target_name": "Sports Complex", "rating": 5, "comment": "Excellent facilities! The swimming pool is well maintained and the gym has modern equipment.", "sentiment": "positive", "helpful": 32, "created_at": "2026-03-18T09:00:00Z"},
    {"id": "rev-005", "user_id": "user-006", "target_id": "bldg-001", "target_type": "building", "target_name": "Block 1 - Sciences", "rating": 4, "comment": "Labs are well-equipped. Sometimes elevators are slow during class transitions.", "sentiment": "positive", "helpful": 11, "created_at": "2026-03-15T11:30:00Z"},
]

STUDY_ROOMS = [
    {"id": "study-001", "building_id": "bldg-004", "building_name": "Library", "name": "Study Hall A", "floor": 1, "capacity": 40, "amenities": ["Wi-Fi", "Power Outlets", "Natural Light", "Whiteboard"], "is_available": True, "current_occupancy": 18, "noise_level": "quiet"},
    {"id": "study-002", "building_id": "bldg-004", "building_name": "Library", "name": "Study Hall B", "floor": 2, "capacity": 30, "amenities": ["Wi-Fi", "Power Outlets", "Projector"], "is_available": True, "current_occupancy": 25, "noise_level": "quiet"},
    {"id": "study-003", "building_id": "bldg-004", "building_name": "Library", "name": "Group Study 1", "floor": 2, "capacity": 8, "amenities": ["Wi-Fi", "Whiteboard", "TV Screen", "Power Outlets"], "is_available": False, "current_occupancy": 6, "noise_level": "collaborative"},
    {"id": "study-004", "building_id": "bldg-004", "building_name": "Library", "name": "Group Study 2", "floor": 2, "capacity": 8, "amenities": ["Wi-Fi", "Whiteboard", "TV Screen", "Power Outlets"], "is_available": True, "current_occupancy": 0, "noise_level": "collaborative"},
    {"id": "study-005", "building_id": "bldg-005", "building_name": "Student Center", "name": "Open Study Area", "floor": 1, "capacity": 50, "amenities": ["Wi-Fi", "Power Outlets", "Vending Machines"], "is_available": True, "current_occupancy": 35, "noise_level": "moderate"},
    {"id": "study-006", "building_id": "bldg-001", "building_name": "Block 1", "name": "Science Commons", "floor": 1, "capacity": 20, "amenities": ["Wi-Fi", "Power Outlets", "Lab Equipment Access"], "is_available": True, "current_occupancy": 8, "noise_level": "moderate"},
]

DEFAULT_COURSES = [
    {"id": "course-001", "code": "CSCI 408", "name": "Senior Project I", "credits": 6, "grade": "A", "grade_points": 4.0, "semester": "Fall 2025", "instructor": "Dr. Askar Boranbayev", "schedule": [{"day": "monday", "startTime": "10:00", "endTime": "11:30", "room": "210", "buildingId": "bldg-002"}, {"day": "wednesday", "startTime": "10:00", "endTime": "11:30", "room": "210", "buildingId": "bldg-002"}]},
    {"id": "course-002", "code": "CSCI 390", "name": "Machine Learning", "credits": 6, "grade": "A-", "grade_points": 3.67, "semester": "Fall 2025", "instructor": "Dr. Elena Kim", "schedule": [{"day": "tuesday", "startTime": "14:00", "endTime": "15:30", "room": "301", "buildingId": "bldg-001"}, {"day": "thursday", "startTime": "14:00", "endTime": "15:30", "room": "301", "buildingId": "bldg-001"}]},
    {"id": "course-003", "code": "CSCI 361", "name": "Software Engineering", "credits": 6, "semester": "Spring 2026", "instructor": "Prof. Nurlan Omarov", "schedule": [{"day": "monday", "startTime": "14:00", "endTime": "15:30", "room": "105", "buildingId": "bldg-002"}, {"day": "wednesday", "startTime": "14:00", "endTime": "15:30", "room": "105", "buildingId": "bldg-002"}]},
    {"id": "course-004", "code": "MATH 273", "name": "Linear Algebra", "credits": 6, "grade": "B+", "grade_points": 3.33, "semester": "Fall 2025", "instructor": "Dr. Samat Yergali", "schedule": [{"day": "monday", "startTime": "09:00", "endTime": "10:30", "room": "101", "buildingId": "bldg-001"}, {"day": "friday", "startTime": "09:00", "endTime": "10:30", "room": "101", "buildingId": "bldg-001"}]},
    {"id": "course-005", "code": "CSCI 409", "name": "Senior Project II", "credits": 6, "semester": "Spring 2026", "instructor": "Dr. Askar Boranbayev", "schedule": [{"day": "tuesday", "startTime": "10:00", "endTime": "11:30", "room": "210", "buildingId": "bldg-002"}, {"day": "thursday", "startTime": "10:00", "endTime": "11:30", "room": "210", "buildingId": "bldg-002"}]},
]

DEFAULT_ACADEMIC_PLAN = {
    "total_credits_required": 240,
    "credits_completed": 198,
    "credits_in_progress": 18,
    "gpa": 3.65,
    "standing": "dean_list",
    "expected_graduation": "May 2026",
    "major": "Computer Science",
    "minor": "Data Science",
}

DEFAULT_SETTINGS = {
    "notifications_settings": {"events": True, "discounts": True, "classReminders": True, "campusAlerts": True},
    "accessibility_settings": {"preferAccessibleRoutes": False, "highContrast": False, "largeText": False},
    "privacy_settings": {"shareLocation": True, "anonymousMode": False},
    "language": "en",
    "theme": "light",
}

DEFAULT_NOTIFICATIONS = [
    {"title": "Upcoming Event", "message": "Tech Talk: AI in Healthcare starts in 1 hour at the Main Auditorium", "type": "events", "read": False, "action": {"screen": "EventDetail", "params": {"eventId": "evt-001"}}},
    {"title": "Class Reminder", "message": "Your CSCI 408 class starts in 15 minutes at Building A, Room 101", "type": "academic", "read": False, "action": {"screen": "Schedule", "params": {}}},
    {"title": "New Discount Available", "message": "Get 20% off at Campus Cafe! Valid until the end of this month.", "type": "discount", "read": True, "action": {"screen": "Discounts", "params": {}}},
    {"title": "Navigation Update", "message": "Building B entrance is temporarily closed. Alternative routes are available.", "type": "navigation", "read": True, "action": {"screen": "MapTab", "params": {}}},
]

# Stub users for review author names (not real accounts)
STUB_USERS = [
    {"id": "user-002", "first_name": "Amir", "last_name": "K.", "student_id": "stub"},
    {"id": "user-003", "first_name": "Dana", "last_name": "S.", "student_id": "stub"},
    {"id": "user-004", "first_name": "Bekzat", "last_name": "T.", "student_id": "stub"},
    {"id": "user-005", "first_name": "Gulnara", "last_name": "M.", "student_id": "stub"},
    {"id": "user-006", "first_name": "Marat", "last_name": "A.", "student_id": "stub"},
]


def seed_static_data(db: Session) -> None:
    """Seed buildings, rooms, events, discounts, study rooms if not present."""
    if db.query(models.Building).first():
        return  # already seeded

    for b in BUILDINGS:
        db.add(models.Building(**b))

    for r in ROOMS:
        db.add(models.Room(**r))

    for e in CAMPUS_EVENTS:
        db.add(models.CampusEvent(**e))

    for d in DISCOUNTS:
        db.add(models.Discount(**d))

    for sr in STUDY_ROOMS:
        db.add(models.StudyRoom(**sr))

    # Stub users needed so reviews have valid user_ids (FK constraint not enforced on SQLite by default,
    # but add them for correctness)
    for su in STUB_USERS:
        exists = db.query(models.User).filter(models.User.id == su["id"]).first()
        if not exists:
            db.add(models.User(
                id=su["id"],
                email=f"{su['id']}@stub.internal",
                password_hash="stub",
                first_name=su["first_name"],
                last_name=su["last_name"],
                student_id=su["student_id"],
            ))

    db.flush()

    for rev in REVIEWS:
        from datetime import datetime, timezone
        created = datetime.fromisoformat(rev["created_at"].replace("Z", "+00:00"))
        db.add(models.Review(
            id=rev["id"],
            user_id=rev["user_id"],
            target_id=rev["target_id"],
            target_type=rev["target_type"],
            target_name=rev["target_name"],
            rating=rev["rating"],
            comment=rev["comment"],
            sentiment=rev["sentiment"],
            helpful=rev["helpful"],
            created_at=created,
        ))

    db.commit()


def seed_new_user(db: Session, user: models.User) -> None:
    """Give a new user default courses, academic plan, settings, and notifications."""
    import uuid

    for c in DEFAULT_COURSES:
        db.add(models.Course(
            id=str(uuid.uuid4()),
            user_id=user.id,
            code=c["code"],
            name=c["name"],
            credits=c["credits"],
            grade=c.get("grade"),
            grade_points=c.get("grade_points"),
            semester=c["semester"],
            instructor=c["instructor"],
            schedule=c["schedule"],
        ))

    db.add(models.AcademicPlan(
        user_id=user.id,
        **DEFAULT_ACADEMIC_PLAN,
    ))

    db.add(models.UserSettings(
        user_id=user.id,
        **DEFAULT_SETTINGS,
    ))

    for n in DEFAULT_NOTIFICATIONS:
        db.add(models.Notification(
            user_id=user.id,
            title=n["title"],
            message=n["message"],
            type=n["type"],
            read=n["read"],
            action=n.get("action"),
        ))

    db.commit()
