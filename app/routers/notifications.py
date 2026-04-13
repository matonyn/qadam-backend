from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notif_out(n: models.Notification) -> schemas.NotificationOut:
    return schemas.NotificationOut(
        id=n.id,
        title=n.title,
        message=n.message,
        type=n.type,
        date=n.date.isoformat() + "Z" if n.date else "",
        read=n.read,
        action=schemas.NotificationAction(**n.action) if n.action else None,
    )


@router.get("", response_model=schemas.ApiResponse[list[schemas.NotificationOut]])
def get_notifications(
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = (
        sb.table("notifications")
        .select("*")
        .eq("user_id", current_user.id)
        .order("date", desc=True)
        .execute()
    )
    notifs = [models.Notification.from_row(r) for r in (res.data or [])]
    return schemas.ApiResponse(success=True, data=[_notif_out(n) for n in notifs])


@router.patch("/read-all", response_model=schemas.ApiResponse[None])
def mark_all_read(
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    sb.table("notifications").update({"read": True}).eq("user_id", current_user.id).eq("read", False).execute()
    return schemas.ApiResponse(success=True, data=None)


@router.patch("/{notif_id}/read", response_model=schemas.ApiResponse[None])
def mark_read(
    notif_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    chk = (
        sb.table("notifications")
        .select("id")
        .eq("id", notif_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    if not chk.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    sb.table("notifications").update({"read": True}).eq("id", notif_id).eq("user_id", current_user.id).execute()
    return schemas.ApiResponse(success=True, data=None)
