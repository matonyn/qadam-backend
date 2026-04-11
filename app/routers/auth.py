from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_db, get_current_user
from app.seed import seed_new_user
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


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


def _build_auth_response(db: Session, user: models.User) -> schemas.AuthResponse:
    access_token = create_access_token(user.id)
    refresh_token_str, expires_at = create_refresh_token(user.id)

    db.add(models.RefreshToken(
        user_id=user.id,
        token=refresh_token_str,
        expires_at=expires_at,
    ))
    db.commit()

    return schemas.AuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token_str,
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_out(user),
    )


@router.post("/login", response_model=schemas.ApiResponse[schemas.AuthResponse])
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return schemas.ApiResponse(success=True, data=_build_auth_response(db, user))


@router.post("/register", response_model=schemas.ApiResponse[schemas.AuthResponse])
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = models.User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.firstName,
        last_name=body.lastName,
        student_id=body.studentId,
    )
    db.add(user)
    db.flush()

    seed_new_user(db, user)

    return schemas.ApiResponse(success=True, data=_build_auth_response(db, user))


@router.post("/logout", response_model=schemas.ApiResponse[None])
def logout(
    body: schemas.LogoutRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    token_row = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == body.refreshToken,
        models.RefreshToken.user_id == current_user.id,
    ).first()
    if token_row:
        token_row.is_revoked = True
        db.commit()

    return schemas.ApiResponse(success=True, data=None)


@router.post("/refresh", response_model=schemas.ApiResponse[dict])
def refresh_token(body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refreshToken)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    token_row = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == body.refreshToken,
        models.RefreshToken.is_revoked == False,
    ).first()
    if not token_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked or not found")

    if token_row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    access_token = create_access_token(payload["sub"])
    return schemas.ApiResponse(
        success=True,
        data={"accessToken": access_token, "expiresIn": ACCESS_TOKEN_EXPIRE_MINUTES * 60},
    )


@router.get("/profile", response_model=schemas.ApiResponse[schemas.UserOut])
def get_profile(current_user: models.User = Depends(get_current_user)):
    return schemas.ApiResponse(success=True, data=_user_out(current_user))


@router.patch("/profile", response_model=schemas.ApiResponse[schemas.UserOut])
def update_profile(
    body: schemas.UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if body.firstName is not None:
        current_user.first_name = body.firstName
    if body.lastName is not None:
        current_user.last_name = body.lastName
    if body.email is not None:
        # Enforce @nu.edu.kz domain
        if not body.email.endswith("@nu.edu.kz"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email must be @nu.edu.kz")
        current_user.email = body.email

    db.commit()
    db.refresh(current_user)
    return schemas.ApiResponse(success=True, data=_user_out(current_user))


@router.post("/forgot-password", response_model=schemas.ApiResponse[None])
def forgot_password(body: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    # In production: send reset email. Here we just acknowledge.
    return schemas.ApiResponse(success=True, data=None, message="Reset link sent to email.")
