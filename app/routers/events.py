from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user
import uuid

router = APIRouter(prefix="/events", tags=["events"])


def _event_out(e: models.CampusEvent) -> schemas.CampusEventOut:
    return schemas.CampusEventOut(
        id=e.id,
        title=e.title,
        description=e.description,
        location=e.location,
        buildingId=e.building_id,
        startDate=e.start_date,
        endDate=e.end_date,
        category=e.category,
        organizer=e.organizer,
        isRegistrationRequired=e.is_registration_required,
        registrationUrl=e.registration_url,
        imageUrl=e.image_url,
    )


@router.get("", response_model=schemas.ApiResponse[list[schemas.CampusEventOut]])
def get_events(
    category: str | None = Query(None),
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.CampusEvent)
    if category:
        q = q.filter(models.CampusEvent.category == category)
    if startDate:
        q = q.filter(models.CampusEvent.start_date >= startDate)
    if endDate:
        q = q.filter(models.CampusEvent.end_date <= endDate + "T23:59:59Z")

    events = q.all()
    return schemas.ApiResponse(success=True, data=[_event_out(e) for e in events])


@router.get("/{event_id}", response_model=schemas.ApiResponse[schemas.CampusEventOut])
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    e = db.query(models.CampusEvent).filter(models.CampusEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_event_out(e))


@router.post("/{event_id}/register", response_model=schemas.ApiResponse[schemas.EventRegistrationOut])
def register_for_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    e = db.query(models.CampusEvent).filter(models.CampusEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if not e.is_registration_required:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This event does not require registration")

    existing = db.query(models.EventRegistration).filter(
        models.EventRegistration.event_id == event_id,
        models.EventRegistration.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already registered")

    reg = models.EventRegistration(
        id=str(uuid.uuid4()),
        event_id=event_id,
        user_id=current_user.id,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    return schemas.ApiResponse(
        success=True,
        data=schemas.EventRegistrationOut(
            registrationId=reg.id,
            eventId=reg.event_id,
            userId=reg.user_id,
            registeredAt=reg.registered_at.isoformat() + "Z",
        ),
    )
