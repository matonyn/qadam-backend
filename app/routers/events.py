from datetime import date, datetime, time, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase

router = APIRouter(prefix="/events", tags=["events"])


def _parse_event_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if len(value) == 10 and value[4] == "-":
            return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone.utc)
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _event_overlaps_range(
    e: models.CampusEvent,
    range_start: datetime | None,
    range_end: datetime | None,
) -> bool:
    es = _parse_event_datetime(e.start_date)
    if not es:
        return True
    ee = _parse_event_datetime(e.end_date) or es
    if range_start and ee < range_start:
        return False
    if range_end and es > range_end:
        return False
    return True


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
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    range_start = None
    range_end = None
    if startDate:
        try:
            range_start = datetime.combine(date.fromisoformat(startDate), time.min, tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid startDate, use YYYY-MM-DD")
    if endDate:
        try:
            range_end = datetime.combine(date.fromisoformat(endDate), time.max, tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid endDate, use YYYY-MM-DD")

    q = sb.table("campus_events").select("*")
    if category:
        q = q.eq("category", category)
    res = q.execute()
    events = [models.CampusEvent.from_row(r) for r in (res.data or [])]
    filtered = [e for e in events if _event_overlaps_range(e, range_start, range_end)]
    return schemas.ApiResponse(success=True, data=[_event_out(e) for e in filtered])


@router.get(
    "/registered",
    response_model=schemas.ApiResponse[list[schemas.RegisteredCampusEventOut]],
)
def get_registered_events(
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    range_start = None
    range_end = None
    if startDate:
        try:
            range_start = datetime.combine(date.fromisoformat(startDate), time.min, tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid startDate, use YYYY-MM-DD")
    if endDate:
        try:
            range_end = datetime.combine(date.fromisoformat(endDate), time.max, tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid endDate, use YYYY-MM-DD")

    regs_res = sb.table("event_registrations").select("*").eq("user_id", current_user.id).execute()
    regs_rows = regs_res.data or []
    if not regs_rows:
        return schemas.ApiResponse(success=True, data=[])

    regs = [models.EventRegistration.from_row(r) for r in regs_rows]
    event_ids = [r.event_id for r in regs if r.event_id]
    if not event_ids:
        return schemas.ApiResponse(success=True, data=[])

    events_res = sb.table("campus_events").select("*").in_("id", event_ids).execute()
    events = [models.CampusEvent.from_row(r) for r in (events_res.data or [])]
    by_id = {e.id: e for e in events}

    registered_at_by_event_id: dict[str, str] = {}
    for r in regs:
        if not r.event_id:
            continue
        ra = r.registered_at.isoformat() + "Z" if r.registered_at else ""
        registered_at_by_event_id[r.event_id] = ra

    out: list[schemas.RegisteredCampusEventOut] = []
    for event_id in event_ids:
        e = by_id.get(event_id)
        if not e:
            continue
        if not _event_overlaps_range(e, range_start, range_end):
            continue
        out.append(
            schemas.RegisteredCampusEventOut(
                **_event_out(e).dict(),
                registeredAt=registered_at_by_event_id.get(event_id, ""),
            )
        )

    # Prefer upcoming by start date; fall back to registration time.
    out.sort(key=lambda x: (x.startDate or "", x.registeredAt or ""))
    return schemas.ApiResponse(success=True, data=out)


@router.get("/{event_id}", response_model=schemas.ApiResponse[schemas.CampusEventOut])
def get_event(
    event_id: str,
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    res = sb.table("campus_events").select("*").eq("id", event_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_event_out(models.CampusEvent.from_row(rows[0])))


@router.post("/{event_id}/register", response_model=schemas.ApiResponse[schemas.EventRegistrationOut])
def register_for_event(
    event_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    er = sb.table("campus_events").select("*").eq("id", event_id).limit(1).execute()
    rows = er.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    e = models.CampusEvent.from_row(rows[0])
    if not e.is_registration_required:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This event does not require registration")

    ex = (
        sb.table("event_registrations")
        .select("id")
        .eq("event_id", event_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    if ex.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already registered")

    reg_id = str(uuid.uuid4())
    ins = (
        sb.table("event_registrations")
        .insert({"id": reg_id, "event_id": event_id, "user_id": current_user.id})
        .execute()
    )
    row = (ins.data or [{"id": reg_id, "event_id": event_id, "user_id": current_user.id, "registered_at": None}])[0]
    reg = models.EventRegistration.from_row(row)
    ra = reg.registered_at.isoformat() + "Z" if reg.registered_at else ""
    return schemas.ApiResponse(
        success=True,
        data=schemas.EventRegistrationOut(
            registrationId=reg.id,
            eventId=reg.event_id,
            userId=reg.user_id,
            registeredAt=ra,
        ),
    )


def _registration_out_from_row(row: dict) -> schemas.EventRegistrationOut:
    reg = models.EventRegistration.from_row(row)
    ra = reg.registered_at.isoformat() + "Z" if reg.registered_at else ""
    return schemas.EventRegistrationOut(
        registrationId=reg.id,
        eventId=reg.event_id,
        userId=reg.user_id,
        registeredAt=ra,
    )


@router.get(
    "/{event_id}/registration",
    response_model=schemas.ApiResponse[schemas.EventRegistrationStatusOut],
)
def get_my_event_registration(
    event_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    er = sb.table("campus_events").select("id").eq("id", event_id).limit(1).execute()
    if not (er.data or []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    ex = (
        sb.table("event_registrations")
        .select("*")
        .eq("event_id", event_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    rows = ex.data or []
    if not rows:
        return schemas.ApiResponse(
            success=True,
            data=schemas.EventRegistrationStatusOut(isRegistered=False, registration=None),
        )
    return schemas.ApiResponse(
        success=True,
        data=schemas.EventRegistrationStatusOut(
            isRegistered=True,
            registration=_registration_out_from_row(rows[0]),
        ),
    )


@router.delete("/{event_id}/register", response_model=schemas.ApiResponse[None])
def unregister_from_event(
    event_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    er = sb.table("campus_events").select("id").eq("id", event_id).limit(1).execute()
    if not (er.data or []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    sb.table("event_registrations").delete().eq("event_id", event_id).eq("user_id", current_user.id).execute()
    return schemas.ApiResponse(success=True, data=None)
