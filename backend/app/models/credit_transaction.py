from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    TIMESTAMP,
    ForeignKey
)
from sqlalchemy.sql import func

from ..database import Base


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    user_id = Column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    action_id = Column(
        BigInteger,
        ForeignKey(
            "civic_actions.id",
            ondelete="SET NULL"
        )
    )

    amount = Column(
        Integer,
        nullable=False
    )

    reason = Column(
        String(255),
        nullable=False
    )

    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp()
    )