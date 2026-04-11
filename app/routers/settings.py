from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app import models, schemas
from app.dependencies import get_db, get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out(s: models.UserSettings) -> schemas.UserSettingsOut:
    return schemas.UserSettingsOut(
        notifications=schemas.NotificationSettings(**(s.notifications_settings or {})),
        accessibility=schemas.AccessibilitySettings(**(s.accessibility_settings or {})),
        privacy=schemas.PrivacySettings(**(s.privacy_settings or {})),
        language=s.language or "en",
        theme=s.theme or "light",
    )


@router.get("", response_model=schemas.ApiResponse[schemas.UserSettingsOut])
def get_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == current_user.id).first()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")
    return schemas.ApiResponse(success=True, data=_settings_out(s))


@router.patch("", response_model=schemas.ApiResponse[schemas.UserSettingsOut])
def update_settings(
    body: schemas.UpdateSettingsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == current_user.id).first()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

    if body.notifications is not None:
        current = dict(s.notifications_settings or {})
        current.update(body.notifications)
        s.notifications_settings = current
        flag_modified(s, "notifications_settings")

    if body.accessibility is not None:
        current = dict(s.accessibility_settings or {})
        current.update(body.accessibility)
        s.accessibility_settings = current
        flag_modified(s, "accessibility_settings")

    if body.privacy is not None:
        current = dict(s.privacy_settings or {})
        current.update(body.privacy)
        s.privacy_settings = current
        flag_modified(s, "privacy_settings")

    if body.language is not None:
        s.language = body.language

    if body.theme is not None:
        s.theme = body.theme

    db.commit()
    db.refresh(s)
    return schemas.ApiResponse(success=True, data=_settings_out(s))
