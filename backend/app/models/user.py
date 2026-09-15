from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    role = Column(String(20), nullable=False, default="citizen")

    credits = Column(Integer, nullable=False, default=0)

    # Rolling 0-100 reputation derived from the credit ledger.
    reputation = Column(Integer, nullable=False, default=100)

    # Optional neighbourhood captured at signup, used for personalisation.
    ward = Column(String(120))

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
