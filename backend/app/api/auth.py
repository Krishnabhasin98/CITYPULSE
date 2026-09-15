"""Authentication routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session

from .. import config
from ..core.security import get_current_user, hash_password, verify_and_upgrade_password
from ..database import get_db
from ..models.user import User
from ..schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile
from ..services import credits as credit_service
from ..services.accountability import city_scorecard

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def token_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "credits": user.credits,
        "reputation": user.reputation,
        "ward": user.ward,
    }


def profile_payload(db: Session, user: User) -> dict:
    reputation = credit_service.reputation_for_user(db, user)
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "credits": user.credits,
        "reputation": user.reputation,
        "ward": user.ward,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "reputation_detail": reputation,
        "ledger": credit_service.ledger_for_user(db, user),
        "is_authority": (user.role or "").lower() in {"authority", "admin"},
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role="citizen",
        credits=0,
        reputation=100,
        ward=(data.ward or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_payload(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if user is None:
        # Same generic message and similar work either way: never reveal which
        # emails exist.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    valid, upgraded = verify_and_upgrade_password(data.password, user.password_hash)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if upgraded:
        # Transparent hash upgrade so no account is ever locked out by a
        # change of hashing parameters.
        user.password_hash = upgraded
        db.commit()
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return token_payload(user)


@router.get("/me", response_model=UserProfile)
def me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return profile_payload(db, current_user)


@router.get("/ledger")
def ledger(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {
        "credits": current_user.credits,
        "reputation": credit_service.reputation_for_user(db, current_user),
        "entries": credit_service.ledger_for_user(db, current_user, limit=50),
    }


@router.post("/demo-session")
def demo_session(role: str = "citizen", db: Session = Depends(get_db)):
    """One-click sign-in for demos and reviewers (disabled in production)."""
    if config.IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not available")
    email = "authority@citypulse.local" if role.lower() in {"authority", "admin"} else "citizen@citypulse.local"
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Demo accounts have not been seeded")
    return token_payload(user)


@router.get("/city-scorecard")
def scorecard(db: Session = Depends(get_db)):
    """Public accountability snapshot: deadlines met, deadlines missed."""
    return city_scorecard(db)
