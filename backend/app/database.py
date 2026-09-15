import logging
import shutil
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

logger = logging.getLogger("citypulse.database")

BASE_DIR = config.BASE_DIR

connect_args = {}
if config.IS_SQLITE:
    # FastAPI serves requests from a thread pool; SQLite must allow cross-thread
    # use of the connection handed to a single request.
    connect_args = {"check_same_thread": False}

engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=not config.IS_SQLITE,
    connect_args=connect_args,
    echo=config.SQL_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if config.IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        try:
            # WAL keeps readers working while a report is being written.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def sqlite_file_path() -> Path | None:
    """Return the on-disk file backing the configured SQLite database."""
    if not config.IS_SQLITE:
        return None
    raw = config.DATABASE_URL.split("sqlite:///")[-1]
    if raw in {"", ":memory:"}:
        return None
    return Path(raw)


def adopt_legacy_database() -> bool:
    """Copy a legacy ``./citypulse.db`` into the canonical location once.

    Older revisions created the SQLite file relative to the working directory,
    which left a populated database at the repository root while every other
    path pointed at ``backend/citypulse.db``. Adopt it so existing demo data is
    not silently abandoned.
    """
    target = sqlite_file_path()
    legacy = config.LEGACY_SQLITE_PATH
    if target is None or legacy == target or not legacy.exists() or target.exists():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
        logger.info("Adopted legacy database %s -> %s", legacy, target)
        return True
    except OSError as exc:  # pragma: no cover - filesystem dependent
        logger.warning("Could not adopt legacy database %s: %s", legacy, exc)
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
