import math
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.dependencies import get_db, get_current_user

router = APIRouter(prefix="/routing", tags=["routing"])


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _nearest_building_name(db: Session, lat: float, lng: float) -> str:
    buildings = db.query(models.Building).all()
    if not buildings:
        return "Unknown Location"
    nearest = min(buildings, key=lambda b: _haversine(lat, lng, b.latitude, b.longitude))
    if _haversine(lat, lng, nearest.latitude, nearest.longitude) < 100:
        return nearest.name
    return "Current Location"


def _generate_route(
    db: Session,
    start_lat: float, start_lng: float, start_name: str,
    end_lat: float, end_lng: float, end_name: str,
    preference: str,
) -> models.Route:
    dist = _haversine(start_lat, start_lng, end_lat, end_lng)
    # Walking speed: ~80 m/min on campus
    duration = max(1, round(dist / 80))

    # Build intermediate waypoints by snapping to nearby buildings
    buildings = db.query(models.Building).all()
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2
    # Pick a building close to the midpoint (not start or end building)
    candidates = sorted(
        buildings,
        key=lambda b: _haversine(mid_lat, mid_lng, b.latitude, b.longitude),
    )
    waypoints = [{"latitude": start_lat, "longitude": start_lng}]
    if candidates and _haversine(mid_lat, mid_lng, candidates[0].latitude, candidates[0].longitude) < 300:
        via = candidates[0]
        waypoints.append({"latitude": via.latitude, "longitude": via.longitude})
    waypoints.append({"latitude": end_lat, "longitude": end_lng})

    # Determine accessibility
    is_accessible = preference == "accessible"

    # Crowd level based on preference
    crowd_map = {"least_crowded": "low", "accessible": "low", "shortest": "medium"}
    crowd_level = crowd_map.get(preference, "medium")

    # Basic turn-by-turn instructions
    bearing = math.degrees(math.atan2(end_lng - start_lng, end_lat - start_lat))
    if -45 <= bearing < 45:
        direction = "north"
    elif 45 <= bearing < 135:
        direction = "east"
    elif bearing >= 135 or bearing < -135:
        direction = "south"
    else:
        direction = "west"

    instructions = [
        f"Head {direction} toward {end_name}",
    ]
    if len(waypoints) == 3:
        instructions.append(f"Pass by {candidates[0].name}")
    instructions.append(f"{end_name} is ahead")
    if is_accessible:
        instructions.append("Use the ramp or elevator as needed")

    return models.Route(
        id=str(uuid.uuid4()),
        start_lat=start_lat,
        start_lng=start_lng,
        start_name=start_name,
        end_lat=end_lat,
        end_lng=end_lng,
        end_name=end_name,
        distance=round(dist),
        duration=duration,
        is_accessible=is_accessible,
        crowd_level=crowd_level,
        waypoints=waypoints,
        instructions=instructions,
        preference=preference,
    )


def _route_out(r: models.Route) -> schemas.RouteOut:
    return schemas.RouteOut(
        id=r.id,
        startLocation=schemas.Location(latitude=r.start_lat, longitude=r.start_lng, name=r.start_name),
        endLocation=schemas.Location(latitude=r.end_lat, longitude=r.end_lng, name=r.end_name),
        distance=r.distance,
        duration=r.duration,
        isAccessible=r.is_accessible,
        crowdLevel=r.crowd_level,
        waypoints=[schemas.Waypoint(**wp) for wp in (r.waypoints or [])],
        instructions=r.instructions or [],
    )


@router.post("/calculate", response_model=schemas.ApiResponse[schemas.RouteOut])
def calculate_route(
    body: schemas.CalculateRouteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start_name = _nearest_building_name(db, body.startLat, body.startLng)
    end_name = _nearest_building_name(db, body.endLat, body.endLng)

    route = _generate_route(
        db,
        body.startLat, body.startLng, start_name,
        body.endLat, body.endLng, end_name,
        body.preference,
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return schemas.ApiResponse(success=True, data=_route_out(route))


@router.get("/saved", response_model=schemas.ApiResponse[list[schemas.RouteOut]])
def get_saved_routes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    saved = db.query(models.SavedRoute).filter(models.SavedRoute.user_id == current_user.id).all()
    routes = [_route_out(sr.route) for sr in saved if sr.route]
    return schemas.ApiResponse(success=True, data=routes)


@router.post("/saved", response_model=schemas.ApiResponse[None])
def save_route(
    body: schemas.SaveRouteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    route = db.query(models.Route).filter(models.Route.id == body.routeId).first()
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    existing = db.query(models.SavedRoute).filter(
        models.SavedRoute.user_id == current_user.id,
        models.SavedRoute.route_id == body.routeId,
    ).first()
    if not existing:
        db.add(models.SavedRoute(user_id=current_user.id, route_id=body.routeId))
        db.commit()

    return schemas.ApiResponse(success=True, data=None)


@router.post("/reroute", response_model=schemas.ApiResponse[schemas.RouteOut])
def reroute(
    body: schemas.RerouteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    original = db.query(models.Route).filter(models.Route.id == body.routeId).first()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    route = _generate_route(
        db,
        body.currentLat, body.currentLng, "Current Location",
        original.end_lat, original.end_lng, original.end_name,
        original.preference,
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return schemas.ApiResponse(success=True, data=_route_out(route))
