import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user

router = APIRouter(prefix="/maps", tags=["maps"])


def _building_out(b: models.Building) -> schemas.BuildingOut:
    return schemas.BuildingOut(
        id=b.id,
        name=b.name,
        shortName=b.short_name,
        description=b.description,
        latitude=b.latitude,
        longitude=b.longitude,
        floors=b.floors,
        hasElevator=b.has_elevator,
        hasRamp=b.has_ramp,
        category=b.category,
        imageUrl=b.image_url,
    )


def _room_out(r: models.Room) -> schemas.RoomOut:
    return schemas.RoomOut(
        id=r.id,
        buildingId=r.building_id,
        name=r.name,
        floor=r.floor,
        type=r.type,
        capacity=r.capacity,
        accessible=r.accessible,
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@router.get("/buildings", response_model=schemas.ApiResponse[list[schemas.BuildingOut]])
def get_buildings(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    buildings = db.query(models.Building).all()
    return schemas.ApiResponse(success=True, data=[_building_out(b) for b in buildings])


@router.get("/buildings/{building_id}", response_model=schemas.ApiResponse[schemas.BuildingOut])
def get_building(
    building_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    b = db.query(models.Building).filter(models.Building.id == building_id).first()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_building_out(b))


@router.get("/buildings/{building_id}/rooms", response_model=schemas.ApiResponse[list[schemas.RoomOut]])
def get_rooms_by_building(
    building_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    b = db.query(models.Building).filter(models.Building.id == building_id).first()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    rooms = db.query(models.Room).filter(models.Room.building_id == building_id).all()
    return schemas.ApiResponse(success=True, data=[_room_out(r) for r in rooms])


@router.get("/search", response_model=schemas.ApiResponse[schemas.MapSearchResult])
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q_lower = q.lower()
    buildings = db.query(models.Building).all()
    matched_buildings = [
        b for b in buildings
        if q_lower in b.name.lower() or q_lower in (b.description or "").lower() or q_lower in b.short_name.lower()
    ]
    rooms = db.query(models.Room).all()
    matched_rooms = [r for r in rooms if q_lower in r.name.lower() or q_lower in r.type.lower()]

    return schemas.ApiResponse(
        success=True,
        data=schemas.MapSearchResult(
            buildings=[_building_out(b) for b in matched_buildings],
            rooms=[_room_out(r) for r in matched_rooms],
        ),
    )


@router.get("/nearby", response_model=schemas.ApiResponse[list[schemas.NearbyBuilding]])
def get_nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: float = Query(500),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    buildings = db.query(models.Building).all()
    result = []
    for b in buildings:
        dist = _haversine(lat, lng, b.latitude, b.longitude)
        if dist <= radius:
            result.append(schemas.NearbyBuilding(
                id=b.id,
                name=b.name,
                shortName=b.short_name,
                latitude=b.latitude,
                longitude=b.longitude,
                distanceMeters=round(dist, 1),
                category=b.category,
            ))
    result.sort(key=lambda x: x.distanceMeters)
    return schemas.ApiResponse(success=True, data=result)
