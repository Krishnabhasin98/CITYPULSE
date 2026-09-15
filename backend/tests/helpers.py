"""Test bootstrap.

Environment is configured *before* any application module is imported, because
``app.config`` reads its settings at import time. Tests run against a throwaway
SQLite file with live external lookups switched off, so they are fast,
deterministic and never touch the developer's demo database.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="citypulse-tests-"))
TEST_DB = TEMP_DIR / "test.db"

os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["CITYPULSE_CACHE_DIR"] = str(TEMP_DIR / "cache")
os.environ["ENABLE_LIVE_DATA"] = "false"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["JWT_SECRET_KEY"] = "citypulse-test-secret"

from app import config  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.civic_action import CivicAction  # noqa: E402
from app.models.incident import CivicIncident  # noqa: E402
from app.models.incident_report import IncidentReport  # noqa: E402
from app.models.post import Post  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.intelligence import ingest_post  # noqa: E402

CONNAUGHT_PLACE = (28.6328, 77.2197)
DWARKA = (28.5806, 77.0460)


def _cleanup() -> None:
    """Release pooled connections and delete the throwaway test directory."""
    engine.dispose()
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


atexit.register(_cleanup)


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


class DatabaseTestCase(unittest.TestCase):
    """Base class giving each test a clean database and a session."""

    def setUp(self) -> None:
        reset_database()
        self.db = SessionLocal()
        self.addCleanup(self.db.close)

    # -- fixtures ---------------------------------------------------------
    def make_user(self, email: str = "citizen@test.local", role: str = "citizen", credits: int = 0) -> User:
        user = User(
            name=email.split("@")[0].title(),
            email=email,
            password_hash=hash_password("password123"),
            role=role,
            credits=credits,
            reputation=100,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def make_authority(self) -> User:
        return self.make_user("authority@test.local", role="authority")

    def report(
        self,
        user: User,
        description: str,
        latitude: float | None = CONNAUGHT_PLACE[0],
        longitude: float | None = CONNAUGHT_PLACE[1],
        **extra,
    ) -> dict:
        payload = {
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
        }
        payload.update(extra)
        return ingest_post(self.db, user, payload)

    def incident_count(self) -> int:
        return self.db.query(CivicIncident).count()

    def action_count(self) -> int:
        return self.db.query(CivicAction).count()
