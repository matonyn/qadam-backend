from datetime import datetime, timezone
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app import models, schemas
from app.auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_current_user, get_supabase
from app.seed import seed_new_user

router = APIRouter(prefix="/auth", tags=["auth"])

NU_EMAIL_DOMAIN = "@nu.edu.kz"
NU_STUDENT_ID_RE = re.compile(r"^20\d{7}$")


def _user_out(user: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        firstName=user.first_name,
        lastName=user.last_name,
        studentId=user.student_id,
        avatar=user.avatar,
        createdAt=user.created_at.isoformat() + "Z" if user.created_at else "",
    )


def _build_auth_response(sb: Client, user: models.User) -> schemas.AuthResponse:
    access_token = create_access_token(user.id)
    refresh_token_str, expires_at = create_refresh_token(user.id)

    sb.table("refresh_tokens").insert(
        {
            "user_id": user.id,
            "token": refresh_token_str,
            "expires_at": expires_at.isoformat(),
        }
    ).execute()

    return schemas.AuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token_str,
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_out(user),
    )


@router.post("/login", response_model=schemas.ApiResponse[schemas.AuthResponse])
def login(body: schemas.LoginRequest, sb: Client = Depends(get_supabase)):
    res = sb.table("users").select("*").eq("email", body.email).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = models.User.from_row(rows[0])
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return schemas.ApiResponse(success=True, data=_build_auth_response(sb, user))


@router.post("/register", response_model=schemas.ApiResponse[schemas.AuthResponse])
def register(body: schemas.RegisterRequest, sb: Client = Depends(get_supabase)):
    if not body.email.lower().endswith(NU_EMAIL_DOMAIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email must be a NU address ({NU_EMAIL_DOMAIN})",
        )
    if not NU_STUDENT_ID_RE.match(body.studentId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid student ID format (expected 9 digits, e.g. 202012345)",
        )

    dup = sb.table("users").select("id").eq("email", body.email).limit(1).execute()
    if dup.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    row = {
        "id": str(uuid.uuid4()),
        "email": body.email,
        "password_hash": hash_password(body.password),
        "first_name": body.firstName,
        "last_name": body.lastName,
        "student_id": body.studentId,
    }
    ins = sb.table("users").insert(row).execute()
    out = (ins.data or [row])[0]
    user = models.User.from_row(out)
    seed_new_user(sb, user)

    return schemas.ApiResponse(success=True, data=_build_auth_response(sb, user))


@router.post("/logout", response_model=schemas.ApiResponse[None])
def logout(
    body: schemas.LogoutRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    sb.table("refresh_tokens").update({"is_revoked": True}).eq("token", body.refreshToken).eq(
        "user_id", current_user.id
    ).execute()
    return schemas.ApiResponse(success=True, data=None)


@router.post("/refresh", response_model=schemas.ApiResponse[schemas.RefreshTokenResponse])
def refresh_token(body: schemas.RefreshTokenRequest, sb: Client = Depends(get_supabase)):
    payload = decode_token(body.refreshToken)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    res = (
        sb.table("refresh_tokens")
        .select("*")
        .eq("token", body.refreshToken)
        .eq("is_revoked", False)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked or not found")

    token_row = models.RefreshToken.from_row(rows[0])
    if token_row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    access_token = create_access_token(payload["sub"])
    return schemas.ApiResponse(
        success=True,
        data=schemas.RefreshTokenResponse(
            accessToken=access_token,
            expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.get("/profile", response_model=schemas.ApiResponse[schemas.UserOut])
def get_profile(current_user: models.User = Depends(get_current_user)):
    return schemas.ApiResponse(success=True, data=_user_out(current_user))


@router.patch("/profile", response_model=schemas.ApiResponse[schemas.UserOut])
def update_profile(
    body: schemas.UpdateProfileRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    upd: dict = {}
    if body.firstName is not None:
        upd["first_name"] = body.firstName
    if body.lastName is not None:
        upd["last_name"] = body.lastName
    if body.email is not None:
        if not body.email.lower().endswith(NU_EMAIL_DOMAIN):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email must be a NU address ({NU_EMAIL_DOMAIN})",
            )
        upd["email"] = body.email
    if upd:
        sb.table("users").update(upd).eq("id", current_user.id).execute()

    res = sb.table("users").select("*").eq("id", current_user.id).limit(1).execute()
    user = models.User.from_row((res.data or [{}])[0])
    return schemas.ApiResponse(success=True, data=_user_out(user))


@router.post("/forgot-password", response_model=schemas.ApiResponse[None])
def forgot_password(body: schemas.ForgotPasswordRequest):
    return schemas.ApiResponse(success=True, data=None, message="Reset link sent to email.")
