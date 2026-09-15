from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DECIMAL,
    Integer,
    TIMESTAMP,
    ForeignKey
)
from sqlalchemy.sql import func

from ..database import Base


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    incident_id = Column(
        BigInteger,
        ForeignKey(
            "civic_incidents.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    post_id = Column(
        BigInteger,
        ForeignKey(
            "posts.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    match_confidence = Column(
        DECIMAL(5, 4),
        default=0
    )

    match_reason = Column(String(500))

    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp()
    )