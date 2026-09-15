from typing import Annotated, Optional

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, Field

from .. import config


def normalise_email(value: str) -> str:
    """Validate and normalise an email address.

    Real addresses go through ``email_validator``. Domains reserved for local
    use (``.local``, ``.test``, ``.internal``) are accepted on syntax alone,
    because the shipped demo accounts are ``citizen@citypulse.local`` and strict
    validation rejected them with a 422 — which broke the documented login.
    """
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError("Email is required")

    local, separator, domain = candidate.partition("@")
    if not separator or not local or not domain or " " in candidate:
        raise ValueError("Enter a valid email address")

    if domain.lower().endswith(config.SPECIAL_USE_EMAIL_SUFFIXES):
        if "." not in domain or not local.replace(".", "").replace("+", "").replace("_", "").replace("-", "").isalnum():
            raise ValueError("Enter a valid email address")
        return f"{local.lower()}@{domain.lower()}"

    try:
        return validate_email(candidate, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


EmailAddress = Annotated[str, AfterValidator(normalise_email)]


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailAddress
    password: str = Field(min_length=6, max_length=72)
    ward: Optional[str] = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_minutes: int
    user_id: int
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    credits: Optional[int] = None
    reputation: Optional[int] = None
    ward: Optional[str] = None


class ReputationDetail(BaseModel):
    credits: int
    lifetime_earned: int
    penalties: int
    reputation_score: int
    tier: str
    ledger_entries: int


class UserProfile(BaseModel):
    user_id: int
    name: str
    email: Optional[str] = None
    role: str
    credits: int
    reputation: Optional[int] = None
    ward: Optional[str] = None
    created_at: Optional[str] = None
    is_authority: bool = False
    reputation_detail: Optional[ReputationDetail] = None
    ledger: list[dict] = []
