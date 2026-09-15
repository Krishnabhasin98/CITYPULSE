"""Domain errors shared by the service layer and the API layer."""

from __future__ import annotations


class CityPulseError(Exception):
    """Base class for expected, user-facing failures."""

    status_code = 400

    def __init__(self, detail: str, *, extra: dict | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra or {}


class ValidationError(CityPulseError):
    status_code = 422


class NotFoundError(CityPulseError):
    status_code = 404


class ForbiddenError(CityPulseError):
    status_code = 403


class ConflictError(CityPulseError):
    status_code = 409
