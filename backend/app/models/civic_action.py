from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from ..database import Base


class CivicAction(Base):
    __tablename__ = "civic_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    incident_id = Column(
        BigInteger, ForeignKey("civic_incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    action_type = Column(String(30), nullable=False)

    description = Column(Text)

    evidence_url = Column(String(1000))

    verification_status = Column(String(20), nullable=False, default="pending")

    credits_awarded = Column(Integer, nullable=False, default=0)

    credits_released = Column(Boolean, nullable=False, default=False)

    verified_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    verification_note = Column(String(500))

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())

    verified_at = Column(TIMESTAMP)
