"""
Nazarbayev University campus pedestrian network (2GIS-style: graph + shortest path).

Uses fixed walkway vertices (plazas / main corridors) plus dynamic links from each
building to nearby vertices — similar to pedestrian routing on a footpath graph,
without relying on proprietary 2GIS data.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app import models

R_EARTH = 6371000.0

# Nazarbayev University main site — bounding ring (lat, lon), closed implicitly for point-in-polygon
# Matches the polygon used for 2GIS Catalog sync (Kabanbay Batyr / central campus blocks).
NU_CAMPUS_RING_LL: list[tuple[float, float]] = [
    (51.0885, 71.3965),
    (51.0885, 71.4035),
    (51.0932, 71.4035),
    (51.0932, 71.3965),
]


def nu_campus_polygon_wkt() -> str:
    """WKT POLYGON for 2GIS Places API (lon lat vertex order)."""
    verts = [f"{lon} {lat}" for lat, lon in NU_CAMPUS_RING_LL]
    verts.append(verts[0])
    return "POLYGON((" + ", ".join(verts) + "))"


def point_in_nu_campus(lat: float, lon: float) -> bool:
    """True if the coordinate lies inside the NU campus import / routing-preference polygon."""
    ring = NU_CAMPUS_RING_LL
    n = len(ring)
    x, y = lon, lat
    inside = False
    for i in range(n):
        j = (i + 1) % n
        xi, yi = ring[i][1], ring[i][0]
        xj, yj = ring[j][1], ring[j][0]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi):
            inside = not inside
    return inside


# Main campus (Astana) — connector nodes along plazas / malls (approximate)
NU_AUX_NODES: dict[str, tuple[float, float]] = {
    "nu-west": (51.0901, 71.39795),
    "nu-plaza": (51.09035, 71.39890),
    "nu-mall-n": (51.09085, 71.39935),
    "nu-mall-e": (51.09055, 71.40015),
    "nu-east-hub": (51.0910, 71.40065),
    "nu-south-walk": (51.08975, 71.39985),
}

# (a, b, crowd_multiplier, edge_accessible) — bidirectional; length from live coordinates
NU_AUX_LINKS: list[tuple[str, str, float, bool]] = [
    ("nu-west", "nu-plaza", 1.0, True),
    ("nu-plaza", "nu-mall-n", 1.0, True),
    ("nu-plaza", "nu-mall-e", 1.0, True),
    ("nu-plaza", "nu-south-walk", 1.0, True),
    ("nu-mall-n", "nu-mall-e", 1.08, True),
    ("nu-mall-e", "nu-east-hub", 1.05, True),
    ("nu-mall-e", "nu-south-walk", 1.0, True),
    ("nu-east-hub", "nu-south-walk", 1.12, True),
]

VIRTUAL_FROM = "__from__"
VIRTUAL_TO = "__to__"

MAX_BUILDING_TO_AUX_M = 520.0
MAX_BUILDING_TO_BUILDING_M = 260.0
VIRTUAL_ATTACH_M = 620.0
VIRTUAL_ATTACH_TOP_K = 8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(min(1.0, a)))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _turn_hint(prev_b: float | None, cur_b: float) -> str | None:
    if prev_b is None:
        return None
    d = (cur_b - prev_b + 540) % 360 - 180
    if abs(d) < 28:
        return "Continue straight"
    if d > 0:
        return "Turn left"
    return "Turn right"


def _building_accessible(b: models.Building) -> bool:
    return bool(b.has_ramp or b.has_elevator)


def _coord(
    node_id: str,
    buildings: dict[str, models.Building],
) -> tuple[float, float] | None:
    if node_id in buildings:
        b = buildings[node_id]
        if b.latitude is None or b.longitude is None:
            return None
        return (b.latitude, b.longitude)
    if node_id in NU_AUX_NODES:
        return NU_AUX_NODES[node_id]
    return None


def _build_adjacency(
    buildings: dict[str, models.Building],
) -> dict[str, list[tuple[str, float, bool, float]]]:
    """
    Adjacency: neighbor_id, length_m, edge_accessible, crowd_mult (for least_crowded weighting).
    """
    adj: dict[str, list[tuple[str, float, bool, float]]] = {}

    def add_edge(u: str, v: str, length_m: float, acc: bool, crowd: float) -> None:
        adj.setdefault(u, []).append((v, length_m, acc, crowd))
        adj.setdefault(v, []).append((u, length_m, acc, crowd))

    # Aux–aux links
    for a, b, crowd, acc in NU_AUX_LINKS:
        ca, cb = NU_AUX_NODES.get(a), NU_AUX_NODES.get(b)
        if not ca or not cb:
            continue
        d = haversine_m(ca[0], ca[1], cb[0], cb[1])
        add_edge(a, b, d, acc, crowd)

    bids = [k for k, b in buildings.items() if b.latitude is not None and b.longitude is not None]

    # Building ↔ nearest aux nodes (footpath entry)
    for bid in bids:
        b = buildings[bid]
        bla, blo = b.latitude, b.longitude
        aux_d: list[tuple[float, str]] = []
        for aid, (ala, alo) in NU_AUX_NODES.items():
            dist = haversine_m(bla, blo, ala, alo)
            aux_d.append((dist, aid))
        aux_d.sort(key=lambda x: x[0])
        for dist, aid in aux_d[:3]:
            if dist <= MAX_BUILDING_TO_AUX_M:
                add_edge(bid, aid, dist, True, 1.0)

    # Short direct links between neighbouring buildings (adjacent blocks)
    for i, bid1 in enumerate(bids):
        b1 = buildings[bid1]
        for bid2 in bids[i + 1 :]:
            b2 = buildings[bid2]
            d = haversine_m(b1.latitude, b1.longitude, b2.latitude, b2.longitude)
            if d <= MAX_BUILDING_TO_BUILDING_M:
                add_edge(bid1, bid2, d, True, 1.05)

    return adj


def _edge_weight(
    length_m: float,
    crowd: float,
    edge_acc: bool,
    preference: str,
    to_id: str,
    end_id: str | None,
    buildings: dict[str, models.Building],
) -> float:
    w = length_m
    if preference == "least_crowded":
        w *= crowd
    elif preference == "accessible":
        w *= crowd
        if to_id in buildings and to_id != end_id:
            if not _building_accessible(buildings[to_id]):
                w *= 4.0
        if not edge_acc:
            w *= 2.0
    else:
        w *= crowd ** 0.35
    return w


def _dijkstra(
    adj: dict[str, list[tuple[str, float, bool, float]]],
    start: str,
    end: str,
    preference: str,
    end_building_id: str | None,
    buildings: dict[str, models.Building],
) -> tuple[float, dict[str, str | None]] | None:
    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, str | None] = {start: None}
    pq: list[tuple[float, str]] = [(0.0, start)]

    while pq:
        d_u, u = heapq.heappop(pq)
        if d_u > dist.get(u, math.inf):
            continue
        if u == end:
            return d_u, prev
        for v, length_m, edge_acc, crowd in adj.get(u, []):
            w = _edge_weight(length_m, crowd, edge_acc, preference, v, end_building_id, buildings)
            nd = d_u + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return None


def _attach_virtual(
    adj: dict[str, list[tuple[str, float, bool, float]]],
    virtual: str,
    lat: float,
    lng: float,
    node_ids: list[str],
    buildings: dict[str, models.Building],
) -> None:
    scored: list[tuple[float, str]] = []
    for nid in node_ids:
        c = _coord(nid, buildings)
        if c is None:
            continue
        dm = haversine_m(lat, lng, c[0], c[1])
        scored.append((dm, nid))
    scored.sort(key=lambda x: x[0])
    for dm, nid in scored[:VIRTUAL_ATTACH_TOP_K]:
        if dm <= VIRTUAL_ATTACH_M:
            adj.setdefault(virtual, []).append((nid, dm, True, 1.0))
            adj.setdefault(nid, []).append((virtual, dm, True, 1.0))


def _reconstruct(prev: dict[str, str | None], end: str) -> list[str]:
    out: list[str] = []
    cur: str | None = end
    while cur is not None:
        out.append(cur)
        cur = prev.get(cur)
    out.reverse()
    return out


@dataclass
class PedestrianRouteResult:
    waypoints: list[dict[str, float]]
    distance_m: float
    instructions: list[str]
    is_accessible: bool
    crowd_level: str


def compute_pedestrian_route(
    buildings: list[models.Building],
    start_lat: float,
    start_lng: float,
    start_name: str,
    end_lat: float,
    end_lng: float,
    end_name: str,
    preference: str,
    end_building: models.Building | None,
) -> PedestrianRouteResult | None:
    """
    Shortest-path on campus walk graph. Returns None if graph is unusable (no buildings).
    """
    bmap = {b.id: b for b in buildings if b.latitude is not None and b.longitude is not None}
    if len(bmap) < 2 and len(bmap) + len(NU_AUX_NODES) < 3:
        return None

    adj = _build_adjacency(bmap)
    node_ids = list({n for n in adj} | set(bmap) | set(NU_AUX_NODES))

    _attach_virtual(adj, VIRTUAL_FROM, start_lat, start_lng, node_ids, bmap)
    _attach_virtual(adj, VIRTUAL_TO, end_lat, end_lng, node_ids, bmap)

    end_bid = end_building.id if end_building is not None else None
    out = _dijkstra(adj, VIRTUAL_FROM, VIRTUAL_TO, preference, end_bid, bmap)
    if out is None:
        return None
    geo_dist, prev = out
    path = _reconstruct(prev, VIRTUAL_TO)
    if len(path) < 2:
        return None

    inner = [n for n in path if n not in (VIRTUAL_FROM, VIRTUAL_TO)]
    waypoints: list[dict[str, float]] = [{"latitude": start_lat, "longitude": start_lng}]
    for nid in inner:
        c = _coord(nid, bmap)
        if c is None:
            continue
        waypoints.append({"latitude": c[0], "longitude": c[1]})
    waypoints.append({"latitude": end_lat, "longitude": end_lng})

    # Dedupe consecutive identical coords
    slim: list[dict[str, float]] = []
    for w in waypoints:
        if slim and abs(slim[-1]["latitude"] - w["latitude"]) < 1e-7 and abs(slim[-1]["longitude"] - w["longitude"]) < 1e-7:
            continue
        slim.append(w)
    waypoints = slim if len(slim) >= 2 else waypoints

    geo_length = 0.0
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        geo_length += haversine_m(a["latitude"], a["longitude"], b["latitude"], b["longitude"])

    # Turn-by-turn style (pedestrian, similar to map apps)
    instructions = [f"Start: {start_name} → {end_name}"]
    prev_brg: float | None = None
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        brg = _bearing_deg(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
        if prev_brg is not None:
            hint = _turn_hint(prev_brg, brg)
            if hint and hint != "Continue straight":
                instructions.append(hint)
        prev_brg = brg
    via: list[str] = []
    seen_names: set[str] = set()
    for nid in inner:
        if nid not in bmap:
            continue
        bb = bmap[nid]
        label = (bb.short_name or bb.name or "").strip()
        if label and label not in seen_names:
            seen_names.add(label)
            via.append(label)
    for v in via[:4]:
        instructions.append(f"Along main walkways near {v}")
    instructions.append(f"Arrive at {end_name}")

    if preference == "accessible":
        instructions.append("Prefer ramps and elevators at building entrances")
    elif preference == "least_crowded":
        instructions.append("Route favors less busy walkway segments where modeled")

    start_b = None
    if bmap:
        nearest_s = min(
            bmap.values(),
            key=lambda bb: haversine_m(start_lat, start_lng, bb.latitude, bb.longitude),
        )
        if haversine_m(start_lat, start_lng, nearest_s.latitude, nearest_s.longitude) < 130:
            start_b = nearest_s

    is_acc = True
    if end_building is not None:
        is_acc = _building_accessible(end_building)
    if start_b is not None:
        is_acc = is_acc and _building_accessible(start_b)
    if preference == "accessible":
        for nid in inner:
            if nid in bmap and not _building_accessible(bmap[nid]):
                is_acc = False
                break

    crowd = "low" if preference == "least_crowded" else ("low" if preference == "accessible" else "medium")
    return PedestrianRouteResult(
        waypoints=waypoints,
        distance_m=geo_length,
        instructions=instructions,
        is_accessible=is_acc,
        crowd_level=crowd,
    )
