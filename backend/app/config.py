"""Central configuration for CityPulse.

Everything is optional and zero-cost by default: no API keys, no paid services.
Every value can be overridden with an environment variable (or backend/.env) so
the exact same code runs on a laptop, in Docker, or on a free hosting tier.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
PROJECT_ROOT = BASE_DIR.parent  # repository root
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _number(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "CityPulse")
APP_VERSION = "2.0.0"
ENVIRONMENT = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT in {"production", "prod"}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DEV_JWT_SECRET = "citypulse-local-dev-secret-change-me"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or DEV_JWT_SECRET
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(_number("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))
USING_DEV_SECRET = JWT_SECRET_KEY == DEV_JWT_SECRET


def new_jwt_secret() -> str:
    """Used by the setup helper to mint a strong secret."""
    return secrets.token_urlsafe(48)


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


DEFAULT_SQLITE_PATH = BASE_DIR / "citypulse.db"
LEGACY_SQLITE_PATH = PROJECT_ROOT / "citypulse.db"

_raw_database_url = (os.getenv("DATABASE_URL") or "").strip()
if _raw_database_url:
    # A relative sqlite path such as sqlite:///./citypulse.db used to resolve
    # against whatever directory uvicorn happened to start in, which silently
    # produced two different databases. Resolve it against backend/ instead.
    if _raw_database_url.startswith("sqlite:///./"):
        DATABASE_URL = _sqlite_url(BASE_DIR / _raw_database_url.removeprefix("sqlite:///./"))
    else:
        DATABASE_URL = _raw_database_url
else:
    DATABASE_URL = _sqlite_url(DEFAULT_SQLITE_PATH)

IS_SQLITE = DATABASE_URL.startswith("sqlite")
SQL_ECHO = _flag("SQL_ECHO", False)


# --------------------------------------------------------------------------
# HTTP / CORS
# --------------------------------------------------------------------------
CORS_ORIGINS = _csv(
    "CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)
CORS_ALLOW_ORIGIN_REGEX = os.getenv("CORS_ALLOW_ORIGIN_REGEX") or r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

# --------------------------------------------------------------------------
# Live (but free) external signals
# --------------------------------------------------------------------------
ENABLE_LIVE_DATA = _flag("ENABLE_LIVE_DATA", True)
HTTP_TIMEOUT_SECONDS = _number("CITYPULSE_HTTP_TIMEOUT", 6.0)
# Nominatim requires a descriptive User-Agent and rejects placeholder contact
# domains outright (a UA containing example.org returns HTTP 403), so the
# default keeps a client identifier without a fake address. Set a real contact
# in CITYPULSE_USER_AGENT before running heavy traffic against public OSM.
HTTP_USER_AGENT = os.getenv(
    "CITYPULSE_USER_AGENT",
    "CityPulse/2.0 (self-hosted civic reporting demo)",
)
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OVERPASS_ENABLED = _flag("OVERPASS_ENABLED", True)

# Background upkeep (SLA escalation sweep) — off in tests, on in the app.
ENABLE_SCHEDULER = _flag("ENABLE_SCHEDULER", True)
SCHEDULER_INTERVAL_SECONDS = int(_number("SCHEDULER_INTERVAL_SECONDS", 300))

CACHE_DIR = Path(os.getenv("CITYPULSE_CACHE_DIR") or (BASE_DIR / ".cache"))
GEOCODE_TTL_SECONDS = int(_number("CITYPULSE_GEOCODE_TTL", 60 * 60 * 24 * 30))
WEATHER_TTL_SECONDS = int(_number("CITYPULSE_WEATHER_TTL", 60 * 20))
AMENITY_TTL_SECONDS = int(_number("CITYPULSE_AMENITY_TTL", 60 * 60 * 24 * 3))
CACHE_ENABLED = _flag("CITYPULSE_CACHE_ENABLED", True)

# --------------------------------------------------------------------------
# Civic engine thresholds
# --------------------------------------------------------------------------
CLUSTER_RADIUS_METERS = _number("CLUSTER_RADIUS_METERS", 180.0)
AREA_RADIUS_METERS = _number("AREA_RADIUS_METERS", 1500.0)
MAX_AMENITY_RADIUS_METERS = _number("MAX_AMENITY_RADIUS_METERS", 900.0)

# Email domains accepted without full deliverability validation. The shipped
# demo accounts use @citypulse.local, which strict email validation rejects as
# a special-use domain — that mismatch used to turn every documented demo login
# into a 422.
SPECIAL_USE_EMAIL_SUFFIXES = tuple(_csv("SPECIAL_USE_EMAIL_SUFFIXES", [".local", ".test", ".internal", ".localhost"]))

# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or (BASE_DIR / "uploads"))
MAX_UPLOAD_MB = _number("MAX_UPLOAD_MB", 8.0)
ALLOWED_IMAGE_TYPES = _csv(
    "ALLOWED_IMAGE_TYPES",
    ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"],
)

# --------------------------------------------------------------------------
# Frontend hosting (single-container deploy)
# --------------------------------------------------------------------------
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST") or (PROJECT_ROOT / "frontend" / "dist"))
SERVE_FRONTEND = _flag("SERVE_FRONTEND", True)

# --------------------------------------------------------------------------
# Demo accounts (created only when the database is empty)
# --------------------------------------------------------------------------
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "password123")
SEED_DEMO_DATA = _flag("SEED_DEMO_DATA", True)


def describe() -> dict:
    """Safe, secret-free summary for /health and startup logs."""
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "database": DATABASE_URL.split("@")[-1],
        "database_kind": "sqlite" if IS_SQLITE else "external",
        "live_data_enabled": ENABLE_LIVE_DATA,
        "cache_dir": str(CACHE_DIR),
        "cluster_radius_m": CLUSTER_RADIUS_METERS,
        "cors_origins": CORS_ORIGINS,
        "jwt_secret_is_default": USING_DEV_SECRET,
        "serve_frontend": SERVE_FRONTEND and FRONTEND_DIST.exists(),
    }
