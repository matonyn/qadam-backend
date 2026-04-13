from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterator

import httpx

from app.campus_graph import nu_campus_polygon_wkt


_WKT_LINESTRING_RE = re.compile(r"LINESTRING\s*\(\s*(?P<body>.+?)\s*\)\s*$", re.IGNORECASE)


def _parse_linestring_points(selection: str) -> list[tuple[float, float]]:
    """
    2GIS returns WKT like: LINESTRING(lon lat, lon lat, ...)
    Output: [(lat, lon), ...]
    """
    if not selection:
        return []
    m = _WKT_LINESTRING_RE.match(selection.strip())
    if not m:
        return []
    body = m.group("body")
    pts: list[tuple[float, float]] = []
    for part in body.split(","):
        nums = part.strip().split()
        if len(nums) < 2:
            continue
        try:
            lon = float(nums[0])
            lat = float(nums[1])
        except ValueError:
            continue
        pts.append((lat, lon))
    return pts


def _dedupe_points(points: list[tuple[float, float]], eps: float = 1e-7) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for lat, lon in points:
        if out and abs(out[-1][0] - lat) < eps and abs(out[-1][1] - lon) < eps:
            continue
        out.append((lat, lon))
    return out


def _extract_route_geometry(route: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []

    begin = route.get("begin_pedestrian_path") or {}
    begin_sel = ((begin.get("geometry") or {}) if isinstance(begin, dict) else {}).get("selection")
    if isinstance(begin_sel, str):
        points.extend(_parse_linestring_points(begin_sel))

    for m in route.get("maneuvers") or []:
        op = (m or {}).get("outcoming_path") or {}
        for seg in op.get("geometry") or []:
            sel = (seg or {}).get("selection")
            if isinstance(sel, str):
                points.extend(_parse_linestring_points(sel))

    end = route.get("end_pedestrian_path") or {}
    end_sel = ((end.get("geometry") or {}) if isinstance(end, dict) else {}).get("selection")
    if isinstance(end_sel, str):
        points.extend(_parse_linestring_points(end_sel))

    return _dedupe_points(points)


def _extract_instructions(route: dict[str, Any]) -> list[str]:
    instr: list[str] = []
    for m in route.get("maneuvers") or []:
        c = (m or {}).get("comment")
        if isinstance(c, str) and c.strip():
            instr.append(c.strip())
    return instr


@dataclass
class TwoGisRoute:
    distance_m: int
    duration_s: int
    waypoints: list[dict[str, float]]
    instructions: list[str]


def get_walking_route(
    *,
    api_key: str,
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
    locale: str = "en",
    timeout_s: float = 10.0,
) -> TwoGisRoute:
    url = "https://routing.api.2gis.com/routing/7.0.0/global"
    payload = {
        "points": [
            {"type": "stop", "lat": start_lat, "lon": start_lng},
            {"type": "stop", "lat": end_lat, "lon": end_lng},
        ],
        "transport": "walking",
        "locale": locale,
    }

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, params={"key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()

    if (data or {}).get("status") != "OK":
        raise RuntimeError(f"2GIS routing failed: status={(data or {}).get('status')!r}")

    routes = (data or {}).get("result") or []
    if not isinstance(routes, list) or not routes:
        raise RuntimeError("2GIS routing returned empty result")

    route0 = routes[0] or {}
    total_distance = int(route0.get("total_distance") or 0)
    total_duration = int(route0.get("total_duration") or 0)

    geom = _extract_route_geometry(route0)
    waypoints = [{"latitude": lat, "longitude": lon} for (lat, lon) in geom] if geom else []

    instructions = _extract_instructions(route0)
    return TwoGisRoute(
        distance_m=total_distance,
        duration_s=total_duration,
        waypoints=waypoints,
        instructions=instructions,
    )


CATALOG_URL = "https://catalog.api.2gis.com/3.0/items"


def iter_catalog_items_in_polygon(
    *,
    api_key: str,
    polygon_wkt: str,
    item_type: str,
    page_size: int = 50,
    max_pages: int = 50,
    timeout_s: float = 15.0,
) -> Iterator[dict[str, Any]]:
    """
    Paginate 2GIS Places API items inside a polygon (no text query required for type=branch|building).
    """
    page = 1
    fields = "items.id,items.name,items.full_name,items.type,items.point,items.address_name,items.address_comment,items.purpose_name"
    while page <= max_pages:
        params: dict[str, Any] = {
            "key": api_key,
            "polygon": polygon_wkt,
            "type": item_type,
            "page": page,
            "page_size": min(max(1, page_size), 50),
            "fields": fields,
        }
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(CATALOG_URL, params=params)
            r.raise_for_status()
            data = r.json()
        result = (data or {}).get("result") or {}
        items = result.get("items") or []
        if not isinstance(items, list):
            break
        if not items:
            break
        for it in items:
            if isinstance(it, dict):
                yield it
        ps = int(params["page_size"])
        total = int(result.get("total") or 0)
        if total and page * ps >= total:
            break
        if len(items) < ps:
            break
        page += 1


def catalog_item_to_building_row(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map a 2GIS catalog item to a `buildings` table row (snake_case)."""
    tid = item.get("id")
    if not tid or not isinstance(tid, str):
        return None
    pt = item.get("point") or {}
    lat, lon = pt.get("lat"), pt.get("lon")
    if lat is None or lon is None:
        return None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None

    name = (item.get("name") or item.get("full_name") or "Campus place").strip()
    if not name:
        return None
    short = name if len(name) <= 80 else (name[:77] + "...")

    parts: list[str] = []
    for k in ("address_name", "address_comment"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    description = " · ".join(parts) if parts else None

    cat = item.get("purpose_name") or item.get("type") or "campus"
    if isinstance(cat, str):
        cat_s = cat[:80]
    else:
        cat_s = "campus"

    row_id = "dgis-" + hashlib.sha256(tid.encode("utf-8")).hexdigest()[:40]

    return {
        "id": row_id,
        "name": name[:500],
        "short_name": short,
        "description": description[:2000] if description else None,
        "latitude": lat_f,
        "longitude": lon_f,
        "floors": 1,
        "has_elevator": True,
        "has_ramp": True,
        "category": cat_s,
        "image_url": None,
        "twogis_id": tid,
        "data_source": "2gis",
    }


def fetch_nu_campus_catalog_rows(
    api_key: str,
    *,
    types: tuple[str, ...] = ("branch", "building"),
    timeout_s: float = 15.0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Collect catalog rows for Nazarbayev University main polygon (branches + buildings).
    Returns (rows, skipped_without_coords).
    """
    wkt = nu_campus_polygon_wkt()
    seen_tid: set[str] = set()
    rows: list[dict[str, Any]] = []
    skipped = 0
    for t in types:
        for item in iter_catalog_items_in_polygon(
            api_key=api_key,
            polygon_wkt=wkt,
            item_type=t,
            page_size=50,
            max_pages=50,
            timeout_s=timeout_s,
        ):
            tid = item.get("id")
            if not isinstance(tid, str) or tid in seen_tid:
                continue
            row = catalog_item_to_building_row(item)
            if row is None:
                skipped += 1
                continue
            seen_tid.add(tid)
            rows.append(row)
    return rows, skipped
