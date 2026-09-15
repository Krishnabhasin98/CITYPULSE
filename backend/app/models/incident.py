from sqlalchemy import Boolean, Column, DECIMAL, Integer, String, TIMESTAMP, Text
from sqlalchemy.sql import func

from ..database import Base


class CivicIncident(Base):
    __tablename__ = "civic_incidents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False, default="Public Works")
    title = Column(String(255), nullable=False)
    description = Column(Text)
    center_latitude = Column(DECIMAL(10, 7))
    center_longitude = Column(DECIMAL(10, 7))
    severity = Column(DECIMAL(5, 2), default=0)
    confidence = Column(DECIMAL(5, 4), default=0)
    report_count = Column(Integer, nullable=False, default=0)
    support_count = Column(Integer, nullable=False, default=0)
    flag_count = Column(Integer, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="open")
    trust_status = Column(String(30), nullable=False, default="Needs Verification")
    affected_area = Column(String(255))
    # Administrative context resolved from OpenStreetMap when available.
    zone = Column(String(120))
    pincode = Column(String(10), index=True)
    city_health_impact = Column(DECIMAL(5, 2), default=0)
    escalated = Column(Boolean, nullable=False, default=False)
    escalated_at = Column(TIMESTAMP)
    first_report_at = Column(TIMESTAMP)
    last_report_at = Column(TIMESTAMP)
    last_action_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
