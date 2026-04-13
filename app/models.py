"""Row types for Supabase/PostgREST responses (snake_case columns)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    s = str(v).replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fnum(x: Any) -> float | None:
    if x is None:
        return None
    return float(x)


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    first_name: str
    last_name: str
    student_id: str
    avatar: str | None
    created_at: datetime | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> User:
        return cls(
            id=r["id"],
            email=r["email"],
            password_hash=r["password_hash"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            student_id=r["student_id"],
            avatar=r.get("avatar"),
            created_at=parse_dt(r.get("created_at")),
        )


@dataclass
class RefreshToken:
    id: str
    user_id: str
    token: str
    expires_at: datetime
    is_revoked: bool
    created_at: datetime | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> RefreshToken:
        exp = parse_dt(r["expires_at"])
        if exp is None:
            raise ValueError("refresh_tokens.expires_at required")
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            token=r["token"],
            expires_at=exp,
            is_revoked=bool(r.get("is_revoked", False)),
            created_at=parse_dt(r.get("created_at")),
        )


@dataclass
class Building:
    id: str
    name: str
    short_name: str
    description: str | None
    latitude: float | None
    longitude: float | None
    floors: int | None
    has_elevator: bool
    has_ramp: bool
    category: str | None
    image_url: str | None
    twogis_id: str | None = None
    data_source: str = "manual"

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Building:
        return cls(
            id=r["id"],
            name=r["name"],
            short_name=r["short_name"],
            description=r.get("description"),
            latitude=fnum(r.get("latitude")),
            longitude=fnum(r.get("longitude")),
            floors=r.get("floors"),
            has_elevator=bool(r.get("has_elevator", False)),
            has_ramp=bool(r.get("has_ramp", False)),
            category=r.get("category"),
            image_url=r.get("image_url"),
            twogis_id=r.get("twogis_id"),
            data_source=str(r.get("data_source") or "manual"),
        )


@dataclass
class Room:
    id: str
    building_id: str
    name: str
    floor: int | None
    type: str | None
    capacity: int | None
    accessible: bool

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Room:
        return cls(
            id=r["id"],
            building_id=r["building_id"],
            name=r["name"],
            floor=r.get("floor"),
            type=r.get("type"),
            capacity=r.get("capacity"),
            accessible=bool(r.get("accessible", True)),
        )


@dataclass
class CampusEvent:
    id: str
    title: str
    description: str | None
    location: str | None
    building_id: str | None
    start_date: str | None
    end_date: str | None
    category: str | None
    organizer: str | None
    is_registration_required: bool
    registration_url: str | None
    image_url: str | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> CampusEvent:
        return cls(
            id=r["id"],
            title=r["title"],
            description=r.get("description"),
            location=r.get("location"),
            building_id=r.get("building_id"),
            start_date=r.get("start_date"),
            end_date=r.get("end_date"),
            category=r.get("category"),
            organizer=r.get("organizer"),
            is_registration_required=bool(r.get("is_registration_required", False)),
            registration_url=r.get("registration_url"),
            image_url=r.get("image_url"),
        )


@dataclass
class EventRegistration:
    id: str
    event_id: str
    user_id: str
    registered_at: datetime | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> EventRegistration:
        return cls(
            id=r["id"],
            event_id=r["event_id"],
            user_id=r["user_id"],
            registered_at=parse_dt(r.get("registered_at")),
        )


@dataclass
class Discount:
    id: str
    vendor_name: str
    vendor_logo: str | None
    title: str
    description: str | None
    discount_percentage: int
    category: str | None
    valid_until: str | None
    code: str | None
    terms: str | None
    is_verified: bool

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Discount:
        return cls(
            id=r["id"],
            vendor_name=r["vendor_name"],
            vendor_logo=r.get("vendor_logo"),
            title=r["title"],
            description=r.get("description"),
            discount_percentage=int(r.get("discount_percentage") or 0),
            category=r.get("category"),
            valid_until=r.get("valid_until"),
            code=r.get("code"),
            terms=r.get("terms"),
            is_verified=bool(r.get("is_verified", True)),
        )


@dataclass
class Review:
    id: str
    user_id: str
    target_id: str
    target_type: str
    target_name: str
    rating: int
    comment: str | None
    sentiment: str | None
    helpful: int
    created_at: datetime | None
    user: User | None = None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Review:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            target_id=r["target_id"],
            target_type=r["target_type"],
            target_name=r["target_name"],
            rating=int(r["rating"]),
            comment=r.get("comment"),
            sentiment=r.get("sentiment"),
            helpful=int(r.get("helpful") or 0),
            created_at=parse_dt(r.get("created_at")),
            user=None,
        )


@dataclass
class Course:
    id: str
    user_id: str
    code: str
    name: str
    credits: int | None
    grade: str | None
    grade_points: float | None
    semester: str | None
    instructor: str | None
    schedule: list[dict[str, Any]] | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Course:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            code=r["code"],
            name=r["name"],
            credits=r.get("credits"),
            grade=r.get("grade"),
            grade_points=fnum(r.get("grade_points")),
            semester=r.get("semester"),
            instructor=r.get("instructor"),
            schedule=r.get("schedule"),
        )


@dataclass
class AcademicPlan:
    id: str
    user_id: str
    total_credits_required: int | None
    credits_completed: int | None
    credits_in_progress: int | None
    gpa: float | None
    standing: str | None
    expected_graduation: str | None
    major: str | None
    minor: str | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> AcademicPlan:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            total_credits_required=r.get("total_credits_required"),
            credits_completed=r.get("credits_completed"),
            credits_in_progress=r.get("credits_in_progress"),
            gpa=fnum(r.get("gpa")),
            standing=r.get("standing"),
            expected_graduation=r.get("expected_graduation"),
            major=r.get("major"),
            minor=r.get("minor"),
        )


@dataclass
class PlannerEvent:
    id: str
    user_id: str
    title: str
    description: str | None
    date: str
    start_time: str
    end_time: str
    type: str | None
    location: str | None
    building_id: str | None
    color: str | None
    is_recurring: bool
    reminder_minutes: int | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> PlannerEvent:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            title=r["title"],
            description=r.get("description"),
            date=r["date"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            type=r.get("type"),
            location=r.get("location"),
            building_id=r.get("building_id"),
            color=r.get("color"),
            is_recurring=bool(r.get("is_recurring", False)),
            reminder_minutes=r.get("reminder_minutes"),
        )


@dataclass
class StudyRoom:
    id: str
    building_id: str
    building_name: str | None
    name: str
    floor: int | None
    capacity: int | None
    amenities: list[Any] | None
    is_available: bool
    current_occupancy: int
    noise_level: str | None
    image_url: str | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> StudyRoom:
        return cls(
            id=r["id"],
            building_id=r["building_id"],
            building_name=r.get("building_name"),
            name=r["name"],
            floor=r.get("floor"),
            capacity=r.get("capacity"),
            amenities=r.get("amenities"),
            is_available=bool(r.get("is_available", True)),
            current_occupancy=int(r.get("current_occupancy") or 0),
            noise_level=r.get("noise_level"),
            image_url=r.get("image_url"),
        )


@dataclass
class StudyRoomBooking:
    id: str
    room_id: str
    user_id: str
    date: str
    start_time: str
    end_time: str
    status: str
    created_at: datetime | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> StudyRoomBooking:
        return cls(
            id=r["id"],
            room_id=r["room_id"],
            user_id=r["user_id"],
            date=r["date"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            status=r.get("status") or "confirmed",
            created_at=parse_dt(r.get("created_at")),
        )


@dataclass
class UserSettings:
    id: str
    user_id: str
    notifications_settings: dict[str, Any] | None
    accessibility_settings: dict[str, Any] | None
    privacy_settings: dict[str, Any] | None
    language: str | None
    theme: str | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> UserSettings:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            notifications_settings=r.get("notifications_settings"),
            accessibility_settings=r.get("accessibility_settings"),
            privacy_settings=r.get("privacy_settings"),
            language=r.get("language"),
            theme=r.get("theme"),
        )


@dataclass
class Notification:
    id: str
    user_id: str
    title: str
    message: str | None
    type: str | None
    date: datetime | None
    read: bool
    action: dict[str, Any] | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Notification:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            title=r["title"],
            message=r.get("message"),
            type=r.get("type"),
            date=parse_dt(r.get("date")),
            read=bool(r.get("read", False)),
            action=r.get("action"),
        )


@dataclass
class Route:
    id: str
    start_lat: float | None
    start_lng: float | None
    start_name: str | None
    end_lat: float | None
    end_lng: float | None
    end_name: str | None
    distance: int | None
    duration: int | None
    is_accessible: bool | None
    crowd_level: str | None
    waypoints: list[dict[str, Any]] | None
    instructions: list[Any] | None
    preference: str | None
    created_at: datetime | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> Route:
        return cls(
            id=r["id"],
            start_lat=fnum(r.get("start_lat")),
            start_lng=fnum(r.get("start_lng")),
            start_name=r.get("start_name"),
            end_lat=fnum(r.get("end_lat")),
            end_lng=fnum(r.get("end_lng")),
            end_name=r.get("end_name"),
            distance=r.get("distance"),
            duration=r.get("duration"),
            is_accessible=r.get("is_accessible"),
            crowd_level=r.get("crowd_level"),
            waypoints=r.get("waypoints"),
            instructions=r.get("instructions"),
            preference=r.get("preference"),
            created_at=parse_dt(r.get("created_at")),
        )


@dataclass
class SavedRoute:
    id: str
    user_id: str
    route_id: str
    saved_at: datetime | None
    route: Route | None = None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> SavedRoute:
        return cls(
            id=r["id"],
            user_id=r["user_id"],
            route_id=r["route_id"],
            saved_at=parse_dt(r.get("saved_at")),
            route=None,
        )
