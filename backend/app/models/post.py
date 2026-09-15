from sqlalchemy import BigInteger, Column, DECIMAL, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.sql import func

from ..database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    department = Column(String(100))
    latitude = Column(DECIMAL(10, 7))
    longitude = Column(DECIMAL(10, 7))
    address = Column(String(500))
    pincode = Column(String(10), index=True)
    image_url = Column(String(1000))
    ai_category = Column(String(100))
    ai_severity = Column(DECIMAL(5, 2))
    ai_confidence = Column(DECIMAL(5, 4))
    trust_status = Column(String(30), nullable=False, default="Needs Verification")
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
