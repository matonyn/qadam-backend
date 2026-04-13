import math
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import Client

from app import models, schemas
from app.config import CAMPUS_2GIS_SYNC_SECRET, CAMPUS_SYNC_CONFIGURED, TWOGIS_API_KEY, TWOGIS_CONFIGURED
from app.dependencies import get_current_user, get_supabase
from app.services.twogis import fetch_nu_campus_catalog_rows

router = APIRouter(prefix="/maps", tags=["maps"])


def _building_out(b: models.Building) -> schemas.BuildingOut:
    lat = b.latitude if b.latitude is not None else 0.0
    lng = b.longitude if b.longitude is not None else 0.0
    return schemas.BuildingOut(
        id=b.id,
        name=b.name,
        shortName=b.short_name,
        description=b.description,
        latitude=lat,
        longitude=lng,
        floors=b.floors if b.floors is not None else 1,
        hasElevator=b.has_elevator,
        hasRamp=b.has_ramp,
        category=b.category or "other",
        imageUrl=b.image_url,
        twogisId=b.twogis_id,
        dataSource=b.data_source,
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


def _sync_secret_ok(provided: str | None) -> bool:
    if not CAMPUS_SYNC_CONFIGURED or not provided:
        return False
    exp = CAMPUS_2GIS_SYNC_SECRET.encode("utf-8")
    got = provided.encode("utf-8")
    if len(exp) != len(got):
        return False
    return secrets.compare_digest(got, exp)


@router.post("/buildings/sync-from-2gis", response_model=schemas.ApiResponse[schemas.Sync2gisBuildingsResult])
def sync_buildings_from_2gis(
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
    x_qadam_sync_key: str | None = Header(default=None, alias="X-Qadam-Sync-Key"),
):
    """
    Import 2GIS branches and buildings inside the NU campus polygon into `buildings`.
    Requires header `X-Qadam-Sync-Key` matching env `CAMPUS_2GIS_SYNC_SECRET`, and `TWOGIS_API_KEY`.
    """
    if not TWOGIS_CONFIGURED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="2GIS API key not configured")
    if not _sync_secret_ok(x_qadam_sync_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing sync key")

    rows, skipped = fetch_nu_campus_catalog_rows(TWOGIS_API_KEY)
    if not rows:
        return schemas.ApiResponse(
            success=True,
            data=schemas.Sync2gisBuildingsResult(upserted=0, fetchedUnique=0, skippedNoCoords=skipped),
        )

    batch = 40
    upserted = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        sb.table("buildings").upsert(chunk, on_conflict="twogis_id").execute()
        upserted += len(chunk)

    return schemas.ApiResponse(
        success=True,
        data=schemas.Sync2gisBuildingsResult(
            upserted=upserted,
            fetchedUnique=len(rows),
            skippedNoCoords=skipped,
        ),
    )


@router.get("/buildings", response_model=schemas.ApiResponse[list[schemas.BuildingOut]])
def get_buildings(
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    res = sb.table("buildings").select("*").execute()
    buildings = [models.Building.from_row(r) for r in (res.data or [])]
    with_coords = [b for b in buildings if b.latitude is not None and b.longitude is not None]
    return schemas.ApiResponse(success=True, data=[_building_out(b) for b in with_coords])


@router.get("/buildings/{building_id}", response_model=schemas.ApiResponse[schemas.BuildingOut])
def get_building(
    building_id: str,
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    res = sb.table("buildings").select("*").eq("id", building_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return schemas.ApiResponse(success=True, data=_building_out(models.Building.from_row(rows[0])))


@router.get("/buildings/{building_id}/rooms", response_model=schemas.ApiResponse[list[schemas.RoomOut]])
def get_rooms_by_building(
    building_id: str,
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    b = sb.table("buildings").select("id").eq("id", building_id).limit(1).execute()
    if not b.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    res = sb.table("rooms").select("*").eq("building_id", building_id).execute()
    rooms = [models.Room.from_row(r) for r in (res.data or [])]
    return schemas.ApiResponse(success=True, data=[_room_out(r) for r in rooms])


@router.get("/search", response_model=schemas.ApiResponse[schemas.MapSearchResult])
def search(
    q: str = Query(..., min_length=1),
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    q_lower = q.lower()
    bres = sb.table("buildings").select("*").execute()
    buildings = [models.Building.from_row(r) for r in (bres.data or [])]
    matched_buildings = [
        b
        for b in buildings
        if b.latitude is not None
        and b.longitude is not None
        and (
            q_lower in b.name.lower()
            or q_lower in (b.description or "").lower()
            or q_lower in b.short_name.lower()
        )
    ]
    rres = sb.table("rooms").select("*").execute()
    rooms = [models.Room.from_row(r) for r in (rres.data or [])]
    matched_rooms = [r for r in rooms if q_lower in r.name.lower() or (r.type and q_lower in r.type.lower())]

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
    sb: Client = Depends(get_supabase),
    _: models.User = Depends(get_current_user),
):
    res = sb.table("buildings").select("*").execute()
    buildings = [models.Building.from_row(r) for r in (res.data or [])]
    result = []
    for b in buildings:
        if b.latitude is None or b.longitude is None:
            continue
        dist = _haversine(lat, lng, b.latitude, b.longitude)
        if dist <= radius:
            result.append(
                schemas.NearbyBuilding(
                    id=b.id,
                    name=b.name,
                    shortName=b.short_name,
                    latitude=b.latitude,
                    longitude=b.longitude,
                    distanceMeters=round(dist, 1),
                    category=b.category,
                )
            )
    result.sort(key=lambda x: x.distanceMeters)
    return schemas.ApiResponse(success=True, data=result)
