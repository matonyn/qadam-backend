from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notifs = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.date.desc()).all()
    return schemas.ApiResponse(success=True, data=[_notif_out(n) for n in notifs])


@router.patch("/read-all", response_model=schemas.ApiResponse[None])
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.read == False,
    ).update({"read": True})
    db.commit()
    return schemas.ApiResponse(success=True, data=None)


@router.patch("/{notif_id}/read", response_model=schemas.ApiResponse[None])
def mark_read(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    n = db.query(models.Notification).filter(
        models.Notification.id == notif_id,
        models.Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    n.read = True
    db.commit()
    return schemas.ApiResponse(success=True, data=None)
