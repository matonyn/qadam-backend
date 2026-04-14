from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import auth as authlib
from .schemas import (
    ApiResponse,
    AuthPayload,
    LanguageUpdateRequest,
    LoginRequest,
    ReadAllNotificationsResponse,
    RegisterRequest,
    ReviewCreateRequest,
    RoutingRequest,
    SimpleOk,
    ThemeUpdateRequest,
    User,
)
from .storage import StoredUser, db


app = FastAPI(title="Qadam API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ml_base_url() -> str:
    return os.getenv("ML_API_URL", "").rstrip("/")


async def _ml_request(method: str, path: str, *, json: Any | None = None) -> Any:
    base = _ml_base_url()
    if not base:
        raise HTTPException(status_code=503, detail="ML service not configured (set ML_API_URL)")
    url = f"{base}{path}"
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(method, url, json=json)
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"ML service unreachable: {e.__class__.__name__}") from e
    if resp.status_code >= 400:
        detail = None
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:500]
        raise HTTPException(status_code=502, detail={"ml_status": resp.status_code, "ml_body": detail})
    return resp.json()


def _user_to_schema(u: StoredUser) -> User:
    return User(
        id=u.id,
        email=u.email,
        firstName=u.firstName,
        lastName=u.lastName,
        studentId=u.studentId,
        avatar=u.avatar,
        createdAt=u.createdAt,
    )


def require_user(authorization: Optional[str] = Header(default=None)) -> StoredUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    payload = authlib.decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = payload.get("sub")
    if not user_id or user_id not in db.users_by_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return db.users_by_id[user_id]


@app.get("/health", response_model=ApiResponse[SimpleOk])
def health() -> ApiResponse[SimpleOk]:
    return ApiResponse(success=True, data=SimpleOk(ok=True))


@app.get("/ml/health", response_model=ApiResponse[dict])
async def ml_health() -> ApiResponse[dict]:
    data = await _ml_request("GET", "/health")
    return ApiResponse(success=True, data=data)


@app.post("/auth/register", response_model=ApiResponse[AuthPayload])
def register(body: RegisterRequest) -> ApiResponse[AuthPayload]:
    email = body.email.lower()
    if email in db.users_by_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = f"user-{uuid.uuid4().hex[:8]}"
    stored = StoredUser(
        id=user_id,
        email=email,
        password_hash=authlib.hash_password(body.password),
        firstName=body.firstName,
        lastName=body.lastName,
        studentId=body.studentId,
        avatar=f"https://i.pravatar.cc/150?u={user_id}",
        createdAt=db.now(),
    )
    db.users_by_email[email] = stored
    db.users_by_id[user_id] = stored

    access = authlib.create_access_token(subject=user_id, expires_in_seconds=3600)
    refresh = authlib.create_refresh_token(subject=user_id)

    return ApiResponse(
        success=True,
        data=AuthPayload(
            accessToken=access,
            refreshToken=refresh,
            expiresIn=3600,
            user=_user_to_schema(stored),
        ),
    )


@app.post("/auth/login", response_model=ApiResponse[AuthPayload])
def login(body: LoginRequest) -> ApiResponse[AuthPayload]:
    email = body.email.lower()
    user = db.users_by_email.get(email)
    if not user or not authlib.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = authlib.create_access_token(subject=user.id, expires_in_seconds=3600)
    refresh = authlib.create_refresh_token(subject=user.id)

    return ApiResponse(
        success=True,
        data=AuthPayload(
            accessToken=access,
            refreshToken=refresh,
            expiresIn=3600,
            user=_user_to_schema(user),
        ),
    )


@app.get("/profile", response_model=ApiResponse[User])
def get_profile(user: StoredUser = Depends(require_user)) -> ApiResponse[User]:
    return ApiResponse(success=True, data=_user_to_schema(user))


@app.patch("/profile/theme", response_model=ApiResponse[SimpleOk])
def set_theme(_: ThemeUpdateRequest, user: StoredUser = Depends(require_user)) -> ApiResponse[SimpleOk]:
    return ApiResponse(success=True, data=SimpleOk(ok=True))


