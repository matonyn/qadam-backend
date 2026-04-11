import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    student_id = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    planner_events = relationship("PlannerEvent", back_populates="user", cascade="all, delete-orphan")
    bookings = relationship("StudyRoomBooking", back_populates="user", cascade="all, delete-orphan")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
    academic_plan = relationship("AcademicPlan", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user")
    event_registrations = relationship("EventRegistration", back_populates="user", cascade="all, delete-orphan")
    saved_routes = relationship("SavedRoute", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")


class Building(Base):
    __tablename__ = "buildings"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    short_name = Column(String, nullable=False)
    description = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    floors = Column(Integer)
    has_elevator = Column(Boolean, default=False)
    has_ramp = Column(Boolean, default=False)
    category = Column(String)
    image_url = Column(String, nullable=True)

    rooms = relationship("Room", back_populates="building")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True)
    building_id = Column(String, ForeignKey("buildings.id"), nullable=False)
    name = Column(String, nullable=False)
    floor = Column(Integer)
    type = Column(String)
    capacity = Column(Integer, nullable=True)
    accessible = Column(Boolean, default=True)

    building = relationship("Building", back_populates="rooms")


class CampusEvent(Base):
    __tablename__ = "campus_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    description = Column(String)
    location = Column(String)
    building_id = Column(String, ForeignKey("buildings.id"), nullable=True)
    start_date = Column(String)
    end_date = Column(String)
    category = Column(String)
    organizer = Column(String)
    is_registration_required = Column(Boolean, default=False)
    registration_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")


class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id = Column(String, primary_key=True, default=gen_uuid)
    event_id = Column(String, ForeignKey("campus_events.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    registered_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    event = relationship("CampusEvent", back_populates="registrations")
    user = relationship("User", back_populates="event_registrations")


class Discount(Base):
    __tablename__ = "discounts"

    id = Column(String, primary_key=True)
    vendor_name = Column(String, nullable=False)
    vendor_logo = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(String)
    discount_percentage = Column(Integer, default=0)
    category = Column(String)
    valid_until = Column(String)
    code = Column(String, nullable=True)
    terms = Column(String)
    is_verified = Column(Boolean, default=True)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    target_id = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_name = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String)
    sentiment = Column(String)
    helpful = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="reviews")
    helpful_marks = relationship("ReviewHelpful", back_populates="review", cascade="all, delete-orphan")
    reports = relationship("ReviewReport", back_populates="review", cascade="all, delete-orphan")


class ReviewHelpful(Base):
    __tablename__ = "review_helpful"

    id = Column(String, primary_key=True, default=gen_uuid)
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_review_user_helpful"),)

    review = relationship("Review", back_populates="helpful_marks")


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id = Column(String, primary_key=True, default=gen_uuid)
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    review = relationship("Review", back_populates="reports")


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    credits = Column(Integer)
    grade = Column(String, nullable=True)
    grade_points = Column(Float, nullable=True)
    semester = Column(String)
    instructor = Column(String)
    schedule = Column(JSON)

    user = relationship("User", back_populates="courses")


class AcademicPlan(Base):
    __tablename__ = "academic_plans"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    total_credits_required = Column(Integer)
    credits_completed = Column(Integer)
    credits_in_progress = Column(Integer)
    gpa = Column(Float)
    standing = Column(String)
    expected_graduation = Column(String)
    major = Column(String)
    minor = Column(String, nullable=True)

    user = relationship("User", back_populates="academic_plan")


class PlannerEvent(Base):
    __tablename__ = "planner_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    date = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    type = Column(String)
    location = Column(String, nullable=True)
    building_id = Column(String, nullable=True)
    color = Column(String)
    is_recurring = Column(Boolean, default=False)
    reminder_minutes = Column(Integer, nullable=True)

    user = relationship("User", back_populates="planner_events")


class StudyRoom(Base):
    __tablename__ = "study_rooms"

    id = Column(String, primary_key=True)
    building_id = Column(String, ForeignKey("buildings.id"), nullable=False)
    building_name = Column(String)
    name = Column(String, nullable=False)
    floor = Column(Integer)
    capacity = Column(Integer)
    amenities = Column(JSON)
    is_available = Column(Boolean, default=True)
    current_occupancy = Column(Integer, default=0)
    noise_level = Column(String)
    image_url = Column(String, nullable=True)

    bookings = relationship("StudyRoomBooking", back_populates="room", cascade="all, delete-orphan")


class StudyRoomBooking(Base):
    __tablename__ = "study_room_bookings"

    id = Column(String, primary_key=True, default=gen_uuid)
    room_id = Column(String, ForeignKey("study_rooms.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    status = Column(String, default="confirmed")
    created_at = Column(DateTime, server_default=func.now())

    room = relationship("StudyRoom", back_populates="bookings")
    user = relationship("User", back_populates="bookings")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    notifications_settings = Column(JSON)
    accessibility_settings = Column(JSON)
    privacy_settings = Column(JSON)
    language = Column(String, default="en")
    theme = Column(String, default="light")

    user = relationship("User", back_populates="user_settings")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String)
    type = Column(String)
    date = Column(DateTime, server_default=func.now())
    read = Column(Boolean, default=False)
    action = Column(JSON, nullable=True)

    user = relationship("User", back_populates="notifications")


class Route(Base):
    __tablename__ = "routes"

    id = Column(String, primary_key=True, default=gen_uuid)
    start_lat = Column(Float)
    start_lng = Column(Float)
    start_name = Column(String)
    end_lat = Column(Float)
    end_lng = Column(Float)
    end_name = Column(String)
    distance = Column(Integer)
    duration = Column(Integer)
    is_accessible = Column(Boolean)
    crowd_level = Column(String)
    waypoints = Column(JSON)
    instructions = Column(JSON)
    preference = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class SavedRoute(Base):
    __tablename__ = "saved_routes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    route_id = Column(String, ForeignKey("routes.id"), nullable=False)
    saved_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="saved_routes")
    route = relationship("Route")
