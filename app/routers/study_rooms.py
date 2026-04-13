import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.dependencies import get_current_user, get_supabase
from app.timeutil import (
    MAX_STUDY_BOOKING_MINUTES,
    MIN_STUDY_BOOKING_MINUTES,
    hhmm_to_minutes,
    minutes_to_hhmm,
    ranges_overlap_half_open,
)

router = APIRouter(prefix="/study-rooms", tags=["study-rooms"])


def _room_out(r: models.StudyRoom) -> schemas.StudyRoomOut:
    return schemas.StudyRoomOut(
        id=r.id,
        buildingId=r.building_id,
        buildingName=r.building_name,
        name=r.name,
        floor=r.floor,
        capacity=r.capacity,
        amenities=r.amenities or [],
        isAvailable=r.is_available,
        currentOccupancy=r.current_occupancy,
        noiseLevel=r.noise_level,
        imageUrl=r.image_url,
    )


def _booking_out(b: models.StudyRoomBooking) -> schemas.BookingOut:
    return schemas.BookingOut(
        id=b.id,
        roomId=b.room_id,
        userId=b.user_id,
        date=b.date,
        startTime=b.start_time,
        endTime=b.end_time,
        status=b.status,
    )


def _generate_slots_half_hour() -> list[schemas.TimeSlot]:
    """30-minute slots from 08:00 through 20:30–21:00 (last interval ends at 21:00)."""
    slots: list[schemas.TimeSlot] = []
    start_min = 8 * 60
    day_end = 21 * 60  # last slot ends at 21:00
    cur = start_min
    while cur + 30 <= day_end:
        slots.append(
            schemas.TimeSlot(
                startTime=minutes_to_hhmm(cur),
                endTime=minutes_to_hhmm(cur + 30),
                available=True,
            )
        )
        cur += 30
    return slots


def _now_minutes_local() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


def _booking_overlaps_now(b: models.StudyRoomBooking, today_iso: str, now_m: int) -> bool:
    if b.date != today_iso or (b.status or "").lower() == "cancelled":
        return False
    try:
        b0 = hhmm_to_minutes(b.start_time)
        b1 = hhmm_to_minutes(b.end_time)
    except ValueError:
        return False
    return b0 <= now_m < b1


