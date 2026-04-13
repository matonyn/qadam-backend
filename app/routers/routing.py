import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app import models, schemas
from app.campus_graph import compute_pedestrian_route, point_in_nu_campus
from app.config import TWOGIS_API_KEY, TWOGIS_CONFIGURED
from app.dependencies import get_current_user, get_supabase
from app.services.twogis import get_walking_route

router = APIRouter(prefix="/routing", tags=["routing"])

PREFERENCE_VALUES = frozenset({"shortest", "accessible", "least_crowded"})


def _route_both_endpoints_on_nu_campus(slat: float, slng: float, elat: float, elng: float) -> bool:
    return point_in_nu_campus(slat, slng) and point_in_nu_campus(elat, elng)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _path_distance_m(waypoints: list[dict[str, float]]) -> float:
    if len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        total += _haversine(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
    return total


def _bearing_cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Initial geographic bearing from (lat1,lon1) toward (lat2,lon2), as N/E/S/W."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    if bearing < 45 or bearing >= 315:
        return "north"
    if bearing < 135:
        return "east"
    if bearing < 225:
        return "south"
    return "west"


def _pick_via_building(
    buildings: list[models.Building],
    mid_lat: float,
    mid_lng: float,
    max_dist_m: float,
    preference: str,
    start_b: models.Building | None,
    end_b: models.Building | None,
) -> models.Building | None:
    """Optional midpoint waypoint; accessible mode only uses ramp/elevator buildings."""
    with_coords = [b for b in buildings if b.latitude is not None and b.longitude is not None]

    def excluded(b: models.Building) -> bool:
        if start_b is not None and b.id == start_b.id:
            return True
        if end_b is not None and b.id == end_b.id:
            return True
        return False

    candidates = [b for b in with_coords if not excluded(b)]
    if preference == "accessible":
        candidates = [b for b in candidates if _building_accessible(b)]

    candidates.sort(key=lambda b: _haversine(mid_lat, mid_lng, b.latitude, b.longitude))
    in_range = [b for b in candidates if _haversine(mid_lat, mid_lng, b.latitude, b.longitude) < max_dist_m]
    if not in_range:
        return None

    if preference == "least_crowded" and len(in_range) >= 2:
        # Slight detour vs. shortest path through midpoint (quieter walkways heuristic).
        return in_range[1]
    return in_range[0]


def _nearest_building(
    buildings: list[models.Building], lat: float, lng: float, snap_m: float = 120
) -> tuple[str, models.Building | None]:
    if not buildings:
        return "Unknown Location", None
    with_coords = [b for b in buildings if b.latitude is not None and b.longitude is not None]
    if not with_coords:
        return "Unknown Location", None
    nearest = min(with_coords, key=lambda b: _haversine(lat, lng, b.latitude, b.longitude))
    if _haversine(lat, lng, nearest.latitude, nearest.longitude) < snap_m:
        return nearest.name, nearest
    return "Current Location", None


def _building_accessible(b: models.Building | None) -> bool:
    if b is None:
        return True
    return bool(b.has_ramp or b.has_elevator)


def _generate_route(
    buildings: list[models.Building],
    start_lat: float,
    start_lng: float,
    start_name: str,
    start_b: models.Building | None,
    end_lat: float,
    end_lng: float,
    end_name: str,
    end_b: models.Building | None,
    preference: str,
) -> models.Route:
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2
    via_building = _pick_via_building(
        buildings, mid_lat, mid_lng, max_dist_m=300, preference=preference, start_b=start_b, end_b=end_b
    )
    waypoints = [{"latitude": start_lat, "longitude": start_lng}]
    if via_building is not None:
        waypoints.append({"latitude": via_building.latitude, "longitude": via_building.longitude})
    waypoints.append({"latitude": end_lat, "longitude": end_lng})

    path_m = _path_distance_m(waypoints)
    if preference == "least_crowded":
        path_m = path_m * 1.12

    if preference == "accessible":
        is_accessible = _building_accessible(start_b) and _building_accessible(end_b)
        if via_building is not None:
            is_accessible = is_accessible and _building_accessible(via_building)
        crowd_level = "low"
    elif preference == "least_crowded":
        is_accessible = _building_accessible(start_b) and _building_accessible(end_b)
        crowd_level = "low"
    else:
        is_accessible = _building_accessible(start_b) and _building_accessible(end_b)
        crowd_level = "medium"

    duration = max(1, round(path_m / 80))

    direction = _bearing_cardinal(start_lat, start_lng, end_lat, end_lng)

    instructions = [f"Head {direction} toward {end_name}"]
    if via_building is not None and len(waypoints) == 3:
        instructions.append(f"Pass by {via_building.name}")
    instructions.append(f"{end_name} is ahead")

    if preference == "accessible":
        instructions.append("Prefer ramps and elevators where available")
        if not is_accessible:
            instructions.append("Note: part of this path may need stairs — verify entrances on site")
    elif preference == "least_crowded":
        instructions.append("Route prefers quieter walkways where possible")

    return models.Route(
        id=str(uuid.uuid4()),
        start_lat=start_lat,
        start_lng=start_lng,
        start_name=start_name,
        end_lat=end_lat,
        end_lng=end_lng,
        end_name=end_name,
        distance=round(path_m),
        duration=duration,
        is_accessible=is_accessible,
        crowd_level=crowd_level,
        waypoints=waypoints,
        instructions=instructions,
        preference=preference,
        created_at=None,
    )


def _route_to_row(r: models.Route) -> dict:
    return {
        "id": r.id,
        "start_lat": r.start_lat,
        "start_lng": r.start_lng,
        "start_name": r.start_name,
        "end_lat": r.end_lat,
        "end_lng": r.end_lng,
        "end_name": r.end_name,
        "distance": r.distance,
        "duration": r.duration,
        "is_accessible": r.is_accessible,
        "crowd_level": r.crowd_level,
        "waypoints": r.waypoints,
        "instructions": r.instructions,
        "preference": r.preference,
    }


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


def _load_buildings(sb: Client) -> list[models.Building]:
    res = sb.table("buildings").select("*").execute()
    return [models.Building.from_row(r) for r in (res.data or [])]


def _find_building(buildings: list[models.Building], bid: str | None) -> models.Building | None:
    if not bid:
        return None
    for b in buildings:
        if b.id == bid:
            return b
    return None


def _route_from_pedestrian_graph(
    buildings: list[models.Building],
    start_lat: float,
    start_lng: float,
    start_name: str,
    start_b: models.Building | None,
    end_lat: float,
    end_lng: float,
    end_name: str,
    end_b: models.Building | None,
    preference: str,
) -> models.Route | None:
    pr = compute_pedestrian_route(
        buildings,
        start_lat,
        start_lng,
        start_name,
        end_lat,
        end_lng,
        end_name,
        preference,
        end_b,
    )
    if pr is None:
        return None
    path_m = pr.distance_m
    if preference == "least_crowded":
        path_m *= 1.06
    duration = max(1, round(path_m / 80))
    is_acc = pr.is_accessible
    if preference == "accessible" and start_b is not None and not _building_accessible(start_b):
        is_acc = False
    instructions = list(pr.instructions)
    if preference == "accessible" and not is_acc:
        instructions.append("Note: verify ramps or elevators at your start and destination")
    return models.Route(
        id=str(uuid.uuid4()),
        start_lat=start_lat,
        start_lng=start_lng,
        start_name=start_name,
        end_lat=end_lat,
        end_lng=end_lng,
        end_name=end_name,
        distance=round(path_m),
        duration=duration,
        is_accessible=is_acc,
        crowd_level=pr.crowd_level,
        waypoints=pr.waypoints,
        instructions=instructions,
        preference=preference,
        created_at=None,
    )


def _route_from_2gis(
    start_lat: float,
    start_lng: float,
    start_name: str,
    start_b: models.Building | None,
    end_lat: float,
    end_lng: float,
    end_name: str,
    end_b: models.Building | None,
    preference: str,
) -> models.Route | None:
    if not TWOGIS_CONFIGURED:
        return None
    # Accessible routing is currently modeled only on the campus graph (ramps/elevators metadata).
    if preference == "accessible":
        return None
    try:
        r = get_walking_route(
            api_key=TWOGIS_API_KEY,
            start_lat=start_lat,
            start_lng=start_lng,
            end_lat=end_lat,
            end_lng=end_lng,
            locale="en",
        )
    except Exception:
        return None

    is_acc = _building_accessible(start_b) and _building_accessible(end_b)
    crowd_level = "low" if preference == "least_crowded" else "medium"

    waypoints = r.waypoints or [{"latitude": start_lat, "longitude": start_lng}, {"latitude": end_lat, "longitude": end_lng}]
    instructions = r.instructions or [f"Start: {start_name} → {end_name}", f"Arrive at {end_name}"]
    if preference == "least_crowded":
        instructions = list(instructions) + ["Route favors less busy segments where available"]

    return models.Route(
        id=str(uuid.uuid4()),
        start_lat=start_lat,
        start_lng=start_lng,
        start_name=start_name,
        end_lat=end_lat,
        end_lng=end_lng,
        end_name=end_name,
        distance=max(0, int(r.distance_m)),
        duration=max(1, int(round((r.duration_s or 0) / 60))) if (r.duration_s or 0) > 0 else max(1, int(round((max(0, r.distance_m) / 80)))),
        is_accessible=is_acc,
        crowd_level=crowd_level,
        waypoints=waypoints,
        instructions=instructions,
        preference=preference,
        created_at=None,
    )


@router.post("/calculate", response_model=schemas.ApiResponse[schemas.RouteOut])
def calculate_route(
    body: schemas.CalculateRouteRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    buildings = _load_buildings(sb)

    start_lat, start_lng = body.startLat, body.startLng
    end_lat, end_lng = body.endLat, body.endLng

    sbld = _find_building(buildings, body.startBuildingId)
    if sbld is not None and sbld.latitude is not None and sbld.longitude is not None:
        start_lat, start_lng = sbld.latitude, sbld.longitude

    ebld = _find_building(buildings, body.endBuildingId)
    if ebld is not None and ebld.latitude is not None and ebld.longitude is not None:
        end_lat, end_lng = ebld.latitude, ebld.longitude

    if sbld is not None:
        start_name, start_b = sbld.name, sbld
    else:
        start_name, start_b = _nearest_building(buildings, start_lat, start_lng)

    if ebld is not None:
        end_name, end_b = ebld.name, ebld
    else:
        end_name, end_b = _nearest_building(buildings, end_lat, end_lng)

    campus_only = _route_both_endpoints_on_nu_campus(start_lat, start_lng, end_lat, end_lng)
    if campus_only:
        route = _route_from_pedestrian_graph(
            buildings,
            start_lat,
            start_lng,
            start_name,
            start_b,
            end_lat,
            end_lng,
            end_name,
            end_b,
            body.preference,
        )
        if route is None:
            route = _route_from_2gis(
                start_lat,
                start_lng,
                start_name,
                start_b,
                end_lat,
                end_lng,
                end_name,
                end_b,
                body.preference,
            )
    else:
        route = _route_from_2gis(
            start_lat,
            start_lng,
            start_name,
            start_b,
            end_lat,
            end_lng,
            end_name,
            end_b,
            body.preference,
        )
        if route is None:
            route = _route_from_pedestrian_graph(
                buildings,
                start_lat,
                start_lng,
                start_name,
                start_b,
                end_lat,
                end_lng,
                end_name,
                end_b,
                body.preference,
            )
    if route is None:
        route = _generate_route(
            buildings,
            start_lat,
            start_lng,
            start_name,
            start_b,
            end_lat,
            end_lng,
            end_name,
            end_b,
            body.preference,
        )
    sb.table("routes").insert(_route_to_row(route)).execute()
    return schemas.ApiResponse(success=True, data=_route_out(route))


@router.get("/saved", response_model=schemas.ApiResponse[list[schemas.RouteOut]])
def get_saved_routes(
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    saved = sb.table("saved_routes").select("*").eq("user_id", current_user.id).execute()
    saved_rows = saved.data or []
    if not saved_rows:
        return schemas.ApiResponse(success=True, data=[])
    route_ids = list({s["route_id"] for s in saved_rows})
    rres = sb.table("routes").select("*").in_("id", route_ids).execute()
    by_id = {r["id"]: models.Route.from_row(r) for r in (rres.data or [])}
    routes = [by_id[s["route_id"]] for s in saved_rows if s["route_id"] in by_id]
    return schemas.ApiResponse(success=True, data=[_route_out(r) for r in routes])


@router.post("/saved", response_model=schemas.ApiResponse[None])
def save_route(
    body: schemas.SaveRouteRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    r = sb.table("routes").select("id").eq("id", body.routeId).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    ex = (
        sb.table("saved_routes")
        .select("id")
        .eq("user_id", current_user.id)
        .eq("route_id", body.routeId)
        .limit(1)
        .execute()
    )
    if not ex.data:
        sb.table("saved_routes").insert({"user_id": current_user.id, "route_id": body.routeId}).execute()

    return schemas.ApiResponse(success=True, data=None)


@router.post("/reroute", response_model=schemas.ApiResponse[schemas.RouteOut])
def reroute(
    body: schemas.RerouteRequest,
    sb: Client = Depends(get_supabase),
    current_user: models.User = Depends(get_current_user),
):
    res = sb.table("routes").select("*").eq("id", body.routeId).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    original = models.Route.from_row(rows[0])

    pref = original.preference if original.preference in PREFERENCE_VALUES else "shortest"
    buildings = _load_buildings(sb)
    start_name, start_b = _nearest_building(buildings, body.currentLat, body.currentLng)
    end_b = None
    for b in buildings:
        if b.name == original.end_name:
            end_b = b
            break

    elat = float(original.end_lat or 0)
    elng = float(original.end_lng or 0)
    campus_only = _route_both_endpoints_on_nu_campus(body.currentLat, body.currentLng, elat, elng)

    if campus_only:
        route = _route_from_pedestrian_graph(
            buildings,
            body.currentLat,
            body.currentLng,
            start_name,
            start_b,
            elat,
            elng,
            original.end_name or "",
            end_b,
            pref,
        )
        if route is None:
            route = _route_from_2gis(
                body.currentLat,
                body.currentLng,
                start_name,
                start_b,
                elat,
                elng,
                original.end_name or "",
                end_b,
                pref,
            )
    else:
        route = _route_from_2gis(
            body.currentLat,
            body.currentLng,
            start_name,
            start_b,
            elat,
            elng,
            original.end_name or "",
            end_b,
            pref,
        )
        if route is None:
            route = _route_from_pedestrian_graph(
                buildings,
                body.currentLat,
                body.currentLng,
                start_name,
                start_b,
                elat,
                elng,
                original.end_name or "",
                end_b,
                pref,
            )
    if route is None:
        route = _generate_route(
            buildings,
            body.currentLat,
            body.currentLng,
            start_name,
            start_b,
            elat,
            elng,
            original.end_name or "",
            end_b,
            pref,
        )
    sb.table("routes").insert(_route_to_row(route)).execute()
    return schemas.ApiResponse(success=True, data=_route_out(route))