@app.patch("/profile/language", response_model=ApiResponse[SimpleOk])
def set_language(_: LanguageUpdateRequest, user: StoredUser = Depends(require_user)) -> ApiResponse[SimpleOk]:
    return ApiResponse(success=True, data=SimpleOk(ok=True))


@app.get("/events", response_model=ApiResponse[list[dict]])
def list_events(user: StoredUser = Depends(require_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(success=True, data=[])


@app.get("/maps/buildings", response_model=ApiResponse[list[dict]])
def list_buildings(user: StoredUser = Depends(require_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(success=True, data=[])


@app.get("/discounts", response_model=ApiResponse[list[dict]])
def list_discounts(user: StoredUser = Depends(require_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(success=True, data=[])


@app.get("/study-rooms", response_model=ApiResponse[list[dict]])
def list_study_rooms(user: StoredUser = Depends(require_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(success=True, data=[])


@app.post("/reviews", response_model=ApiResponse[dict])
def create_review(body: ReviewCreateRequest, user: StoredUser = Depends(require_user)) -> ApiResponse[dict]:
    review = {
        "id": f"review-{uuid.uuid4().hex[:8]}",
        "targetType": body.targetType,
        "targetId": body.targetId,
        "rating": body.rating,
        "text": body.text,
        "author": {"id": user.id, "firstName": user.firstName, "lastName": user.lastName},
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    return ApiResponse(success=True, data=review)


@app.get("/notifications", response_model=ApiResponse[list[dict]])
def list_notifications(user: StoredUser = Depends(require_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(success=True, data=db.notifications_by_user.get(user.id, []))


@app.patch("/notifications/read-all", response_model=ApiResponse[ReadAllNotificationsResponse])
def read_all_notifications(user: StoredUser = Depends(require_user)) -> ApiResponse[ReadAllNotificationsResponse]:
    existing = db.notifications_by_user.get(user.id, [])
    updated = len(existing)
    db.notifications_by_user[user.id] = []
    return ApiResponse(success=True, data=ReadAllNotificationsResponse(updated=updated))


@app.post("/routing/calculate", response_model=ApiResponse[dict])
def calculate_route(body: RoutingRequest, user: StoredUser = Depends(require_user)) -> ApiResponse[dict]:
    return ApiResponse(
        success=True,
        data={
            "fromBuildingId": body.fromBuildingId,
            "toBuildingId": body.toBuildingId,
            "etaMinutes": 8,
            "distanceMeters": 620,
            "steps": [],
        },
    )


# ── ML proxy endpoints (powered by vendor/senior_project_ML) ───────────────────


@app.post("/ml/sentiment/predict", response_model=ApiResponse[dict])
async def ml_sentiment_predict(payload: dict, user: StoredUser = Depends(require_user)) -> ApiResponse[dict]:
    """
    Proxies to ML service: POST /sentiment/predict
    Expected payload: {"text": "..."}
    """
    data = await _ml_request("POST", "/sentiment/predict", json=payload)
    return ApiResponse(success=True, data=data)


@app.post("/ml/recommend", response_model=ApiResponse[dict])
async def ml_recommend(payload: dict, user: StoredUser = Depends(require_user)) -> ApiResponse[dict]:
    """
    Proxies to ML service: POST /recommend
    Expected payload: {"user_id": "...", "type": "all", "n": 5, "context": {...}}
    """
    data = await _ml_request("POST", "/recommend", json=payload)
    return ApiResponse(success=True, data=data)


@app.post("/ml/crowd/predict", response_model=ApiResponse[dict])
async def ml_crowd_predict(payload: dict, user: StoredUser = Depends(require_user)) -> ApiResponse[dict]:
    """
    Proxies to ML service: POST /crowd/predict
    Expected payload: {"horizon_minutes": 0, "event_flags": {...}}
    """
    data = await _ml_request("POST", "/crowd/predict", json=payload)
    return ApiResponse(success=True, data=data)

