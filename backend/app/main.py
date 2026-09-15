"""CityPulse API application.

Startup order matters and is all in one place: adopt a legacy database if one
exists, create tables, apply additive migrations, seed demo data, then start the
SLA escalation sweep. The built React app is served from the same process when
``frontend/dist`` exists, so a single container is a complete deployment.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import config
from .api.area import router as area_router
from .api.assistant import router as assistant_router
from .api.auth import router as auth_router
from .api.incidents import router as incidents_router
from .api.posts import router as posts_router
from .api.system import router as system_router
from .api.uploads import router as uploads_router
from .database import Base, SessionLocal, adopt_legacy_database, engine
from .models import CivicAction, CivicIncident, CreditTransaction, IncidentReport, Post, User  # noqa: F401
from .services.errors import CityPulseError
from .services.intelligence import escalation_sweep
from .services.migrations import apply_additive_migrations
from .services.seed import seed_if_empty
from .services.storage import UPLOAD_DIR

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("citypulse")


async def _sla_sweeper() -> None:
    """Re-check deadlines in the background so breaches surface without a request."""
    while True:
        await asyncio.sleep(config.SCHEDULER_INTERVAL_SECONDS)
        try:
            with SessionLocal() as db:
                escalated = escalation_sweep(db)
                if escalated:
                    logger.info("SLA sweep escalated incidents %s", escalated)
        except Exception:  # pragma: no cover - defensive background loop
            logger.exception("SLA sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    adopt_legacy_database()
    Base.metadata.create_all(bind=engine)
    applied = apply_additive_migrations()
    if applied:
        logger.info("Applied %s schema migration(s)", len(applied))

    with SessionLocal() as db:
        result = seed_if_empty(db)
        if result.get("seeded"):
            logger.info("Seeded demo data: %s", result)
        escalation_sweep(db)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("CityPulse %s starting with %s", config.APP_VERSION, config.describe())
    if config.USING_DEV_SECRET and config.IS_PRODUCTION:
        logger.warning("Running in production with the default JWT secret. Set JWT_SECRET_KEY.")

    sweep_task = None
    if config.ENABLE_SCHEDULER:
        sweep_task = asyncio.create_task(_sla_sweeper())

    try:
        yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()
            with suppress(asyncio.CancelledError):
                await sweep_task


app = FastAPI(
    title="CityPulse API",
    description=(
        "AI-assisted civic intelligence for Delhi: reports cluster into real-world incidents, "
        "every incident carries a response deadline, and live OpenStreetMap/Open-Meteo signals "
        "keep the risk picture current."
    ),
    version=config.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=config.CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CityPulseError)
async def citypulse_error_handler(_request: Request, exc: CityPulseError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, **exc.extra},
    )


app.include_router(system_router)
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(incidents_router)
app.include_router(area_router)
app.include_router(uploads_router)
app.include_router(assistant_router)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def api_banner() -> dict:
    return {
        "message": "CityPulse API is running",
        "status": "online",
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/api", include_in_schema=False)
def api_root():
    """Always-available API banner, regardless of frontend hosting."""
    return api_banner()


@app.get("/", include_in_schema=False)
def root():
    """Serve the built app when it exists, otherwise explain that this is the API.

    Without this the single-container deploy answered ``GET /`` with JSON, so a
    visitor to the published URL saw an API banner instead of the application.
    """
    index = config.FRONTEND_DIST / "index.html"
    if config.SERVE_FRONTEND and index.exists():
        return FileResponse(index)
    return api_banner()


# ---------------------------------------------------------------------------
# Optional single-container frontend hosting
# ---------------------------------------------------------------------------
if config.SERVE_FRONTEND and config.FRONTEND_DIST.exists():
    assets_dir = config.FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """Serve the built SPA, letting the router own every non-API path."""
        if full_path.startswith(("api/", "uploads/", "docs", "redoc", "openapi.json")):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (config.FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and config.FRONTEND_DIST in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:

    @app.get("/{full_path:path}", include_in_schema=False)
    async def missing_frontend(full_path: str):
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Not found",
                "hint": "Run the frontend dev server, or build it (npm run build in frontend/) to serve it from here.",
            },
        )
