from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user
import uuid

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


def _generate_slots() -> list[schemas.TimeSlot]:
    """Generate hourly slots from 08:00 to 21:00."""
    return [
        schemas.TimeSlot(
            startTime=f"{h:02d}:00",
            endTime=f"{h+1:02d}:00",
            available=True,
        )
        for h in range(8, 21)
    ]


@router.get("", response_model=schemas.ApiResponse[list[schemas.StudyRoomOut]])
def get_study_rooms(
    buildingId: str | None = Query(None),
    available: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.StudyRoom)
    if buildingId:
        q = q.filter(models.StudyRoom.building_id == buildingId)
    if available is not None:
        q = q.filter(models.StudyRoom.is_available == available)
    rooms = q.all()
    return schemas.ApiResponse(success=True, data=[_room_out(r) for r in rooms])


@router.get("/bookings", response_model=schemas.ApiResponse[list[schemas.BookingOut]])
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    bookings = db.query(models.StudyRoomBooking).filter(
        models.StudyRoomBooking.user_id == current_user.id,
        models.StudyRoomBooking.status != "cancelled",
    ).all()
    return schemas.ApiResponse(success=True, data=[_booking_out(b) for b in bookings])


@router.delete("/bookings/{booking_id}", response_model=schemas.ApiResponse[None])
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    booking = db.query(models.StudyRoomBooking).filter(
        models.StudyRoomBooking.id == booking_id,
        models.StudyRoomBooking.user_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    booking.status = "cancelled"
    db.commit()
    return schemas.ApiResponse(success=True, data=None)


@router.get("/{room_id}/availability", response_model=schemas.ApiResponse[list[schemas.TimeSlot]])
def get_room_availability(
    room_id: str,
    date: str = Query(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    room = db.query(models.StudyRoom).filter(models.StudyRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Get existing bookings for this room and date
    bookings = db.query(models.StudyRoomBooking).filter(
        models.StudyRoomBooking.room_id == room_id,
        models.StudyRoomBooking.date == date,
        models.StudyRoomBooking.status != "cancelled",
    ).all()

    slots = _generate_slots()
    for slot in slots:
        for b in bookings:
            if b.start_time <= slot.startTime < b.end_time or b.start_time < slot.endTime <= b.end_time:
                slot.available = False
                break

    return schemas.ApiResponse(success=True, data=slots)


@router.post("/{room_id}/book", response_model=schemas.ApiResponse[schemas.BookingOut])
def book_room(
    room_id: str,
    body: schemas.BookRoomRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    room = db.query(models.StudyRoom).filter(models.StudyRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if not room.is_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not available")

    # Check for conflicts
    conflict = db.query(models.StudyRoomBooking).filter(
        models.StudyRoomBooking.room_id == room_id,
        models.StudyRoomBooking.date == body.date,
        models.StudyRoomBooking.status != "cancelled",
        models.StudyRoomBooking.start_time < body.endTime,
        models.StudyRoomBooking.end_time > body.startTime,
    ).first()
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time slot already booked")

    booking = models.StudyRoomBooking(
        id=str(uuid.uuid4()),
        room_id=room_id,
        user_id=current_user.id,
        date=body.date,
        start_time=body.startTime,
        end_time=body.endTime,
        status="confirmed",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return schemas.ApiResponse(success=True, data=_booking_out(booking))
