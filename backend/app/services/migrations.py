"""Additive schema migrations.

CityPulse intentionally avoids a migration framework (no Alembic dependency,
no extra deploy step) but still has to keep an existing database working when
new columns appear. Every migration here only *adds* a nullable/defaulted
column, which is safe to run on SQLite and PostgreSQL at startup and is a no-op
once applied.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from ..database import engine

logger = logging.getLogger("citypulse.migrations")

BOOLEAN_DEFAULT_TRUE = "BOOLEAN NOT NULL DEFAULT {value}"


def _boolean(default: bool) -> str:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        return f"BOOLEAN NOT NULL DEFAULT {'true' if default else 'false'}"
    return f"BOOLEAN NOT NULL DEFAULT {1 if default else 0}"


ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("reputation", "INTEGER NOT NULL DEFAULT 100"),
        ("ward", "VARCHAR(120)"),
    ],
    "posts": [
        ("pincode", "VARCHAR(10)"),
    ],
    "civic_incidents": [
        ("zone", "VARCHAR(120)"),
        ("pincode", "VARCHAR(10)"),
        ("escalated", _boolean(False)),
        ("escalated_at", "TIMESTAMP"),
        ("last_action_at", "TIMESTAMP"),
    ],
    "civic_actions": [
        ("credits_released", _boolean(False)),
        ("verified_by", "BIGINT"),
        ("verification_note", "VARCHAR(500)"),
    ],
}


def apply_additive_migrations() -> list[str]:
    """Add any missing columns; returns the list of applied statements."""
    applied: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, columns in ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl in columns:
            if name in present:
                continue
            statement = f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
                applied.append(statement)
                logger.info("Applied migration: %s", statement)
            except Exception as exc:  # pragma: no cover - dialect dependent
                logger.warning("Migration failed (%s): %s", statement, exc)
    return applied
