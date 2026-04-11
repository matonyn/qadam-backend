from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, EmailStr

T = TypeVar("T")


# ── Generic response wrapper ────────────────────────────────────────────────

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    message: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    firstName: str
    lastName: str
    studentId: str


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class LogoutRequest(BaseModel):
    refreshToken: str


class UpdateProfileRequest(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class UserOut(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
    studentId: str
    avatar: Optional[str] = None
    createdAt: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int
    user: UserOut


# ── Maps ─────────────────────────────────────────────────────────────────────

class BuildingOut(BaseModel):
    id: str
    name: str
    shortName: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    floors: int
    hasElevator: bool
    hasRamp: bool
    category: str
    imageUrl: Optional[str] = None

    class Config:
        from_attributes = True


class RoomOut(BaseModel):
    id: str
    buildingId: str
    name: str
    floor: int
    type: str
    capacity: Optional[int] = None
    accessible: bool

    class Config:
        from_attributes = True


class NearbyBuilding(BaseModel):
    id: str
    name: str
    shortName: str
    latitude: float
    longitude: float
    distanceMeters: float
    category: str


class MapSearchResult(BaseModel):
    buildings: list[BuildingOut]
    rooms: list[RoomOut]


# ── Routing ──────────────────────────────────────────────────────────────────

class Waypoint(BaseModel):
    latitude: float
    longitude: float


class Location(BaseModel):
    latitude: float
    longitude: float
    name: str


class RouteOut(BaseModel):
    id: str
    startLocation: Location
    endLocation: Location
    distance: int
    duration: int
    isAccessible: bool
    crowdLevel: str
    waypoints: list[Waypoint]
    instructions: list[str]


class CalculateRouteRequest(BaseModel):
    startLat: float
    startLng: float
    endLat: float
    endLng: float
    preference: str = "shortest"


class SaveRouteRequest(BaseModel):
    routeId: str


class RerouteRequest(BaseModel):
    routeId: str
    currentLat: float
    currentLng: float


# ── Events ───────────────────────────────────────────────────────────────────

class CampusEventOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    buildingId: Optional[str] = None
    startDate: str
    endDate: str
    category: str
    organizer: str
    isRegistrationRequired: bool
    registrationUrl: Optional[str] = None
    imageUrl: Optional[str] = None

    class Config:
        from_attributes = True


class EventRegistrationOut(BaseModel):
    registrationId: str
    eventId: str
    userId: str
    registeredAt: str


# ── Discounts ────────────────────────────────────────────────────────────────

class DiscountOut(BaseModel):
    id: str
    vendorName: str
    vendorLogo: Optional[str] = None
    title: str
    description: Optional[str] = None
    discountPercentage: int
    category: str
    validUntil: str
    code: Optional[str] = None
    terms: Optional[str] = None
    isVerified: bool

    class Config:
        from_attributes = True


class VerifyEligibilityRequest(BaseModel):
    studentId: str


class EligibilityResult(BaseModel):
    eligible: bool
    reason: Optional[str] = None


# ── Reviews ──────────────────────────────────────────────────────────────────

class ReviewOut(BaseModel):
    id: str
    userId: str
    userName: str
    userAvatar: Optional[str] = None
    targetId: str
    targetType: str
    targetName: str
    rating: int
    comment: Optional[str] = None
    sentiment: str
    helpful: int
    createdAt: str

    class Config:
        from_attributes = True


class CreateReviewRequest(BaseModel):
    targetId: str
    targetType: str
    targetName: str
    rating: int
    comment: Optional[str] = None


class ReportReviewRequest(BaseModel):
    reason: str


class HelpfulResult(BaseModel):
    helpful: int


# ── Academic ─────────────────────────────────────────────────────────────────

class CourseScheduleItem(BaseModel):
    day: str
    startTime: str
    endTime: str
    room: str
    buildingId: str


class CourseOut(BaseModel):
    id: str
    code: str
    name: str
    credits: int
    grade: Optional[str] = None
    gradePoints: Optional[float] = None
    semester: str
    instructor: str
    schedule: list[CourseScheduleItem]

    class Config:
        from_attributes = True


class AcademicPlanOut(BaseModel):
    totalCreditsRequired: int
    creditsCompleted: int
    creditsInProgress: int
    gpa: float
    standing: str
    expectedGraduation: str
    major: str
    minor: Optional[str] = None

    class Config:
        from_attributes = True


# ── Planner ──────────────────────────────────────────────────────────────────

class PlannerEventOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    date: str
    startTime: str
    endTime: str
    type: str
    location: Optional[str] = None
    buildingId: Optional[str] = None
    color: str
    isRecurring: bool
    reminderMinutes: Optional[int] = None

    class Config:
        from_attributes = True


class CreatePlannerEventRequest(BaseModel):
    title: str
    description: Optional[str] = None
    date: str
    startTime: str
    endTime: str
    type: str
    location: Optional[str] = None
    buildingId: Optional[str] = None
    color: str = "#3B82F6"
    isRecurring: bool = False
    reminderMinutes: Optional[int] = None


class UpdatePlannerEventRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    buildingId: Optional[str] = None
    color: Optional[str] = None
    isRecurring: Optional[bool] = None
    reminderMinutes: Optional[int] = None


# ── Study Rooms ──────────────────────────────────────────────────────────────

class StudyRoomOut(BaseModel):
    id: str
    buildingId: str
    buildingName: str
    name: str
    floor: int
    capacity: int
    amenities: list[str]
    isAvailable: bool
    currentOccupancy: int
    noiseLevel: str
    imageUrl: Optional[str] = None

    class Config:
        from_attributes = True


class TimeSlot(BaseModel):
    startTime: str
    endTime: str
    available: bool


class BookRoomRequest(BaseModel):
    date: str
    startTime: str
    endTime: str


class BookingOut(BaseModel):
    id: str
    roomId: str
    userId: str
    date: str
    startTime: str
    endTime: str
    status: str

    class Config:
        from_attributes = True


# ── Settings ─────────────────────────────────────────────────────────────────

class NotificationSettings(BaseModel):
    events: bool = True
    discounts: bool = True
    classReminders: bool = True
    campusAlerts: bool = True


class AccessibilitySettings(BaseModel):
    preferAccessibleRoutes: bool = False
    highContrast: bool = False
    largeText: bool = False


class PrivacySettings(BaseModel):
    shareLocation: bool = True
    anonymousMode: bool = False


class UserSettingsOut(BaseModel):
    notifications: NotificationSettings
    accessibility: AccessibilitySettings
    privacy: PrivacySettings
    language: str
    theme: str


class UpdateSettingsRequest(BaseModel):
    notifications: Optional[dict] = None
    accessibility: Optional[dict] = None
    privacy: Optional[dict] = None
    language: Optional[str] = None
    theme: Optional[str] = None


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationAction(BaseModel):
    screen: str
    params: dict


class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    type: str
    date: str
    read: bool
    action: Optional[NotificationAction] = None

    class Config:
        from_attributes = True
