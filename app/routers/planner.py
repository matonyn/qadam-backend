import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase
from app.timeutil import hhmm_to_minutes

router = APIRouter(prefix="/planner", tags=["planner"])


def _validate_times(start_time: str, end_time: str) -> None:
    try:
        a = hhmm_to_minutes(start_time)
        b = hhmm_to_minutes(end_time)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if b <= a:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endTime must be after startTime")


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
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    q = sb.table("planner_events").select("*").eq("user_id", current_user.id)
    if startDate:
        q = q.gte("date", startDate)
    if endDate:
        q = q.lte("date", endDate)
    res = q.execute()
    events = [models.PlannerEvent.from_row(r) for r in (res.data or [])]
    events.sort(key=lambda e: (e.date, e.start_time))
    return schemas.ApiResponse(success=True, data=[_event_out(e) for e in events])


@router.post("/events", response_model=schemas.ApiResponse[schemas.PlannerEventOut])
def create_event(
    body: schemas.CreatePlannerEventRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    _validate_times(body.startTime, body.endTime)

    row = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "title": body.title,
        "description": body.description,
        "date": body.date,
        "start_time": body.startTime,
        "end_time": body.endTime,
        "type": body.type,
        "location": body.location,
        "building_id": body.buildingId,
        "color": body.color,
        "is_recurring": body.isRecurring,
        "reminder_minutes": body.reminderMinutes,
    }
    ins = sb.table("planner_events").insert(row).execute()
    ev = models.PlannerEvent.from_row((ins.data or [row])[0])
    return schemas.ApiResponse(success=True, data=_event_out(ev))


@router.patch("/events/{event_id}", response_model=schemas.ApiResponse[schemas.PlannerEventOut])
def update_event(
    event_id: str,
    body: schemas.UpdatePlannerEventRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = (
        sb.table("planner_events")
        .select("*")
        .eq("id", event_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = models.PlannerEvent.from_row(rows[0])

    start_time = body.startTime if body.startTime is not None else event.start_time
    end_time = body.endTime if body.endTime is not None else event.end_time
    if body.startTime is not None or body.endTime is not None:
        _validate_times(start_time, end_time)

    upd: dict = {}
    if body.title is not None:
        upd["title"] = body.title
    if body.description is not None:
        upd["description"] = body.description
    if body.date is not None:
        upd["date"] = body.date
    if body.startTime is not None:
        upd["start_time"] = body.startTime
    if body.endTime is not None:
        upd["end_time"] = body.endTime
    if body.type is not None:
        upd["type"] = body.type
    if body.location is not None:
        upd["location"] = body.location
    if body.buildingId is not None:
        upd["building_id"] = body.buildingId
    if body.color is not None:
        upd["color"] = body.color
    if body.isRecurring is not None:
        upd["is_recurring"] = body.isRecurring
    if body.reminderMinutes is not None:
        upd["reminder_minutes"] = body.reminderMinutes

    if upd:
        sb.table("planner_events").update(upd).eq("id", event_id).eq("user_id", current_user.id).execute()

    fres = (
        sb.table("planner_events")
        .select("*")
        .eq("id", event_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    ev = models.PlannerEvent.from_row((fres.data or rows)[0])
    return schemas.ApiResponse(success=True, data=_event_out(ev))


@router.delete("/events/{event_id}", response_model=schemas.ApiResponse[None])
def delete_event(
    event_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    chk = (
        sb.table("planner_events")
        .select("id")
        .eq("id", event_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    if not chk.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    sb.table("planner_events").delete().eq("id", event_id).eq("user_id", current_user.id).execute()
    return schemas.ApiResponse(success=True, data=None)
