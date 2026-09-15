"""Health, metadata and operations endpoints.

``/api/meta`` exists so the UI fetches the reward matrix, category map and
thresholds from the backend instead of hardcoding a second copy that drifts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import config
from ..core.security import get_optional_user, is_authority, require_authority
from ..database import engine, get_db
from ..models.incident import CivicIncident
from ..models.post import Post
from ..models.user import User
from ..services import live
from ..services.accountability import breach_summary
from ..services.area import category_directory
from ..services.intelligence import action_catalog
from ..services.storage import upload_stats

router = APIRouter(tags=["System"])


@router.get("/health")
def health() -> dict:
    return {"status": "healthy", "version": config.APP_VERSION, "environment": config.ENVIRONMENT}


@router.get("/health/database")
def database_health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "kind": "sqlite" if config.IS_SQLITE else "external",
            "users": db.query(User).count(),
            "incidents": db.query(CivicIncident).count(),
            "reports": db.query(Post).count(),
        }
    except Exception as exc:  # pragma: no cover - infrastructure dependent
        return {"status": "error", "database": "disconnected", "error": str(exc)}


@router.get("/health/deep")
def deep_health(db: Session = Depends(get_db)) -> dict:
    """Everything an operator needs before deciding the deploy is sane."""
    return {
        "status": "healthy",
        "config": config.describe(),
        "counts": {
            "users": db.query(User).count(),
            "incidents": db.query(CivicIncident).count(),
            "open_incidents": db.query(CivicIncident).filter(CivicIncident.status != "resolved").count(),
            "reports": db.query(Post).count(),
        },
        "sla": breach_summary(db),
        "uploads": upload_stats(),
        "cache": {"dir": str(config.CACHE_DIR), "exists": config.CACHE_DIR.exists()},
    }


@router.get("/health/live")
def live_health() -> dict:
    """Actively probe the free external services (can take a few seconds)."""
    return live.live_status()


@router.get("/api/meta")
def meta(current: User | None = Depends(get_optional_user)) -> dict:
    payload = {
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "cluster_radius_m": config.CLUSTER_RADIUS_METERS,
        "area_radius_m": config.AREA_RADIUS_METERS,
        "live_data_enabled": config.ENABLE_LIVE_DATA,
        "categories": category_directory(),
        "credits": action_catalog(),
        "trust_labels": ["Verified", "Needs Verification", "Suspicious"],
        "incident_statuses": ["open", "in_progress", "resolved"],
        "map": {
            "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenStreetMap contributors",
            "default_center": {"latitude": 28.6139, "longitude": 77.2090},
        },
        "external_sources": [
            {"name": "OpenStreetMap Nominatim", "purpose": "area + postal code resolution"},
            {"name": "Open-Meteo", "purpose": "live weather and monsoon outlook"},
            {"name": "OpenStreetMap Overpass", "purpose": "schools, hospitals, markets exposure scan"},
        ],
        "authenticated": current is not None,
    }
    if current is not None:
        payload["role"] = current.role
        payload["can_authority_actions"] = is_authority(current)
    return payload


@router.post("/api/system/cache/clear")
def clear_cache(namespace: str | None = None, _: User = Depends(require_authority)) -> dict:
    from ..services.http import clear_cache as _clear

    removed = _clear(namespace)
    return {"message": f"Cleared {removed} cached live response(s)", "namespace": namespace or "all"}