@router.get("", response_model=schemas.ApiResponse[list[schemas.StudyRoomOut]])
def get_study_rooms(
    buildingId: str | None = Query(None),
    available: bool | None = Query(None),
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    q = sb.table("study_rooms").select("*")
    if buildingId:
        q = q.eq("building_id", buildingId)
    res = q.execute()
    rooms = [models.StudyRoom.from_row(r) for r in (res.data or [])]

    today_iso = date.today().isoformat()
    now_m = _now_minutes_local()
    bres = (
        sb.table("study_room_bookings")
        .select("*")
        .eq("date", today_iso)
        .neq("status", "cancelled")
        .execute()
    )
    bookings_by_room: dict[str, list[models.StudyRoomBooking]] = {}
    for row in bres.data or []:
        b = models.StudyRoomBooking.from_row(row)
        bookings_by_room.setdefault(b.room_id, []).append(b)

    out: list[schemas.StudyRoomOut] = []
    for r in rooms:
        cap = int(r.capacity or 0)
        room_bookings = bookings_by_room.get(r.id, [])
        has_active = any(_booking_overlaps_now(b, today_iso, now_m) for b in room_bookings)
        # Exclusive booking model: an active reservation uses the room; show as full for occupancy bar.
        live_occ = cap if has_active and cap > 0 else 0
        live_available = bool(r.is_available) and not has_active
        if available is not None and live_available != available:
            continue
        patched = models.StudyRoom(
            id=r.id,
            building_id=r.building_id,
            building_name=r.building_name,
            name=r.name,
            floor=r.floor,
            capacity=r.capacity,
            amenities=r.amenities,
            is_available=live_available,
            current_occupancy=live_occ,
            noise_level=r.noise_level,
            image_url=r.image_url,
        )
        out.append(_room_out(patched))
    return schemas.ApiResponse(success=True, data=out)


@router.get("/bookings", response_model=schemas.ApiResponse[list[schemas.BookingOut]])
def get_user_bookings(
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = sb.table("study_room_bookings").select("*").eq("user_id", current_user.id).neq("status", "cancelled").execute()
    bookings = [models.StudyRoomBooking.from_row(r) for r in (res.data or [])]
    return schemas.ApiResponse(success=True, data=[_booking_out(b) for b in bookings])


@router.delete("/bookings/{booking_id}", response_model=schemas.ApiResponse[None])
def cancel_booking(
    booking_id: str,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    chk = (
        sb.table("study_room_bookings")
        .select("id")
        .eq("id", booking_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    if not chk.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    sb.table("study_room_bookings").update({"status": "cancelled"}).eq("id", booking_id).eq(
        "user_id", current_user.id
    ).execute()
    return schemas.ApiResponse(success=True, data=None)


@router.get("/{room_id}/availability", response_model=schemas.ApiResponse[list[schemas.TimeSlot]])
def get_room_availability(
    room_id: str,
    date: str = Query(...),
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    r = sb.table("study_rooms").select("id").eq("id", room_id).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    bres = (
        sb.table("study_room_bookings")
        .select("*")
        .eq("room_id", room_id)
        .eq("date", date)
        .neq("status", "cancelled")
        .execute()
    )
    bookings = [models.StudyRoomBooking.from_row(x) for x in (bres.data or [])]

    try:
        slots = _generate_slots_half_hour()
        for slot in slots:
            s0 = hhmm_to_minutes(slot.startTime)
            s1 = hhmm_to_minutes(slot.endTime)
            for b in bookings:
                b0 = hhmm_to_minutes(b.start_time)
                b1 = hhmm_to_minutes(b.end_time)
                if ranges_overlap_half_open(s0, s1, b0, b1):
                    slot.available = False
                    break
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return schemas.ApiResponse(success=True, data=slots)


@router.post("/{room_id}/book", response_model=schemas.ApiResponse[schemas.BookingOut])
def book_room(
    room_id: str,
    body: schemas.BookRoomRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    rres = sb.table("study_rooms").select("*").eq("id", room_id).limit(1).execute()
    rows = rres.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    room = models.StudyRoom.from_row(rows[0])
    if not room.is_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not available")

    try:
        new_start = hhmm_to_minutes(body.startTime)
        new_end = hhmm_to_minutes(body.endTime)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if new_end <= new_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endTime must be after startTime")

    duration = new_end - new_start
    if duration > MAX_STUDY_BOOKING_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bookings may be at most {MAX_STUDY_BOOKING_MINUTES // 60} hours",
        )
    if duration < MIN_STUDY_BOOKING_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bookings must be at least {MIN_STUDY_BOOKING_MINUTES} minutes",
        )
    if new_start % 30 != 0 or new_end % 30 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="startTime and endTime must align to 30-minute boundaries (e.g. 09:00, 09:30)",
        )

    bres = (
        sb.table("study_room_bookings")
        .select("*")
        .eq("room_id", room_id)
        .eq("date", body.date)
        .neq("status", "cancelled")
        .execute()
    )
    for br in bres.data or []:
        b = models.StudyRoomBooking.from_row(br)
        try:
            b0 = hhmm_to_minutes(b.start_time)
            b1 = hhmm_to_minutes(b.end_time)
        except ValueError:
            continue
        if ranges_overlap_half_open(new_start, new_end, b0, b1):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time slot already booked")

    row = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "user_id": current_user.id,
        "date": body.date,
        "start_time": body.startTime,
        "end_time": body.endTime,
        "status": "confirmed",
    }
    ins = sb.table("study_room_bookings").insert(row).execute()
    booking = models.StudyRoomBooking.from_row((ins.data or [row])[0])
    return schemas.ApiResponse(success=True, data=_booking_out(booking))
