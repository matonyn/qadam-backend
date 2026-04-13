from fastapi import APIRouter, Depends
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase
from app.seed import ensure_user_settings

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
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    s = ensure_user_settings(sb, current_user.id)
    return schemas.ApiResponse(success=True, data=_settings_out(s))


@router.patch("", response_model=schemas.ApiResponse[schemas.UserSettingsOut])
def update_settings(
    body: schemas.UpdateSettingsRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    s = ensure_user_settings(sb, current_user.id)

    upd: dict = {}

    if body.notifications is not None:
        current = dict(s.notifications_settings or {})
        current.update(body.notifications)
        upd["notifications_settings"] = current

    if body.accessibility is not None:
        current = dict(s.accessibility_settings or {})
        current.update(body.accessibility)
        upd["accessibility_settings"] = current

    if body.privacy is not None:
        current = dict(s.privacy_settings or {})
        current.update(body.privacy)
        upd["privacy_settings"] = current

    if body.language is not None:
        upd["language"] = body.language

    if body.theme is not None:
        upd["theme"] = body.theme

    if upd:
        sb.table("user_settings").update(upd).eq("user_id", current_user.id).execute()

    res = sb.table("user_settings").select("*").eq("user_id", current_user.id).limit(1).execute()
    row = (res.data or [{}])[0]
    s2 = models.UserSettings.from_row(row)
    return schemas.ApiResponse(success=True, data=_settings_out(s2))
