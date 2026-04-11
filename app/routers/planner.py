from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user
import uuid

router = APIRouter(prefix="/planner", tags=["planner"])


def _event_out(e: models.PlannerEvent) -> schemas.PlannerEventOut:
    return schemas.PlannerEventOut(
        id=e.id,
        title=e.title,
        description=e.description,
        date=e.date,
        startTime=e.start_time,
        endTime=e.end_time,
        type=e.type,
        location=e.location,
        buildingId=e.building_id,
        color=e.color,
        isRecurring=e.is_recurring,
        reminderMinutes=e.reminder_minutes,
    )


@router.get("/events", response_model=schemas.ApiResponse[list[schemas.PlannerEventOut]])
def get_events(
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.PlannerEvent).filter(models.PlannerEvent.user_id == current_user.id)
    if startDate:
        q = q.filter(models.PlannerEvent.date >= startDate)
    if endDate:
        q = q.filter(models.PlannerEvent.date <= endDate)
    events = q.order_by(models.PlannerEvent.date, models.PlannerEvent.start_time).all()
    return schemas.ApiResponse(success=True, data=[_event_out(e) for e in events])


@router.post("/events", response_model=schemas.ApiResponse[schemas.PlannerEventOut])
def create_event(
    body: schemas.CreatePlannerEventRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = models.PlannerEvent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        date=body.date,
        start_time=body.startTime,
        end_time=body.endTime,
        type=body.type,
        location=body.location,
        building_id=body.buildingId,
        color=body.color,
        is_recurring=body.isRecurring,
        reminder_minutes=body.reminderMinutes,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return schemas.ApiResponse(success=True, data=_event_out(event))


@router.patch("/events/{event_id}", response_model=schemas.ApiResponse[schemas.PlannerEventOut])
def update_event(
    event_id: str,
    body: schemas.UpdatePlannerEventRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = db.query(models.PlannerEvent).filter(
        models.PlannerEvent.id == event_id,
        models.PlannerEvent.user_id == current_user.id,
    ).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if body.title is not None:
        event.title = body.title
    if body.description is not None:
        event.description = body.description
    if body.date is not None:
        event.date = body.date
    if body.startTime is not None:
        event.start_time = body.startTime
    if body.endTime is not None:
        event.end_time = body.endTime
    if body.type is not None:
        event.type = body.type
    if body.location is not None:
        event.location = body.location
    if body.buildingId is not None:
        event.building_id = body.buildingId
    if body.color is not None:
        event.color = body.color
    if body.isRecurring is not None:
        event.is_recurring = body.isRecurring
    if body.reminderMinutes is not None:
        event.reminder_minutes = body.reminderMinutes

    db.commit()
    db.refresh(event)
    return schemas.ApiResponse(success=True, data=_event_out(event))


@router.delete("/events/{event_id}", response_model=schemas.ApiResponse[None])
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    event = db.query(models.PlannerEvent).filter(
        models.PlannerEvent.id == event_id,
        models.PlannerEvent.user_id == current_user.id,
    ).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    db.delete(event)
    db.commit()
    return schemas.ApiResponse(success=True, data=None)
