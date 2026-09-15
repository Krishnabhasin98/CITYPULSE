"""Area Intelligence API — works for any Delhi location, not a fixed list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..services import live, policy
from ..services.area import analyze_area, area_summary, category_directory

router = APIRouter(prefix="/api/area", tags=["Area Intelligence"])


@router.get(
    "/analyze",
    summary="Risk, evidence and live weather for any pincode, area name or GPS fix",
)
def analyze(
    query: str | None = Query(default=None, description="Pincode (110092), area name (Karol Bagh) or free text"),
    pincode: str | None = Query(
        default=None,
        description="Pincode alias, so ?pincode=110043 works the same as ?query=110043",
    ),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    radius: float | None = Query(default=None, ge=200, le=10000, description="Analysis radius in metres"),
    deep: bool = Query(default=False, description="Also run the OpenStreetMap exposure scan (slower)"),
    db: Session = Depends(get_db),
):
    place = (query or "").strip() or (pincode or "").strip() or None
    return analyze_area(db, query=place, latitude=lat, longitude=lon, radius_m=radius, deep=deep)


@router.get("/resolve", summary="Resolve a place without running the full analysis")
def resolve(
    query: str | None = Query(default=None),
    pincode: str | None = Query(default=None, description="Pincode alias for query"),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
):
    from ..services.area import resolve_location

    place_text = (query or "").strip() or (pincode or "").strip() or None
    place, provenance = resolve_location(place_text, lat, lon)
    return {
        "resolved": place is not None,
        "place": place.as_dict() if place else None,
        "provenance": provenance,
    }


@router.get("/summary", summary="City rollup grouped by affected area")
def summary(db: Session = Depends(get_db)):
    return area_summary(db)


@router.get("/monsoon", summary="Live monsoon outlook against water-sensitive incidents")
def monsoon(db: Session = Depends(get_db)):
    return policy.monsoon_outlook(db)


@router.get("/categories", summary="Category to department map used by the classifier")
def categories():
    return {
        "categories": category_directory(),
        "cluster_radius_m": config.CLUSTER_RADIUS_METERS,
        "area_radius_m": config.AREA_RADIUS_METERS,
    }


@router.get("/search", summary="Search OpenStreetMap directly for any Delhi locality")
def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=5, ge=1, le=10),
):
    """Pass-through search so the UI can offer 'did you mean' options."""
    from ..services.http import fetch_json

    result = fetch_json(
        f"{config.NOMINATIM_URL}/search",
        {
            "q": q if "delhi" in q.lower() else f"{q}, Delhi, India",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": limit,
            "countrycodes": "in",
        },
        namespace="geocode",
        ttl_seconds=config.GEOCODE_TTL_SECONDS,
    )
    items = result.data if isinstance(result.data, list) else []
    return {
        "query": q,
        "results": [
            {
                "label": item.get("display_name"),
                "latitude": float(item["lat"]),
                "longitude": float(item["lon"]),
                "postcode": (item.get("address") or {}).get("postcode"),
                "area": (item.get("address") or {}).get("suburb")
                or (item.get("address") or {}).get("neighbourhood")
                or (item.get("address") or {}).get("city"),
            }
            for item in items
        ],
        **result.meta(),
    }


@router.get("/probe", summary="Are the free external services reachable?")
def probe():
    return live.live_status()
