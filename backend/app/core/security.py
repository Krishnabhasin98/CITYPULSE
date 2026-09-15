"""Authentication primitives: password hashing and JWT bearer handling.

Password hashing uses Argon2id through ``pwdlib``. If that dependency is
missing we refuse to start instead of quietly downgrading every password to an
unsalted SHA-256 digest: that silent fallback previously made ``/login`` return
401 for every seeded account while JWT-issued sessions kept working, which is
almost impossible to debug from the outside.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models.user import User

logger = logging.getLogger("citypulse.security")

try:  # pragma: no cover - import guard
    from pwdlib import PasswordHash
    from pwdlib.exceptions import UnknownHashError
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "pwdlib is required for password hashing. Install the backend "
        "requirements (pip install -r backend/requirements.txt) and run the app "
        "with that interpreter, e.g. .venv/Scripts/python -m uvicorn app.main:app "
        "--app-dir backend. Silently falling back to an unsalted hash scheme "
        "would break every existing account, so CityPulse refuses to start."
    ) from exc

_password_hash = PasswordHash.recommended()

SECRET_KEY = config.JWT_SECRET_KEY
ALGORITHM = config.JWT_ALGORITHM
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True only when the password matches a supported stored hash."""
    if not hashed_password:
        return False
    try:
        return bool(_password_hash.verify(password, hashed_password))
    except UnknownHashError:
        logger.warning("Rejected login: stored hash uses an unsupported scheme")
        return False
    except Exception:  # pragma: no cover - defensive
        logger.warning("Password verification failed unexpectedly", exc_info=True)
        return False


def verify_and_upgrade_password(password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Verify a password and return a fresh hash when the parameters changed."""
    if not hashed_password:
        return False, None
    try:
        is_valid, updated = _password_hash.verify_and_update(password, hashed_password)
        return bool(is_valid), updated
    except UnknownHashError:
        logger.warning("Rejected login: stored hash uses an unsupported scheme")
        return False, None
    except Exception:  # pragma: no cover - defensive
        logger.warning("Password verification failed unexpectedly", exc_info=True)
        return False, None


def _decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user = db.query(User).filter(User.id == _decode_token(credentials.credentials)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def require_authority(current_user: User = Depends(get_current_user)) -> User:
    """Guard for municipal-only operations."""
    if not is_authority(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority role required for this action",
        )
    return current_user


def is_authority(user: User | None) -> bool:
    if user is None:
        return False
    return (user.role or "").lower() in {"authority", "admin"}
